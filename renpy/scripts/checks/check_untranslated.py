#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查 Ren'Py TL 翻译文件中的未翻译条目（精准版）

匹配规则:
1. translate_block:  # "原文" 下一行 "译文"，两者完全相同
2. character: # <任意角色> "原文" 后跟同名角色译文（c_x/e/mmc 等）
3. old_new: old "原文" 后跟 new "原文"，内容完全相同

过滤规则:
- 忽略纯省略号/空格/空白: ..., ....., ......, 空白
- 忽略纯数字: 1, 20, 100, 10C, -5
- 忽略纯符号/图标: arrow, star, degree
- 忽略纯 ASCII 变量/格式码: [c_***], {#weekday}, {size=...}
- 忽略纯 ASCII 格式码: {cps=...}, {w=...}, {nw}, {i}, {s}
- 忽略纯 Ren'Py 标签行: # game/...
- 忽略单字符纯 ASCII 串 (<=1 字符)
- 仅当文本包含: CJK/日文假名/连续2+字母的单词时，才视为需要翻译

用法:
    python check_untranslated.py <tl目录路径>
    python check_untranslated.py <tl目录路径> --csv report.csv
    python check_untranslated.py <tl目录路径> --csv report.csv --all
"""

import argparse
import csv
import os
import re
import sys

_SHARED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shared")
if _SHARED_DIR not in sys.path:
    sys.path.insert(0, _SHARED_DIR)

from rpy_syntax import iter_translation_pairs  # noqa: E402
from base_checker import TL_DIR, BaseChecker, CheckContext  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 需要过滤的 Ren'Py 标签（不翻译）
RENPY_TAGS = {
    "{cps",
    "{w=",
    "{nw}",
    "{i}",
    "{/i}",
    "{s}",
    "{/s}",
    "{rb}",
    "{/rb}",
    "{nw}",
    "{fast}",
    "{wait}",
    "{#",
    "{size=",
    "{/size}",
    "{color=#",
    "{/color}",
    "{font=",
    "{/font}",
    "{b}",
    "{/b}",
}


def is_punct_only(text):
    """剥离标签后是否只剩标点/符号（无任何实词）。

    [c_mc_name]? / ?! / {i}...{/i} 等条目的可译内容为零，
    空译文时游戏会回退显示英文原句，无需翻译。
    """
    stripped = strip_renpy_tags(text)
    if not stripped:
        return True
    punct = set(".,!?-–—…*~?!，。、；；：:\"'“”‘’()[]（）%+")
    return all(ch in punct or ch.isspace() for ch in stripped)


def is_renpy_tag_line(text):
    """判断是否是纯 Ren'Py 标签/格式码/仅标点（无实质可译文本）"""
    if text.strip().startswith("# game/"):
        return True
    if re.match(r"^\[[^\]]+\]$", text.strip()):
        return True
    # 去掉所有标签后再看有没有实质文本
    stripped = strip_renpy_tags(text)
    if not stripped:
        return True
    # 剩余只有标点/符号/空格，也算纯标签行
    if is_punct_only(text):
        return True
    return False


def strip_renpy_tags(text):
    """剥离 Ren'Py 标签，提取纯文本"""
    text = re.sub(r"\{#[^}]*\}", "", text)
    text = re.sub(r"\{[^}]*\}", "", text)
    text = re.sub(r"\[[^\]]*\]", "", text)
    return text.strip()


def has_real_text(text):
    """判断文本是否包含实质可翻译内容"""
    stripped = text.strip()

    if re.match(r"^[.\s]*$", stripped):
        return False

    clean = strip_renpy_tags(stripped)

    if not clean:
        return False

    if re.match(r"^[\x00-\x7F]*$", clean):
        # 纯 ASCII 文本
        # 需要至少连续 2+ 字母的单词（Hi, No, Yo 等短对话）
        if re.search(r"\b[a-zA-Z]{2,}\b", clean):
            return True
        # 或包含连字符的缩写/口吃（S-so, I-I）
        if re.search(r"\b[a-zA-Z]-[a-zA-Z]", clean):
            return True
        return False

    # 含 CJK 或日文假名
    if re.search(r"[\u4e00-\u9fff\u3400-\u4dbf\u3040-\u309f\u30a0-\u30ff]", clean):
        return True

    # 含其他 Unicode 非 ASCII
    if re.search(r"[^\x00-\x7F]", clean):
        return True

    return False


def extract_meaningful_text(text):
    """从文本中提取有意义的内容（去除标签和变量）"""
    clean = strip_renpy_tags(text)
    clean = re.sub(r"\{[^}]*\}", "", clean)
    clean = re.sub(r"\[[^\]]*\]", "", clean)
    return clean.strip()


def _pair_to_untranslated_item(pair, strict=False):
    """把翻译对转换为未翻译报告项；无需报告时返回 ``None``。"""
    if pair.translated is None:
        return None

    is_empty = pair.translated == ""
    is_same = pair.original == pair.translated
    if not (is_empty or is_same):
        return None
    if is_renpy_tag_line(pair.original):
        return None
    if is_same and not has_real_text(pair.original):
        return None

    # 默认严格模式只报告空译文；原文=译文由 --all / --skip-same 显式纳入。
    if strict and is_same:
        return None

    item = {
        "line": pair.original_line,
        "type": pair.kind,
        "orig": pair.original,
        "empty": is_empty,
    }
    if pair.kind == "cd":
        item["char"] = pair.translated_speaker or pair.original_speaker
    return item


def _check_pairs(lines, strict=False, kinds=None):
    items = []
    for pair in iter_translation_pairs(lines):
        if kinds is not None and pair.kind not in kinds:
            continue
        item = _pair_to_untranslated_item(pair, strict=strict)
        if item is not None:
            items.append(item)
    return items


def check_translate_blocks(lines, strict=False):
    """检查旁白翻译块（``# "原文"`` → ``"译文"``）。"""
    return _check_pairs(lines, strict=strict, kinds={"tb"})


def check_character_dialogue(lines, strict=False):
    """检查任意角色变量对话（``e``、``c_x``、``mmc`` 等）。"""
    return _check_pairs(lines, strict=strict, kinds={"cd"})


def check_old_entries(lines, strict=False):
    """检查 ``translate strings`` 的 old/new 条目。"""
    return _check_pairs(lines, strict=strict, kinds={"on"})


def scan_file(filepath, strict=False):
    """扫描单个 rpy 文件，返回未翻译条目列表。"""
    with open(filepath, "r", encoding="utf-8-sig") as f:
        lines = f.read().splitlines()
    return _check_pairs(lines, strict=strict)


def collect_rpy_files(tl_dir):
    """递归收集翻译文件，跳过隐藏目录和工具生成的备份目录。"""
    all_rpy = []
    for root, dirs, files in os.walk(tl_dir):
        dirs[:] = [d for d in dirs if not d.startswith(".") and not d.startswith("_")]
        for f in files:
            if f.endswith(".rpy"):
                all_rpy.append(os.path.join(root, f))
    all_rpy.sort()
    return all_rpy


def print_report(all_rpy, tl_dir, strict):
    """终端打印未翻译报告"""
    total_untranslated = 0
    total_empty = 0
    file_summary = []

    for rpy_path in all_rpy:
        items = scan_file(rpy_path, strict=strict)
        if not items:
            continue
        rel_path = os.path.relpath(rpy_path, tl_dir)
        file_summary.append((rel_path, items))
        total_untranslated += len(items)

        for item in items:
            tag = "[EMPTY]" if item.get("empty") else "[SAME]"
            clean = extract_meaningful_text(item["orig"])
            if len(clean) > 100:
                clean = clean[:100] + "..."
            print(f"  {rel_path}:{item['line']}  {tag}  [{item['orig'][:120]}]")
            if not item.get("empty"):
                print(f"    -> {clean}")

    print()
    print("=" * 50)
    if total_untranslated == 0:
        print("[OK] No untranslated entries found.")
    else:
        total_empty = sum(
            1 for _, items in file_summary for it in items if it.get("empty")
        )
        print(
            f"Total: {total_untranslated} untranslated ({total_empty} empty, {total_untranslated - total_empty} same)"
        )
        print(f"Files: {len(file_summary)}")
        for rel_path, items in file_summary:
            empty_count = sum(1 for it in items if it.get("empty"))
            same_count = len(items) - empty_count
            detail = []
            if empty_count:
                detail.append(f"{empty_count} empty")
            if same_count:
                detail.append(f"{same_count} same")
            print(f"  {rel_path}: {len(items)} ({', '.join(detail)})")
    return total_untranslated


def export_csv(all_rpy, tl_dir, out_path, strict):
    """导出未翻译条目为 CSV"""
    report = []
    for rpy_path in all_rpy:
        items = scan_file(rpy_path, strict=strict)
        if not items:
            continue
        rel = os.path.relpath(rpy_path, tl_dir)
        for item in items:
            report.append(
                {
                    "file": rel,
                    "line": item["line"],
                    "type": item["type"],
                    "orig": item["orig"],
                    "trans": "",
                    "char": item.get("char", ""),
                }
            )

    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["file", "line", "type", "char", "orig", "trans"],
        )
        writer.writeheader()
        writer.writerows(report)

    mode = "strict" if strict else "all"
    print(f"Scanned {len(all_rpy)} files, {len(report)} untranslated (mode: {mode})")
    print(f"Exported: {out_path}")
    return len(report)


