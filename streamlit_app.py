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
import json
import re
from PIL import Image, ImageOps

# JSONファイルを読み込む関数
@st.cache_data  # 毎回ファイルを読み込まないようにキャッシュする
def load_options():
    with open("master_data.json", "r", encoding="utf-8") as f:
        return json.load(f)

# 画像を開いてEXIFに基づいて回転を補正する関数
def load_fixed_image(path):
    img = Image.open(path)
    img = ImageOps.exif_transpose(img) # 回転情報を物理的に反映
    return img

# Pinecone設定（secrets優先、無ければ環境変数）
# - PINECONE_API_KEY
# - PINECONE_INDEX_NAME
# - PINECONE_NAMESPACE (任意)
PINECONE_API_KEY = st.secrets.get("PINECONE_API_KEY", os.getenv("PINECONE_API_KEY"))
PINECONE_INDEX_NAME = st.secrets.get("PINECONE_INDEX_NAME", os.getenv("PINECONE_INDEX_NAME"))
PINECONE_NAMESPACE = st.secrets.get("PINECONE_NAMESPACE", os.getenv("PINECONE_NAMESPACE", "multimodal"))

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
    if "answer_image_paths" not in st.session_state:
        st.session_state.answer_image_paths = []

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
                # 1. 独自の命令書（プロンプト）を作成
                template = """
                あなたは精油の専門家です。以下の【提供された資料】のみを使用して、質問に答えてください。
                資料に数値（％など）がある場合は、その数値を必ず「数値として」読み取り、比較してランキングを作成してください。
                資料にない情報は「資料にはありません」と答え、自分の知識で補完しないでください。

                【手順】
                1. 各資料の冒頭にある「【出典情報】」から、book名とsource名を正確に読み取ってください。
                2. その直後の「内容:」から、指定成分を含む精油名、その含有量（%の数値）、および引用元情報をすべて抽出してください。
                3. パーセンテージが範囲（例：30-40%）で記載されている場合は、その中間値または代表的な数値を1つの数値(float)として抽出してください。
                4. 資料に存在しない精油や自分の知識による補完は、一般常識であっても絶対に回答に含めないでください。
                5. 出力は必ず以下のJSON形式のみとし、説明文や「資料にはありません」というテキストも一切含めないでください。
                6. 資料に数値（％）の記載がない精油は、抽出対象から除外してください。
                7. 資料に該当する精油が一つも存在しない場合、または指定された成分に関する記述がない場合は、何も書かずに必ず空のリスト `[]` のみを出力してください。

                【出力フォーマット】
                [
                {{
                    "name": "精油名（産地など）",
                    "value": 数値のみ(float),
                    "display_value": "XX.X%",
                    "book": "読み取ったbook名",
                    "source": "読み取ったsource名"
                }}
                ]
                ※該当なしの場合は `[]` を出力。

                【提供された資料】:
                {context}

                質問: {question}
                回答:
                """

                PROMPT = PromptTemplate(template=template, input_variables=["context", "question"])
                # 1. DBと条件を指定
                retriever=vectorstore.as_retriever(search_kwargs={"k": 20})
                # 2. DBに対してquestionに沿った検索を実行し、内容が似ている情報を指定数分取得
                docs = retriever.invoke(question) # vectorstoreから関連資料を先に取得
                # 3. 取得したdocsを、メタデータを含めたテキストとして結合
                context_elements = []
                for doc in docs:
                    content = doc.page_content
                    # メタデータから取得（取得できない場合のデフォルト値を設定）
                    book_name = doc.metadata.get('book', '不明な書籍')
                    source_name = doc.metadata.get('source', '不明なソース')
                    # テキストの直前に出典情報を明記する
                    element = f"【出典情報】book: {book_name}, source: {source_name}\n内容: {content}"
                    context_elements.append(element)

                # セパレーターで区切って一つの巨大な文字列（context）にする
                context = "\n\n---\n\n".join(context_elements)
                # 4. AIに関する設定
                llm = ChatOpenAI(model_name="gpt-4o", temperature=0)
                # PromptTemplateを使ってプロンプトを組み立てる
                final_prompt = PROMPT.format(context=context, question=question)
                
                with st.spinner("検索中..."):
                    response = llm.invoke(final_prompt)
                    raw_content = response.content
                    try:
                        # JSONとしてパース
                        clean_content = raw_content.strip().replace("```json", "").replace("```", "")
                        extracted_data = json.loads(clean_content)
                        # --- ここで「情報が存在しない場合」を判定 ---
                        if not extracted_data:
                            st.session_state.result_btn3 = "ご指定の成分を含む精油の情報は、提供された資料内には見つかりませんでした。"
                        else:
                            # Python側で確実に降順ソート
                            sorted_data = sorted(extracted_data, key=lambda x: x['value'], reverse=True)
                            # 表示用テキストの作成
                            display_lines = []
                            ref_list = []
                            for i, item in enumerate(sorted_data, 1):
                                # 1位: ラベンダー  45.0% [出典: 精油大事典 / img001.jpg]
                                line = (
                                    f"**{i}位: {item['name']}  {item['display_value']}**  \n"
                                    f"&nbsp;&nbsp;&nbsp;[出典: {item['book']} / {item['source']}]\n"
                                )
                                display_lines.append(line)

                            st.session_state.result_btn3 = "\n".join(display_lines)
                    except Exception as e:
                        st.error(f"データ解析エラー: {e}\nRaw content: {raw_content}")
            if st.session_state.result_btn3:
                st.info(st.session_state.result_btn3)

    with col_right:
        with st.container(border=True):
            st.subheader("香りの情報を得る")
            st.caption("書籍の中から探す")
            options_map = load_options()
            col1, col2, col3 = st.columns([0.4, 0.4, 0.2])
            with col1:
                # Step 1: カテゴリー選択
                category = st.selectbox(
                    "Step1. 知りたい項目を選択",
                    options=list(options_map.keys()),
                    index=0,
                    label_visibility="collapsed"
                )
            with col2:
                # Step 2: カテゴリーに応じた具体的なキーワード選択
                # categoryが変わると、ここに出てくる選択肢が自動で切り替わります
                specific_item = st.selectbox(
                    f"Step2. 具体的な「{category}」を選択",
                    options=options_map[category],
                    label_visibility="collapsed"
                )
            with col3:
                executed_btn_4 = st.button("検索", key="btn_4", use_container_width=True)
            if executed_btn_4 and category and specific_item:
                # 1. 独自の命令書（プロンプト）を作成
                template = """
                あなたは精油の専門家です。以下の【提供された資料】のみを使用して、質問に答えてください。
                資料にない情報は「資料にはありません」と答え、自分の知識で補完しないでください。
                各資料の冒頭にある「【出典情報】」から、book名とsource名を正確に読み取ってください。
                【ルール】
                1. **資料（ページ）ごとに、必ず1つのJSONオブジェクトを作成してください。** 複数の画像ソースにまたがる情報を1つの `content` にまとめないでください。
                2. 引用した資料ごとに、その内容と対応する `book`, `source` をセットにしてリスト形式で出力してください。
                3. 出力は必ず以下のJSON形式のみとし、説明文などは一切含めないでください。

                【出力フォーマット】
                [
                {{
                    "content": "質問に沿った回答",
                    "book": "読み取ったbook名",
                    "source": "読み取ったsource名"
                }},
                {{
                    "content": "別の資料から読み取った具体的な回答内容",
                    "book": "読み取ったbook名",
                    "source": "読み取ったsource名"
                }}
                ]
                ... (以下、資料の数だけ続く)
                ※該当なしの場合は `[]` を出力。

                【提供された資料】:
                {context}

                質問: {question}
                回答:"""

                PROMPT = PromptTemplate(template=template, input_variables=["context", "question"])
                # 1. DBと条件を指定
                retriever=vectorstore.as_retriever(search_kwargs={"k": 10})
                # 2. DBに対してquestionに沿った検索を実行し、内容が似ている情報を指定数分取得
                question = f"{category}における{specific_item}について、提供された資料をもとに500文字以内で教えてください。"
                docs = retriever.invoke(question) # vectorstoreから関連資料を先に取得
                # 3. 取得したdocsを、メタデータを含めたテキストとして結合
                context_elements = []
                for doc in docs:
                    content = doc.page_content
                    # メタデータから取得（取得できない場合のデフォルト値を設定）
                    book_name = doc.metadata.get('book', '不明な書籍')
                    source_name = doc.metadata.get('source', '不明なソース')
                    # テキストの直前に出典情報を明記する
                    element = f"【出典情報】book: {book_name}, source: {source_name}\n内容: {content}"
                    context_elements.append(element)

                # セパレーターで区切って一つの巨大な文字列（context）にする
                context = "\n\n---\n\n".join(context_elements)
                # 4. AIに関する設定
                llm = ChatOpenAI(model_name="gpt-4o", temperature=0)
                # PromptTemplateを使ってプロンプトを組み立てる
                final_prompt = PROMPT.format(context=context, question=question)
                
                with st.spinner("検索中..."):
                    response = llm.invoke(final_prompt)
                    raw_content = response.content
                    answer_lines = []
                    answer_image_paths = []
                    try:
                        # JSONとしてパース
                        clean_content = raw_content.strip().replace("```json", "").replace("```", "")
                        data_list = json.loads(clean_content)
                        # --- ここで「情報が存在しない場合」を判定 ---
                        if not data_list:
                            st.session_state.result_btn4 = "ご指定の成分を含む精油の情報は、提供された資料内には見つかりませんでした。"
                            st.session_state.answer_image_paths = []
                        else:
                            for item in data_list:
                                # 1. コンテンツの改行処理（「。」を改行に置換）
                                fixed_line = item.get("content", "").replace("。", "。  \n")
                                answer_lines.append(fixed_line)
                                # 2. 画像パスの組み立てと表示
                                book = item.get("book")
                                source = item.get("source")
                                path = f"./data/{book}/{source}"
                                # 重複を避けて保存
                                if path not in answer_image_paths:
                                    answer_image_paths.append(path)
                            # 最終的な回答文（出典情報を除いたもの）
                            clean_answer = "".join(answer_lines)
                            st.session_state.result_btn4 = clean_answer
                            st.session_state.answer_image_paths = answer_image_paths
                    except Exception as e:
                        st.error(f"JSONの解析に失敗しました: {e}")
                        st.session_state.result_btn4 = ""
                        st.session_state.answer_image_paths = []

            if st.session_state.result_btn4:
                st.info(st.session_state.result_btn4)
                # 画像部分を表示
                # if answer_image_paths:
                if st.session_state.answer_image_paths:
                    # 1行に3枚並べる（1枚あたりのサイズが小さくなります）
                    cols = st.columns(3)
                    for i, img_path in enumerate(st.session_state.answer_image_paths):
                        with cols[i % 3]:
                            if os.path.exists(img_path):
                                parts = img_path.split("/") # Pathを/区切りで分割
                                custom_caption = "【参考文献】"+"[".join(parts[-2:])+"]" # 直近2つを取得
                                # そのまま画像を表示させるとスキャン時のEXIF情報（回転情報）に依存するので制御する。
                                st.image(load_fixed_image(img_path), caption=custom_caption, width="stretch")
                            else:
                                st.warning(f"画像ファイルが見つかりません: {img_path}")


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