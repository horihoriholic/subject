"""
LangChain_study/課題/output 配下の全 JSON を Supabase に投入する。

登録対象カラム:
  - category
  - keyword
  - clean_answer
  - answer_image_paths（jsonb）

注意:
  - output の各 JSON は question も含みますが、本スクリプトでは格納しません。
  - 重複投入防止のため、(category, keyword) で upsert します。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Iterable

from supabase import create_client


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
SECRETS_PATH = BASE_DIR / ".streamlit" / "secrets.toml"


def _load_toml_secrets() -> dict[str, Any]:
    if not SECRETS_PATH.exists():
        return {}
    try:
        import tomllib  # type: ignore[import-not-found]
    except ImportError:  # pragma: no cover
        import tomli as tomllib  # type: ignore[no-redef]

    with SECRETS_PATH.open("rb") as f:
        return tomllib.load(f)


def _load_supabase_credentials() -> tuple[str, str]:
    secrets = _load_toml_secrets()
    supabase_secrets = secrets.get("supabase", {}) if isinstance(secrets, dict) else {}

    url = (os.getenv("SUPABASE_URL") or supabase_secrets.get("url") or "").strip()
    key = (os.getenv("SUPABASE_KEY") or supabase_secrets.get("key") or "").strip()

    if not url or not key:
        raise RuntimeError(
            "Supabase 認証情報が不足しています。"
            " 次のいずれかで設定してください: "
            "`SUPABASE_URL`, `SUPABASE_KEY` または `.streamlit/secrets.toml` の [supabase]."
        )
    return url.rstrip("/"), key


def _iter_output_json_files(output_dir: Path) -> Iterable[Path]:
    if not output_dir.exists():
        raise RuntimeError(f"output ディレクトリが見つかりません: {output_dir}")
    # 拡張子が .json のみ対象（念のため）
    yield from sorted(output_dir.rglob("*.json"))


def _to_record(item: dict[str, Any], *, file_path: Path) -> dict[str, Any] | None:
    category = item.get("category")
    keyword = item.get("keyword")
    clean_answer = item.get("clean_answer")
    answer_image_paths = item.get("answer_image_paths", [])

    if not category or not keyword:
        print(f"[SKIP] category/keyword がありません: {file_path}")
        return None

    if clean_answer is None:
        clean_answer = ""

    # answer_image_paths は jsonb に格納するため list/dict を許容するが、
    # 期待形でない場合は空配列にフォールバックする。
    if not isinstance(answer_image_paths, list):
        answer_image_paths = []

    return {
        "category": str(category),
        "keyword": str(keyword),
        "clean_answer": str(clean_answer),
        "answer_image_paths": answer_image_paths,
    }


def _upsert_batch(
    *,
    supabase,
    table_name: str,
    records: list[dict[str, Any]],
    batch_no: int,
) -> None:
    if not records:
        return

    # Supabase 側で UNIQUE(category, keyword) が定義されている前提
    # on_conflict は "col1,col2" 形式で指定できる。
    supabase.table(table_name).upsert(
        records,
        on_conflict="category,keyword",
    ).execute()

    print(f"[UPSERT] batch={batch_no} records={len(records)}")


def main() -> None:
    # Windows で文字化けする場合があるため、可能なら UTF-8 に寄せる
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass

    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=str, default=str(OUTPUT_DIR))
    parser.add_argument("--table-name", type=str, default="col_right_answers")
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--max-files", type=int, default=-1)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--sleep-sec", type=float, default=0.0)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    table_name = args.table_name
    batch_size = max(1, args.batch_size)

    url, key = _load_supabase_credentials()
    supabase = create_client(url, key)

    json_files = list(_iter_output_json_files(output_dir))
    if args.max_files >= 0:
        json_files = json_files[: args.max_files]

    print(f"[INFO] table={table_name}")
    print(f"[INFO] output_json_files={len(json_files)}")
    print(f"[INFO] batch_size={batch_size}")

    batch: list[dict[str, Any]] = []
    batch_no = 0
    total = 0
    skipped = 0

    for i, path in enumerate(json_files, start=1):
        try:
            with path.open("r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception as e:
            print(f"[SKIP] JSON 読み込み失敗: {path} ({e})")
            skipped += 1
            continue

        if not isinstance(raw, dict):
            print(f"[SKIP] JSON が dict ではありません: {path}")
            skipped += 1
            continue

        record = _to_record(raw, file_path=path)
        if record is None:
            skipped += 1
            continue

        batch.append(record)
        total += 1

        if len(batch) >= batch_size:
            batch_no += 1
            if not args.dry_run:
                _upsert_batch(
                    supabase=supabase,
                    table_name=table_name,
                    records=batch,
                    batch_no=batch_no,
                )
                if args.sleep_sec > 0:
                    time.sleep(args.sleep_sec)
            batch = []

        if i % 50 == 0:
            print(f"[PROGRESS] i={i} inserted_candidate={total} skipped={skipped}")

    # 残り
    if batch:
        batch_no += 1
        if not args.dry_run:
            _upsert_batch(
                supabase=supabase,
                table_name=table_name,
                records=batch,
                batch_no=batch_no,
            )

    print("[DONE]")
    print(f"  upsert_candidates={total}")
    print(f"  skipped={skipped}")


if __name__ == "__main__":
    main()

