import streamlit as st
import streamlit_authenticator as stauth
import streamlit.components.v1 as components
import chromadb
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import Chroma
from langchain_classic.chains import RetrievalQA
from langchain_classic.prompts import PromptTemplate

config = st.secrets.to_dict()
# cookie の設定も手動で組み立てる
authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days']
)
try:
    authenticator.login()
except Exception as e:
    st.error(e)

if st.session_state["authentication_status"]:
    col1, col2 = st.columns([0.8, 0.2])
    with col1:
        st.write(f"👤 ログイン中: **{st.session_state['name']}** さん")
    with col2:
        # 'sidebar' ではなく 'main' を指定（または location を省略）
        authenticator.logout('ログアウト', 'main')

    st.divider() # 区切り線を入れるとスッキリします
    st.title("精油成分サーチRAG")

    # Chromaのクライアント設定を作成
    persistent_client = chromadb.PersistentClient(path="./chroma_db")

    # 保存済みのDBを読み込む
    vectorstore = Chroma(
        client=persistent_client,
        embedding_function=OpenAIEmbeddings()
    )

    # 1. 独自の命令書（プロンプト）を作成
    template = """
    あなたは精油の専門家です。以下の【提供された資料】のみを使用して、質問に答えてください。
    資料に数値（％など）がある場合は、それを比較してランキングを作成してください。
    資料にない情報は「資料にはありません」と答え、自分の知識で補完しないでください。
    【ルール】
    1. 抽出した精油名が、提供された資料の【source】（ファイル名）と一致しているか厳密に確認してください。
    2. 資料に存在しない精油（例: プチグレン等）は、一般常識であっても絶対に回答に含めないでください。
    3. 数値の根拠（例: 43.4%）も併せて回答してください。

    【提供された資料】:
    {context}

    質問: {question}
    回答:"""

    PROMPT = PromptTemplate(template=template, input_variables=["context", "question"])
    question = st.text_input("知りたい成分や精油について入力してください", "リナロールを多く含む精油ベスト3を教えて")
    if st.button("検索実行"):
        if question:
            # 検索と回答
            llm = ChatOpenAI(model_name="gpt-4o", temperature=0)
            #  QAチェーンにプロンプトを組み込む
            qa_chain = RetrievalQA.from_chain_type(
                llm=llm,
                chain_type="stuff",
                retriever=vectorstore.as_retriever(search_kwargs={"k": 20}), # 上位20件の資料を渡す※ループではない。20個のみを渡す
                chain_type_kwargs={"prompt": PROMPT}
            )
            
            with st.spinner("検索中..."):
                response = qa_chain.invoke(question)
                st.write(response["result"])

elif st.session_state.get("authentication_status") is False:
    st.error("Usernameまたは、passwordが間違っています")

# Streamlit特有の 「状態が変わるたびに、上から下まで全部読み直す」 ので、IF文を再度なめてくれて、ログアウトするとここに到達する。
elif st.session_state.get("authentication_status") is None:
    st.warning("Usernameとpasswordを入力してください")
    # 未ログイン時のダミーページ（サイドバーを隠すため）
    login_page = [st.Page(lambda: None, title="Login", icon="🔒")]
    pg = st.navigation(login_page, position="hidden") # position="hidden"でナビを隠す
    pg.run() 