import streamlit as st
import pandas as pd
from connect_supabase import init_supabase

st.set_page_config(
    page_title="PubChemサーチ",  # ブラウザのタブ名
    layout="wide"
)
supabase = init_supabase()

# 3. データの取得（キャッシュを利用して高速化）
@st.cache_data(ttl=600) # 10分間キャッシュを保持
def load_data():
    # "compounds" テーブルから全件取得
    response = supabase.table("compounds").select("*").execute()
    return response.data

# データの読み込み
data = load_data()

if data:
    df = pd.DataFrame(data)
    all_names = sorted(df["japanese_name"].unique().tolist())

    st.subheader("表示フィルター")

    # 1. まず「全表示」のチェックボックスを配置
    show_all = st.checkbox("全表示", value=True) # 初期状態をTrueに設定
    
    st.write("---") # 区切り線

    selected_names = []
    
    # 2. 「全表示」がオフの時だけ個別選択を有効にする
    if not show_all:
        st.write("表示したい化合物を個別に選択してください：")
        # 5列表示で4行ぶん程度の高さに固定し、残りは縦スクロールにする
        with st.container(height=180, border=True):
            cols = st.columns(5)
            for i, name in enumerate(all_names):
                with cols[i % 5]:
                    if st.checkbox(name, key=name):
                        selected_names.append(name)
    else:
        st.info("現在、全てのデータが表示されています。個別選択をするには「全表示」を外してください。")

    # 3. フィルタリング処理
    if show_all:
        display_df = df
    else:
        if not selected_names:
            st.warning("表示する化合物が選択されていません。")
            display_df = pd.DataFrame()
        else:
            display_df = df[df["japanese_name"].isin(selected_names)]

    # 4. テーブル表示
    if not display_df.empty:
        st.divider()
        
        # カラム整理
        cols_order = ["japanese_name", "cas_number", "english_name", "molecular_formula", "molecular_weight", "logp", "vapor_pressure","tpsa", "smiles"]
        display_df = display_df[[c for c in cols_order if c in df.columns]]
        
        st.write(f"表示件数: **{len(display_df)}** 件")
        st.dataframe(
            display_df, 
            hide_index=True,
            column_config={
                "molecular_weight": st.column_config.TextColumn(
                    "分子量",
                    width="small",  # "small", "medium", "large" などで指定可能
                ),
                "logp": st.column_config.TextColumn(
                    "LogP値",
                    width="small",  # "small", "medium", "large" などで指定可能
                ),
                "vapor_pressure": st.column_config.TextColumn(
                    "蒸気圧",
                ),
                "cas_number": st.column_config.TextColumn(
                    "CAS番号",
                    # width=100,  # 数値でピクセル指定も可能
                ),
                # 他の列も必要に応じて設定できます
            }
        )
        # --- 補足情報の表示 ---
        with st.chat_message("assistant", avatar="🧪"):
            st.markdown("""
            - 分子量が大きいと気化しにくく、分子量が小さいと気化しやすい
            - LogP値は値が大きいほど脂溶性（親油性）が高く、小さいほど水溶性（親水性）が高い。
            - 植物が作り出す多くの香り成分は、イソプレン（C5H8）が複数個集まってできたテルペン化合物で、テルペン類とも呼ばれている。
            - イソプレンが2個結合したものを「モノテルペン類」と呼ぶ。（C10H16）小さい分子であるため、揮発性が高く、トップノートとして扱われる。
                - 主な香りの成分：α-ピネン、リモネン。
                - 特徴：香りが弱い。酸化しやすい。抗ウイルス・抗菌、皮膚や粘膜を刺激。
            - イソプレンが3個結合したものを「セスキテルペン類」と呼ぶ。（C15H24）分子の大きさがモノテルペン類より大きく、粘性があることから揮発性はそれほど高くない。
                - 主な香りの成分：カマズレン、パチュレン、ネロリドール。
                - 特徴：香りが強い。粘り気がある。リラックス、抗炎症作用。皮膚や粘膜をやや刺激。
            - イソプレンが4個結合したものを「ジテルペン類」と呼ぶ。（C20H32）分子の大きさがセスキテルペン類よりもさらに大きく、揮発性が低いことから水蒸気蒸留ではほとんど蒸留されない。
                - 主な香りの成分：スクラレオール、イソフィトール
                - 特徴：香りはほとんどないor弱い。香りを長持ちさせる保留剤の役割をする。アブソリュートに多く含まれる。
            - 分子と分子の間には、自然と引き合う力（分子間力）があり、一般に分子間力は分子が大きくなるほど強く働き、気体になりにくいことがわかっている。
            - 分子構造に「個性的な特徴をもつ塊」がいくつか存在しており、これを官能基と呼ぶ。
            - ヒドロキシ基（-OH）：テルペン類にOH基が結合した「アルコール類」とベンゼン環に結合した「フェノール類」の2種類がある。いずれも名前の語尾が「オール」になる
                - アルコール類
                    - 特徴：安定。柔らかく香る、酸化されやすい、気分を高揚させる作用、抗菌作用、毒性はなく皮膚にも穏やか
                    - 主な香りの成分（モノテルペン）：ゲラニオール、リナロール、メントール、テルピネン-4-オール
                    - 主な香りの成分（セスキテルペン）：ネロリドール、パチュロール、ベチベロール、サンタロール
                    - 主な香りの成分（ジテルペン）：スクラレオール
                    - 主な香りの成分（芳香族）：フェニルエチルアルコール
                - フェノール類
                    - 特徴：揮発性が低い、強力な抗菌作用、皮膚や粘膜への刺激強い、長時間使用しない、高濃度で使用しない
                    - 主な香りの成分：オイゲノール
            - アルデヒド基（-CHO）：アルデヒド基を含む化合物をアルデヒド類という。名前の語尾は「アール」
                - アルデヒド類
                    - 特徴：シャープ。酸化されやすい、虫よけ作用、高濃度では皮膚や粘膜を刺激
                    - 主な香りの成分：シトラール、シトロネラール、ネラール
            - カルボニル基（-CO-）：カルボニル基を含む化合物を「ケトン類」という。名前の語尾は「～オン」となるものが多い。
                - ケトン類
                    - 特徴：少量では鎮静作用、刺激の強い成分や毒性のあるものが存在する、乳幼児・妊婦・授乳中・てんかんを持つ方への使用は注意
                    - 主な香りの成分：カンファー、ヌートカトン、メントン
            - エステル結合（-COO-）：酸とアルコール類が反応して生成される「エステル類」と環性構造の中にエステル結合を含む「ラクトン・クマリン類」がある。
                - エステル類：名前は「～酸、～イル」
                    - 特徴：甘くてフルーティな強い香り、深い鎮静作用、刺激は少ない
                    - 主な香りの成分：酢酸リナリル、酢酸ベンジル、安息香酸メチル
                - ラクトン、クマリン類
                    - 特徴：揮発性は低い、水蒸気蒸留で得られる成分には含まれていない、光毒性の原因物質、皮膚に塗布後の紫外線はNG
                    - 主な香りの成分：ベルガプテン
            - エーテル結合（-O-）：環状構造の中にエーテル結合を含む化合物を「オキサイド類」という。
                - オキサイド類
                    - 特徴：揮発性が高く、強い爽快感のある香り、強力な去痰作用、抗感染作用、多量使用すると皮膚を刺激
                    - 主な香りの成分：1,8-シオネール
            """)

else:
    st.info("データがありません。")