import base64
import os

from openai import OpenAI
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone
import streamlit as st

client = OpenAI()

# 画像（JPG/PNGなど）を本ごとのフォルダに分けて配置するルートフォルダ
IMAGE_ROOT_FOLDER = "./data"

# Pinecone設定（環境変数で指定してください）
# - PINECONE_API_KEY: PineconeのAPIキー
# - PINECONE_INDEX_NAME: 事前に作成したPinecone index名（embedding次元と一致が必要）
# - PINECONE_NAMESPACE: 任意（未指定なら "default"）
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = st.secrets["PINECONE_INDEX_NAME"]
PINECONE_NAMESPACE = os.getenv("PINECONE_NAMESPACE", "multimodal")


def _encode_image_bytes(image_bytes: bytes) -> str:
    """画像バイト列を Base64 エンコードして文字列に変換"""
    return base64.b64encode(image_bytes).decode("utf-8")


def _make_ascii_id(book_name: str, filename: str) -> str:
    """
    Pinecone の制約に合わせて、ID を ASCII のみにするためのユーティリティ。
    book_name や filename に日本語が含まれていても使えるように、
    「book_name:filename」を UTF-8 → URL-safe Base64 でエンコードして ID にする。
    """
    raw = f"{book_name}:{filename}"
    b64 = base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")
    # '=' のパディングは不要なので削って少し短くしておく
    return b64.rstrip("=")


def image_bytes_to_caption(image_bytes: bytes) -> str:
    """
    Vision LLM（GPT-4o）に画像を渡し、図表・写真の内容を詳細に説明するテキスト（キャプション）を生成させる。
    """
    base64_image = _encode_image_bytes(image_bytes)

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "この画像は香りに関する資料で、図版・表・写真・グラフを含みます。"
                            "画像から読み取れる情報を記述してください。グラフ以外の本文も大事です。"
                            # "画像内の非人間的な要素（グラフの数値、表のテキスト、凡例、芳香成分やその分子構造）のみを対象に、構造化データとして書き出してください。人物に関する情報はすべて無視してください。"
                            "1000文字を超える場合、もしくは、文が途中で切れている場合は予測や要約を許可します"
                            "非人間的な要素（グラフの数値、表のテキスト、凡例、芳香成分やその分子構造）については、構造化データとして書き出してください。"
                            "グラフ内にある精油名、成分名とそれぞれの含有率（％）を、漏れなく正確にリストアップしてください。割合が小さい項目も省略せず、必ず全て記述すること。"
                            "構造化データは、**Markdownテーブル形式**で出力してください。"
                            # "人間が読んで理解できるように、重要な情報を日本語でできるだけ詳しく説明してください。"
                            "もし花や植物、分子構造が写っている場合は、その名称・特徴・関係性をできるだけ具体的に書いてください。"
                            "特に円グラフや表の数値は重要です。数値は、ドット（.）を見落とさないよう注意してください（例：6.1%を61%と間違えないこと）。"
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                    },
                ],
            }
        ],
    )
    # choicesはリストなので [0] が必要
    return response.choices[0].message.content


def image_to_text(image_path: str) -> str:
    """
    既存の画像ファイルパスからキャプションを生成するラッパー（互換性維持用）。
    ingest5.py では主に PDF から抽出した画像バイト列版を使う。
    """
    with open(image_path, "rb") as f:
        image_bytes = f.read()
    return image_bytes_to_caption(image_bytes)

# --- 実行部分 ---

# 1. Embeddings（Pinecone indexの次元と合わせる）
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

# 2. Pineconeへ接続
if not PINECONE_API_KEY:
    raise RuntimeError("環境変数 PINECONE_API_KEY が未設定です。")
if not PINECONE_INDEX_NAME:
    raise RuntimeError("環境変数 PINECONE_INDEX_NAME が未設定です。（Pinecone側でindexを事前作成してください）")

pc = Pinecone(PINECONE_API_KEY)
index = pc.Index(PINECONE_INDEX_NAME)

# 接続確認（index名のtypo等を早期検出）
try:
    index.describe_index_stats()
except Exception as e:
    raise RuntimeError(
        f"Pinecone index '{PINECONE_INDEX_NAME}' に接続できませんでした。"
        "Pineconeコンソールで index が存在するか、次元が embeddings と一致しているか確認してください。"
    ) from e

# 3. LangChainのVectorStoreとして利用
vectorstore = PineconeVectorStore(
    index_name=PINECONE_INDEX_NAME,
    embedding=embeddings,
    namespace=PINECONE_NAMESPACE,
)

def _exists_in_pinecone(doc_id: str) -> bool:
    """Pinecone上にIDが存在するかを fetch で確認（=重複投入防止）"""
    res = index.fetch(ids=[doc_id], namespace=PINECONE_NAMESPACE)
    # pineconeの戻りはバージョン差があるため両対応
    if isinstance(res, dict):
        return doc_id in (res.get("vectors") or {})
    vectors = getattr(res, "vectors", None)
    if isinstance(vectors, dict):
        return doc_id in vectors
    return False


# --- メイン実行部 ---
# ./data/{本の名前}/ の下にある JPG / JPEG / PNG を、画像1枚＝1ドキュメントとして扱い、
# GPT-4o による詳細キャプションを生成して Pinecone に格納します。
for book_name in os.listdir(IMAGE_ROOT_FOLDER):
    book_path = os.path.join(IMAGE_ROOT_FOLDER, book_name)
    if not os.path.isdir(book_path):
        continue

    print(f"--- 本フォルダ: {book_name} の処理を開始 ---")

    for filename in os.listdir(book_path):
        if not filename.lower().endswith((".jpg", ".jpeg", ".png")):
            continue

        image_path = os.path.join(book_path, filename)
        # 本の名前＋画像ファイル名から ASCII のみを使った一意な ID を作る
        doc_id = _make_ascii_id(book_name, filename)

        if _exists_in_pinecone(doc_id):
            print(f"スキップ: {doc_id} は既にDBに登録されています。")
            continue

        print(f"GPT-4oが解析中: 本={book_name}, ファイル={filename} ...")
        caption = image_to_text(image_path)

        vectorstore.add_texts(
            [caption],
            metadatas=[
                {
                    "source": filename,
                    "book": book_name,
                    "type": "image",
                }
            ],
            ids=[doc_id],
            namespace=PINECONE_NAMESPACE,
        )

print("すべての本フォルダ内の画像に対するキャプション生成とベクトル登録が完了しました！")
