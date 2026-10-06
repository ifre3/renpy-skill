# -*- coding: utf-8 -*-
"""抽取 tl 目录全部 say 条目为 JSON（润色管线的第一步）。

用法::

    python extract_say.py <tl目录> -o entries.json

输出条目结构见 _say_parse.py；可直接作为 screen_suspicious / merge_polish 的输入。
"""
import argparse
import io
import json
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).parent))
from _say_parse import iter_say_entries


def main():
    ap = argparse.ArgumentParser(description="抽取 tl 目录 say 条目")
    ap.add_argument("tl_dir")
    ap.add_argument("-o", "--out", default="entries.json")
    ap.add_argument("--skip-empty", action="store_true", help="跳过空译文")
    args = ap.parse_args()

    entries = []
    for e in iter_say_entries(args.tl_dir):
        if args.skip_empty and e["trans"] == "":
            continue
        entries.append(e)

    Path(args.out).write_text(
        json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"抽取 {len(entries)} 条 -> {args.out}")


if __name__ == "__main__":
    main()
