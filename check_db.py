import os
from pinecone import Pinecone

# Pinecone設定（環境変数で指定してください）
# - PINECONE_API_KEY
# - PINECONE_INDEX_NAME
# - PINECONE_NAMESPACE (任意)
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = "fragrance-subject-test"
PINECONE_NAMESPACE = os.getenv("PINECONE_NAMESPACE", "default")

image_folder = "./data"  # ingest2.py と合わせる（ID=ファイル名で投入している前提）
TEXT_KEY = "text"  # langchain-pineconeのデフォルト

if not PINECONE_API_KEY:
    raise RuntimeError("環境変数 PINECONE_API_KEY が未設定です。")
if not PINECONE_INDEX_NAME:
    raise RuntimeError("環境変数 PINECONE_INDEX_NAME が未設定です。")

pc = Pinecone(PINECONE_API_KEY)
index = pc.Index(PINECONE_INDEX_NAME)

stats = index.describe_index_stats()
print(f"合計ベクトル数: {stats.get('total_vector_count')}")

def _fetch_one(doc_id: str):
    res = index.fetch(ids=[doc_id], namespace=PINECONE_NAMESPACE)
    if isinstance(res, dict):
        return (res.get("vectors") or {}).get(doc_id)
    vectors = getattr(res, "vectors", None)
    if isinstance(vectors, dict):
        return vectors.get(doc_id)
    return None

# 登録済みファイル一覧（ローカルのdataフォルダにあるファイル名で存在確認）
found = []
missing = []
if os.path.isdir(image_folder):
    for filename in sorted(os.listdir(image_folder)):
        if not filename.lower().endswith((".png", ".jpg", ".jpeg")):
            continue
        v = _fetch_one(filename)
        if v is None:
            missing.append(filename)
        else:
            found.append(filename)

print(f"登録済み（data内で確認できたもの）: {len(found)}件")
print(f"未登録（data内で見つからないもの）: {len(missing)}件")
if found:
    print(f"登録済み例（先頭10件）: {found[:10]}")

# 最初の3件だけ中身（テキスト）を表示してみる（metadata['text'] を使用）
for i, filename in enumerate(found[:3], start=1):
    v = _fetch_one(filename)
    meta = (v or {}).get("metadata") or {}
    text = meta.get(TEXT_KEY, "")
    print(f"\n--- データ {i} ---")
    print(f"Source: {meta.get('source', filename)}")
    print(f"Text: {text[:200]}...")
