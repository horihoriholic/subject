import pubchempy as pcp
import streamlit as st
import pandas as pd
import requests
import re #正規表現
import pprint
import os
from supabase import create_client, Client
from connect_supabase import init_supabase

st.set_page_config(
    page_title="PubChem情報登録",  # ブラウザのタブ名
    layout="wide"
)
supabase = init_supabase()

def log_not_found_name(name_jp):
    log_path = os.path.join(os.path.dirname(__file__), "not_found_cid.log")
    with open(log_path, "a", encoding="utf-8") as log_file:
        log_file.write(f"{name_jp}\n")

def load_name_pairs_from_log():
    log_path = os.path.join(os.path.dirname(__file__), "not_found_cid.log")
    if not os.path.exists(log_path):
        print(f"ログファイルが見つかりません: {log_path}")
        return []

    pairs = []
    with open(log_path, "r", encoding="utf-8") as log_file:
        for line in log_file:
            raw = line.strip()
            if not raw or ":" not in raw:
                continue
            name_jp, english_name = raw.split(":", 1)
            name_jp = name_jp.strip()
            english_name = english_name.strip()
            if name_jp and english_name:
                pairs.append((name_jp, english_name))
    return pairs

def get_vapor_pressure(cid):
    if not cid:
        return "CIDなし"
        
    # PUG View APIのURL
    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound/{cid}/JSON"
    
    # 対策1: ブラウザからのアクセスに見せかける（User-Agent）
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 404: return "データなし"
        
        data = response.json()

        # JSONの深い階層から String をすべて拾い集める
        def collect_strings(obj):
            found = []
            if isinstance(obj, dict):
                if 'String' in obj: found.append(obj['String'])
                for v in obj.values(): found.extend(collect_strings(v))
            elif isinstance(obj, list):
                for item in obj: found.extend(collect_strings(item))
            return found

        all_strings = collect_strings(data)

        # 拾った文字列の中から、蒸気圧らしい記述（数値 + mm Hgなど）を正規表現で探す
        # 例: "0.6 mm Hg at 20 °C"
        vp_pattern = re.compile(r'(\d+\.?\d*\s*(?:mm\s*Hg|Pa|hPa|torr)[^.]*)', re.IGNORECASE)

        for s in all_strings:
            match = vp_pattern.search(s)
            if match:
                return match.group(1).strip() # 最初に見つかった蒸気圧を返す

        return "データなし"

    except Exception as e:
        return f"取得失敗: {e}"

        
def get_full_compound_info(name_jp, english_name):
    """
    日本語名から英語名、正式名、CAS番号を取得して辞書で返す
    """
    print(f"検索中: {name_jp}...")
    
    # 返却用の初期値（見つからなかった場合などのため）
    result_data = {
        "日本語名": name_jp,
        "英語名": None,
        "正式名": None,
        "CAS番号": None,
        "分子式": None,
        "分子量": None,
        "LogP": None,
        "蒸気圧": None,
        "TPSA": None,
        "SMILES": None
    }
    
    try:
        # ＜jsonから取得する場合＞
        # # 1. 翻訳（日本語 -> 英語）
        # english_name = GoogleTranslator(source='ja', target='en').translate(name_jp)
        # result_data["英語名"] = english_name.capitalize()

        # ＜logから取得する場合＞      
        # 1. ログ記載の英語名を使用
        result_data["英語名"] = english_name
        
        # 2. PubChem検索
        results = pcp.get_compounds(english_name, 'name')
        
        if not results:
            log_not_found_name(name_jp)
            return [result_data]

        c = results[0]
        
        # 3. 全てのCAS番号を抽出
        cas_pattern = re.compile(r'^\d{2,7}-\d{2}-\d$')
        # setを使うことで、重複（同じ番号が複数回リストにある場合）を排除
        all_cas = sorted(list(set([s for s in c.synonyms if cas_pattern.match(s)])))

        # 4. ヒットした各CAS番号ごとにデータを作成
        final_list = []
        for cas in all_cas:

            result_data["CAS番号"] = cas
            result_data["正式名"] = c.iupac_name
            result_data["分子式"] = c.molecular_formula
            result_data["分子量"] = c.molecular_weight
            result_data["LogP"] = c.xlogp
            result_data["TPSA"] = c.tpsa
            result_data["SMILES"] = c.canonical_smiles
            # 【追加】CIDを使って蒸気圧を取得
            result_data["蒸気圧"] = get_vapor_pressure(c.cid)
            
            final_list.append(result_data.copy())
            
        return final_list
            
    except Exception as e:
        print(f"エラー発生 ({name_jp}): {e}")
        return [result_data]

def upsert_to_supabase_by_cas(results_list):
    deduped_by_cas = {}
    for item in results_list:
        # CAS番号が「未登録」や「見つかりませんでした」の場合は
        # ユニーク制約でエラーになる可能性があるため、有効な形式かチェックすると安全です
        cas = item["CAS番号"]
        if not cas or cas == "未登録" or cas == "CAS番号なし":
            continue # CAS番号がないものはスキップ、あるいは別の処理へ

        deduped_by_cas[cas] = {
            "japanese_name": item["日本語名"],
            "english_name": item["英語名"],
            "iupac_name": item["正式名"],
            "cas_number": cas, # リストの最初の1つを文字列として登録
            "molecular_formula": item["分子式"],
            "molecular_weight": item["分子量"],
            "logp": item["LogP"],
            "vapor_pressure": item["蒸気圧"],
            "tpsa": item["TPSA"],
            "smiles": item["SMILES"]
        }

    data_to_insert = list(deduped_by_cas.values())

    if not data_to_insert:
        print("登録対象のデータがありませんでした。")
        return None

    try:
        # on_conflict を cas_number に変更
        response = supabase.table("compounds").upsert(
            data_to_insert, 
            on_conflict="cas_number"
        ).execute()
        
        print(f"CAS番号を基準に {len(data_to_insert)} 件をアップサートしました。")
        return response
    except Exception as e:
        print(f"エラーが発生しました: {e}")
        return None

# ＜logから取得する場合＞
name_pairs = load_name_pairs_from_log()

# ＜master_data.jsonから取得する場合＞
# with open('master_data.json', 'r', encoding='utf-8') as f:
#     data = json.load(f)
# compounds_list = data["香りの成分"]
# for name in compounds_list:
#     final_results.extend(get_full_compound_info(name))

final_results = []
for name_jp, english_name in name_pairs:
    final_results.extend(get_full_compound_info(name_jp, english_name))

# 結果を一つ見やすく表示
# pprint.pprint(final_results[7])

# SUPABASEに登録
response = upsert_to_supabase_by_cas(final_results)
