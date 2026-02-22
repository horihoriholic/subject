import os
import chromadb
from langchain_community.document_loaders import UnstructuredImageLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma

# 1. 既存のChroma DBに接続する設定
persist_directory = "./chroma_db"
embeddings = OpenAIEmbeddings()

# 既存のDBを読み込む（なければ新規作成される）
vectorstore = Chroma(
    persist_directory=persist_directory,
    embedding_function=embeddings
)

# 2. すでに登録済みのファイル名を取得（重複チェック用）
# メタデータの "source" にファイル名を入れている前提
existing_docs = vectorstore.get()
already_ingested = set(meta["source"] for meta in existing_docs["metadatas"])

# 1. 画像の読み込み
image_folder = "./data"
documents = []
text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)

# 3. ループ処理
for filename in os.listdir(image_folder):
    if filename.endswith((".png", ".jpg", ".jpeg")):
        # 【ここがポイント】すでにDBにあるファイルはスキップ！
        if filename in already_ingested:
            print(f"スキップ: {filename} は登録済みです")
            continue
            
        print(f"処理中: {filename}...")
        path = os.path.join(image_folder, filename)
        loader = UnstructuredImageLoader(path, strategy="hi_res", languages=["jpn"])
        
        # 読み込んで追加
        new_docs = loader.load()
        for d in new_docs:
            d.metadata["source"] = filename
            
        # 分割して追加
        splits = text_splitter.split_documents(new_docs)
        vectorstore.add_documents(splits) # .from_documents ではなく .add_documents を使う
        print(f"完了: {filename} をDBに追加しました")

print("すべてのファイルの読み込みが完了しました！")