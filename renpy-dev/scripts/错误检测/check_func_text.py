#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检测 Ren'Py 中函数调用文本缺少 _() 包裹。
覆盖: renpy.input / renpy.notify / 自定义屏幕调用(heading/settings_item 等)

用法:
  python check_func_text.py <项目目录> [-l schinese] [-o report.txt]
"""
import argparse
import os
import re
import sys

from common import (
    green, red, yellow, TRANS_FUNC_PAT, should_skip, scan_files,
    load_trans, print_items, RENPY_FUNC_KW, SCREEN_CALL_KW,
)


def check_renpy_func(lines, rel):
    results = []
    kw_pat = "|".join(re.escape(k) for k in RENPY_FUNC_KW)
    pat = re.compile(r"\b(" + kw_pat + r")\s*\(\s*(?!" + TRANS_FUNC_PAT + r")(\"[^\"]+\"|'[^']+')")
    for no, line in enumerate(lines, 1):
        if line.strip().startswith("#"):
            continue
        for m in pat.finditer(line):
            text = m.group(2)[1:-1]
            if not should_skip(text):
                results.append({"line": no, "text": text, "file": rel, "func": m.group(1)})
    return results


def check_screen_calls(lines, rel):
    results = []
    kw_pat = "|".join(re.escape(k) for k in SCREEN_CALL_KW)
    pat = re.compile(r"(?:use\s+)?\b(" + kw_pat + r")\s*\(\s*(?!" + TRANS_FUNC_PAT + r")(\"[^\"]+\"|'[^']+')")
    for no, line in enumerate(lines, 1):
        if line.strip().startswith("#"):
            continue
        for m in pat.finditer(line):
            text = m.group(2)[1:-1]
            if not should_skip(text):
                results.append({"line": no, "text": text, "file": rel, "screen": m.group(1)})
    return results


def main():
    ap = argparse.ArgumentParser(description="检测 Ren'Py 函数调用文本缺少 _()")
    ap.add_argument("project", help="游戏目录（含 game/）")
    ap.add_argument("-l", "--language", default="schinese")
    ap.add_argument("-o", "--output", help="输出报告文件")
    args = ap.parse_args()

    project = os.path.abspath(args.project)
    if not os.path.isdir(project):
        print(f"目录不存在: {project}")
        sys.exit(1)

    game = os.path.join(project, "game")
    tl_path = os.path.join(game, "tl") if os.path.isdir(game) else os.path.join(project, "tl")
    trans = load_trans(tl_path, args.language)
    print(f"翻译条目: {len(trans)}")

    files = scan_files(project)
    print(f"扫描文件: {len(files)} 个\n")

    func_results, screen_results = [], []
    for fpath in files:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                lines = f.read().splitlines(keepends=False)
        except Exception as e:
            print(f"  跳过 {fpath}: {e}", file=sys.stderr)
            continue
        rel = os.path.relpath(fpath, os.path.dirname(game))
        func_results.extend(check_renpy_func(lines, rel))
        screen_results.extend(check_screen_calls(lines, rel))

    print("=" * 60)
    print(yellow("  [ WARN ] 函数调用文本缺少 _()"))
    print("=" * 60)
    print_items(func_results, trans, "renpy.input / renpy.notify", severity="warn")
    print_items(screen_results, trans, "自定义屏幕调用 (heading/settings_item 等)", severity="warn")

    total = len(func_results) + len(screen_results)
    uncovered = sum(1 for i in func_results + screen_results if i["text"] not in trans)
    print(f"\n总计: {total} 条, 未翻译: {red(str(uncovered))} 条")
    return 1 if uncovered else 0


if __name__ == "__main__":
    sys.exit(main() or 0)
