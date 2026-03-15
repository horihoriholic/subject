# 精油成分サーチRAGアプリ
精油の成分に関する情報を調べることができるアプリです。
Webや複数の書籍から情報を取得します。

### 開発の目的

趣味で香りの制作をしていて、香りについて学習する中で、必要な情報をパッと入手できたらいいなと思う場面が何度もある。  
Webにも有益な情報はあるが、書籍にのみ情報が記載されていることがある上に、複数の書籍に情報が分散されていたりもする。  
それらの情報を統合して必要な情報を取得したい場合は、頭にインプットしたり、書籍を持ち歩いたり、自分用にノートにまとめたりする必要があるし、
必要な情報を探す場合、都度時間をかけて探さなければならない。  
これを統合して、ほしい情報がすぐに取得できる状況になると、制作の幅は広がり、学習も加速して快適になる。  
生成AIのRAGの技術を用いれば、これを実現できる。  
また、「散在する情報を統合して即時検索ができるアプリ」は、香り以外でも需要があると感じており、学んだ技術をもとに自身で作成したいと思った。


### 主な機能
- ログイン/ログアウト  
- 招待制のユーザー登録機能
  - バリデーション
    - ユーザー名が既登録でない（ユーザー名とパスワードでログインできるので、ユーザー名はユニーク制限）
    - パスワードルール（8桁以上、大文字・小文字・数字を含む）
    - 有効期限が切れた場合は登録不可
    - 一度利用したことのある招待URLは使いまわし不可
- ホーム画面：精油成分サーチ機能
  - 香りの成分を探す
    - 解決したい症状/悩みから成分を探す（例：「イライラを鎮める」のに有効な成分をリストアップ）
    - 香りの種類から成分を探す（例：「フレッシュな香り」に含まれる成分をリストアップ）
  - 該当成分を多く含む精油を書籍から探す
    - ランキング形式で書籍の中から探す（例：「リナロール」を多く含む精油ベスト3を教えて）※出典も表示
  - 香りの情報を得る
    - 書籍の中から探す（例：「蒸気圧」について教えて）※要約に加えて、該当書籍の画像も表示
- ＜管理者のみ利用可能＞ユーザー登録機能　
  - 24時間有効な招待URLを発行 ※コピーしてSNSやメール等で連携

---
### 本番環境URL
https://me7scwcmrla8bed8amr9tt.streamlit.app/  
※動かない場合は、画面左下の「Manage App」をクリックし、三点リーダーをクリックした先にある「Reboot」をクリックしてください。  
※招待制となっています。招待URLは管理者に問合せください。

---
### アプリ仕様設計
#### 簡易アプリ企画
https://docs.google.com/spreadsheets/d/1w8PtIr3ZZKe-TH6n9YBiajAvAot4BloSruv5poqmniA/edit?gid=1446009625#gid=1446009625
#### 簡易アプリ仕様設計
https://docs.google.com/spreadsheets/d/1w8PtIr3ZZKe-TH6n9YBiajAvAot4BloSruv5poqmniA/edit?gid=577430712#gid=577430712

---
### 使用技術
| 分類                                                        | ツール・モデル  | 選定理由                                                             | 
| ----------------------------------------------------------- | --------------- | -------------------------------------------------------------------- | 
| 言語                                                        | Python 3.12     | ・学習で利用したから<br>・利用可能ライブラリの動作が安定しているから | 
| Webサーバー                                                 | Streamlit Cloud | ・構築不要でデプロイが簡単だから                                     | 
| ChatModel　<br>※LLMを用いた質問応答（OpenAIによる回答）                                                                                   | gpt-4o-mini     | ・学習で利用したから<br>・低コストだから                             | 
| ChatModel　<br>※LLMを用いた質問応答（RAGによる回答）と画像解析                                                                            | gpt-4o          | ・2026年2月時点のフラッグシップモデルだから                          | 
| ベクトルDB　<br>※著作権の観点でプログラムと切り離して管理したいので<br>外部DBを採択                                                           | Pinecone        | ・学習で利用したから<br>・無料で利用できるから                       | 
| ユーザー管理・招待token管理<br>※個人利用目的のため、secrets管理で事足りていたが、<br>提出課題ということで、アカウント作成機能をつける上で採択 | SUPABASE        | ・無料で利用できるから<br>・クラウドストレージも使えるから           | 
| ストレージ<br>※著作権の観点でプログラムと切り離して管理したいので<br>外部ストレージを採択                                             | SUPABASE        | ・無料で利用できるから<br>・DBも使えるから                           | 


---
### 必要な環境変数
```
OPENAI_API_KEY = ***
PINECONE_API_KEY = ***
PINECONE_INDEX_NAME = ***
[app]
base_url = ***
[supabase]
bucket_name = ***
url = ***
key = ***
```
上記をsecretに記述

