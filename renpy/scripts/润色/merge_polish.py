# -*- coding: utf-8 -*-
"""把 AI 润色稿（file:line -> 新译文）合并为 apply 格式批次 JSON。

用法::

    python merge_polish.py --pool entries.json --fixes fixes.json -o polish_batch.json

fixes.json 格式::

    {"HazelEvents.rpy:954": "润色后的译文", ...}

合并时从 pool 中取该行的锚点（file/line/type/orig/char），AI 只需要提供新译文，
不需要碰行号和原文——锚点错误由 merge 阶段直接报缺，不会污染回填。
"""
import argparse
import io
import json
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def main():
    ap = argparse.ArgumentParser(description="润色稿合并为 apply 批次")
    ap.add_argument("--pool", required=True, help="extract_say 输出的条目池 JSON")
    ap.add_argument("--fixes", required=True, help="file:line -> 新译文 的 JSON")
    ap.add_argument("-o", "--out", default="polish_batch.json")
    args = ap.parse_args()

    pool = {}
    for e in json.loads(Path(args.pool).read_text(encoding="utf-8")):
        pool[(e["file"], e["line"])] = e

    fixes = json.loads(Path(args.fixes).read_text(encoding="utf-8"))
    entries, missing = [], []
    for key, new_trans in fixes.items():
        fname, _, line = key.rpartition(":")
        anchor = pool.get((fname, int(line)))
        if anchor is None:
            missing.append(key)
            continue
        entry = {"file": fname, "line": int(line), "type": anchor["type"],
                 "orig": anchor["orig"], "trans": new_trans}
        if anchor.get("char"):
            entry["char"] = anchor["char"]
        entries.append(entry)

    Path(args.out).write_text(
        json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")
    if missing:
        print(f"[警告] {len(missing)} 条无锚点，未纳入批次:")
        for m in missing[:10]:
            print("  ", m)
    print(f"生成 {len(entries)} 条 -> {args.out}")


if __name__ == "__main__":
    main()
