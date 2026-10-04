#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TL 注释行英文检测与恢复工具
==========================
Ren'Py 翻译文件中的注释行(# 开头)应该保留原始英文。
在统一名字时，可能误将注释行中的英文名字替换为中文。
此工具检测并恢复这些注释行。

Step 1: 检测注释行中是否存在中文(术语表中的中文译名)
Step 2: 根据术语表反向恢复(中文->英文)
Step 3: 再次检测确认无残留

用法:
  python fix_translation_comments.py --project <项目> --glossary <术语表> --dry-run
  python fix_translation_comments.py --project <项目> --glossary <术语表> --apply
  python fix_translation_comments.py --project <项目> --glossary <术语表> --language schinese
"""

import argparse
import os
import re
import sys

# ── 引入共享公共 ──
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "公共")
)
from backup import atomic_write_text
from rpy_syntax import parse_original_comment

try:
    import openpyxl
except ImportError:
    openpyxl = None

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def load_glossary(path):
    """加载术语表，返回 {英文: 中文} 字典"""
    ext = os.path.splitext(path)[1].lower()

    if ext == ".json":
        import json

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            result = {}
            for item in data:
                if isinstance(item, dict):
                    src = item.get("原文") or item.get("source") or item.get("key")
                    dst = item.get("译文") or item.get("target") or item.get("value")
                    if src and dst:
                        result[str(src).strip()] = str(dst).strip()
                elif isinstance(item, (list, tuple)) and len(item) >= 2:
                    result[str(item[0])] = str(item[1])
            return result
        elif isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}

    elif ext == ".xlsx":
        if openpyxl is None:
            print("错误: 需要 openpyxl 库，请运行: pip install openpyxl")
            sys.exit(1)
        wb = openpyxl.load_workbook(path, read_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return {}
        header = rows[0]
        src_col = dst_col = None
        for i, h in enumerate(header):
            if h is None:
                continue
            h_str = str(h).strip()
            if h_str in ("原文", "source", "Source", "key"):
                src_col = i
            elif h_str in ("译文", "target", "Target", "value", "translation"):
                dst_col = i
        if src_col is None:
            src_col = 0
        if dst_col is None:
            dst_col = 1
        result = {}
        for row in rows[1:]:
            src = row[src_col] if src_col < len(row) else None
            dst = row[dst_col] if dst_col < len(row) else None
            if src and dst:
                result[str(src).strip()] = str(dst).strip()
        return result

    else:
        print(f"错误: 不支持的术语表格式: {ext}")
        sys.exit(1)


def fix_translation_comments(tl_dir, reverse_map, language, dry_run=True):
    """检测并恢复翻译文件中的注释行"""
    rpy_files = []
    for root, dirs, files in os.walk(tl_dir):
        dirs[:] = [name for name in dirs if not name.startswith((".", "_"))]
        for f in files:
            if f.endswith(".rpy"):
                rpy_files.append(os.path.join(root, f))

    total_issues = 0
    total_fixed = 0

    # 按中文长度排序（长的先替换，避免部分匹配）
    # 预编译正则：用 re.escape 处理特殊字符，用 lookahead/lookbehind 避免子串误匹配
    sorted_items = sorted(reverse_map.items(), key=lambda x: -len(x[0]))
    # 构建正则替换列表: [(compiled_regex, replacement), ...]
    replace_patterns = []
    for cn, en in sorted_items:
        # 使用 re.escape 转义中文中的特殊字符（虽然中文一般无特殊字符，但更安全）
        pattern = re.compile(re.escape(cn))
        replace_patterns.append((pattern, en))

    translate_pattern = re.compile(
        rf"^translate\s+{re.escape(language)}(?:\s|$)"
    )

    for tl_path in sorted(rpy_files):
        rel_path = os.path.relpath(tl_path, tl_dir)
        with open(tl_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        new_lines = []
        file_changed = False
        in_translate_block = False
        is_strings_block = False

        for i, line in enumerate(lines):
            stripped = line.strip()

            # 追踪 translate 块
            if translate_pattern.match(stripped):
                in_translate_block = True
                is_strings_block = "strings:" in stripped
                new_lines.append(line)
                continue

            if in_translate_block:
                # 检查块是否结束（非缩进的非空行）
                if stripped and not line.startswith(" ") and not line.startswith("\t"):
                    in_translate_block = False
                    is_strings_block = False
                    new_lines.append(line)
                    continue

                # 跳过 strings 块中的所有内容
                if is_strings_block:
                    new_lines.append(line)
                    continue

                # 检测是否是注释行（不是文件引用注释）
                if stripped.startswith("#") and not stripped.startswith("# game/"):
                    comment_content = stripped.lstrip("#").strip()
                    # 只修复 Ren'Py 生成的“英文原文注释”。普通人工注释即使
                    # 含中文也不应被术语表反向替换。
                    if parse_original_comment(line) is None:
                        new_lines.append(line)
                        continue

                    # 检查是否包含术语表中的中文
                    has_chinese = False
                    for cn, en in sorted_items:
                        if cn in comment_content:
                            has_chinese = True
                            break

                    if has_chinese:
                        # 恢复注释行（中文->英文）
                        # 使用正则替换，避免 str.replace 的子串误匹配
                        restored_content = comment_content
                        for pattern, en in replace_patterns:
                            restored_content = pattern.sub(en, restored_content)

                        # 保留原始缩进
                        indent = line[: len(line) - len(line.lstrip())]
                        restored_line = indent + "# " + restored_content + "\n"

                        if dry_run:
                            print(f"  [待恢复] {rel_path}:L{i + 1}")
                            print(f"    当前: {line.rstrip()}")
                            print(f"    恢复: {restored_line.rstrip()}")
                            total_issues += 1
                            new_lines.append(line)  # 预览模式下不修改
                        else:
                            new_lines.append(restored_line)
                            file_changed = True
                            total_fixed += 1
                            print(f"  [已恢复] {rel_path}:L{i + 1}")
                            print(f"    恢复: {restored_line.rstrip()}")
                        continue

                new_lines.append(line)
            else:
                new_lines.append(line)

        if not dry_run and file_changed:
            atomic_write_text(
                tl_path,
                "".join(new_lines),
                encoding="utf-8",
                backup=True,
            )

    if dry_run:
        print(f"\n共发现 {total_issues} 处需要恢复")
        print("使用 --apply 执行实际恢复")
    else:
        print(f"\n共修复 {total_fixed} 处")

    return total_issues if dry_run else total_fixed


def main():
    parser = argparse.ArgumentParser(
        description="检测并恢复 Ren'Py 翻译文件注释行中被替换的英文名字"
    )
    parser.add_argument("--project", required=True, help="游戏项目路径")
    parser.add_argument(
        "--glossary", required=True, help="术语表文件路径 (.xlsx 或 .json)"
    )
    parser.add_argument("--language", default="schinese", help="翻译语言目录名")
    parser.add_argument("--apply", action="store_true", help="执行恢复")
    args = parser.parse_args()

    project_dir = os.path.abspath(args.project)
    tl_dir = os.path.join(project_dir, "game", "tl", args.language)
    glossary_path = os.path.abspath(args.glossary)

    if not os.path.isdir(tl_dir):
        print(f"错误: 翻译目录不存在: {tl_dir}")
        sys.exit(1)
    if not os.path.isfile(glossary_path):
        print(f"错误: 术语表文件不存在: {glossary_path}")
        sys.exit(1)

    # 加载术语表并创建反向映射 {中文: 英文}
    glossary = load_glossary(glossary_path)
    reverse_map = {v: k for k, v in glossary.items()}
    print(f"加载术语表: {glossary_path} ({len(glossary)} 个条目)")
    print(f"反向映射: {len(reverse_map)} 个")

    mode = "预览" if not args.apply else "恢复"
    print(f"\n=== Step 1: 检测注释行中文 ({mode}模式) ===")
    print(f"项目: {project_dir}")
    print(f"翻译: {tl_dir}")
    print()

    fix_translation_comments(tl_dir, reverse_map, args.language, dry_run=not args.apply)

    # 恢复后再检测
    if args.apply:
        print("\n=== Step 3: 残留检测 ===")
        remaining = fix_translation_comments(
            tl_dir, reverse_map, args.language, dry_run=True
        )
        if remaining == 0:
            print("OK: 无残留，全部恢复完成")
        else:
            print(f"WARNING: 仍有 {remaining} 处未恢复，请检查")


if __name__ == "__main__":
    main()
