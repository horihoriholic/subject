"""output/精油/ 以下の JSON から clean_answer の成分名を抽出し output_compound.csv に出力する。"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_CSV = BASE_DIR / "output_compound.csv"

EXCLUDE_EXACT = {
    "精油",
    "香り",
    "主に",
    "次いで",
    "その他",
    "成分",
    "含有量",
    "データ",
    "全体",
    "占め",
    "香料",
    "安息香酸",
    "酢酸",
    "多様な微量成分",
    "様々な成分",
    "モノテルペン炭化水素",
    "モノテルペンエステル",
    "モノテルペンエステル類",
    "モノテルペンアルコール類",
    "セスキテルペン",
    "セスキテルペンアルコール類",
    "ジテルペン",
    "芳香族",
    "脂肪族エステル類",
    "高級脂肪酸",
    "多様な安息香酸誘導体",
    "C₁₀～C₁₅系テルペン炭化水素",
    "から",
    "されています",
    "アルデヒド類",
    "オレンジ",
    "セスキテルペン含酸素",
    "ハーバルなトーン",
    "3-ジエン",
}

EXCLUDE_CONTAINS = (
    "作用",
    "効果",
    "香り",
    "香調",
    "精油",
    "抽出",
    "蒸留",
    "ノート",
    "示唆",
    "可能",
    "占有",
    "含有率",
    "作業",
    "免疫",
    "消化",
    "血流",
    "鎮静",
    "抗",
    "殺菌",
    "肝臓",
    "テルペン炭化水素",
    "エステル類",
    "アルコール類",
    "値は",
    "OCi",
    "です",
    "であり",
    "成分",
    "主な",
    "主成分",
    "微量成分",
    "特有",
    "効能",
    "精神",
    "身体",
    "示され",
    "回復",
    "再生",
    "衛生",
    "同様",
    "研究",
    "神経",
    "粘膜",
    "占め",
    "含まれ",
    "さを感じ",
    "軽減",
    "トーン",
    "量を増",
    "が加わり",
    "にはα-",
    "サンバック",
    "役立つ",
    "水蒸気",
    "必要",
    "時間がかか",
)

PREFIXES = (
    r"主な?成分(?:には|としては|は)?",
    r"主成分は?",
    r"その他の成分として",
    r"少量成分として",
    r"成分組成としては",
    r"構成成分には",
    r"成分としては",
    r"成分には",
    r"主要成分は",
    r"主に",
    r"次いで",
    r"他に",
    r"他にも",
    r"他の成分には",
    r"特に",
    r"成分一覧には",
    r"成分の含有率は",
    r"香成分には",
    r"特徴的な芳香成分には",
    r"特有の少量成分として",
    r"して",
    r"も",
    r"[^、,]*には",
)

SUFFIXES = (
    r"などが含まれ(?:ています|ます|る)?.*$",
    r"が含まれ(?:ています|ます|る).*$",
    r"は含まれています.*$",
    r"があり.*$",
    r"と最も多く含まれ.*$",
    r"が最も多く含まれています.*$",
    r"が主要成分であり.*$",
    r"が挙げられます.*$",
    r"があります.*$",
    r"などです.*$",
    r"なども含まれます.*$",
    r"などがあります.*$",
    r"などのモノテルペン.*$",
    r"が特徴です.*$",
    r"を占めています.*$",
    r"でを占め(?:ます|ています)?.*$",
    r"を占め(?:ます|ています)?.*$",
    r"を含むことが特徴です.*$",
    r"のOCi値.*$",
    r"を含みます.*$",
    r"が加わり.*$",
)


def normalize_dashes(text: str) -> str:
    return re.sub(r"[−－―‐‑]", "-", text)


def clean_fragment(fragment: str) -> str:
    text = normalize_dashes(fragment.strip())
    for prefix in PREFIXES:
        text = re.sub("^" + prefix, "", text)
    for suffix in SUFFIXES:
        text = re.sub(suffix, "", text)
    text = re.sub(r"など$", "", text)
    return text.strip(" 、,のにはがでをとやおよび及び")


def is_valid_compound(name: str) -> bool:
    if not name or len(name) < 2:
        return False
    if name in EXCLUDE_EXACT:
        return False
    if re.fullmatch(r"[\d\.%～\-〜\(\)（）\s,、]+", name):
        return False
    if any(token in name for token in EXCLUDE_CONTAINS):
        return False
    if re.match(r"^\([\d\.]+$", name):
        return False
    return True


def add_compound(compounds: set[str], raw: str) -> None:
    raw = clean_fragment(raw)
    if not raw:
        return
    for part in re.split(r"[とや]", raw):
        name = clean_fragment(part)
        if is_valid_compound(name):
            compounds.add(name)


def extract_compounds(text: str) -> set[str]:
    compounds: set[str] = set()
    text = normalize_dashes(text)

    for match in re.finditer(
        r"([^(（、。\n]+?)[（(](\d+(?:\.\d+)?(?:[～〜-]\d+(?:\.\d+)?)?%)[）)]",
        text,
    ):
        add_compound(compounds, match.group(1))

    for match in re.finditer(
        r"([ぁ-んァ-ンー一-龥a-zA-Z0-9α-ωΑ-Ω\(\)\-\.]+?)"
        r"(?:が|は|で)(\d+(?:\.\d+)?(?:[～〜-]\d+(?:\.\d+)?)?)%",
        text,
    ):
        add_compound(compounds, match.group(1))

    for match in re.finditer(
        r"([ぁ-んァ-ンー一-龥a-zA-Z0-9α-ωΑ-Ω\(\)\-\.]{2,}?)(\d+(?:\.\d+)?)%",
        text,
    ):
        add_compound(compounds, match.group(1))

    list_trigger = (
        r"(?:主な?成分(?:には|としては|は)?|主成分は?|その他の成分として|少量成分として|"
        r"成分組成としては|構成成分には|成分としては|成分には|特徴的な芳香成分には|香成分には)"
        r"([^。\n]+)"
    )
    for match in re.finditer(list_trigger, text):
        segment = match.group(1)
        segment = re.sub(r"[（(][^）)]*%[）)]", "", segment)
        segment = re.sub(r"\d+(?:\.\d+)?(?:[～〜-]\d+(?:\.\d+)?)?%", "", segment)
        for part in re.split(r"[、,]", segment):
            add_compound(compounds, part)

    for match in re.finditer(
        r"(?:その他の成分として|少量成分として|構成成分には|エキストラには|サードには|"
        r"主な成分には|主な成分として|成分には)([^。\n]+?)(?:など)?が含まれ",
        text,
    ):
        segment = match.group(1)
        segment = re.sub(r"[（(][^）)]*%[）)]", "", segment)
        segment = re.sub(r"\d+(?:\.\d+)?(?:[～〜-]\d+(?:\.\d+)?)?%", "", segment)
        for part in re.split(r"[、,]", segment):
            add_compound(compounds, part)

    return compounds


def find_essential_oil_dir() -> Path:
    for directory in OUTPUT_DIR.iterdir():
        if not directory.is_dir():
            continue
        json_files = list(directory.glob("*.json"))
        if not json_files:
            continue
        data = json.loads(json_files[0].read_text(encoding="utf-8"))
        if data.get("category") == "精油":
            return directory
    raise RuntimeError("output/精油 ディレクトリが見つかりません。")


def main() -> None:
    oil_dir = find_essential_oil_dir()
    all_compounds: set[str] = set()

    for json_path in sorted(oil_dir.glob("*.json")):
        data = json.loads(json_path.read_text(encoding="utf-8"))
        all_compounds |= extract_compounds(data.get("clean_answer", ""))

    sorted_compounds = sorted(all_compounds)
    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["成分名"])
        for name in sorted_compounds:
            writer.writerow([name])

    print(f"JSON files: {len(list(oil_dir.glob('*.json')))}")
    print(f"Unique compounds: {len(sorted_compounds)}")
    print(f"Output: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
