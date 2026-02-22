import sys #コマンドライン引数を取得する
from dotenv import load_dotenv #.env から API キーなどを読み込む
from langchain_community.document_loaders import PyPDFLoader # PDFからテキストを抽出
from langchain_text_splitters import RecursiveCharacterTextSplitter #テキストを小さな塊（チャンク）に分割
from langchain_openai import OpenAIEmbeddings, ChatOpenAI #テキストをベクトルに変換
from langchain_community.vectorstores import Chroma #ベクトル検索を行うライブラリ
from langchain_classic.chains import RetrievalQA #検索した情報を元にLLMで回答を生成
from langchain_community.document_loaders import UnstructuredImageLoader
load_dotenv()

img_path = sys.argv[1] #画像ファイルパスをコマンドライン引数から取得

# 画像読み込み
# loader = PyPDFLoader(pdf_path)
loader = UnstructuredImageLoader(
    img_path,
    strategy="hi_res",  # 高精度モード（必須に近い）
    languages=["jpn"]    # 日本語を指定)
)
pages = loader.load()

# print(f"読み込んだページ数: {len(pages)}")
# if len(pages) > 0:
#     print(f"最初の100文字: {pages[0].page_content[:100]}")

documents = loader.load() #documents はPDF内のテキストがページごとに分かれたリスト
# 例
# [
#   {"page_content": "ここに1ページ目のテキスト"},
#   {"page_content": "ここに2ページ目のテキスト"},
# ]

# 共通のRAG処理
text_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=200) #1チャンクあたり800文字で前後のチャンクと200文字重複させる
splits = text_splitter.split_documents(documents)
embeddings = OpenAIEmbeddings(model="text-embedding-3-small") #テキストをベクトル化
vectorstore = Chroma.from_documents(splits, embeddings) #Chroma に保存して検索可能にする

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0) #temperature=0 で回答を安定化（ランダム性を減らす）
qa_chain = RetrievalQA.from_chain_type( # RetrievalQAはベクトル検索と生成を組み合わせるチェーン
    llm=llm,
    chain_type="stuff", #関連チャンクをすべてまとめて LLM に渡す方式
    retriever=vectorstore.as_retriever()
)
answer = qa_chain.invoke({"query":"一文で要約してください"}) #query に質問を渡すと、ベクトル検索で関連チャンクを取得し、LLMが回答を生成
print(answer["result"])