#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查 Ren'Py 翻译文件中重复的 old 字符串定义。

Ren'Py 不允许同一个 old 字符串在多个翻译文件中定义（即使翻译内容相同）。
此脚本扫描 tl/<lang>/ 目录下的所有 翻译 .rpy 文件，检测重复条目并报告。

用法:
  python tools/check_duplicate_translations.py <游戏目录>
  python tools/check_duplicate_translations.py <游戏目录> -l schinese

示例:
  python check_duplicate_translations.py MyGame-1.0-pc
  python check_duplicate_translations.py /path/to/MyGame-1.0-pc -l schinese
"""

import argparse
import os
import re
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# old 行解析统一走 shared/rpy_syntax.py（正确处理转义），不再用 old "(.*)" 弱正则
_TOOLS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SHARED_DIR = os.path.join(_TOOLS_DIR, "shared")
if _SHARED_DIR not in sys.path:
    sys.path.insert(0, _SHARED_DIR)

from rpy_syntax import parse_old_line  # noqa: E402
# 契约层在 shared/（跨组共享，故按相对路径加入 sys.path）
_SHARED_CONTRACT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "../shared")
if _SHARED_CONTRACT_DIR not in sys.path:
    sys.path.insert(0, _SHARED_CONTRACT_DIR)

from base_checker import PROJECT, BaseChecker  # noqa: E402


class DuplicateTranslationsChecker(BaseChecker):
    """重复 old 检测。"""

    name = "duplicate"
    summary = "检测翻译文件中重复的 old 字符串"
    takes = PROJECT
    requires_tl = True


#: 门面发现用的实例（契约见 shared/base_checker.py）
CHECKER = DuplicateTranslationsChecker()



def red(s):
    return f"\033[91m{s}\033[0m" if sys.stdout.isatty() else s


def yellow(s):
    return f"\033[93m{s}\033[0m" if sys.stdout.isatty() else s


def green(s):
    return f"\033[92m{s}\033[0m" if sys.stdout.isatty() else s


def scan_tl_files(project, lang):
    """扫描 tl/<lang>/ 目录下的所有 翻译 .rpy 文件"""
    game = os.path.join(project, "game") if os.path.isdir(os.path.join(project, "game")) else project
    tl_dir = os.path.join(game, "tl", lang)

    if not os.path.isdir(tl_dir):
        print(f"翻译目录不存在: {tl_dir}")
        return []

    files = []
    for root, dirs, fnames in os.walk(tl_dir):
        # 跳过备份目录
        dirs[:] = [d for d in dirs if not d.startswith(".") and not d.startswith("_")]
        for f in fnames:
            if f.endswith(".rpy"):
                files.append(os.path.join(root, f))

    return sorted(files)


def load_old_strings(filepath):
    """从翻译文件中提取所有 old 字符串及其位置（shared 解析器，解码后为运行时文本）"""
    entries = []
    comment_pat = re.compile(r'^\s*#\s*(game/[^:]+):(\d+)')

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            current_source = None
            for line_no, line in enumerate(f, 1):
                # 检测注释行获取源文件位置
                m = comment_pat.match(line)
                if m:
                    current_source = (m.group(1), int(m.group(2)))
                    continue
                # 检测 old 行
                lit = parse_old_line(line)
                if lit is not None:
                    old_str = lit.value
                    entries.append({
                        "old": old_str,
                        "line": line_no,
                        "source_file": current_source[0] if current_source else None,
                        "source_line": current_source[1] if current_source else None,
                        "tl_file": os.path.relpath(filepath, os.path.dirname(filepath))
                    })
    except Exception as e:
        print(f"  跳过 {filepath}: {e}", file=sys.stderr)

    return entries


def check_duplicates(entries_by_file):
    """检测重复的 old 字符串"""
    # 按 old 字符串聚合
    by_old = defaultdict(list)
    for filepath, entries in entries_by_file.items():
        for e in entries:
            by_old[e["old"]].append({**e, "tl_file_full": filepath})

    # 找出重复的
    duplicates = {}
    for old_str, locations in by_old.items():
        if len(locations) > 1:
            duplicates[old_str] = locations

    return duplicates


def main():
    ap = argparse.ArgumentParser(description="检测 Ren'Py 翻译文件中重复的 old 字符串")
    ap.add_argument("project", help="游戏目录（含 game/）")
    ap.add_argument("-l", "--language", default="schinese", help="语言代码")
    ap.add_argument("-o", "--output", help="输出报告文件")
    args = ap.parse_args()

    project = os.path.abspath(args.project)
    game_root = os.path.join(project, "game") if os.path.isdir(os.path.join(project, "game")) else project
    if not os.path.isdir(project):
        print(f"目录不存在: {project}")
        sys.exit(1)

    tl_files = scan_tl_files(project, args.language)
    print(f"扫描翻译文件: {len(tl_files)} 个\n")

    # 加载所有 old 字符串
    entries_by_file = {}
    for fpath in tl_files:
        entries = load_old_strings(fpath)
        if entries:
            entries_by_file[fpath] = entries
            print(f"  {os.path.basename(fpath)}: {len(entries)} 条 old 字符串")

    # 检测重复
    duplicates = check_duplicates(entries_by_file)

    if not duplicates:
        print(green("\n✓ 未检测到重复的 old 字符串"))
        return 0

    print(red(f"\n✗ 发现 {len(duplicates)} 个重复的 old 字符串:\n"))

    for old_str, locations in sorted(duplicates.items()):
        print(yellow(f'  old "{old_str}"'))
        for loc in locations:
            rel_tl = os.path.relpath(loc["tl_file_full"], game_root)
            source_info = ""
            if loc["source_file"]:
                source_info = f" (来自 {loc['source_file']}:{loc['source_line']})"
            print(f"    → {rel_tl}:{loc['line']}{source_info}")
        print()

    # 输出报告文件
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fo:
            fo.write(f"Ren'Py 翻译文件重复检测报告\n")
            fo.write(f"游戏: {project}\n语言: {args.language}\n\n")

            for old_str, locations in sorted(duplicates.items()):
                fo.write(f'old "{old_str}"\n')
                for loc in locations:
                    rel_tl = os.path.relpath(loc["tl_file_full"], game_root)
                    fo.write(f"  {rel_tl}:{loc['line']}\n")
                fo.write("\n")

        print(f"报告已保存: {args.output}")

    print("=" * 60)
    print(red(f"总计: {len(duplicates)} 个重复条目需要清理"))
    print("\n建议: 删除重复条目中较晚定义的（保留最早定义的），")
    print("或按源文件归属删除（如 screens.rpy 的条目应只在 screens_translated.rpy）。")


    return 1


if __name__ == "__main__":
    sys.exit(main() or 0)