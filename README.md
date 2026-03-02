## Pinecone版（Chroma→Pinecone移行メモ）

このフォルダの `ingest2.py` / `streamlit_app.py` / `check_db.py` は、**ローカル永続化（Chroma）ではなく Pinecone に保存・検索**するように変更済みです。

### 必要な環境変数

- **`PINECONE_API_KEY`**: Pinecone の API Key  
- **`PINECONE_INDEX_NAME`**: 事前に作成した Pinecone の index 名  
- **`PINECONE_NAMESPACE`**（任意）: 未指定なら `"default"`

### Pinecone index 側の注意

- **Embedding**: `OpenAIEmbeddings(model="text-embedding-3-small")` を使っています  
- **次元**: `text-embedding-3-small` は一般に **1536次元**（indexのdimensionを一致させてください）
- **メトリクス**: cosine（一般的）

※ index の作成は Pinecone コンソール側で行ってください（クラウド/リージョン等の指定が必要なため）。

### 動作概要

- **投入（`ingest2.py`）**: 画像→GPT-4oでテキスト化→Pineconeへ保存  
  - **IDはファイル名**（例: `img001.jpg`）に固定しているので、同じファイルは重複投入されません（`fetch` で存在確認）。
- **検索（`streamlit_app.py`）**: Pinecone の index から類似検索して RAG を実行
- **確認（`check_db.py`）**: `./data` のファイル名（=ID）で Pinecone に存在するかをチェックし、先頭数件の内容を表示

### インストール（例）

```bash
pip install -r requirements.txt
```


