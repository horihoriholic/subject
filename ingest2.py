import base64
import os
from openai import OpenAI
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_classic.schema import Document

client = OpenAI()
image_folder = "./data"
persist_directory="./chroma_db"

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

all_docs = []
# 3. 既存のDBに接続（なければ新規作成）
embeddings = OpenAIEmbeddings()
vectorstore = Chroma(
    persist_directory=persist_directory,
    embedding_function=embeddings
)
# 4. すでにDBに登録済みのファイル名を取得（重複チェック用）
existing_docs = vectorstore.get()
already_ingested = set(meta["source"] for meta in existing_docs["metadatas"])

for filename in os.listdir(image_folder):
    if filename.endswith((".png", ".jpg", ".jpeg")):
        # すでに登録済みならスキップ
        if filename in already_ingested:
            print(f"スキップ: {filename} は既にDBに登録されています。")
            continue

        path = os.path.join(image_folder, filename)
        print(f"GPT-4oが解析中: {filename}...")
        
        # GPT-4oによる高度なOCR
        text_content = image_to_text(path)
        
        # 引用元特定のため、メタデータ付きでDocument化
        doc = Document(
            page_content=text_content,
            metadata={"source": filename}
        )
        vectorstore.add_documents([doc]) # デフォルトでTextというキーに保存される

print("高度な解析が完了しました！")
