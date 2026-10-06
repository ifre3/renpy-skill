#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查 Ren'Py 翻译文件中的 AI 翻译完整性问题。

覆盖 ``translate strings`` 的 old/new、普通旁白以及任意角色变量的 say
对话（例如 ``c_x``、``e``、``mmc``）。检查变量、标签结构、标签参数、Ren'Py
特殊转义和译文角色是否被改动。

用法::

    python check_translation_integrity.py <项目目录> [-l schinese] [-o report.txt]
"""

import argparse
import os
import re
import sys
from collections import Counter

_SHARED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shared")
if _SHARED_DIR not in sys.path:
    sys.path.insert(0, _SHARED_DIR)

from rpy_syntax import iter_bracket_groups, iter_translation_pairs  # noqa: E402
# 契约层在 shared/（跨组共享，故按相对路径加入 sys.path）
_SHARED_CONTRACT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "../shared")
if _SHARED_CONTRACT_DIR not in sys.path:
    sys.path.insert(0, _SHARED_CONTRACT_DIR)

from base_checker import PROJECT, BaseChecker  # noqa: E402


class TranslationIntegrityChecker(BaseChecker):
    """翻译完整性检测。"""

    name = "integrity"
    summary = "检查变量、角色、标签结构、参数和转义完整性"
    takes = PROJECT
    requires_tl = True


#: 门面发现用的实例（契约见 shared/base_checker.py）
CHECKER = TranslationIntegrityChecker()


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
else:  # pragma: no cover - Python 3.6 及更早版本
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def red(text):
    return f"\033[91m{text}\033[0m" if sys.stdout.isatty() else text


def yellow(text):
    return f"\033[93m{text}\033[0m" if sys.stdout.isatty() else text


def green(text):
    return f"\033[92m{text}\033[0m" if sys.stdout.isatty() else text


# ── 文本标记提取 ──────────────────────────────────────────────────────

TAG_RE = re.compile(r"\{(/?)([a-zA-Z]+)(?:=[^}]*)?\}")

# 与 Ren'Py 8.5 renpy/text/extras.py 的 text_tags 保持一致：这里只列出
# 必须闭合的内置标签。自定义标签由 SDK lint 判断，未知标签在本工具中忽略，
# 避免把 {glitch} 等项目自定义标签误报为“多余闭标签”。
PAIRED_TAGS = {
    "alpha",
    "alt",
    "art",
    "axis",
    "instance",
    "feature",
    "b",
    "i",
    "u",
    "a",
    "plain",
    "font",
    "color",
    "outlinecolor",
    "size",
    "noalt",
    "s",
    "shader",
    "rt",
    "rb",
    "k",
    "cps",
}


def _extract_interpolations(text):
    """返回按出现顺序排列的 ``(表达式, 标志, 完整匹配)``。

    Ren'Py 支持任意合法 Python 表达式和 PEP 3101 格式说明，不应只检查
    ``[identifier]``。例如 ``[renpy.version_only]``、``[items[0]]`` 和
    ``[score / max_score:.1%]`` 都必须被视为格式标记。
    """
    result = []
    flag_suffix = re.compile(r"^(.*?)(!+[A-Za-z]+)$")
    for content, full in iter_bracket_groups(text):
        match = flag_suffix.match(content)
        if match:
            expression, flag = match.group(1), match.group(2).lstrip("!")
        else:
            expression, flag = content, ""
        result.append((expression, flag, full))
    return result


def _iter_tag_matches(text):
    """跳过 ``{{`` 转义后提取 Ren'Py 文本标签。"""
    index = 0
    while index < len(text):
        if text[index] != "{":
            index += 1
            continue
        if index + 1 < len(text) and text[index + 1] == "{":
            index += 2
            continue
        match = TAG_RE.match(text, index)
        if match:
            yield match
            index = match.end()
        else:
            index += 1


def _tag_counter(text):
    return Counter(match.group(0) for match in _iter_tag_matches(text))


def _tag_structure_errors(text):
    """检查成对文本标签的闭合与嵌套，返回简短错误说明。"""
    stack = []
    errors = []
    for match in _iter_tag_matches(text):
        closing, name = match.group(1), match.group(2)
        if name not in PAIRED_TAGS:
            continue
        if closing:
            if not stack:
                errors.append(f"多余的闭标签 {{{name}}}")
            elif stack[-1] != name:
                errors.append(
                    f"标签嵌套错误: 期望 {{/{stack[-1]}}}，实际 {{{name}}}"
                )
                if name in stack:
                    while stack and stack[-1] != name:
                        stack.pop()
                if stack:
                    stack.pop()
            else:
                stack.pop()
        elif name in PAIRED_TAGS:
            stack.append(name)
    if stack:
        errors.append("未闭合标签: " + ", ".join("{" + name + "}" for name in stack))
    return errors


def find_interpolations(text):
    """提取所有变量插值，返回 ``{变量名: 完整匹配}``（兼容旧 API）。"""
    return {
        var_name: full
        for var_name, _flag, full in _extract_interpolations(text)
    }


def find_all_bracket_content(text):
    """提取所有非转义插值（忽略标签参数中的方括号）。"""
    return list(iter_bracket_groups(text))


def find_tags(text):
    """提取文本中所有不同的 Ren'Py 标签。"""
    return {match.group(0) for match in _iter_tag_matches(text)}


def find_escapes(text):
    """提取 Ren'Py 转义计数。

    字符串字面量已经解码，因此源码中的 ``\\n`` / ``\\t`` 在这里表现为实际
    换行/制表符；``[[`` / ``{{`` 则保持原样。
    """
    result = Counter(
        {
            "[[": text.count("[["),
            "{{": text.count("{{"),
            "\\n": text.count("\n"),
            "\\t": text.count("\t"),
            "\\\\": text.count("\\"),
        }
    )
    return +result


def _issue(issue_type, severity, line_no, rel_path, desc, old_text="", new_text=""):
    return {
        "type": issue_type,
        "severity": severity,
        "file": rel_path,
        "line": line_no,
        "desc": desc,
        "original": old_text[:100],
        "translated": new_text[:100],
    }


def check_pair(old_text, new_text, line_no, rel_path, context_type="dialogue"):
    """对比一条原文和译文。``context_type`` 保留为兼容参数。"""
    errors = []

    def add(kind, severity, desc):
        errors.append(
            _issue(kind, severity, line_no, rel_path, desc, old_text, new_text)
        )

    # 1. 变量名和出现次数。Counter 可发现重复变量只保留一次的情况。
    old_interps = _extract_interpolations(old_text)
    new_interps = _extract_interpolations(new_text)
    old_var_counts = Counter(name for name, _flag, _full in old_interps)
    new_var_counts = Counter(name for name, _flag, _full in new_interps)

    for var_name, count in (old_var_counts - new_var_counts).items():
        add("LOST_VAR", "ERROR", f"变量丢失: 原文有 {count} 处 [{var_name}]，译文不足")
    for var_name, count in (new_var_counts - old_var_counts).items():
        add("EXTRA_VAR", "ERROR", f"变量新增: 译文多了 {count} 处 [{var_name}]，原文没有")

    # 2. !t / !ti 等标志按变量分别比较。
    old_flags = {}
    new_flags = {}
    for name, flag, _full in old_interps:
        old_flags.setdefault(name, Counter())[flag] += 1
    for name, flag, _full in new_interps:
        new_flags.setdefault(name, Counter())[flag] += 1
    for var_name in sorted(set(old_flags) & set(new_flags)):
        # 译文新增 !t / !ti 往往正是为了翻译变量值，是合法修复；只在原文
        # 已带标志而译文删除或改错标志时报告。
        if any(old_flags[var_name]) and old_flags[var_name] != new_flags[var_name]:
            old_desc = ", ".join(
                flag or "(无)" for flag, _count in old_flags[var_name].items()
            )
            new_desc = ", ".join(
                flag or "(无)" for flag, _count in new_flags[var_name].items()
            )
            add(
                "FLAG_MISMATCH",
                "WARN",
                f"变量标志不一致: [{var_name}] 原文={old_desc}，译文={new_desc}",
            )

    # 3. 表达式被翻译/改写，或新增了明显非法的中文方括号内容。
    old_expressions = [name for name, _flag, _full in old_interps]
    old_expression_set = set(old_expressions)
    for content, _full in find_all_bracket_content(new_text):
        base_expression = content
        flag_suffix = re.match(r"^(.*?)(!+[A-Za-z]+)$", content)
        if flag_suffix:
            base_expression = flag_suffix.group(1)
        if base_expression in old_expression_set:
            continue
        if old_expressions:
            add(
                "VAR_TRANSLATED",
                "ERROR",
                f"插值表达式被修改: 原文 [{old_expressions[0]}] → 译文 [{content}]",
            )
        elif re.search(r"[\u3400-\u9fff]", content):
            add(
                "INVALID_VAR",
                "WARN",
                f"非法插值表达式: [{content}] 含中文变量/占位内容",
            )

    # 4. 标签既比较完整 token（含颜色/字号参数），也检查嵌套结构。
    old_tags = _tag_counter(old_text)
    new_tags = _tag_counter(new_text)
    for tag, count in (old_tags - new_tags).items():
        add("LOST_TAG", "ERROR", f"标签丢失: 原文有 {count} 处 {tag}，译文不足")
    for tag, count in (new_tags - old_tags).items():
        add("EXTRA_TAG", "WARN", f"标签新增或参数改变: 译文多了 {count} 处 {tag}")
    for detail in _tag_structure_errors(new_text):
        add("TAG_MISMATCH", "ERROR", f"标签结构错误: {detail}")

    # 5. Ren'Py 特殊转义与换行/制表符。
    old_escapes = find_escapes(old_text)
    new_escapes = find_escapes(new_text)
    for esc, count in (old_escapes - new_escapes).items():
        add("LOST_ESCAPE", "ERROR", f"转义丢失: 原文有 {count} 处 {esc}，译文不足")
    for esc, count in (new_escapes - old_escapes).items():
        add("EXTRA_ESCAPE", "WARN", f"转义新增: 译文多了 {count} 处 {esc}")
    raw_newline_to_literal = (
        "\\n" in old_text and "\n" in new_text and "\\n" not in new_text
    )
    literal_newline_to_raw = (
        "\n" in old_text and "\\n" in new_text and "\n" not in new_text
    )
    if raw_newline_to_literal or literal_newline_to_raw:
        add("ESCAPE_BROKEN", "WARN", "\\n 的换行转义被改成了另一种形式")
    if "\\t" in old_text and "\t" in new_text and "\\t" not in new_text:
        add("ESCAPE_BROKEN", "WARN", "\\t 被写成了可见的反斜杠+t，而不是制表符")
    if "\t" in old_text and "\\t" in new_text and "\t" not in new_text:
        add("ESCAPE_BROKEN", "WARN", "\\t 的制表符转义被改成了另一种形式")

    return errors


def check_file(fpath, rel_path):
    """检查单个翻译文件；读取失败会显式报告，不再静默当作通过。"""
    try:
        with open(fpath, "r", encoding="utf-8-sig") as stream:
            lines = stream.read().splitlines()
    except (OSError, UnicodeError) as exc:
        return [
            _issue(
                "READ_ERROR",
                "ERROR",
                0,
                rel_path,
                f"无法读取翻译文件: {exc}",
            )
        ]

    errors = []
    for pair in iter_translation_pairs(lines):
        line_no = pair.translated_line or pair.original_line
        if pair.translated is None:
            errors.append(
                _issue(
                    "COUNT_MISMATCH",
                    "ERROR",
                    pair.original_line,
                    rel_path,
                    "翻译目标缺失: 找到原文但没有对应译文行",
                    pair.original,
                    "",
                )
            )
            continue

        errors.extend(
            check_pair(pair.original, pair.translated, line_no, rel_path, pair.kind)
        )
        if (
            pair.kind == "cd"
            and pair.original_speaker
            and pair.translated_speaker
            and pair.original_speaker != pair.translated_speaker
        ):
            errors.append(
                _issue(
                    "SPEAKER_MISMATCH",
                    "ERROR",
                    line_no,
                    rel_path,
                    "角色不一致: "
                    f"原文 {pair.original_speaker} → 译文 {pair.translated_speaker}",
                    pair.original,
                    pair.translated,
                )
            )
    return errors


def _resolve_tl_dir(project, language):
    if os.path.isdir(os.path.join(project, "game", "tl", language)):
        return os.path.join(project, "game", "tl", language)
    if os.path.isdir(os.path.join(project, "tl", language)):
        return os.path.join(project, "tl", language)
    if os.path.isdir(project) and os.path.basename(project).casefold() == language.casefold():
        return project
    return None


def _collect_rpy_files(tl_dir):
    files = []
    for root, dirs, filenames in os.walk(tl_dir):
        dirs[:] = [name for name in dirs if not name.startswith((".", "_"))]
        for filename in filenames:
            if filename.endswith(".rpy"):
                files.append(os.path.join(root, filename))
    return sorted(files)


def main():
    parser = argparse.ArgumentParser(
        description="检查 Ren'Py 翻译文件中的完整性错误",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("project", help="游戏目录（含 game/ 子目录）或 tl/ 目录")
    parser.add_argument("-l", "--language", default="schinese", help="翻译语言代码")
    parser.add_argument("-o", "--output", help="输出报告文件路径")
    args = parser.parse_args()

    project = os.path.abspath(args.project)
    tl_dir = _resolve_tl_dir(project, args.language)
    if tl_dir is None:
        print(red(f"翻译目录不存在: {project}/game/tl/{args.language}"))
        return 1

    rpy_files = _collect_rpy_files(tl_dir)
    print(f"扫描翻译目录: {tl_dir}")
    print(f"翻译文件: {len(rpy_files)} 个\n")

    all_errors = []
    for filepath in rpy_files:
        rel = os.path.relpath(filepath, tl_dir)
        errors = check_file(filepath, rel)
        all_errors.extend(errors)
        if errors:
            print(yellow(f"  {rel}: {len(errors)} 个问题"))

    by_type = {}
    for error in all_errors:
        by_type.setdefault(error["type"], []).append(error)

    type_labels = {
        "LOST_VAR": "变量丢失",
        "EXTRA_VAR": "变量新增",
        "VAR_TRANSLATED": "变量名被翻译",
        "INVALID_VAR": "非法变量名",
        "FLAG_MISMATCH": "变量标志不一致",
        "LOST_TAG": "标签丢失",
        "EXTRA_TAG": "标签新增/参数改变",
        "TAG_MISMATCH": "标签结构错误",
        "LOST_ESCAPE": "转义丢失",
        "EXTRA_ESCAPE": "转义新增",
        "ESCAPE_BROKEN": "转义损坏",
        "COUNT_MISMATCH": "原文/译文数量不一致",
        "SPEAKER_MISMATCH": "角色被修改",
        "READ_ERROR": "文件读取失败",
    }

    if all_errors:
        print(f"\n{'─' * 60}")
        print(red(f"发现 {len(all_errors)} 个问题:\n"))
        for issue_type, errors in sorted(by_type.items()):
            label = type_labels.get(issue_type, issue_type)
            print(yellow(f"  [{label}] {len(errors)} 个"))
            for error in errors[:20]:
                print(f"    {error['file']}:{error['line']} — {error['desc']}")
                if error.get("original"):
                    print(f"      原文: {error['original']}")
                if error.get("translated"):
                    print(f"      译文: {error['translated']}")
            if len(errors) > 20:
                print(f"    ... 还有 {len(errors) - 20} 条")
            print()
    else:
        print(green("✓ 所有可比较的翻译条目均通过检查。"))

    if args.output and all_errors:
        output = os.path.abspath(args.output)
        os.makedirs(os.path.dirname(output), exist_ok=True)
        with open(output, "w", encoding="utf-8") as stream:
            for error in all_errors:
                stream.write(
                    f"{error['file']}:{error['line']} "
                    f"[{error['type']}] {error['desc']}\n"
                )
                if error.get("original"):
                    stream.write(f"  原文: {error['original']}\n")
                if error.get("translated"):
                    stream.write(f"  译文: {error['translated']}\n")
                stream.write("\n")
        print(f"报告已保存: {output}")

    return 1 if all_errors else 0


if __name__ == "__main__":
    sys.exit(main() or 0)
