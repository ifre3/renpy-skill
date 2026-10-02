#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
角色名字框翻译工具

功能：
  1. 从术语表（xlsx 或 json）读取角色名字翻译映射
  2. 扫描项目的 characters.rpy（或所有 .rpy）提取 Character("Name") 定义
  3. 扫描翻译目录中已有的 translate strings 块，找出已翻译的名字
  4. 将未翻译的名字补充到指定翻译文件的 strings 块末尾

用法：
  python sync_namebox_translation.py --project MyGame-1.0-pc
  python sync_namebox_translation.py --project MyGame-1.0-pc --glossary glossary.xlsx
   python sync_namebox_translation.py --project MyGame-1.0-pc --language schinese          # 默认试运行
   python sync_namebox_translation.py --project MyGame-1.0-pc --language schinese --apply  # 确认后实际写入

原理：
  Ren'Py 中 Character("Hina") 定义的角色，名字框显示 "Hina"。
  要翻译名字框，需在 translate <lang> strings: 块中添加：
      old "Hina"
      new "雏"
  Ren'Py 会自动用字符串翻译替换名字框文本。
"""

import argparse
import json
import os
import re
import sys

# -- Shared backup module --
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "公共")
)
from backup import atomic_write_text
from rpy_syntax import (
    encode_rpy_string_content,
    parse_new_line,
    parse_old_line,
    replace_literal_content,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_LANGUAGE = "schinese"
DEFAULT_GLOSSARY_XLSX = "导出_术语表.xlsx"
DEFAULT_GLOSSARY_JSON = "glossary.json"
DEFAULT_TARGET_FILE = "script_translated.rpy"  # 默认追加到此文件的 strings 块


def load_glossary(glossary_path):
    """从 xlsx 或 json 文件加载术语表，返回 {原文: 译文} 字典"""
    ext = os.path.splitext(glossary_path)[1].lower()

    if ext == ".json":
        with open(glossary_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # json 格式可能是 [{"原文":..,"译文":..}, ...] 或 {原文:译文, ...}
        if isinstance(data, list):
            result = {}
            for item in data:
                if isinstance(item, dict):
                    # 尝试常见键名
                    src = item.get("原文") or item.get("source") or item.get("key")
                    dst = item.get("译文") or item.get("target") or item.get("value")
                    if src and dst:
                        result[str(src)] = str(dst)
                elif isinstance(item, (list, tuple)) and len(item) >= 2:
                    result[str(item[0])] = str(item[1])
            return result
        elif isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}

    if ext == ".xlsx":
        try:
            import openpyxl
        except ImportError:
            print("错误: 读取 xlsx 需要 openpyxl 库，请运行: pip install openpyxl")
            sys.exit(1)
        wb = openpyxl.load_workbook(glossary_path, read_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return {}
        # 第一行是表头，找原文和译文列
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
        # 如果没找到表头，假设前两列
        if src_col is None:
            src_col = 0
        if dst_col is None:
            dst_col = 1
        result = {}
        for row in rows[1:]:
            if row is None:
                continue
            src = row[src_col] if src_col < len(row) else None
            dst = row[dst_col] if dst_col < len(row) else None
            if src and dst:
                result[str(src).strip()] = str(dst).strip()
        return result

    print(f"错误: 不支持的术语表格式 {ext}（支持 .xlsx 和 .json）")
    sys.exit(1)


def extract_character_names(game_dir):
    """从 game 目录的 .rpy 文件中提取 Character("Name") 定义的名字

    返回 {名字: (文件相对路径, 行号)} 字典
    """
    pattern = re.compile(r'Character\(\s*"([^"]+)"')
    names = {}
    # 优先扫描 characters.rpy，然后扫描其他 .rpy
    files_to_scan = []
    for root, dirs, files in os.walk(game_dir):
        dirs[:] = [
            name
            for name in dirs
            if name != "tl" and not name.startswith((".", "_"))
        ]
        for fname in files:
            if fname.endswith(".rpy"):
                files_to_scan.append(os.path.join(root, fname))

    for filepath in files_to_scan:
        rel_path = os.path.relpath(filepath, game_dir)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for lineno, line in enumerate(f, 1):
                    for m in pattern.finditer(line):
                        name = m.group(1)
                        # 跳过变量插值的名字如 [c_mc_name]
                        if name.startswith("["):
                            continue
                        # 跳过含文本标签的名字如 {font=...}
                        if name.startswith("{"):
                            continue
                        if name not in names:
                            names[name] = (rel_path, lineno)
        except (UnicodeDecodeError, OSError):
            continue
    return names


def find_existing_string_translations(tl_dir, language):
    """扫描翻译目录中已有的字符串翻译

    返回 {old字符串: new字符串} 字典
    """
    translations = {}
    lang_dir = os.path.join(tl_dir, language)
    if not os.path.isdir(lang_dir):
        print(f"警告: 翻译目录不存在: {lang_dir}")
        return translations

    old_pattern = re.compile(r'^\s*old\s+"(.*)"\s*$')
    new_pattern = re.compile(r'^\s*new\s+"(.*)"\s*$')

    for root, dirs, files in os.walk(lang_dir):
        dirs[:] = [name for name in dirs if not name.startswith((".", "_"))]
        for fname in files:
            if not fname.endswith(".rpy"):
                continue
            filepath = os.path.join(root, fname)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    last_old = None
                    for line in f:
                        m_old = old_pattern.match(line)
                        if m_old:
                            last_old = m_old.group(1)
                            continue
                        m_new = new_pattern.match(line)
                        if m_new and last_old is not None:
                            new_value = m_new.group(1)
                            if new_value.strip() or last_old not in translations:
                                translations[last_old] = new_value
                            last_old = None
            except (UnicodeDecodeError, OSError):
                continue
    return translations


def new_pattern_match(line):
    return bool(re.match(r'^\s*new\s+"(.*)"\s*$', line))


def find_strings_block(target_file):
    """找到 translate strings 块的末尾位置

    返回 (块起始行号, 块末尾行号, 文件所有行) 或 None
    """
    with open(target_file, "r", encoding="utf-8", newline="") as f:
        lines = f.readlines()

    block_start = None
    block_end = None
    for i, line in enumerate(lines):
        if re.match(r"^translate\s+\w+\s+strings\s*:", line):
            block_start = i
        elif (
            block_start is not None
            and line.strip()
            and not line.startswith(" ")
            and not line.startswith("\t")
        ):
            # 块结束：遇到非缩进的非空行
            block_end = i
            break

    if block_start is None:
        return None
    if block_end is None:
        block_end = len(lines)

    # 找到块中最后一个 new "..." 行
    last_new_idx = block_start
    for i in range(block_start, block_end):
        if new_pattern_match(lines[i]):
            last_new_idx = i

    return block_start, last_new_idx, lines


def append_translations(target_file, entries, language):
    """向翻译文件的 strings 块末尾追加翻译条目

    entries: [(源文件相对路径, 行号, old文本, new文本), ...]
    返回追加的条目数
    """
    result = find_strings_block(target_file)
    if result is None:
        print(f"错误: 在 {target_file} 中未找到 translate strings 块")
        return 0

    block_start, last_new_idx, lines = result

    updated = 0
    to_append = []
    for entry in entries:
        _src_file, _lineno, old_text, new_text = entry
        found = False
        for index in range(block_start, len(lines)):
            old_literal = parse_old_line(lines[index])
            if old_literal is None or old_literal.value != old_text:
                continue
            found = True
            for new_index in range(index + 1, min(index + 8, len(lines))):
                new_literal = parse_new_line(lines[new_index])
                if new_literal is None:
                    if parse_old_line(lines[new_index]) is not None:
                        break
                    continue
                if new_literal.value == "":
                    lines[new_index] = replace_literal_content(
                        lines[new_index], new_literal, new_text
                    )
                    updated += 1
                break
            break
        if not found:
            to_append.append(entry)

    new_lines = []
    if to_append:
        new_lines.append("\n")
        for src_file, lineno, old_text, new_text in to_append:
            comment = f"    # game/{src_file}:{lineno}\n"
            old_line = f'    old "{encode_rpy_string_content(old_text)}"\n'
            new_line = f'    new "{encode_rpy_string_content(new_text)}"\n'
            new_lines.extend([comment, old_line, new_line, "\n"])

    if to_append:
        insert_pos = last_new_idx + 1
        lines = lines[:insert_pos] + new_lines + lines[insert_pos:]
    if updated or to_append:
        newline = "\r\n" if any(line.endswith("\r\n") for line in lines) else "\n"
        atomic_write_text(
            target_file,
            "".join(lines),
            encoding="utf-8",
            backup=True,
            newline=newline,
        )

    return updated + len(to_append)


def main():
    parser = argparse.ArgumentParser(
        description="同步角色名字框翻译（从术语表生成字符串翻译）"
    )
    parser.add_argument(
        "--project",
        required=True,
        help="项目目录名或路径（相对于 SDK 根目录或绝对路径）",
    )
    parser.add_argument(
        "--glossary",
        help="术语表文件路径（.xlsx 或 .json）",
    )
    parser.add_argument(
        "--language",
        default=DEFAULT_LANGUAGE,
        help=f"翻译语言目录名（默认: {DEFAULT_LANGUAGE}）",
    )
    parser.add_argument(
        "--target-file",
        default=DEFAULT_TARGET_FILE,
        help=f"追加翻译的目标文件名（默认: {DEFAULT_TARGET_FILE}）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="(默认即为试运行，保留此参数仅为兼容旧命令行)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="实际写入文件；不带此参数一律只预览不修改",
    )
    args = parser.parse_args()

    # 解析路径
    sdk_dir = os.path.dirname(os.path.abspath(__file__))
    sdk_dir = os.path.dirname(sdk_dir)  # tools/
    sdk_dir = os.path.dirname(sdk_dir)  # SDK 根目录

    project_path = args.project
    if not os.path.isabs(project_path):
        project_path = os.path.join(sdk_dir, project_path)
    project_path = os.path.abspath(project_path)

    game_dir = os.path.join(project_path, "game")
    tl_dir = os.path.join(game_dir, "tl")
    target_file = os.path.join(tl_dir, args.language, args.target_file)

    if not os.path.isdir(game_dir):
        print(f"错误: 游戏目录不存在: {game_dir}")
        sys.exit(1)

    # 1. 加载术语表
    glossary_path = args.glossary
    if not glossary_path:
        # 自动查找术语表（当前目录和 SDK 根目录）
        for candidate in [DEFAULT_GLOSSARY_XLSX, DEFAULT_GLOSSARY_JSON]:
            for search_dir in [os.getcwd(), sdk_dir]:
                p = os.path.join(search_dir, candidate)
                if os.path.isfile(p):
                    glossary_path = p
                    break
            if glossary_path:
                break
    if not glossary_path or not os.path.isfile(glossary_path):
        print("错误: 未找到术语表文件，请用 --glossary 指定")
        sys.exit(1)

    print(f"加载术语表: {glossary_path}")
    glossary = load_glossary(glossary_path)
    print(f"  术语表包含 {len(glossary)} 个条目")

    # 2. 提取角色名字
    print(f"\n扫描角色定义: {game_dir}")
    char_names = extract_character_names(game_dir)
    print(f"  找到 {len(char_names)} 个 Character 名字定义")

    # 3. 查找已有翻译
    print(f"\n扫描已有字符串翻译: {os.path.join(tl_dir, args.language)}")
    existing = find_existing_string_translations(tl_dir, args.language)
    print(f"  找到 {len(existing)} 个已有字符串翻译")

    # 4. 找出需要补充的翻译
    to_add = []
    already_translated = []
    not_in_glossary = []

    for name, (src_file, lineno) in sorted(char_names.items(), key=lambda x: x[1][1]):
        existing_value = existing.get(name)
        if existing_value is not None and existing_value.strip():
            already_translated.append((name, existing_value))
        elif name in glossary:
            to_add.append((src_file, lineno, name, glossary[name]))
        else:
            not_in_glossary.append((name, src_file, lineno))

    # 5. 输出报告
    print("\n" + "=" * 60)
    print("翻译状态报告")
    print("=" * 60)

    if already_translated:
        print(f"\n✓ 已翻译的角色名字（{len(already_translated)} 个）:")
        for name, trans in already_translated:
            print(f"  {name} → {trans}")

    if to_add:
        print(f"\n＋ 将要补充翻译的角色名字（{len(to_add)} 个）:")
        for src_file, lineno, name, trans in to_add:
            print(f"  {name} → {trans}  (来自 {src_file}:{lineno})")

    if not_in_glossary:
        print(f"\n？ 术语表中未找到的角色名字（{len(not_in_glossary)} 个，不处理）:")
        for name, src_file, lineno in not_in_glossary:
            print(f"  {name}  (来自 {src_file}:{lineno})")

    # 6. 执行追加（默认试运行，--apply 才写）
    if to_add and args.apply:
        if not os.path.isfile(target_file):
            print(f"\n错误: 目标文件不存在: {target_file}")
            sys.exit(1)

        # 检查是否有重复（防止重复运行）
        count = append_translations(target_file, to_add, args.language)
        print(f"\n✓ 已向 {target_file} 追加 {count} 条翻译")
    elif to_add:
        print(f"\n[试运行] 将向 {target_file} 追加 {len(to_add)} 条翻译（未实际修改；确认无误后加 --apply 写入）")
    else:
        print("\n无需补充翻译，所有术语表中的角色名字均已翻译。")


if __name__ == "__main__":
    main()
