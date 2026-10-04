"""
patch_renpy_say.py — 用外部 CSV 匹配规则替换 Ren'Py game/ 下 renpy.say() 中的硬编码英文文本

匹配文件格式 (CSV, UTF-8):
    filename,old_text,new_text
    globals.rpy,"Hello","你好"
    script.rpy,"Old text","新文本"

CSV 匹配规则:
  - 仅在 .rpy/.rpym/.py 源码的单行内精确子串替换（不是正则）
  - filename 为 basename（不含路径，区分大小写）
  - old_text 双引号内的内容（不包括引号本身），支持 \" 转义
  - 如果不是字符串替换，整个 old_text 列视为精确匹配

用法:
    python patch_renpy_say.py <game目录>                     (预览, 默认) 
    python patch_renpy_say.py <game目录> --execute            (执行)
    python patch_renpy_say.py <game目录> --match-file my.csv  (指定匹配规则)
"""

import csv
import os
import sys

# ── 引入共享公共 ──
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "公共")
)
from backup import atomic_write_text

DEFAULT_MATCH_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "renpy_say_replacements.csv")


def load_replacements(csv_path: str | None) -> list[tuple[str, str, str]]:
    """从 CSV 加载替换规则：[(filename, old, new), ...]"""
    if csv_path is None:
        csv_path = DEFAULT_MATCH_FILE
    if not os.path.isfile(csv_path):
        print(f"[!] 匹配文件未找到: {csv_path}")
        print(f"    创建 CSV 文件即可启用，格式: filename,old_text,new_text")
        return []
    rules: list[tuple[str, str, str]] = []
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or row[0].startswith("#"):
                continue
            if len(row) >= 3:
                # old/new 列可能有意包含首尾空格，不能 strip；只规范化文件名。
                filename = row[0].strip()
                if filename and row[1]:
                    rules.append((filename, row[1], row[2]))
    print(f"[+] 加载了 {len(rules)} 条替换规则")
    return rules


def apply_replacements(content: str, basename: str, rules: list[tuple[str, str, str]]) -> tuple[str, int, int]:
    """逐行应用当前文件规则，返回 ``(新内容, 命中规则数, 错过规则数)``。

    旧实现对整个文件执行 ``str.replace``，短词可能误改标识符；这里把匹配
    范围限制到单行，且调用方只处理 Python/Ren'Py 源码扩展名。
    """
    file_rules = [(old, new) for fname, old, new in rules if fname == basename]
    if not file_rules:
        return content, 0, 0

    output = []
    matched = set()
    for line in content.splitlines(keepends=True):
        updated = line
        for index, (old, new) in enumerate(file_rules):
            if old in line:
                updated = updated.replace(old, new)
                matched.add(index)
        output.append(updated)

    for index, (old, _new) in enumerate(file_rules):
        if index not in matched:
            print(f"  [??] 未匹配: {old[:55]}...")

    new_content = "".join(output)
    return new_content, len(matched), len(file_rules) - len(matched)


def process_file(filepath: str, rules: list[tuple[str, str, str]], dry_run: bool = True) -> tuple[int, int]:
    """处理单个源码文件，返回 (命中规则数, 错过规则数)。"""
    if not filepath.lower().endswith((".rpy", ".rpym", ".py")):
        return 0, 0
    basename = os.path.basename(filepath)

    with open(filepath, "r", encoding="utf-8", newline="") as stream:
        content = stream.read()

    new_content, matched, missed = apply_replacements(content, basename, rules)

    if matched == 0:
        return 0, missed

    if not dry_run:
        newline = "\r\n" if "\r\n" in content else "\n"
        atomic_write_text(
            filepath,
            new_content,
            encoding="utf-8",
            backup=True,
            newline=newline,
        )

    return matched, missed


def main():
    import argparse

    ap = argparse.ArgumentParser(description="用外部规则替换 .rpy 中的硬编码英文文本")
    ap.add_argument("target", help="game 目录路径")
    ap.add_argument("-x", "--execute", action="store_true", help="执行替换（默认仅预览）")
    ap.add_argument("--match-file", default=None, help=f"CSV 匹配规则文件（默认: {DEFAULT_MATCH_FILE}）")
    args = ap.parse_args()

    target = args.target
    if not os.path.isdir(target):
        print(f"ERROR: 目录不存在: {target}")
        sys.exit(1)

    rules = load_replacements(args.match_file)
    if not rules:
        print("[!] 没有加载到替换规则，退出。")
        print(f"    请创建 CSV 文件: {args.match_file or DEFAULT_MATCH_FILE}")
        sys.exit(0)

    mode = "EXECUTE" if args.execute else "DRY RUN"
    print(f"[{mode}] Scanning: {target}\n")

    total_files = 0
    total_matched = 0

    for root, dirs, files in os.walk(target):
        dirs[:] = [name for name in dirs if not name.startswith((".", "_"))]
        for f in sorted(files):
            filepath = os.path.join(root, f)
            rel = os.path.relpath(filepath, target)
            matched, missed = process_file(filepath, rules, dry_run=not args.execute)
            if matched > 0:
                total_files += 1
                total_matched += matched
                status = "will modify" if not args.execute else "modified"
                print(f"  {rel}: {matched} changes ({missed} missed) [{status}]\n")
            elif missed > 0:
                print(f"  {rel}: 0 changes ({missed} missed) [no match]\n")

    print(f"Total: {total_matched} changes in {total_files} files.", end="")
    if not args.execute and total_matched > 0:
        print("  Add --execute to apply.")
    elif total_matched == 0:
        print("  Nothing to do.")
    else:
        print()


if __name__ == "__main__":
    main()
