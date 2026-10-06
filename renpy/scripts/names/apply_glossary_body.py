# -*- coding: utf-8 -*-
"""按术语表统一正文人名：译文中的英文名 → 定标中文（原文同含该名才替换）。

名字说明（2026-10-07 由 unify_names.py 更名）：与 unify_name_translations.py
只差两个词、极易调错脚本，故改成自述动作的名字——把术语表直接应用到正文。
分工见本目录 README：快速批改走本脚本（无审核需求），逐条审核/中文变体/回滚走 v6。

用法::

    python apply_glossary_body.py <tl目录> --glossary glossary.json -o name_fix.json

glossary.json 格式::

    {"Jin": "金", "Hazel": "海泽尔", ...}

替换规则：长名优先（Bellatrix 先于 Bella）；仅当原文与译文都含该英文名；
替换后自动收紧中文名与相邻中文之间的空格。
输出为 apply 格式（autotranslate.py apply --input ... --overwrite）。
"""
import argparse
import io
import json
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).parent.parent / "polish"))
from _say_parse import iter_say_entries

CJK = r"[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef…—·”“‘’]"


def tighten(text, zh_names):
    """去掉插入的中文名与相邻中文之间的空格。"""
    for zh in zh_names:
        text = re.sub(rf"({CJK})\s+({zh})", r"\1\2", text)
        text = re.sub(rf"({zh})\s+({CJK})", r"\1\2", text)
    return text


def main():
    ap = argparse.ArgumentParser(description="按术语表统一正文人名")
    ap.add_argument("tl_dir")
    ap.add_argument("-g", "--glossary", required=True, help="JSON: 英文名 -> 中文")
    ap.add_argument("-o", "--out", default="name_fix.json")
    args = ap.parse_args()

    glossary = json.loads(Path(args.glossary).read_text(encoding="utf-8"))
    order = sorted(glossary, key=len, reverse=True)
    pat = {n: re.compile(r"(?<![A-Za-z])" + re.escape(n) + r"(?![A-Za-z])")
           for n in order}
    zh_names = set(glossary.values())

    entries, seen_same = [], 0
    for e in iter_say_entries(args.tl_dir):
        if e["trans"] == "":
            continue
        new_text = e["trans"]
        hit = False
        for n in order:
            if pat[n].search(e["orig"]) and pat[n].search(new_text):
                new_text = pat[n].sub(glossary[n], new_text)
                hit = True
        if hit:
            new_text = tighten(new_text, zh_names)
        if hit and new_text != e["trans"]:
            entry = {"file": e["file"], "line": e["line"], "type": e["type"],
                     "orig": e["orig"], "trans": new_text}
            if e.get("char"):
                entry["char"] = e["char"]
            entries.append(entry)
        elif hit:
            seen_same += 1

    Path(args.out).write_text(
        json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"生成统一条目 {len(entries)}（另 {seen_same} 条已符合）-> {args.out}")


if __name__ == "__main__":
    main()
