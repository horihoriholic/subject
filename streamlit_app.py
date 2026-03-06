import os
import streamlit as st
import streamlit_authenticator as stauth
import streamlit.components.v1 as components
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_pinecone import PineconeVectorStore
from langchain_classic.chains import RetrievalQA
from langchain_classic.prompts import PromptTemplate
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# Pinecone設定（secrets優先、無ければ環境変数）
# - PINECONE_API_KEY
# - PINECONE_INDEX_NAME
# - PINECONE_NAMESPACE (任意)
PINECONE_API_KEY = st.secrets.get("PINECONE_API_KEY", os.getenv("PINECONE_API_KEY"))
PINECONE_INDEX_NAME = st.secrets.get("PINECONE_INDEX_NAME", os.getenv("PINECONE_INDEX_NAME"))
PINECONE_NAMESPACE = st.secrets.get("PINECONE_NAMESPACE", os.getenv("PINECONE_NAMESPACE", "default"))

config = st.secrets.to_dict()
# cookie の設定も手動で組み立てる
authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days']
)
st.set_page_config(layout="wide")
try:
    authenticator.login()
except Exception as e:
    st.error(e)

if st.session_state["authentication_status"]:
    if not PINECONE_API_KEY:
        st.error("PINECONE_API_KEY が未設定です。（Streamlit secrets か環境変数で設定してください）")
        st.stop()
    if not PINECONE_INDEX_NAME:
        st.error("PINECONE_INDEX_NAME が未設定です。（Pinecone側でindexを作成し、secrets/環境変数で指定してください）")
        st.stop()

    # langchain-pinecone は環境変数 PINECONE_API_KEY を参照するため、secretsから来た場合も反映
    os.environ["PINECONE_API_KEY"] = PINECONE_API_KEY

    # PineconeのVectorStore（既存indexに接続して検索に利用）
    vectorstore = PineconeVectorStore(
        index_name=PINECONE_INDEX_NAME,
        embedding=OpenAIEmbeddings(model="text-embedding-3-small"),
        namespace=PINECONE_NAMESPACE,
    )
    with st.sidebar:
        st.write(f"👤 ログイン中: \n\n**{st.session_state['name']}** さん")
        authenticator.logout('ログアウト', 'main')

    # --- 1. 結果を保持する箱を準備（初回のみ） ---
    if "result_btn1" not in st.session_state:
        st.session_state.result_btn1 = ""
    if "result_btn2" not in st.session_state:
        st.session_state.result_btn2 = ""
    if "result_btn3" not in st.session_state:
        st.session_state.result_btn3 = ""
    if "result_btn4" not in st.session_state:
        st.session_state.result_btn4 = ""

    st.title("精油成分サーチRAG")
    col_left, col_right = st.columns(2)

    with col_left:
        with st.container(border=True):
            st.subheader("香りの成分を探す")
            chat_model = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
            output_parser = StrOutputParser()


            ######################################################
            ######       解決したい症状/悩みから成分を探す     ######
            ######################################################

            st.caption("解決したい症状/悩みから成分を探す")
            col1, col2 = st.columns([0.8, 0.2])
            with col1:
                search_by_problem = st.text_input(
                    "悩みや症状を入力してください", 
                    value="イライラを鎮めたい",
                    label_visibility="collapsed" # label_visibility="collapsed" でラベルを消すと高さが揃って綺麗です
                )
            with col2:
                executed_btn_1 = st.button("検索", key="btn_1", use_container_width=True)

            if executed_btn_1 and search_by_problem:
                prompt_txt = ChatPromptTemplate.from_messages(
                    [
                        ("system", "あなたは鼻の利く、知識豊富なアロマテラピーアドバイザーです。"), #"system"（システムメッセージ）:AIの振る舞いや性格、ルールを設定します。
                        ("human", """
                        訪問者は{search_by_problem}という悩みがあります。悩みにアプローチする香りの成分や芳香分子を教えてください。
                        例：「睡眠が浅い」という悩みなら、「酢酸ボルニル」
                        【ルール】
                        1.アロマの名前や精油名は説明の中で触れるのはOKですが、成分を強調してください。
                        ×ラベンダー（ラベンダー油）
                        ○「リナロール」や「リナリルアセテート」
                        2.回答の出だしを「～～にアプローチする香りの成分として、以下をおすすめします。」としてください。
                        3.成分は箇条書きにして、一言説明を添えてください。
                        4.仮に悩みが文脈に沿わない場合、以下の通り回答してください。
                        「申し訳ございません。理解できませんでした。『花粉症がつらい』や『眠れない』など解決したい症状や悩みを入力してください。」
                        """) #"human"（ユーザーメッセージ）:人間（利用者）からの入力内容です。
                    ]
                )
                chain = prompt_txt | chat_model | output_parser
                with st.spinner("検索中..."):
                    st.session_state.result_btn1 = chain.invoke(search_by_problem)
            if st.session_state.result_btn1:
                st.info(st.session_state.result_btn1)



            # --- ここで隙間を作る ---
            st.divider() # 区切り線
            ######################################################
            ######           香りの種類から成分を探す         ######
            ######################################################

            st.caption("香りの種類から成分を探す")
            col1, col2 = st.columns([0.8, 0.2])
            with col1:
                search_by_fragrance = st.text_input(
                    "求めている香りはどんな香りですか",
                    value="フレッシュな香り",
                    label_visibility="collapsed" # label_visibility="collapsed" でラベルを消すと高さが揃って綺麗です
                )
            with col2:
                executed_btn_2 = st.button("検索", key="btn_2", use_container_width=True)
            if executed_btn_2 and search_by_fragrance:
                prompt_txt = ChatPromptTemplate.from_messages(
                    [
                        ("system", "あなたは鼻の利く、知識豊富なアロマテラピーアドバイザーです。"), #"system"（システムメッセージ）:AIの振る舞いや性格、ルールを設定します。
                        ("human", """
                        訪問者は以下の入力をしました：
                        「{search_by_fragrance}」

                        【手順】
                        1. まず、入力内容が「香り、植物、感覚、リラックス、またはそれらに関連する形容詞」であるかを厳格に判断してください。
                        2. 全く関係のない単語（例：あああ、テスト、こんにちは等）や、意味不明な文字列の場合は、理由を問わず【拒否回答】のみを出力してください。
                        3. 香りに関連する場合は、アロマの名前や精油名は説明の中で触れるのはOKですが、成分を強調してください。
                        ×ラベンダー（ラベンダー油）
                        ○「リナロール」や「リナリルアセテート」

                        【ルール】
                        ・成分名（例：リモネン、リナロール）を主役にしてください。精油名は補足に留めます。
                        ・成分は箇条書きにして、一言説明を添えてください。
                        ・文脈に合わない場合の【拒否回答】：
                        「申し訳ございません。入力された内容から香りの意図が理解できませんでした。オリエンタルな香りやエキゾチックな香り、あるいは『落ち着く香り』のように入力してください。」

                        【回答構成例】
                        ・適合時：成分名を中心に解説。
                        ・不適合時：【拒否回答】の定型文のみ。
                        """) #"human"（ユーザーメッセージ）:人間（利用者）からの入力内容です。
                    ]
                )
                chain = prompt_txt | chat_model | output_parser
                with st.spinner("検索中..."):
                    st.session_state.result_btn2 = chain.invoke(search_by_fragrance)
            if st.session_state.result_btn2:
                st.info(st.session_state.result_btn2)
                # --- ここで隙間を作る ---
            st.markdown("<br>", unsafe_allow_html=True) 


        ######################################################
        ######       該当成分を含む精油を書籍から探す      ######
        ######################################################

        st.markdown("<br>", unsafe_allow_html=True) 
        with st.container(border=True):
            st.subheader("該当成分を含む精油を書籍から探す")
            st.caption("書籍の中から探す")

            # 1. 独自の命令書（プロンプト）を作成
            template = """
            あなたは精油の専門家です。以下の【提供された資料】のみを使用して、質問に答えてください。
            資料に数値（％など）がある場合は、それを比較してランキングを作成してください。
            資料にない情報は「資料にはありません」と答え、自分の知識で補完しないでください。
            【ルール】
            1. 抽出した精油名が、提供された資料の【source】（ファイル名）と一致しているか厳密に確認してください。
            2. 資料に存在しない精油（例: プチグレン等）は、一般常識であっても絶対に回答に含めないでください。
            3. 数値の根拠（例: 43.4%）も併せて回答してください。
            4. その成分が含まれていない精油は除外してください。
            5. ランキング形式では、含有量を比べて数値の高い順に並べて表示してください。

            【提供された資料】:
            {context}

            質問: {question}
            回答:"""

            PROMPT = PromptTemplate(template=template, input_variables=["context", "question"])
            col1, col2 = st.columns([0.8, 0.2])
            with col1:
                question = st.text_input(
                    "知りたい成分や精油について入力してください", 
                    value="リナロールを多く含む精油ベスト3を教えて",
                    label_visibility="collapsed" # label_visibility="collapsed" でラベルを消すと高さが揃って綺麗です
                )
            with col2:
                executed_btn_3 = st.button("検索", key="btn_3", use_container_width=True)
            if executed_btn_3 and question:
                # 1. DBと条件を指定
                retriever=vectorstore.as_retriever(search_kwargs={"k": 20})
                # 2. DBに対してquestionに沿った検索を実行し、内容が似ている情報を指定数分取得
                docs = retriever.invoke(question) # vectorstoreから関連資料を先に取得
                referenced_books = list(set([doc.metadata.get("book", "不明") for doc in docs]))

                # 3. 取得したdocsをテキストとして結合（context作成）
                context = "\n\n".join([doc.page_content for doc in docs])
                # 4. AIに関する設定
                llm = ChatOpenAI(model_name="gpt-4o", temperature=0)
                # PromptTemplateを使ってプロンプトを組み立てる
                final_prompt = PROMPT.format(context=context, question=question)
                
                with st.spinner("検索中..."):
                    response = llm.invoke(final_prompt)
                    st.session_state.result_btn3 = response.content
                    st.session_state.referenced_books = referenced_books
            if st.session_state.result_btn3:
                st.info(st.session_state.result_btn3)
                # 引用元の本を表示
                if st.session_state.referenced_books:
                    st.caption(f"📚 参照した書籍: {', '.join(st.session_state.referenced_books)}")

    with col_right:
        with st.container(border=True):
            st.subheader("香りの成分について知る")
            st.caption("書籍の中から探す")

            # 1. 独自の命令書（プロンプト）を作成
            template = """
            あなたは精油の専門家です。以下の【提供された資料】のみを使用して、質問に答えてください。

            【提供された資料】:
            {context}

            質問: {question}
            回答:"""

            PROMPT = PromptTemplate(template=template, input_variables=["context", "question"])
            col1, col2 = st.columns([0.8, 0.2])
            with col1:
                question = st.text_input(
                    "知りたい成分を入力してください", 
                    value="リナロールについて教えて",
                    label_visibility="collapsed" # label_visibility="collapsed" でラベルを消すと高さが揃って綺麗です
                )
            with col2:
                executed_btn_4 = st.button("検索", key="btn_4", use_container_width=True)
            if executed_btn_4 and question:
                # 1. DBと条件を指定
                retriever=vectorstore.as_retriever(search_kwargs={"k": 20})
                # 2. DBに対してquestionに沿った検索を実行し、内容が似ている情報を指定数分取得
                docs = retriever.invoke(question) # vectorstoreから関連資料を先に取得
                referenced_books = list(set([doc.metadata.get("book", "不明") for doc in docs]))

                # 3. 取得したdocsをテキストとして結合（context作成）
                context = "\n\n".join([doc.page_content for doc in docs])
                # 4. AIに関する設定
                llm = ChatOpenAI(model_name="gpt-4o", temperature=0)
                # PromptTemplateを使ってプロンプトを組み立てる
                final_prompt = PROMPT.format(context=context, question=question)
                
                with st.spinner("検索中..."):
                    response = llm.invoke(final_prompt)
                    st.session_state.result_btn4 = response.content
                    st.session_state.referenced_books = referenced_books
            if st.session_state.result_btn4:
                st.info(st.session_state.result_btn4)
                # 引用元の本を表示
                if st.session_state.referenced_book4:
                    st.caption(f"📚 参照した書籍: {', '.join(st.session_state.referenced_books)}")


elif st.session_state.get("authentication_status") is False:
    st.error("Usernameまたは、passwordが間違っています")

# Streamlit特有の 「状態が変わるたびに、上から下まで全部読み直す」 ので、IF文を再度なめてくれて、ログアウトするとここに到達する。
elif st.session_state.get("authentication_status") is None:
    st.warning("Usernameとpasswordを入力してください")
    st.markdown(
        """
        <style>
            /* サイドバー本体を消す */
            [data-testid="stSidebar"] {
                display: none;
            }
            /* サイドバーが開くための左側の余白(パディング)を0にする */
            [data-testid="stSidebarCollapsedControl"] {
                display: none;
            }
            section[data-testid="stMain"] {
                margin-left: 0rem;
                width: 100%;
            }
        </style>
        """,
        unsafe_allow_html=True # 本来は禁止されている『HTMLやCSS』を、例外的に実行することを許可する
    )