"""col_right 検索結果の後処理（ingest6.py / main.py 共通）"""

from __future__ import annotations

import re

# LLM が「資料に情報なし」と返すときの典型フレーズ
NO_INFO_PHRASES = (
    "資料にはありません",
    "提供された資料にはありません",
    "提供された資料には、",
    "資料内にはありません",
    "資料に記載がありません",
    "資料には記載がありません",
    "該当する情報は資料にはありません",
    "該当する情報はありません",
    "記載がありません",
)


def is_material_not_found(content: str) -> bool:
    """
    資料に情報がない旨のみの回答かどうか。
    実質的な説明が含まれる場合は False（有効な回答として残す）。
    """
    if not content or not content.strip():
        return True

    text = content.strip()
    if not any(phrase in text for phrase in NO_INFO_PHRASES):
        return False

    remainder = text
    for phrase in NO_INFO_PHRASES:
        remainder = remainder.replace(phrase, "")
    remainder = re.sub(r"[。．、,.\s　「」『』\[\]（）()]", "", remainder)
    return len(remainder) < 15


def build_col_right_result(
    data_list: list[dict],
    get_image_entry,
) -> tuple[str, list[dict]]:
    """
    LLM の JSON 配列から clean_answer と answer_image_paths を組み立てる。

    get_image_entry(book, source) -> dict | None
      画像エントリ（path, book, source 等）を返す。不要なら None。
    """
    answer_lines: list[str] = []
    answer_image_paths: list[dict] = []

    for item in data_list:
        content = item.get("content", "")
        if is_material_not_found(content):
            continue

        fixed_line = content.replace("。", "。  \n")
        answer_lines.append(fixed_line)

        book = item.get("book")
        source = item.get("source")
        if not book or not source:
            continue

        entry = get_image_entry(book, source)
        if entry is None:
            continue
        path = entry.get("path")
        if path and not any(img.get("path") == path for img in answer_image_paths):
            answer_image_paths.append(entry)

    return "".join(answer_lines), answer_image_paths
