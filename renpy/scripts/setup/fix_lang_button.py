#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ren'Py 语言按钮修复脚本
=======================
修复运行时 UI 中"语言按钮写死或缺目标语言项"的问题，
对应玩家侧常见症状：汉化已完成但游戏里看不到/切不到中文。

检测与修复三类问题:
  1. 写死按钮: 语言按钮 action 固定为 Language("english")，无法切到目标语言
  2. 缺目标项: 已有语言按钮列表(如 english/japanese)，但没有目标语言按钮
  3. 无语言入口: 整个项目找不到任何 Language() 按钮 (仅提示，不自动新建)

配套脚本边界:
  - 默认语言切换 / 首次启动生效 -> 用 switch_default_language.py
  - 字体注入与回退链            -> 用 add_fonts.py / sdk/setup_fonts.py
  本脚本只负责"语言按钮本身"的检测与修复。

使用方法:
  # 试运行: 只报告将做的修改，不落盘
  python fix_lang_button.py MyGame-1.0-pc

  # 实际修复: 在最后一个语言按钮后注入目标语言按钮
  python fix_lang_button.py MyGame-1.0-pc --apply
  python fix_lang_button.py MyGame-1.0-pc --apply -l japanese

参数:
  项目路径   包含 game/ 目录的项目根路径
  -l/--language  目标语言代码 (默认 schinese)
  --apply    实际写入文件；不加则只试运行
