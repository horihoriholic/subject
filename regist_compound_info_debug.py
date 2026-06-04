import pubchempy as pcp
import streamlit as st
import pandas as pd
import requests
import re #正規表現
from deep_translator import GoogleTranslator
import json
import pprint
import os
from supabase import create_client, Client
from connect_supabase import init_supabase

st.set_page_config(
    page_title="PubChemサーチ",  # ブラウザのタブ名
    layout="wide"
)
supabase = init_supabase()

########################### デバッグここから ##########################
def Boc_AA_OH(name_list):
    properties = ['iupacname', 'molecularformula', 'molecularweight', 'xlogp', 'tpsa', 'canonicalsmiles']
    return_list = []
    for n in name_list:
        AA = 'Boc-' + str(n) + '-OH'
        # print(str(n))
        # print("--------------------------------")
        # print(AA)
        x = pcp.get_properties(properties, AA, 'name')
        if len(x) == 1:
            # print(x[0])
            return_list.append(x[0])
        else:
            return_list.append('NA')
            print('{} was not retrived properly.')
    return return_list

# properties = ['IUPACName', 'MolecularFormula', 'MolecularWeight', 'XLogP', 'TPSA', 'CanonicalSMILES']
# a = pcp.get_properties(properties, 'alanine', 'name', as_dataframe=True)
# print(a)

# aa = pcp.get_compounds('alanine', 'name')
# for i in aa:
#     print('CID: {}\tName: {}'.format(i.cid, i.iupac_name))


def create_wikipedia_dataframe():
    url = 'https://en.wikipedia.org/wiki/Amino_acid'
    header = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    # Fetch the page content manually
    response = requests.get(url, headers=header)
    dfs = pd.read_html(response.text)
    df = dfs[0]
    print(df.head())
    names = df[('3- and 1-letter symbols', '3')] #マルチインデックスの場合、「（1段目, 2段目）」をタプル（組）にして指定することで取得できます。
    print(names.head())
    # names = ['Ala', 'Arg', 'Asn', 'Asp'] pubchempyでプロパティを取得できるか確認する用
    y = Boc_AA_OH(names)


    aa_df = pd.DataFrame(y)
    aa_df = aa_df.set_index('CID') # CIDをインデックスに設定＋データフレームからCIDを削除
    st.dataframe(aa_df)

# create_wikipedia_dataframe()

def get_cas_from_japanese(japanese_name):
    print(f"検索中: {japanese_name}...")
    try:
        # 翻訳 (deep-translatorを使用)
        english_name = GoogleTranslator(source='ja', target='en').translate(japanese_name)
        print(f"【翻訳】 {english_name}")
        
        # PubChem検索
        results = pcp.get_compounds(english_name, 'name')
        if not results:
            return "見つかりませんでした。"

        compound = results[0]
        print(f"【正式名】 {compound.iupac_name}")
        cas_pattern = re.compile(r'^\d{2,7}-\d{2}-\d$')
        cas_numbers = [s for s in compound.synonyms if cas_pattern.match(s)]
        
        return sorted(list(set(cas_numbers))) if cas_numbers else "CAS番号なし"

    except Exception as e:
        return f"エラー: {e}"

# compounds_list = ["リモネン", "リナロール"]
# for name in compounds_list:
#     cas = get_cas_from_japanese(name)
#     print(f"【{name}】 CAS番号: {cas}\n")
########################### デバッグここまで ##########################

