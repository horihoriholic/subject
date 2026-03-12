import os
import streamlit as st
import secrets
from datetime import datetime, timedelta
import streamlit_authenticator as stauth
from connect_supabase import init_supabase

def get_base_url():
    # 1. 実行環境が「Streamlit Community Cloud」かどうかを判定
    is_cloud = os.getenv("STREAMLIT_RUNTIME_ENV") == "cloud" or "HOSTNAME" in os.environ
    
    if is_cloud:
        # 本番環境：Secretsから取得
        return st.secrets["app"]["base_url"]
    else:
        # ローカル環境：標準のポート番号を返す
        return "http://localhost:8501"

def create_invitation():
    # 24時間有効なランダムトークンを生成
    token = secrets.token_urlsafe(16)
    expires_at = datetime.now() + timedelta(hours=24)
    try:
        # Supabaseに保存
        supabase.table("invitations").insert({
            "token": token,
            "expires_at": expires_at.isoformat(),
            "is_used": False
        }).execute()
        base_url = get_base_url()
        return f"{base_url}/?token={token}"

    except Exception as e:
        st.error(f"招待状の作成に失敗しました: {e}")
        return None

config = st.secrets.to_dict()
authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days']
)
if st.session_state["authentication_status"]:
    # --- StreamlitデフォルトのPagesナビ（sidebar先頭）を非表示 ---
    st.markdown(
        """
        <style>
            /* サイドバー先頭に出る「Pages」ナビを消す */
            [data-testid="stSidebarNav"] { display: none; }
        </style>
        """,
        unsafe_allow_html=True,
    )


    st.set_page_config(
        page_title="ユーザー登録画面",  # ブラウザのタブ名
    )
    with st.sidebar:
        st.write(f"👤 ログイン中: \n\n**{st.session_state['name']}** さん")
        authenticator.logout('ログアウト', 'main')
        st.divider()
        st.caption("メニュー")
        if st.button("ホーム"):
                # Streamlit multipage: `pages/page1.py` に遷移
                if hasattr(st, "switch_page"):
                    st.switch_page("streamlit_app.py")
                else:
                    st.warning("このStreamlitバージョンではページ遷移APIが利用できません。`pages/page1.py` を直接開いてください。")
    # 管理者メニューでの表示
    st.title("ユーザー登録")
    # クライアントの取得
    supabase = init_supabase()
    if st.button("招待URLを発行する"):
        invite_url = create_invitation()
        if not invite_url == None:
            st.success("以下のURLをSlackで送ってください：")
            st.code(invite_url)


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