依存関係は、各pyファイルのimportおよびrequirements.txtを参照してください。  
バージョンについては、下記を参考にしてください。
```
- aiohappyeyeballs==2.6.1
- aiohttp==3.13.3
- aiohttp-retry==2.9.1
- aiosignal==1.4.0
- altair==6.0.0
- annotated-types==0.7.0
- anyio==4.12.1
- attrs ==25.4.0
- bcrypt==5.0.0
- blinker==1.9.0
- cachetools==6.2.6
- captcha==0.7.1
- certifi==2026.2.25
- cffi==2.0.0
- charset-normalizer==3.4.5
- click==8.3.1
- cryptography==46.0.5
- deprecation==2.1.0
- distro==1.9.0
- extra-streamlit-components ==0.1.81
- frozenlist==1.8.0
- fsspec==2026.2.0
- gitdb==4.0.12
- gitpython==3.1.46
- greenlet==3.3.2
- h11== 0.16.0
- h2==4.3.0
- hpack==4.1.0
- httpcore==1.0.9
- httpx==0.28.1
- hyperframe==6.1.0
- idna==3.11 
- jinja2==3.1.6
- jiter==0.13.0
- jsonpatch==1.33
- jsonpointer==3.0.0
- jsonschema==4.26.0
- jsonschema-specifications ==2025.9.1
- langchain-classic==1.0.3
- langchain-core==1.2.19
- langchain-openai==1.1.11
- langchain-pinecone==0.2.13
- langchain-text-splitters==1.1.1
- langsmith==0.7.17
- markdown-it-py==4.0.0
- markupsafe==3.0.3
- mdurl==0.1.2
- mmh3==5.2.1
- multidict==6.7.1
- narwhals==2.18.0
- numpy==2.4.3
- openai==2.28.0
- orjson==3.11.7
- packaging==24.2
- pandas==2.3.3
- pillow==12.1.1 
- pinecone==7.3.0
- pinecone-plugin-assistant==1.8.0
- pinecone-plugin-interface==0.0.7
- postgrest==2.28.2
- propcache==0.4.1
- protobuf==6.33.5
- pyarrow==23.0.1
- pycparser==3.0
- pydantic==2.12.5
- pydantic-core==2.41.5
- pydeck==0.9.1 
- pygments==2.19.2
- pyiceberg==0.11.1
- pyjwt==2.12.1
- pyparsing==3.3.2
- pyroaring==1.0.3 
- python-dateutil==2.9.0.post0
- pytz==2026.1.post1
- pyyaml==6.0.3
- realtime==2.28.2
- referencing==0.37.0
-  regex==2026.2.28
- requests==2.32.5
- requests-toolbelt==1.0.0
- rich==14.3.3
- rpds-py==0.30.0
- simsimd ==6.5.16
- six==1.17.0
- smmap==5.0.3
- sniffio==1.3.1
- sqlalchemy==2.0.48
- storage3== 2.28.2
- streamlit==1.55.0
- streamlit-authenticator==0.4.2
- streamlit-js-eval==1.0.0
- strenum==0.4.15
- strictyaml==1.7.3 
- supabase==2.28.2
- supabase-auth==2.28.2
- supabase-functions==2.28.2
- tenacity==9.1.4
- tiktoken==0.12.0
- toml==0.10.2 
- tornado==6.5.5
- tqdm==4.67.3
- typing-extensions==4.15.0
- typing-inspection==0.4.2
- tzdata==2025.3
- urllib3==2.6.3
- uuid-utils==0.14.1 
- watchdog==6.0.0
- websockets==15.0.1
- xxhash==3.6.0
- yarl==1.23.0
- zstandard==0.25.0
```

---
### Pinecone index 側の注意

- **Embedding**: `OpenAIEmbeddings(model="text-embedding-3-small")` を使用 
- **次元**: `text-embedding-3-small` **1536次元**
- **メトリクス**: cosine
- **NAMESPACE**: multimodal

---
### 利用の流れ
#### 【準備】
1. **投入（`ingest5.py`）**: 画像→GPT-4oでテキスト化→Pineconeへ保存 ※ローカルで実行 `streamlit run ingest5.py`
    1. **IDは「book_name:filename」を UTF-8 → URL-safe Base64 でエンコード**に固定しているので、同じファイルは重複投入されません（`fetch` で存在確認）。
    2. 内容はPineconeのINDEX名.Namespace名を参照することで確認できるが、`check_db.py`でも確認可能 ※最初の10件のみ
2. **画像配置（手動でSUPABASEに配置）**: SUPABASE（https://supabase.com/） の`bucket_name`に`data`フォルダを作成の上、配置する。
#### 【利用】
1. **招待URL発行（`sign_up_page.py`）**: 管理者に招待URLを発行してもらう。<br> 管理者作成は手動で、SUPABASEのusersテーブルに、ロール：adminで登録する
2. **招待URLにアクセス（`streamlit_app.py`）**: 希望ユーザー名とパスワードを入力の上、登録してログインする。<br> 以降はパラメーターなしのURLにアクセスしてログインする。
3. **検索（`streamlit_app.py`）**: Pineconeから類似検索して RAG を実行。<br> 「情報を得る」パートでは、要約だけでなく、回答の元にした画像をSUPABASEのストレージから取得して表示する。


