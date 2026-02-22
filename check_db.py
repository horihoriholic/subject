import chromadb
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings

# DBに接続
persist_directory = "./chroma_db"
vectorstore = Chroma(
    persist_directory=persist_directory,
    embedding_function=OpenAIEmbeddings()
)

# 全データを取得
data = vectorstore.get()

# 1. 登録されているファイル数（チャンク数）を確認
print(f"合計チャンク数: {len(data['ids'])}")

# 2. 登録されているソース（ファイル名）の一覧を確認
sources = set(meta["source"] for meta in data["metadatas"])
print(f"登録済みファイル一覧: {sources}")

# 3. 最初の3件だけ中身（テキスト）を表示してみる
for i in range(min(3, len(data['documents']))):
    print(f"\n--- データ {i+1} ---")
    print(f"Source: {data['metadatas'][i]['source']}")
    print(f"Text: {data['documents'][i][:200]}...") # 最初の200文字だけ
