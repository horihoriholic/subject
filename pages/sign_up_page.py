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

st.set_page_config(
    page_title="ユーザー登録画面",  # ブラウザのタブ名
    layout="wide"
)
# 管理者メニューでの表示
st.title("ユーザー登録")
# クライアントの取得
supabase = init_supabase()
if st.button("招待URLを発行する"):
    invite_url = create_invitation()
    if not invite_url == None:
        st.success("以下のURLをSlackで送ってください：")
        st.code(invite_url)
