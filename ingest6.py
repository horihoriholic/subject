"""
col_right（香りの情報を得る）の検索を一括実行し、結果を output/ 以下に JSON で保存する。

main.py の col_right と同じプロンプト・検索フローを使用する。
カテゴリー・キーワードは master_data.json（main.py の load_options と同じ）を参照する。

必要な環境変数:
  - OPENAI_API_KEY
  - PINECONE_API_KEY

.streamlit/secrets.toml または環境変数:
  - PINECONE_INDEX_NAME
  - PINECONE_NAMESPACE（任意、既定: multimodal）
  - supabase.url, supabase.bucket_name（画像 URL 組み立て用）

使い方:
  python ingest6.py
    → 1件だけ試行し、出力を表示。問題なければ y で全件実行
  python ingest6.py --all
    → 確認なしで全件一括実行
  python ingest6.py --all --skip-existing
    → 試行済み分をスキップして残りを実行
  python ingest6.py --trial
    → 1件だけ試行して終了（確認プロンプトなし）
  python ingest6.py --category "香りの成分" --keyword "リモネン"
    → 試行対象を指定
  python ingest6.py --retry-items "香りのサイエンス / 香りの分子の毒性;精油 / ティートリー&カユプテ"
    → 指定した組み合わせだけ再実行（既存JSONは上書き）
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

from langchain_classic.prompts import PromptTemplate
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore

from search_result_utils import build_col_right_result

BASE_DIR = Path(__file__).resolve().parent
MASTER_DATA_PATH = BASE_DIR / "master_data.json"
BOOK_MASTER_PATH = BASE_DIR / "book_master.json"
OUTPUT_DIR = BASE_DIR / "output"
SECRETS_PATH = BASE_DIR / ".streamlit" / "secrets.toml"

NOT_FOUND_MESSAGE = (
    "ご指定の成分を含む精油の情報は、提供された資料内には見つかりませんでした。"
)

PROMPT_TEMPLATE = """
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


def load_toml_secrets() -> dict:
    if not SECRETS_PATH.exists():
        return {}
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]

    with SECRETS_PATH.open("rb") as f:
        return tomllib.load(f)


def get_config() -> dict[str, str]:
    secrets = load_toml_secrets()
    supabase = secrets.get("supabase", {})

    pinecone_index = os.getenv("PINECONE_INDEX_NAME") or secrets.get("PINECONE_INDEX_NAME")
    pinecone_namespace = (
        os.getenv("PINECONE_NAMESPACE")
        or secrets.get("PINECONE_NAMESPACE")
        or "multimodal"
    )
    supabase_url = os.getenv("SUPABASE_URL") or supabase.get("url", "")
    bucket_name = os.getenv("SUPABASE_BUCKET_NAME") or supabase.get("bucket_name", "")

    return {
        "pinecone_api_key": os.getenv("PINECONE_API_KEY", ""),
        "pinecone_index_name": pinecone_index or "",
        "pinecone_namespace": pinecone_namespace,
        "supabase_url": supabase_url.rstrip("/"),
        "supabase_bucket_name": bucket_name,
    }


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def safe_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*\n\r]', "_", name).strip() or "unknown"


def get_img_url(
    book: str,
    source: str,
    book_master: dict[str, str],
    supabase_url: str,
    bucket_name: str,
) -> str:
    book_id = book_master.get(book, book)
    path_of_bucket = f"data/{book_id}/{source}"
    return f"{supabase_url}/storage/v1/object/public/{bucket_name}/{path_of_bucket}"


def build_context(docs: list) -> str:
    context_elements = []
    for doc in docs:
        content = doc.page_content
        book_name = doc.metadata.get("book", "不明な書籍")
        source_name = doc.metadata.get("source", "不明なソース")
        element = (
            f"【出典情報】book: {book_name}, source: {source_name}\n内容: {content}"
        )
        context_elements.append(element)
    return "\n\n---\n\n".join(context_elements)


def parse_llm_json(raw_content: str) -> list:
    clean_content = raw_content.strip().replace("```json", "").replace("```", "")
    return json.loads(clean_content)


