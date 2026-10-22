#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""角色名字框翻译工具

功能：
  1. 从术语表（xlsx 或 json）读取角色名字翻译映射
  2. 扫描项目的 .rpy 识别全部会在名字栏显示的说话人（三种写法，见 shared/namebox.py）
  3. 扫描翻译目录中已有的 translate strings 块，找出已翻译的名字
  4. 把未翻译的名字补成 ``translate <lang> strings:`` 条目

用法：
    python sync_namebox_translation.py --project MyGame-1.0-pc
    python sync_namebox_translation.py --project MyGame-1.0-pc --glossary glossary.xlsx
    python sync_namebox_translation.py --project MyGame-1.0-pc --language schinese  # 默认试运行
    python sync_namebox_translation.py --project MyGame-1.0-pc --language schinese --apply
    python sync_namebox_translation.py --project MyGame-1.0-pc --stub game/tl/schinese/zz_namebox.rpy --apply

原理（源码依据，别凭印象改）
----------------------------
Ren'Py 显示裸字符串说话人时，现场把它包成 Character
（``renpy/defaultstore.py:420-422``），名字再经
``prefix_suffix`` → ``substitute(..., translate=True)``
（``renpy/character.py:1348-1349, 1454``）查字符串翻译
（``renpy/substitutions.py:344-345``）。查找是
``renpy/translation/__init__.py:545`` 的**全串精确匹配**：