"""

import argparse
import os
import re
import sys

# ── 引入 shared/ 公共模块 ──
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shared")
)
from backup import atomic_write_text

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── 语言代码到显示名称的映射 (与 switch_default_language.py 保持一致) ──
LANGUAGE_NAMES = {
    "english": "English",
    "schinese": "简体中文",
    "tchinese": "繁體中文",
    "japanese": "日本語",
    "korean": "한국어",
    "russian": "Русский",
    "spanish": "Español",
    "french": "Français",
    "german": "Deutsch",
}

# 语言按钮 action 行: 支持 action Language("x") 与 action [ Language("x") ] 等
LANG_ACTION_RE = re.compile(
    r'action\s*(?:\[[^\]]*\])?\s*Language\(\s*["\']([^"\']+)["\']\s*\)'
)
# 一行式按钮: textbutton "English" action Language("english")
ONE_LINE_BTN_RE = re.compile(r"textbutton\b")
# 块头按钮: textbutton _("English"):  (action 单独成行)
BTN_HEAD_RE = re.compile(r"^\s*(?:textbutton|button|imagebutton)\b")


def get_language_display(lang_code):
    """获取语言的显示名称"""
    return LANGUAGE_NAMES.get(lang_code, lang_code)


def list_available_languages(project_path):
    """列出项目中所有可用的语言 (基于 tl/ 目录)"""
    tl_dir = os.path.join(project_path, "game", "tl")
    if not os.path.isdir(tl_dir):
        return []
    languages = []
    for entry in sorted(os.listdir(tl_dir)):
        full_path = os.path.join(tl_dir, entry)
        if os.path.isdir(full_path) and not entry.startswith("."):
            languages.append(entry)
    return languages


def find_rpy_files(project_path):
    """收集 game/ 下所有 .rpy(排除 tl/ 翻译目录)，返回绝对路径列表"""
    game_dir = os.path.join(project_path, "game")
    if not os.path.isdir(game_dir):
        return []
    result = []
    for root, dirs, files in os.walk(game_dir):
        # 跳过翻译目录: tl/ 内的 rpy 是译文，不含语言按钮
        dirs[:] = [d for d in dirs if d != "tl"]
        for fn in files:
            if fn.endswith(".rpy"):
                result.append(os.path.join(root, fn))
    return result


def scan_file(fpath):
    """扫描单个 .rpy 中的语言按钮 action 行

    Returns:
        list[dict]: {idx, indent, lang, one_line, leader_indent}
           idx   行号(从0开始)
           indent 该行缩进宽度
           lang   按钮绑定的语言代码
           one_line  是否一行式(textbutton ... action Language(...))
           leader_indent 两行式时按钮头(textbutton)的缩进，找不到时为 indent-4
    """
    with open(fpath, "r", encoding="utf-8", newline="") as f:
        content = f.read()
    lines = content.split("\n")

    hits = []
    for idx, line in enumerate(lines):
        if "Language(" not in line:
            continue
        if line.strip().startswith("#"):
            continue
        m = LANG_ACTION_RE.search(line)
        if not m:
            continue
        indent = len(line) - len(line.lstrip(" "))
        one_line = bool(ONE_LINE_BTN_RE.search(line))
        leader_indent = indent - 4 if indent >= 4 else 0
        if not one_line:
            # 向上找所属按钮头行，取其缩进作为按钮缩进
            for j in range(idx - 1, -1, -1):
                prev = lines[j]
                if prev.strip().startswith("#"):
                    continue
                if BTN_HEAD_RE.match(prev):
                    p_indent = len(prev) - len(prev.lstrip(" "))
                    if p_indent < indent:
                        leader_indent = p_indent
                    break
                if prev.strip() and not prev.startswith(" "):
                    break  # 已退出按钮块
        hits.append(
            {
                "idx": idx,
                "indent": indent,
                "lang": m.group(1),
                "one_line": one_line,
                "leader_indent": leader_indent,
            }
        )
    return content, lines, hits


def build_inject_lines(target_lang, hit):
    """构造注入的目标语言按钮行 (list[str]，含行尾换行已在 join 时处理)"""
    display = get_language_display(target_lang)
    if hit["one_line"]:
        ind = " " * hit["indent"]
        return [f'{ind}textbutton _("{display}") action Language("{target_lang}")']
    ind = " " * hit["indent"]
    lead = " " * hit["leader_indent"]
    return [
        f'{lead}textbutton _("{display}"):',
        f'{ind}action Language("{target_lang}")',
    ]


def fix_file(fpath, target_lang, apply_changes):
    """检测并(可选)修复单个文件；返回 (action描述, 是否改动)"""
    content, lines, hits = scan_file(fpath)
    if not hits:
        return None, False

    langs = {h["lang"] for h in hits}
    # 简化相对展示: 从项目根看（game 目录本身或其下的 tl/ 等子目录）
    game_dir = os.path.dirname(fpath)
    while (
        os.path.basename(game_dir) != "game"
        and os.path.dirname(game_dir) != game_dir
    ):
        game_dir = os.path.dirname(game_dir)
    rel = os.path.relpath(fpath, os.path.dirname(game_dir))

    if target_lang in langs:
        return f"[跳过] {rel}: 已存在语言按钮 Language({target_lang!r})", False

    # 找注入点: 最后一个语言按钮的 action 行
    last = hits[-1]
    inject_lines = build_inject_lines(target_lang, last)
    insert_after = last["idx"] + 1

    summary = (
        f"[修复] {rel}: 语言按钮 {sorted(langs)} 缺少 {target_lang!r}，"
        f"在第 {insert_after + 1} 行后注入 {len(inject_lines)} 行"
    )

    if not apply_changes:
        return summary, False

    # ── 幂等: 写入后再次扫描将命中 target_lang → 跳过 ──
    new_lines = lines[:insert_after] + inject_lines + lines[insert_after:]
    new_content = "\n".join(new_lines)
    # 保留原文件行尾风格
    newline = "\r\n" if "\r\n" in content else "\n"
    atomic_write_text(fpath, new_content, backup=True, newline=newline)
    return summary, True


def main():
    ap = argparse.ArgumentParser(
        description="修复 Ren'Py 语言按钮写死/缺目标语言项",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例:\n"
        "  python fix_lang_button.py MyGame-1.0-pc            # 试运行\n"
        "  python fix_lang_button.py MyGame-1.0-pc --apply    # 实际写入\n"
        "  python fix_lang_button.py MyGame-1.0-pc --apply -l japanese",
    )
    ap.add_argument("project", help="项目根路径 (包含 game/ 目录)")
    ap.add_argument(
        "-l", "--language", default="schinese", help="目标语言代码 (默认 schinese)"
    )
    ap.add_argument(
        "--apply",
        action="store_true",
        help="实际写入文件；不加则只试运行(默认)",
    )
    args = ap.parse_args()

    project = os.path.abspath(args.project)
    if not os.path.isdir(os.path.join(project, "game")):
        print(f"错误: 找不到 game 目录: {project}")
        sys.exit(1)

    target = args.language
    print("=" * 70)
    print("  Ren'Py 语言按钮修复")
    print("=" * 70)
    print(f"  项目路径: {project}")
    print(f"  目标语言: {target} ({get_language_display(target)})")
    print(f"  模式: {'实际写入' if args.apply else '试运行 (不加 --apply 不落盘)'}")
    print()

    # 语言可用性提示
    available = list_available_languages(project)
    if available:
        print(f"  可用语言 (tl/): {', '.join(available)}")
        if target != "english" and target not in available:
            print(
                f"  警告: {target} 不在 tl/ 目录，切换后译文可能缺失(回退原文)。"
                "仍可注入按钮。"
            )
    else:
        print("  提示: 未找到 tl/ 目录，无法验证语言可用性")
    print()

    rpy_files = find_rpy_files(project)
    if not rpy_files:
        print("错误: game/ 下没有 .rpy 文件")
        sys.exit(1)

    changed = 0
    no_entry = 0
    for fpath in sorted(rpy_files):
        result, did_change = fix_file(fpath, target, args.apply)
        if result is None:
            no_entry += 1
            continue
        print(result)
        if did_change:
            changed += 1

    if no_entry:
        print()
        print(f"  未发现语言按钮的文件: {no_entry} 个")
        print("  提示: 项目可能没有语言切换入口，请先运行 sdk/setup_i18n.py 生成。")

    print()
    if args.apply:
        print(f"完成: 修复 {changed} 个文件 (每次写入前已生成 .bak 备份)")
        print(f"回滚: 用对应 .bak 覆盖原文件即可")
    else:
        print(f"试运行结束: 将修复 {changed} 个文件。确认后加 --apply 实际写入。")
    print("=" * 70)


if __name__ == "__main__":
    main()
