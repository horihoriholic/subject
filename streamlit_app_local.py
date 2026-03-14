import os
import streamlit as st
import extra_streamlit_components as stx
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
from supabase import create_client, Client
import requests
from io import BytesIO
from connect_supabase import init_supabase
from datetime import datetime, timedelta
import bcrypt
from streamlit_js_eval import streamlit_js_eval, get_cookie
import time

def register_new_user(username, password, token):
    # 1. パスワードをハッシュ化（ソルト込み）
    # bcryptは bytes 型を扱うため encode() が必要です
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    try:
        # 2. users テーブルに新規ユーザーを登録
        # role はデフォルトで 'user' に設定（管理者は手動か別ルートで作成）
        user_res = supabase.table("users").insert({
            "username": username,
            "password_hash": hashed_password,
            "role": "user"
        }).execute()

        if user_res.data:
            # 3. 招待状を「使用済み」に更新する
            supabase.table("invitations").update({"is_used": True}).eq("token", token).execute()
            return True
    except Exception as e:
        st.error(f"登録に失敗しました。: {e}")
        return False

def disable_sidebar():
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

def get_base_url():
    # 1. 実行環境が「Streamlit Community Cloud」かどうかを判定
    is_cloud = os.getenv("STREAMLIT_RUNTIME_ENV") == "cloud" or "HOSTNAME" in os.environ
    
    if is_cloud:
        # 本番環境：Secretsから取得
        return st.secrets["app"]["base_url"]
    else:
        # ローカル環境：標準のポート番号を返す
        return "localhost"

# Cookieに追加/削除
def operation_cookie_data(add: bool, user_name: str):
    if add:
        order = "max-age=172800" # 2日間
        domain = ""
    else:
        order = "max-age=0"
        domain = f"domain={get_base_url()};"
    
    # js_code生成時にインデントを揃えないと挙動が不安定になるので、編集する場合は注意
    command = f"""
        window.parent.document.cookie = "logged_in_user={user_name}; path=/; {domain} {order}";
    """
    raw_code = """
    <script>
        // 親画面（parent）のドキュメントに対してCookie処理を命じる
        __COMMAND__

        // Streamlitに「完了」を通知
        const streamlitDoc = window.parent.document;
        
        // 共通のフォーマット（JavaScriptのルール）
        //new CustomEvent("宛先（合言葉）※streamlitの場合は「streamlit:setComponentValue」", {
        //    detail: "送る中身" // 箱の名前は必ず detail
        //});
        const event = new CustomEvent("streamlit:setComponentValue", {
            detail: "done"
        });

        // 送る中身が届き、js_resultが受け取る
        streamlitDoc.dispatchEvent(event);
    </script>
    """
    js_code = raw_code.replace("__COMMAND__", command)
    # print(js_code)
    js_result = components.html(
        js_code,
        height=0, # 画面に何も表示したくないときは高さを0にする
    )
    return js_result

def check_login(username, password):
    # Supabaseからユーザーを1件取得
    res = supabase.table("users").select("*").eq("username", username).execute()
    
    if res.data:
        user = res.data[0]
        # DBに保存されたハッシュ化パスワードと、入力されたパスワードを照合
        if bcrypt.checkpw(password.encode('utf-8'), user["password_hash"].encode('utf-8')):
            return user # 成功したらユーザー情報を返す
    return None

def control_expires_at(add_day):
    return datetime.now() + timedelta(days=add_day)


# 1. 各ページを定義（ファイルとして切り出しておく）
page_main = st.Page("pages/main.py", title="ホーム", default=True)
page_signup = st.Page("pages/sign_up_page.py", title="ユーザー登録")

pages = []
# 状態の初期化（アプリの冒頭などで一度だけ実行）
if "reg_success" not in st.session_state:
    st.session_state.reg_success = False

query_params = st.query_params
st.set_page_config(layout="wide")
supabase = init_supabase()
cookie_manager = stx.CookieManager()
# リロード時：Cookieがあればログイン状態を復元（一番上に書く）
try:
    # saved_user = cookie_manager.get(cookie="logged_in_user")
    saved_user = st.context.cookies.get("logged_in_user")
except Exception as e:
    saved_user = None