def run_col_right_search(
    category: str,
    keyword: str,
    vectorstore: PineconeVectorStore,
    llm: ChatOpenAI,
    book_master: dict[str, str],
    supabase_url: str,
    bucket_name: str,
) -> dict:
    """main.py col_right と同じ検索・後処理を行い、JSON 用の dict を返す。"""
    question = (
        f"{category}における{keyword}について、"
        "提供された資料をもとに500文字以内で教えてください。"
    ) 
    retriever = vectorstore.as_retriever(search_kwargs={"k": 10})
    search_query = f"{keyword}"
    docs = retriever.invoke(search_query)
    # docs = retriever.invoke(question)
    context = build_context(docs)

    prompt = PromptTemplate(
        template=PROMPT_TEMPLATE, input_variables=["context", "question"]
    )
    final_prompt = prompt.format(context=context, question=question)
    response = llm.invoke(final_prompt)
    raw_content = response.content

    result: dict = {
        "category": category,
        "keyword": keyword,
        "question": question,
        "clean_answer": "",
        "answer_image_paths": [],
    }

    try:
        data_list = parse_llm_json(raw_content)
    except json.JSONDecodeError as e:
        result["error"] = f"JSONの解析に失敗しました: {e}"
        result["raw_content"] = raw_content
        return result

    def get_image_entry(book: str, source: str) -> dict:
        return {
            "path": get_img_url(
                book, source, book_master, supabase_url, bucket_name
            ),
            "book": book,
            "source": source,
        }

    clean_answer, answer_image_paths = build_col_right_result(
        data_list, get_image_entry
    )

    if not clean_answer:
        result["clean_answer"] = NOT_FOUND_MESSAGE
        result["answer_image_paths"] = []
        return result

    result["clean_answer"] = clean_answer
    result["answer_image_paths"] = answer_image_paths
    return result


def output_path(category: str, keyword: str) -> Path:
    return OUTPUT_DIR / safe_filename(category) / f"{safe_filename(keyword)}.json"


def iter_jobs(
    options_map: dict[str, list[str]],
    category_filter: str | None = None,
) -> list[tuple[str, str]]:
    jobs: list[tuple[str, str]] = []
    categories = (
        [category_filter]
        if category_filter
        else list(options_map.keys())
    )
    for category in categories:
        for keyword in options_map[category]:
            jobs.append((category, keyword))
    return jobs


