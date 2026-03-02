import base64
import os
from openai import OpenAI
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone
import streamlit as st
client = OpenAI()
image_folder = "./data"

# Pinecone設定（環境変数で指定してください）
# - PINECONE_API_KEY: PineconeのAPIキー
# - PINECONE_INDEX_NAME: 事前に作成したPinecone index名（embedding次元と一致が必要）
# - PINECONE_NAMESPACE: 任意（未指定なら "default"）
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = st.secrets["PINECONE_INDEX_NAME"]
PINECONE_NAMESPACE = os.getenv("PINECONE_NAMESPACE", "default")

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        # Base64：バイナリデータ（画像や音声など）を、テキストデータ（英数字など）に変換する符号化方式（エンコード方式）
        return base64.b64encode(image_file.read()).decode('utf-8')

def image_to_text(image_path):
    base64_image = encode_image(image_path)
    
    # GPT-4oに「画像の中身を正確に書き起こして」と依頼
    # マルチモーダルモデル：画像や音声、テキストなどの複数のモーダルのデータをコンピュータで処理して予測や分類を行う技術のこと
    # 画像をそのままAI（GPT-4oなど）に見せて、テキスト化してもらう
    # UnstructuredImageLoaderをやめる
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user", # 人間から送る情報の意味
                "content": [ # 文字と画像をセットで送る
                    {
                        "type": "text", 
                        "text": "この画像は精油の紹介資料です。精油名、成分名とそれぞれの含有率（％）、香りの特徴、論文紹介の内容を、漏れなく正確にテキスト化してください。特に円グラフの数値は重要です。"
                    },
                    {
                        "type": "image_url", 
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                    }
                ]
            }
        ],
    )
    # choicesはリストなので [0] が必要です
    return response.choices[0].message.content

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

for book_name in os.listdir(image_folder):
    book_path = os.path.join(image_folder, book_name)
    if os.path.isdir(book_path):
        print(f"--- 本: {book_name} の処理を開始 ---")
        for filename in os.listdir(book_path):
            if filename.endswith((".png", ".jpg", ".jpeg")):
                doc_id = f"{book_name}_{filename}" # IDの重複を防ぐため本の名を付与
                # すでに登録済みならスキップ（ID=ファイル名）
                if _exists_in_pinecone(doc_id):
                    print(f"スキップ: {filename} は既にDBに登録されています。")
                    continue

                path = os.path.join(book_path, filename)
                print(f"GPT-4oが解析中: {filename}...")
        
                # GPT-4oによる高度なOCR
                text_content = image_to_text(path)
        
                # 引用元特定のため、メタデータ付きで保存（IDも固定化して重複を防ぐ）
                vectorstore.add_texts(
                    [text_content],
                    metadatas=[{"source": filename, "book": book_name}],
                    ids=[doc_id],
                    namespace=PINECONE_NAMESPACE
                )

print("高度な解析が完了しました！")