* ``old "{color=#0f37f2}Niwa{/color}"`` 只能被同名整串命中；
* ``old "Niwa"`` **命中不了**带颜色标签的串；
* 引擎只剥离 ``{#...}`` 翻译注释标签，``{color=}`` 这类文本标签不剥。

因此补条目时 ``new`` 必须**连颜色标签一起写**，否则角色配色会丢。
"""

import argparse
import json
import os
import re
import sys

# -- Shared modules --
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shared")
)
from backup import atomic_write_text
from rpy_syntax import (
    encode_rpy_string_content,
    parse_new_line,
    parse_old_line,
    replace_literal_content,
)
from namebox import (
    load_tl_strings,
    lookup_translation,
    render_entry,
    render_strings_block,
    scan_namebox_names,
    splice_tags,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_LANGUAGE = "schinese"
DEFAULT_GLOSSARY_XLSX = "导出_术语表.xlsx"
DEFAULT_GLOSSARY_JSON = "glossary.json"
DEFAULT_TARGET_FILE = "script_translated.rpy"  # 默认追加到此文件的 strings 块


def load_glossary_with_notes(glossary_path):
    """读术语表，返回 ``({原文: 译文}, {原文: 备注})``。

    备注列承载消歧信息，其中「可保留英文」是名字栏的**语义指令**：
    这类名字（如 ``NOT ME``）在原游戏里是刻意的异国语言喊叫，翻成中文会
    削弱效果，因此不生成 ``translate strings`` 条目——原样显示即已正确。
    """
    ext = os.path.splitext(glossary_path)[1].lower()

    if ext == ".json":
        with open(glossary_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        mapping, notes = {}, {}
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    src = item.get("原文") or item.get("source") or item.get("key")
                    dst = item.get("译文") or item.get("target") or item.get("value")
                    if src and dst:
                        mapping[str(src)] = str(dst)
                        note = item.get("备注") or item.get("note") or ""
                        if note:
                            notes[str(src)] = str(note)
                elif isinstance(item, (list, tuple)) and len(item) >= 2:
                    mapping[str(item[0])] = str(item[1])
        elif isinstance(data, dict):
            mapping = {str(k): str(v) for k, v in data.items()}
        return mapping, notes

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
            return {}, {}
        header = rows[0]
        src_col = dst_col = note_col = None
        for i, h in enumerate(header):
            if h is None:
                continue
            h_str = str(h).strip()
            if h_str in ("原文", "source", "Source", "key"):
                src_col = i
            elif h_str in ("译文", "target", "Target", "value", "translation"):
                dst_col = i
            elif h_str in ("备注", "note", "Note", "comment"):
                note_col = i
        if src_col is None:
            src_col = 0
        if dst_col is None:
            dst_col = 1
        mapping, notes = {}, {}
        for row in rows[1:]:
            if row is None:
                continue
            src = row[src_col] if src_col < len(row) else None
            dst = row[dst_col] if dst_col < len(row) else None
            if src and dst:
                mapping[str(src).strip()] = str(dst).strip()
                if note_col is not None and note_col < len(row) and row[note_col]:
                    notes[str(src).strip()] = str(row[note_col]).strip()
        return mapping, notes

    print(f"错误: 不支持的术语表格式 {ext}（支持 .xlsx 和 .json）")
    sys.exit(1)


def load_glossary(glossary_path):
    """从 xlsx 或 json 文件加载术语表，返回 {原文: 译文} 字典"""
    return load_glossary_with_notes(glossary_path)[0]


#: 备注里出现这些词 ⇒ 名字栏保留英文原文，不生成翻译条目
KEEP_ENGLISH_MARKERS = ("保留英文", "保持英文", "不译")


def build_target_value(name_value, translation):
    """把术语表的裸译名塞回名字栏的标签骨架。

    ``("{color=#0f37f2}Niwa{/color}", "丹羽")`` → ``"{color=#0f37f2}丹羽{/color}"``

    无标签时原样返回；多文本段（语义有歧义）返回 ``None``，由调用方报告。
    """
    if name_value == translation:
        return translation
    return splice_tags(name_value, translation)


def extract_character_names(game_dir):
    """兼容旧调用方：返回 ``{显示名: (相对路径, 行号)}``。

    新代码请直接用 ``shared/namebox.scan_namebox_names``——它保留完整串与
    台词条数，这两项生成条目时都要用。
    """
    result = {}
    for nd in scan_namebox_names(game_dir):
        rel, _, lineno = nd.source.rpartition(":")
        result.setdefault(nd.plain, (rel, int(lineno) if lineno.isdigit() else 0))
    return result


def find_existing_string_translations(tl_dir, language):
    """兼容旧调用方：``tl/<language>`` 下的 old→new 映射。"""
    lang_dir = os.path.join(tl_dir, language)
    if not os.path.isdir(lang_dir):
        print(f"警告: 翻译目录不存在: {lang_dir}")
        return {}
    return load_tl_strings(lang_dir)


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
            block_end = i
            break

    if block_start is None:
        return None
    if block_end is None:
        block_end = len(lines)

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
            comment = f"    # game/{src_file}:{lineno}"
            old_line = f'    old "{encode_rpy_string_content(old_text)}"'
            new_line = f'    new "{encode_rpy_string_content(new_text)}"'
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


def write_namebox_file(path, entries, language):
    """写一个独立的 ``translate <lang> strings:`` 文件（每次运行整体重写）。

    entries: [(源相对路径, 行号, old完整串, new完整串), ...]
    """
    # 引擎 add_string_translation 对重复 old 是 fail-closed 的
    # （translation/__init__.py:534 直接抛 "already exists"），
    # 所以这里最后拦一道，宁可不写也不要产出启动即崩的文件。
    seen = {}
    for _src, _lineno, old, _new in entries:
        if old in seen:
            raise ValueError(
                f"old 条目重复: {old!r}（{seen[old]} 与 {_src}:{_lineno}）——"
                "名字栏显示的是同一个串，应合并为一条"
            )
        seen[old] = f"{_src}:{_lineno}"

    header = "\n".join([
        "角色名字框中文（由 sync_namebox_translation.py 生成）。",
        "old 必须与名字栏显示的完整串精确相等——含 {color=} 标签时也带上标签；",
        "new 保留同样标签，否则角色配色会丢。改完可在同名文件里手工微调，",
        "再次运行本工具会整体覆盖本文件。",
    ])
    body = [
        render_entry(old, new, comment=f"game/{src}:{lineno}")
        for src, lineno, old, new in entries
    ]
    text = render_strings_block(language, body, header=header)
    # 只在**覆盖**既有文件时才备份：首次生成没有原件可备，
    # 而 ensure_bak 是 fail-closed 的（文件不存在会抛 FileNotFoundError）。
    atomic_write_text(path, text, encoding="utf-8",
                      backup=os.path.isfile(path), newline="\n")
    return len(entries)


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
        help=f"翻译语言目录名（默认 {DEFAULT_LANGUAGE}）",
    )
    parser.add_argument(
        "--target-file",
        default=DEFAULT_TARGET_FILE,
        help="追加翻译的目标文件名（默认 script_translated.rpy）",
    )
    parser.add_argument(
        "--stub",
        help="改为写一个独立的 translate strings 文件到该路径（推荐：不污染既有翻译文件）",
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

    if not os.path.isdir(game_dir):
        print(f"错误: 游戏目录不存在: {game_dir}")
        sys.exit(1)

    # 1. 加载术语表
    glossary_path = args.glossary
    if not glossary_path:
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
    glossary, glossary_notes = load_glossary_with_notes(glossary_path)
    print(f"  术语表包含 {len(glossary)} 个条目")

    # 2. 识别说话人
    print(f"\n扫描说话人定义: {game_dir}")
    names = scan_namebox_names(game_dir)
    print(f"  找到 {len(names)} 个说话人"
          f"（character {sum(1 for n in names if n.kind == 'character')}"
          f" / define {sum(1 for n in names if n.kind == 'define')}"
          f" / inline {sum(1 for n in names if n.kind == 'inline')}）")
    if not names:
        print("  一个都没扫到——若为纯 .rpyc 发行版请先反编译。")

    # 3. 查找已有翻译
    print(f"\n扫描已有字符串翻译: {os.path.join(tl_dir, args.language)}")
    existing = load_tl_strings(os.path.join(tl_dir, args.language))
    print(f"  找到 {len(existing)} 个已有字符串翻译")

    # 4. 找出需要补充的翻译
    to_add = []
    already_translated = []
    not_in_glossary = []
    ambiguous = []
    keep_english = []

    for nd in sorted(names, key=lambda n: (-n.say_lines, n.plain.lower())):
        hit = lookup_translation(nd.value, existing)
        if hit is not None and hit.strip():
            already_translated.append((nd, hit))
            continue

        translation = glossary.get(nd.plain)
        if not translation:
            not_in_glossary.append(nd)
            continue

        note = glossary_notes.get(nd.plain, "")
        if any(marker in note for marker in KEEP_ENGLISH_MARKERS):
            # 原样显示即正确，不生成 new==old 的空转条目。
            keep_english.append(nd)
            continue

        target = build_target_value(nd.value, translation)
        if target is None:
            ambiguous.append((nd, translation))
            continue

        rel, _, lineno = nd.source.rpartition(":")
        to_add.append((rel, lineno, nd.value, target))

    # 5. 输出报告
    print("\n" + "=" * 60)
    print("翻译状态报告")
    print("=" * 60)

    if already_translated:
        print(f"\n[OK] 已有译文的说话人（{len(already_translated)} 个）:")
        for nd, trans in already_translated[:20]:
            print(f"  {nd.plain} → {trans}")
        if len(already_translated) > 20:
            print(f"  ... 其余 {len(already_translated) - 20} 个省略")

    if to_add:
        print(f"\n[+] 将要补充的说话人（{len(to_add)} 个）:")
        for src, lineno, old, new in to_add[:30]:
            flag = "含标签" if old != new else "裸名  "
            print(f"  {flag}  {old}  →  {new}")
        if len(to_add) > 30:
            print(f"  ... 其余 {len(to_add) - 30} 个省略")

    if not_in_glossary:
        print(f"\n[?] 术语表中未收录的说话人（{len(not_in_glossary)} 个，不处理）:")
        for nd in sorted(not_in_glossary, key=lambda n: -n.say_lines)[:20]:
            print(f"  {nd.plain}（{nd.say_lines} 句，{nd.kind}） <- {nd.source}")
        if len(not_in_glossary) > 20:
            print(f"  ... 其余 {len(not_in_glossary) - 20} 个省略")
        print("  提示：这些名字在游戏里会显示英文，补进术语表后重跑本工具。")

    if keep_english:
        print(f"\n[-] 术语表标注「保留英文」的名字（{len(keep_english)} 个，不生成条目）:")
        for nd in sorted(keep_english, key=lambda n: -n.say_lines):
            print(f"  {nd.plain}（{nd.say_lines} 句）← {glossary_notes.get(nd.plain, '')}")

    if ambiguous:
        print(f"\n[!] 标签骨架有多个文本段、无法安全拼接（{len(ambiguous)} 个）:")
        for nd, translation in ambiguous:
            print(f"  {nd.value!r} -> 译名 {translation!r}")

    # 6. 执行
    if args.stub:
        if not to_add:
            print("\n无需补充翻译，未生成文件。")
        elif args.apply:
            count = write_namebox_file(args.stub, to_add, args.language)
            print(f"\n[OK] 已写出 {args.stub}（{count} 条）")
        else:
            print(f"\n[试运行] 将写出 {args.stub}（{len(to_add)} 条，未实际修改）")
    elif to_add and args.apply:
        target_file = os.path.join(tl_dir, args.language, args.target_file)
        if not os.path.isfile(target_file):
            print(f"\n错误: 目标文件不存在: {target_file}")
            print("      建议改用 --stub <路径> 写独立文件，避免依赖既有 strings 块。")
            sys.exit(1)
        count = append_translations(target_file, to_add, args.language)
        print(f"\n[OK] 已向 {target_file} 追加 {count} 条翻译")
    elif to_add:
        print(f"\n[试运行] 未修改任何文件（{len(to_add)} 条待补）")
    else:
        print("\n无需补充翻译。")


if __name__ == "__main__":
    main()