class UntranslatedChecker(BaseChecker):
    """未翻译检测器（tl 侧样板）。只读：不加 --csv 时只打印，不写任何文件。

    本组唯一吃 tl_dir 的检查器（位置参数就是 tl 目录），所以 requires_tl=True。
    同类分居两处（另两个 tl 侧检查器在 translate/）是已知待收敛项，契约层
    先让它们能被门面统一发现。
    """

    name = "untranslated"
    summary = "检查未翻译或空译文条目（支持 CSV）"
    takes = TL_DIR
    requires_tl = True

    def run(self, ctx):
        if not ctx.has_tl_dir():
            return 0
        all_rpy = collect_rpy_files(str(ctx.tl_dir))
        strict = True
        print(f"Scanning {len(all_rpy)} .rpy files...\n")
        issue_count = print_report(all_rpy, str(ctx.tl_dir), strict)
        return 1 if issue_count else 0


#: 门面发现用的实例（契约见 shared/base_checker.py）
CHECKER = UntranslatedChecker()


def main():
    ap = argparse.ArgumentParser(
        description="Check untranslated entries in Ren'Py TL files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  python check_untranslated.py "game/tl/schinese"
  python check_untranslated.py "game/tl/schinese" --csv report.csv
  python check_untranslated.py "game/tl/schinese" --csv report.csv --all
""",
    )
    ap.add_argument("tl_dir", help="TL directory path (e.g. game/tl/schinese)")
    ap.add_argument(
        "--csv",
        dest="csv_path",
        help="Export untranslated entries to CSV instead of printing",
    )
    ap.add_argument(
        "--all",
        action="store_true",
        help="Include same-as-source entries (default: empty translations only)",
    )
    # 与统一 CLI 的 `all <项目> -l <lang>` 风格保持一致：本工具从 tl_dir 路径
    # 已能确定语言，接受该参数仅为兼容统一入口的参数透传，不产生任何效果。
    ap.add_argument(
        "-l", "--language", default=None,
        help="语言代码（从 tl_dir 路径已可确定，仅兼容统一 CLI 透传）",
    )
    args = ap.parse_args()

    tl_dir = args.tl_dir
    if not os.path.isdir(tl_dir):
        print(f"Error: directory not found: {tl_dir}")
        sys.exit(1)

    all_rpy = collect_rpy_files(tl_dir)
    strict = not args.all

    print(f"Scanning {len(all_rpy)} .rpy files...\n")

    if args.csv_path:
        issue_count = export_csv(all_rpy, tl_dir, args.csv_path, strict)
    else:
        issue_count = print_report(all_rpy, tl_dir, strict)
    return 1 if issue_count else 0


if __name__ == "__main__":
    sys.exit(main() or 0)