# st.session_state["authentication_status"]の値が切り替わると再度実行されるので、ANDで繋ぐ
if saved_user and "authentication_status" not in st.session_state:
# if saved_user and "relode" not in st.session_state:
    # st.session_state["relode"] = True
    # print(f"{st.session_state["relode"]} 到達relode")
    # Cookieがあれば、Cookieから情報を取得してログイン状態を保持。ただしロールはDBを再照合
    res = supabase.table("users").select("role").eq("username", saved_user).execute()
    if res.data:
        user_info = res.data[0]
        st.session_state["name"] = saved_user
        st.session_state["role"] = user_info["role"]
        st.session_state["authentication_status"] = True
        print(f"{st.session_state["authentication_status"]} 到達Auth")
# tokenあり（登録フォーム）
if "token" in query_params:
    disable_sidebar()
    token = query_params["token"]
    new_user = ""
    # すでに登録成功しているかどうかで表示を分ける
    if not st.session_state.reg_success:
        # 1. トークンの有効性をDBで確認
        res = supabase.table("invitations").select("*").eq("token", token).eq("is_used", False).execute()
        if res.data:
            invite_data = res.data[0]
            # 2. 有効期限のチェック（現在時刻 < expires_at）
            expires_at = datetime.fromisoformat(invite_data["expires_at"])
            if datetime.now() < expires_at:
                st.subheader("新規ユーザー登録")
                with st.form("registration_form"):
                    new_user = st.text_input("希望のユーザー名")
                    new_pass = st.text_input("パスワード", type="password")
                    if st.form_submit_button("登録"):
                        # ここでハッシュ化して保存 ＆ is_usedをTrueに更新
                        if register_new_user(new_user, new_pass, token):
                            st.session_state.reg_success = True
                            st.session_state["name"] = new_user
                            st.rerun()
            else:
                st.error("招待リンクの有効期限が切れています。")
                if st.button("ログイン画面へ"):
                    st.query_params.clear()
        else:
            st.error("このリンクは無効か、既に使用されています。")
            if st.button("ログイン画面へ"):
                st.query_params.clear()
    else:
        # 【登録成功後の表示】フォームの外なので st.button が使える
        st.success("登録が完了しました！")
        st.balloons()
        if st.button("ログイン"):
            # URLパラメータを消して、フラグを戻してからリロード
            st.query_params.clear()
            st.session_state.reg_success = False
            st.session_state["authentication_status"] = True
            st.session_state["role"] = "user" # 新規は一般ユーザー
            cookie_manager.set("logged_in_user", new_user, expires_at=control_expires_at(2))
            st.rerun()

# tokenなし（未ログイン：ログイン画面 / ログイン済み：ホーム画面）
else:
    # if "authentication_status" not in st.session_state:
    #     st.session_state["authentication_status"] = None

    if not st.session_state["authentication_status"]:
        disable_sidebar()
        with st.form("login_form"):
            u = st.text_input("ユーザー名")
            p = st.text_input("パスワード", type="password")
            if st.form_submit_button("ログイン"):
                user = check_login(u, p)
                if user:
                    # cookie_manager.set("logged_in_user", user["username"], expires_at=control_expires_at(2))
                    js_result = operation_cookie_data(add=True, user_name=user["username"])
                    if js_result is None:
                        st.stop()
                    st.session_state["authentication_status"] = True
                    st.session_state["name"] = user["username"]
                    st.session_state["role"] = user["role"]
                    st.rerun()
                else:
                    # st.session_state["authentication_status"] = False
                    st.error("Usernameまたは、passwordが間違っています")
            else:
                st.warning("Usernameとpasswordを入力してください")
    else:
        st.session_state["authentication_status"] = True
        pages.append(page_main)
        if st.session_state["role"] == "admin":
            pages.append(page_signup)
        pg = st.navigation(pages)
        with st.sidebar:
            st.write(f"👤 ログイン中: \n\n**{st.session_state['name']}** さん")
            if st.button("ログアウト"):
                # cookie_manager.delete("logged_in_user")                
                # URLを初期化して再描画
                st.query_params.clear()
                js_result = operation_cookie_data(add=False, user_name="invalid")
                if js_result is None:
                    st.stop()
                st.session_state.logout_js_done = True

            if st.session_state.get("logout_js_done"):
                st.session_state.logout_js_done = False
                st.session_state["authentication_status"] = None
                # セッション情報をすべて消去（またはログイン関連のみ消去）
                st.session_state.clear()
                st.session_state["role"] = None
                st.rerun()

        pg.run()
