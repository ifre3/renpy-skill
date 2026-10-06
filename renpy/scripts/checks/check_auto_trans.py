#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检测 Ren'Py 中由字符串翻译系统自动处理的文本（仅交叉引用翻译状态）。
覆盖: Character 名字框 / menu 选择项

用法:
  python check_auto_trans.py <项目目录> [-l schinese] [-o report.txt]
"""
import argparse
import os
import re
import sys

from common import (
    green, red, yellow, should_skip, scan_files, load_trans, print_items,
    decode_quoted_literal,
)
# 契约层在 shared/（跨组共享，故按相对路径加入 sys.path）
_SHARED_CONTRACT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "../shared")
if _SHARED_CONTRACT_DIR not in sys.path:
    sys.path.insert(0, _SHARED_CONTRACT_DIR)

from base_checker import PROJECT, BaseChecker  # noqa: E402


class AutoTransChecker(BaseChecker):
    """名字框/menu 交叉引用检测。"""

    name = "auto"
    summary = "交叉引用 Character 名字框和 menu 选项翻译覆盖"
    takes = PROJECT
    requires_tl = False


#: 门面发现用的实例（契约见 shared/base_checker.py）
CHECKER = AutoTransChecker()



def check_char(lines, rel):
    results = []
    for no, line in enumerate(lines, 1):
        for m in re.finditer(r'Character\(\s*("(?:[^"\\]|\\.)*")', line):
            n = decode_quoted_literal(m.group(1))
            if not n.startswith("["):
                results.append({"line": no, "text": n, "file": rel})
        for m in re.finditer(r'Character\(\s*.*?name\s*=\s*("(?:[^"\\]|\\.)*")', line):
            n = decode_quoted_literal(m.group(1))
            if not n.startswith("["):
                results.append({"line": no, "text": n, "file": rel})
        for m in re.finditer(r"Character\(\s*('(?:[^'\\]|\\.)*')", line):
            n = decode_quoted_literal(m.group(1))
            if not n.startswith("["):
                results.append({"line": no, "text": n, "file": rel})
    return results


def check_menu_choices(lines, rel):
    results = []
    in_menu = False
    for no, line in enumerate(lines, 1):
        s = line.strip()
        if s.startswith("#"):
            continue
        if re.match(r"menu\s*(\([^)]*\))?\s*:", s):
            in_menu = True
            continue
        if in_menu:
            if line and not line[0].isspace() and s:
                in_menu = False
                continue
            m = re.match(r'(?!_{1,3}\s*\()("((?:[^"\\]|\\.)*)"|\'((?:[^\'\\]|\\.)*)\')\s*(if\s+.+?)?\s*:', s)
            if m:
                text = decode_quoted_literal(m.group(1))
                if not should_skip(text):
                    results.append({"line": no, "text": text, "file": rel})
    return results


def main():
    ap = argparse.ArgumentParser(description="交叉引用 Ren'Py 自动翻译文本的覆盖状态")
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

    char_results, menu_results = [], []
    for fpath in files:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                lines = f.read().splitlines(keepends=False)
        except Exception as e:
            print(f"  跳过 {fpath}: {e}", file=sys.stderr)
            continue
        rel = os.path.relpath(fpath, os.path.dirname(game))
        char_results.extend(check_char(lines, rel))
        menu_results.extend(check_menu_choices(lines, rel))

    print("=" * 60)
    print("  [ INFO ] 字符串翻译系统自动处理，仅交叉引用")
    print("=" * 60)
    print_items(char_results, trans, "Character 名字框（无需 _()）", severity="info")
    print_items(menu_results, trans, "menu 选择项（Ren'Py 自动提取）", severity="info")

    total = len(char_results) + len(menu_results)
    uncovered = sum(1 for i in char_results + menu_results if i["text"] not in trans)
    print(f"\n总计: {total} 条, 未翻: {red(str(uncovered))} 条")
    return 1 if uncovered else 0


if __name__ == "__main__":
    sys.exit(main() or 0)