def parse_retry_items(
    retry_items: str,
    all_jobs: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """
    文字列で渡された「カテゴリー / キーワード」一覧を実行ジョブに変換する。
    例: "香りのサイエンス / 香りの分子の毒性;精油 / ティートリー&カユプテ"
    """
    known_jobs = set(all_jobs)
    parsed: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    raw_items = [item.strip() for item in retry_items.split(";") if item.strip()]
    if not raw_items:
        raise ValueError("再実行対象が空です。--retry-items の値を確認してください。")

    for raw in raw_items:
        if "/" not in raw:
            raise ValueError(
                f"形式エラー: '{raw}'。'カテゴリー / キーワード' 形式で指定してください。"
            )
        category, keyword = [part.strip() for part in raw.split("/", 1)]
        pair = (category, keyword)
        if pair not in known_jobs:
            raise ValueError(
                f"master_data.json に存在しない組み合わせです: {category} / {keyword}"
            )
        if pair not in seen:
            parsed.append(pair)
            seen.add(pair)

    return parsed


def find_trial_job(
    jobs: list[tuple[str, str]],
    category: str | None,
    keyword: str | None,
) -> tuple[str, str]:
    if category and keyword:
        pair = (category, keyword)
        if pair not in jobs:
            raise ValueError(
                f"指定の組み合わせが見つかりません: {category} / {keyword}"
            )
        return pair
    if category and not keyword:
        for cat, kw in jobs:
            if cat == category:
                return cat, kw
        raise ValueError(f"カテゴリー '{category}' にキーワードがありません")
    return jobs[0]


def save_result(out_path: Path, result: dict) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


def print_result_preview(result: dict, out_path: Path) -> None:
    print("\n--- 試行結果プレビュー ---")
    print(f"保存先: {out_path.relative_to(BASE_DIR)}")
    if "error" in result:
        print(f"エラー: {result['error']}")
    answer = result.get("clean_answer", "")
    preview = answer[:300] + ("..." if len(answer) > 300 else "")
    print(f"clean_answer ({len(answer)} 文字):\n{preview}")
    images = result.get("answer_image_paths", [])
    print(f"answer_image_paths: {len(images)} 件")
    for img in images[:3]:
        print(f"  - {img.get('book')} / {img.get('source')}")
    if len(images) > 3:
        print(f"  ... 他 {len(images) - 3} 件")
    print("--------------------------\n")


def process_one(
    category: str,
    keyword: str,
    vectorstore: PineconeVectorStore,
    llm: ChatOpenAI,
    book_master: dict[str, str],
    config: dict[str, str],
    skip_existing: bool,
) -> tuple[str, bool, bool]:
    """
    1件処理する。
    戻り値: (status, skipped, failed)
    status は "ok" | "skip" | "fail"
    """
    out_path = output_path(category, keyword)
    if skip_existing and out_path.exists():
        print(f"[SKIP] {category} / {keyword}")
        return "skip", True, False

    print(f"[RUN] {category} / {keyword}")
    try:
        result = run_col_right_search(
            category,
            keyword,
            vectorstore,
            llm,
            book_master,
            config["supabase_url"],
            config["supabase_bucket_name"],
        )
        save_result(out_path, result)
        if "error" in result:
            print(f"  -> 保存したが解析エラー: {result['error']}")
            return "fail", False, True
        print(f"  -> {out_path.relative_to(BASE_DIR)}")
        return "ok", False, False
    except Exception as e:
        err_result = {
            "category": category,
            "keyword": keyword,
            "question": (
                f"{category}における{keyword}について、"
                "提供された資料をもとに500文字以内で教えてください。"
            ),
            "clean_answer": "",
            "answer_image_paths": [],
            "error": str(e),
        }
        save_result(out_path, err_result)
        print(f"  -> 失敗: {e}", file=sys.stderr)
        return "fail", False, True


def ask_continue() -> bool:
    while True:
        answer = input(
            "出力 JSON を確認し、問題なければ全件実行します。\n"
            "続行しますか？ [y/N]: "
        ).strip().lower()
        if answer in ("y", "yes"):
            return True
        if answer in ("", "n", "no"):
            return False
        print("y または N で入力してください。")


def main() -> int:
    parser = argparse.ArgumentParser(description="col_right 検索結果を一括生成する")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--trial",
        action="store_true",
        help="1件だけ試行して終了（確認プロンプトなし）",
    )
    mode.add_argument(
        "--all",
        action="store_true",
        help="確認なしで全件一括実行",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="試行後の確認プロンプトをスキップして全件実行",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="既に output に JSON がある組み合わせはスキップする",
    )
    parser.add_argument(
        "--category",
        help="カテゴリーを指定（--keyword と併用で試行対象を固定）",
    )
    parser.add_argument(
        "--keyword",
        help="キーワードを指定（試行対象の固定、または --all 時の単一実行）",
    )
    parser.add_argument(
        "--retry-items",
        help=(
            "再実行する組み合わせをセミコロン区切りで指定。"
            "形式: 'カテゴリー / キーワード;カテゴリー / キーワード'"
        ),
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="各検索の間に入れる待機秒数（API レート制限対策）",
    )
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY が未設定です。", file=sys.stderr)
        return 1

    config = get_config()
    if not config["pinecone_api_key"]:
        print("ERROR: PINECONE_API_KEY が未設定です。", file=sys.stderr)
        return 1
    if not config["pinecone_index_name"]:
        print(
            "ERROR: PINECONE_INDEX_NAME が未設定です（環境変数または secrets.toml）。",
            file=sys.stderr,
        )
        return 1
    if not config["supabase_url"] or not config["supabase_bucket_name"]:
        print(
            "ERROR: supabase.url / supabase.bucket_name が未設定です。",
            file=sys.stderr,
        )
        return 1

    if not MASTER_DATA_PATH.exists():
        print(f"ERROR: {MASTER_DATA_PATH} が見つかりません。", file=sys.stderr)
        return 1
    if not BOOK_MASTER_PATH.exists():
        print(f"ERROR: {BOOK_MASTER_PATH} が見つかりません。", file=sys.stderr)
        return 1

    options_map = load_json(MASTER_DATA_PATH)
    book_master = load_json(BOOK_MASTER_PATH)

    os.environ["PINECONE_API_KEY"] = config["pinecone_api_key"]

    vectorstore = PineconeVectorStore(
        index_name=config["pinecone_index_name"],
        embedding=OpenAIEmbeddings(model="text-embedding-3-small"),
        namespace=config["pinecone_namespace"],
    )
    llm = ChatOpenAI(model_name="gpt-4o", temperature=0)

    if args.category and args.category not in options_map:
        print(
            f"ERROR: カテゴリー '{args.category}' は master_data.json に存在しません。",
            file=sys.stderr,
        )
        return 1

    if args.keyword and not args.category:
        print("ERROR: --keyword は --category と併用してください。", file=sys.stderr)
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    all_jobs = iter_jobs(options_map, args.category)
    if args.keyword:
        all_jobs = [(c, k) for c, k in all_jobs if k == args.keyword]
        if not all_jobs:
            print(
                f"ERROR: キーワード '{args.keyword}' が見つかりません。",
                file=sys.stderr,
            )
            return 1

    if args.retry_items:
        try:
            all_jobs = parse_retry_items(args.retry_items, iter_jobs(options_map))
        except ValueError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1
        # 再実行は指定分のみを上書きするため、全件モードで skip せずに実行する
        args.all = True
        args.skip_existing = False

    if not all_jobs:
        print("ERROR: 実行対象がありません。", file=sys.stderr)
        return 1

    run_all = args.all
    run_trial_only = args.trial

    if not run_all and not run_trial_only:
        # デフォルト: 1件試行 → 確認 → 全件
        try:
            trial_cat, trial_kw = find_trial_job(
                all_jobs, args.category, args.keyword
            )
        except ValueError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1

        print(f"【試行モード】1件だけ実行します: {trial_cat} / {trial_kw}")
        status, _, trial_failed = process_one(
            trial_cat,
            trial_kw,
            vectorstore,
            llm,
            book_master,
            config,
            skip_existing=False,
        )
        if status == "fail":
            print("試行で失敗しました。出力 JSON を確認してから再実行してください。")
            return 1

        trial_path = output_path(trial_cat, trial_kw)
        with trial_path.open("r", encoding="utf-8") as f:
            trial_result = json.load(f)
        print_result_preview(trial_result, trial_path)

        if args.yes:
            run_all = True
        elif not ask_continue():
            print(
                "\n中断しました。問題なければ次で残りを実行できます:\n"
                "  python ingest6.py --all --skip-existing"
            )
            return 0

        run_all = True
        args.skip_existing = True

    elif run_trial_only:
        try:
            trial_cat, trial_kw = find_trial_job(
                all_jobs, args.category, args.keyword
            )
        except ValueError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1

        print(f"【試行のみ】{trial_cat} / {trial_kw}")
        status, _, trial_failed = process_one(
            trial_cat,
            trial_kw,
            vectorstore,
            llm,
            book_master,
            config,
            skip_existing=args.skip_existing,
        )
        if status != "skip":
            trial_path = output_path(trial_cat, trial_kw)
            with trial_path.open("r", encoding="utf-8") as f:
                print_result_preview(json.load(f), trial_path)
        print(
            "\n全件実行する場合:\n"
            "  python ingest6.py --all --skip-existing"
        )
        return 1 if trial_failed else 0

    # 全件実行
    total = len(all_jobs)
    done = 0
    skipped = 0
    failed = 0

    print(f"【全件実行】対象: {total} 件")

    for i, (category, keyword) in enumerate(all_jobs, 1):
        print(f"({i}/{total})", end=" ")
        status, was_skipped, was_failed = process_one(
            category,
            keyword,
            vectorstore,
            llm,
            book_master,
            config,
            skip_existing=args.skip_existing,
        )
        done += 1
        if was_skipped:
            skipped += 1
        if was_failed:
            failed += 1
        if args.delay > 0 and status == "ok":
            time.sleep(args.delay)

    print(f"\n完了: 処理 {done} 件 / スキップ {skipped} 件 / 失敗 {failed} 件")
    print(f"出力先: {OUTPUT_DIR}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
