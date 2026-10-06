#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检测 Ren'Py screen 语言中 UI 显示文本的翻译状况。

覆盖: textbutton / text / label / button / show text / text f-string

【⚠ 源码验证关键发现 — Ren'Py 8.5.3】
Ren'Py 的 translation/scanstrings.py 会自动捕获 screen 中的纯字面字符串
（无拼接、无插值的静态文本如 textbutton "Cancel":），这些不需要手动 _() 包裹。
因此本工具区分三级严重度：

  BUG    → 确定无法被翻译系统捕获（拼接文本缺 _()、f-string）
  WARN   → 拼接/插值文本（需要 _()）
  INFO   → 纯字面量（Ren'Py 会自动处理，仅交叉引用翻译状态）

用法:
  python check_ui_text.py <项目目录> [-l schinese] [-o report.txt]
"""
import argparse
import os
import re
import sys

from common import (
    green, red, yellow, TRANS_FUNC_PAT, should_skip, scan_files,
    load_trans, print_items, TEXT_KW,
    decode_quoted_literal,
)
# 契约层在 shared/（跨组共享，故按相对路径加入 sys.path）
_SHARED_CONTRACT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "../shared")
if _SHARED_CONTRACT_DIR not in sys.path:
    sys.path.insert(0, _SHARED_CONTRACT_DIR)

from base_checker import PROJECT, BaseChecker  # noqa: E402


class UiTextChecker(BaseChecker):
    """UI 文本漏 _() 检测。"""

    name = "ui"
    summary = "检测 screen UI 文本 (textbutton/label/show text) 缺少 _()"
    takes = PROJECT
    requires_tl = False


#: 门面发现用的实例（契约见 shared/base_checker.py）
CHECKER = UiTextChecker()



# ── text_属性名（不检测）──
TEXT_PROP_RE = re.compile(
    r"\btext_(font|size|color|align|xalign|yalign|outlines|"
    r"idle_color|hover_color|selected_color|insensitive_color|"
    r"idle|hover|selected|insensitive|bold|italic|underline|strikethrough|"
    r"kerning|line_spacing|line_leading|justify|"
    r"hover_bold|selected_bold|hover_italic|selected_italic)\b"
)


def is_pure_literal(text: str) -> bool:
    """判断字符串是否为纯字面量（无拼接、无插值、非 f-string）。

    纯字面量如 text "Cancel" 会被 renpy/translation/scanstrings.py 自动捕获，
    不需要 _() 包裹。拼接/插值文本则必须手动 _()。
    """
    # 检查 f-string 前缀（f" 或 f'）
    if text.startswith("f\"") or text.startswith("f'"):
        return False

    # 检查字符串拼接：去掉转义引号后检查是否还有 +" 或 +'
    unescaped = text.replace('\\"', 'XX').replace("\\'", 'XX')
    for delim in ['+"', "+'", '+"', "+'"]:
        if delim in unescaped:
            return False

    # 检查 Ren'Py 插值 [var]
    if "[" in text:
        return False

    return True


def check_ui(lines, rel):
    """扫描 screen 中的文本显示语句。"""
    results_bug = []    # 拼接/插值 但缺 _()
    results_info = []   # 纯字面量（仅交叉引用）
    in_say = False
    kw_pat = "|".join(TEXT_KW)
    pat = re.compile(
        r"\b(" + kw_pat + r")\s+(?!" + TRANS_FUNC_PAT + r")(\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*')"
    )
    for no, line in enumerate(lines, 1):
        s = line.strip()
        if s.startswith("#"):
            continue
        if s.startswith("screen say("):
            in_say = True
        elif in_say and re.match(r"^screen\s", s):
            in_say = False
        if in_say or s.startswith("style ") or (TEXT_PROP_RE.search(s) and re.match(r"\s*text_", s)):
            continue
        for m in pat.finditer(s):
            raw = m.group(2)
            text = decode_quoted_literal(raw)
            if not should_skip(text):
                entry = {"line": no, "text": text, "file": rel}
                if is_pure_literal(raw):
                    # 纯字面量→Ren'Py 自动处理，INFO 级别
                    results_info.append(entry)
                else:
                    # 拼接/插值→确定需要 _()，BUG 级别
                    results_bug.append(entry)
    return results_bug, results_info


def check_showtext(lines, rel):
    """扫描 show text 语句（没有 _() 一定不翻译）。"""
    results = []
    pat = re.compile(
        r"show\s+text\s+(?!" + TRANS_FUNC_PAT + r')("((?:[^"\\]|\\.)*)"|\'((?:[^\'\\]|\\.)*)\')'
    )
    for no, line in enumerate(lines, 1):
        if line.strip().startswith("#"):
            continue
        m = pat.search(line)
        if m:
            text = decode_quoted_literal(m.group(1))
            if not should_skip(text):
                results.append({"line": no, "text": text, "file": rel})
    return results


def check_fstring_text(lines, rel):
    """检测 f-string — 确定不翻译，BUG 级别。"""
    results = []
    pat = re.compile(r'\btext\s+f("((?:[^"\\]|\\.)*)"|\'((?:[^\'\\]|\\.)*)\')')
    for no, line in enumerate(lines, 1):
        s = line.strip()
        if s.startswith("#") or s.startswith("style "):
            continue
        for m in pat.finditer(s):
            raw = m.group(1)
            results.append({
                "line": no, "text": "f" + raw, "file": rel, "note": "f-string"
            })
    return results


def main():
    ap = argparse.ArgumentParser(
        description="检测 Ren'Py UI 显示文本翻译状况（区分纯字面/拼接）"
    )
    ap.add_argument("project", help="游戏目录（含 game/）")
    ap.add_argument("-l", "--language", default="schinese")
    ap.add_argument("-o", "--output", help="输出报告文件")
    args = ap.parse_args()

    project = os.path.abspath(args.project)
    if not os.path.isdir(project):
        print(f"目录不存在: {project}")
        sys.exit(1)

    game = os.path.join(project, "game")
    tl_path = (
        os.path.join(game, "tl") if os.path.isdir(game)
        else os.path.join(project, "tl")
    )
    trans = load_trans(tl_path, args.language)
    print(f"翻译条目: {len(trans)}")

    files = scan_files(project)
    print(f"扫描文件: {len(files)} 个\n")

    ui_bug, ui_info = [], []
    st_results, fstr_results = [], []

    for fpath in files:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                lines = f.read().splitlines(keepends=False)
        except Exception as e:
            print(f"  跳过 {fpath}: {e}", file=sys.stderr)
            continue
        rel = os.path.relpath(fpath, os.path.dirname(game))
        b, i = check_ui(lines, rel)
        ui_bug.extend(b)
        ui_info.extend(i)
        st_results.extend(check_showtext(lines, rel))
        fstr_results.extend(check_fstring_text(lines, rel))

    # ── 输出 ──
    print("=" * 60)
    print(red("  [ BUG ] 拼接/插值文本缺 _() — 一定不翻译"))
    print("=" * 60)
    print_items(ui_bug, trans, "拼接/插值文本 (textbutton/text/label)", severity="bug")

    print("\n" + "=" * 60)
    print(yellow("  [ WARN ] show text — 缺少 _() 包裹"))
    print("=" * 60)
    print_items(st_results, trans, "show text", severity="warn")

    print("\n" + "=" * 60)
    print(red("  [ BUG ] f-string 文本 — 一定不翻译"))
    print("=" * 60)
    print_items(fstr_results, trans, "text f-string", severity="bug")

    print("\n" + "=" * 60)
    print("  [ INFO ] 纯字面量 — Ren'Py 自动处理，仅交叉引用")
    print("=" * 60)
    print_items(ui_info, trans, "纯字面文本 (自动处理)", severity="info")

    total_bug = len(ui_bug) + len(fstr_results)
    total_warn = len(st_results)
    total_info = len(ui_info)
    total = total_bug + total_warn + total_info

    uncovered = sum(
        1 for i in ui_bug + fstr_results + st_results + ui_info
        if i["text"] not in trans
    )
    print(f"\n{'=' * 60}")
    print(
        f"总计: {total} 条"
        f"  |  {red(f'BUG {total_bug}')}"
        f"  |  {yellow(f'WARN {total_warn}')}"
        f"  |  INFO {total_info}"
    )
    print(f"未翻译: {red(str(uncovered))} 条")
    return 1 if total_bug or uncovered else 0


if __name__ == "__main__":
    sys.exit(main() or 0)
