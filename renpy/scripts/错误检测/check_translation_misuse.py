#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检测 Ren'Py 中翻译函数误用和翻译标志缺失。
检测项:
  - Character("[var]") 缺 !t 翻译标志 → 真正 bug
  - define/default 中 _() 无效（init 阶段 _() 返回原值）
  - _() 内 [变量] 插值缺 !t → 变量值可能需翻译

用法:
  python check_translation_misuse.py <项目目录> [-l schinese] [-o report.txt]
"""
import argparse
import os
import re
import sys

from common import green, red, yellow, should_skip, scan_files, print_items


# ── 数值变量（不需要 !t）──
NUMERIC_VAR_RE = re.compile(r"^\d+$")


def check_char_var_no_t(lines, rel):
    results = []
    for no, line in enumerate(lines, 1):
        if line.strip().startswith("#"):
            continue
        for m in re.finditer(r"Character\((?:_{1,3}\s*\()?\"\[([^\]!]+)\]\"", line):
            var_name = m.group(1)
            if f"[{var_name}!t]" not in line:
                results.append({
                    "line": no, "text": f"[{var_name}]", "file": rel,
                    "note": f"缺 !t — 改为 [{var_name}!t]",
                })
        for m in re.finditer(r"Character\((?:_{1,3}\s*\()?\'\[([^\]!]+)\]\'", line):
            var_name = m.group(1)
            if f"[{var_name}!t]" not in line:
                results.append({
                    "line": no, "text": f"[{var_name}]", "file": rel,
                    "note": f"缺 !t — 改为 [{var_name}!t]",
                })
    return results


def check_define_default_misuse(lines, rel):
    results = []
    pat = re.compile(r'^(?:define|default)\s+\w+\s*=\s*_\(("([^"]+)"|\'([^\']+)\')\)')
    for no, line in enumerate(lines, 1):
        if line.strip().startswith("#"):
            continue
        m = pat.match(line)
        if m:
            text = m.group(2) or m.group(3)
            results.append({
                "line": no, "text": text, "file": rel,
                "note": "_() 在 init 时返回原值，改用 __() 或 [var!t]",
            })
    return results


def check_interpolation_no_t(lines, rel):
    results = []
    trans_func_str = re.compile(r'_{1,3}\s*\(\s*("([^"]+)"|\'([^\']+)\')\s*\)')
    interp_no_t = re.compile(r"\[([^\]!]+)\]")
    for no, line in enumerate(lines, 1):
        if line.strip().startswith("#"):
            continue
        for tm in trans_func_str.finditer(line):
            content = tm.group(2) or tm.group(3)
            if not content:
                continue
            for im in interp_no_t.finditer(content):
                var_name = im.group(1).strip()
                if NUMERIC_VAR_RE.match(var_name) or "." in var_name:
                    continue
                if f"[{var_name}!t]" in content or f"[{var_name}!ti]" in content:
                    continue
                results.append({
                    "line": no, "text": f"[{var_name}]", "file": rel,
                    "note": f"在 _() 内 [{var_name}] 缺 !t — 若值需翻译请改为 [{var_name}!t]",
                    "context": content,
                })
    return results


def main():
    ap = argparse.ArgumentParser(description="检测翻译函数误用和标志缺失")
    ap.add_argument("project", help="游戏目录（含 game/）")
    ap.add_argument("-l", "--language", default="schinese")
    ap.add_argument("-o", "--output", help="输出报告文件")
    args = ap.parse_args()

    project = os.path.abspath(args.project)
    if not os.path.isdir(project):
        print(f"目录不存在: {project}")
        sys.exit(1)

    game = os.path.join(project, "game")
    files = scan_files(project)
    print(f"扫描文件: {len(files)} 个\n")

    var_no_t, misuse, interp_no_t = [], [], []
    for fpath in files:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                lines = f.read().splitlines(keepends=False)
        except Exception as e:
            print(f"  跳过 {fpath}: {e}", file=sys.stderr)
            continue
        rel = os.path.relpath(fpath, os.path.dirname(game))
        var_no_t.extend(check_char_var_no_t(lines, rel))
        misuse.extend(check_define_default_misuse(lines, rel))
        interp_no_t.extend(check_interpolation_no_t(lines, rel))

    print("=" * 60)
    print(red("  [ BUG ] 翻译函数误用 — 不会生效"))
    print("=" * 60)
    print_items(var_no_t, {}, "Character('[var]') 缺 !t", severity="bug")
    print_items(misuse, {}, "define/default 中 _() 无效", severity="bug")
    print_items(interp_no_t, {}, "_() 内 [变量] 缺 !t", severity="bug")

    total = len(var_no_t) + len(misuse) + len(interp_no_t)
    print(f"\n总计 BUG: {red(str(total))} 条")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main() or 0)
