#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ren'Py 翻译文本的轻量解析工具。

只解析翻译优化所需的稳定子集：``old/new``、对话注释和对应的单行字符串。
与散落在各脚本中的 ``(.*)`` 正则相比，本模块能正确处理：

* 双引号、单引号和字符串前缀；
* ``\\\"`` / ``\\\\`` 等转义；
* 任意角色变量名（``c_x``、``e``、``mmc`` 等），不再局限于 ``c_xxx``；
* 缺失的译文目标，供完整性检查报告而不是静默漏过。

本模块不会尝试解析完整 Ren'Py 语法；完整语法仍应交给 Ren'Py SDK lint。
"""

from __future__ import annotations

import ast
import re
import warnings
from dataclasses import dataclass
from typing import Iterator, Optional


_STRING_PREFIX_CHARS = frozenset("rRuUbBfF")
_SOURCE_PATH_RE = re.compile(
    r"^(?:game|renpy)[/\\][^:]+(?:\.rpyc?|\.rpym?):\d+", re.IGNORECASE
)
_KEYWORD_LINE_RE = re.compile(r"^\s*(old|new)\b", re.IGNORECASE)
_IDENTIFIER_RE = re.compile(r"[A-Za-z_]\w*")

# 这些是 say/translate 语句属性，不是角色变量。
_SAY_MODIFIERS = {
    "extend",
    "centered",
    "vcentered",
    "nvl",
    "voice",
    "with",
    "id",
    "attributes",
    "what_prefix",
    "what_suffix",
    "what_aftername",
    "show",
    "hide",
    "scene",
    "play",
    "stop",
    "queue",
    "pause",
    "nobreak",
    "slow",
    "fast",
    "fade",
    "window",
    "restore",
    "roll",
    "new",
    "old",
}


@dataclass(frozen=True)
class StringLiteral:
    """一个 Python/Ren'Py 字符串字面量。``value`` 已解码，``raw`` 保留源码。"""

    raw: str
    value: str
    start: int
    end: int
    quote: str
    closed: bool


@dataclass(frozen=True)
class TranslationPair:
    """一个原文/译文对。缺失目标时 ``translated`` 为 ``None``。"""

    kind: str  # tb / cd / on
    original: str
    translated: Optional[str]
    original_line: int  # 1-based
    translated_line: Optional[int]  # 1-based
    original_speaker: str = ""
    translated_speaker: str = ""


def _decode_literal(raw: str, quote: str, closed: bool) -> str:
    """尽最大努力把字面量解码为运行时文本，失败时退回引号内源码。"""
    if not closed:
        return raw[len(quote) :]
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            value = ast.literal_eval(raw)
        return value if isinstance(value, str) else raw
    except (SyntaxError, ValueError):
        return raw[len(quote) : -len(quote)]


def find_string_literal(text: str) -> Optional[StringLiteral]:
    """返回文本中的第一个字符串字面量。

    扫描器而不是正则可正确跳过 ``\\\"``，并能识别三引号。未闭合字面量也会
    返回（``closed=False``），供诊断工具使用。
    """
    i = 0
    while i < len(text):
        if text[i] not in ("'", '"'):
            i += 1
            continue

        quote_char = text[i]
        triple = text[i : i + 3] == quote_char * 3
        quote = quote_char * 3 if triple else quote_char

        # 把紧邻引语的 r/u/b/f 前缀纳入 raw。
        prefix_start = i
        while prefix_start > 0 and text[prefix_start - 1] in _STRING_PREFIX_CHARS:
            prefix_start -= 1
        if prefix_start < i - 2:
            prefix_start = i

        j = i + len(quote)
        closed = False
        while j < len(text):
            if text[j] == "\\":
                j += 2
                continue
            if text.startswith(quote, j):
                j += len(quote)
                closed = True
                break
            j += 1
        if not closed:
            j = len(text)

        raw = text[prefix_start:j]
        value = _decode_literal(raw, quote, closed)
        return StringLiteral(
            raw=raw,
            value=value,
            start=prefix_start,
            end=j,
            quote=quote,
            closed=closed,
        )
    return None


def decode_quoted_literal(raw: str) -> str:
    """解码带引号的字符串字面量，如 ``"a \\"b\\" c"`` → ``a "b" c``。

    供各检查器把正则捕获到的原始字面量（含首尾引号）还原为运行时文本，
    与 ``load_trans`` 等解析方的键保持一致。字面量无法闭合解码时退回
    去掉首尾引号的原文。
    """
    if len(raw) >= 2 and raw[0] in ("'", '"') and raw[-1] == raw[0]:
        literal = find_string_literal(raw)
        if literal is not None and literal.closed:
            return literal.value
        return raw[1:-1]
    return raw


def _speaker_from_prefix(prefix: str) -> str:
    """从 say 语句前缀提取角色变量；修饰属性会被跳过。"""
    for token in _IDENTIFIER_RE.findall(prefix):
        if token.lower() not in _SAY_MODIFIERS:
            return token
    return ""


def _iter_text_tag_matches(text: str):
    """提取文本标签，且不把 ``{{`` 转义识别成标签。"""
    index = 0
    tag_re = re.compile(r"\{(/?)([A-Za-z][A-Za-z0-9_]*)(?:=[^}]*)?\}")
    while index < len(text):
        if text[index] != "{":
            index += 1
            continue
        if index + 1 < len(text) and text[index + 1] == "{":
            index += 2
            continue
        match = tag_re.match(text, index)
        if match:
            yield match
            index = match.end()
        else:
            index += 1


def _mask_text_tags(text: str) -> str:
    """遮住标签本体，防止把 ``{a=[url]}`` 的参数误当成文本插值。"""
    chars = list(text)
    for match in _iter_text_tag_matches(text):
        for index in range(match.start(), match.end()):
            if chars[index] not in "\r\n":
                chars[index] = " "
    return "".join(chars)


def iter_bracket_spans(text: str):
    """产出非转义 Ren'Py 插值的 ``(start, end)`` 半开区间。

    Ren'Py 允许 ``[player.names[0]]`` 和带格式说明的任意 Python 表达式，
    因此不能用简单正则。扫描器处理嵌套方括号和表达式内字符串，同时跳过
    ``[[`` 转义及文本标签参数中的方括号。
    """
    scan_text = _mask_text_tags(text)
    index = 0
    while index < len(scan_text):
        if scan_text[index] != "[":
            index += 1
            continue
        if index + 1 < len(scan_text) and scan_text[index + 1] == "[":
            index += 2
            continue
        if index > 0 and scan_text[index - 1] == "[":
            index += 1
            continue

        depth = 1
        cursor = index + 1
        quote = None
        closing_index = None
        while cursor < len(scan_text):
            char = scan_text[cursor]
            if quote is not None:
                if char == "\\":
                    cursor += 2
                    continue
                if char == quote:
                    quote = None
            elif char in ("'", '"'):
                quote = char
            elif char == "\\":
                cursor += 2
                continue
            elif char == "[":
                depth += 1
            elif char == "]":
                depth -= 1
                if depth == 0:
                    closing_index = cursor
                    break
            cursor += 1

        if closing_index is None:
            # 未闭合括号由 SDK lint 报告；这里继续扫描，避免遮蔽后续有效插值。
            index += 1
            continue
        yield index, closing_index + 1
        index = closing_index + 1


def iter_bracket_groups(text: str):
    """产出非转义插值的 ``(内容, 完整匹配)``。"""
    for start, end in iter_bracket_spans(text):
        yield text[start + 1 : end - 1], text[start:end]


def encode_rpy_string_content(text: str, quote: str = '"') -> str:
    """把运行时文本编码为 .rpy 单行字符串内容。"""
    quote_char = quote[0]
    result = []
    for char in text:
        if char == "\\":
            result.append("\\\\")
        elif char == quote_char:
            result.append("\\" + char)
        elif char == "\n":
            result.append("\\n")
        elif char == "\r":
            result.append("\\r")
        elif char == "\t":
            result.append("\\t")
        else:
            result.append(char)
    return "".join(result)


def replace_literal_content(
    line: str, literal: StringLiteral, translated: str
) -> str:
    """替换字面量内容，保留语句前缀、引号类型和尾部属性。"""
    encoded = encode_rpy_string_content(translated, literal.quote)
    quote = literal.quote
    return line[: literal.start] + quote + encoded + quote + line[literal.end :]


def _parse_keyword_line(line: str, keyword: str) -> Optional[StringLiteral]:
    match = re.match(rf"^\s*{re.escape(keyword)}\b", line, re.IGNORECASE)
    if not match:
        return None
    literal = find_string_literal(line[match.end() :])
    if literal is None:
        return None
    offset = match.end()
    return StringLiteral(
        raw=literal.raw,
        value=literal.value,
        start=offset + literal.start,
        end=offset + literal.end,
        quote=literal.quote,
        closed=literal.closed,
    )


def parse_old_line(line: str) -> Optional[StringLiteral]:
    return _parse_keyword_line(line, "old")


def parse_new_line(line: str) -> Optional[StringLiteral]:
    return _parse_keyword_line(line, "new")


_CJK_RE = re.compile(r"[\u3000-\u303f\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff00-\uffef]")


def parse_original_comment(line: str):
    """解析翻译块中的英文原文注释。

    返回 ``(StringLiteral, speaker)``；普通注释和 ``# game/...`` 路径注释
    返回 ``None``。

    严格判定，避免把**手写文档注释**误当成原文：
    - 引号必须闭合（散文里 ``Ren'Py`` 这类未闭合单引号不算）；
    - 闭合引号之后只允许 Ren'Py 参数/关键字（如 ``(multiple=2)``、``nointeract``），
      出现中日韩字符说明是在正文里引用了一段话，不是 ``# 角色 "原文"`` 注释。
    """
    stripped = line.strip()
    if not stripped.startswith("#"):
        return None
    content = stripped[1:].strip()
    if not content or _SOURCE_PATH_RE.match(content):
        return None
    literal = find_string_literal(content)
    if literal is None or not literal.closed:
        return None
    tail = content[literal.end:].strip()
    if tail and _CJK_RE.search(tail):
        return None
    return literal, _speaker_from_prefix(content[: literal.start])


def parse_translation_line(line: str):
    """解析翻译目标行，返回 ``(StringLiteral, speaker)``。"""
    stripped = line.strip()
    if (
        not stripped
        or stripped.startswith("#")
        or re.match(r"^translate\b", stripped, re.IGNORECASE)
        or parse_old_line(line) is not None
        or parse_new_line(line) is not None
    ):
        return None
    literal = find_string_literal(line)
    if literal is None:
        return None
    return literal, _speaker_from_prefix(line[: literal.start])


def _is_skippable_between_pair(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if stripped.startswith("#"):
        # 另一个带字符串的注释是下一条原文，不能跨越。
        return parse_original_comment(line) is None
    return bool(re.match(r"^translate\b", stripped, re.IGNORECASE))


def _find_new_after_old(lines: list[str], start_index: int, max_gap: int = 12):
    end = min(len(lines), start_index + max_gap + 1)
    for index in range(start_index + 1, end):
        line = lines[index]
        if not line.strip() or line.strip().startswith("#"):
            continue
        new_literal = parse_new_line(line)
        if new_literal is not None:
            return index, new_literal
        if parse_old_line(line) is not None:
            break
    return None, None


def _find_translation_after_original(
    lines: list[str], start_index: int, max_gap: int = 8
):
    end = min(len(lines), start_index + max_gap + 1)
    for index in range(start_index + 1, end):
        line = lines[index]
        if _is_skippable_between_pair(line):
            continue

        # 不允许跨到下一条原文或 old 条目去误配译文。
        if parse_original_comment(line) is not None or parse_old_line(line) is not None:
            break

        parsed = parse_translation_line(line)
        if parsed is not None:
            return index, parsed[0], parsed[1]
        break
    return None, None, ""


def iter_translation_pairs(lines: list[str]) -> Iterator[TranslationPair]:
    """逐行解析 old/new 和对话原文/译文对。

    找不到译文时仍会产出一对（``translated is None``），让调用方可以报告
    ``COUNT_MISMATCH``。解析器不跨过下一条原文或 old 行，避免行号漂移时
    把译文写到错误条目。
    """
    index = 0
    total = len(lines)
    while index < total:
        old_literal = parse_old_line(lines[index])
        if old_literal is not None:
            target_index, new_literal = _find_new_after_old(lines, index)
            yield TranslationPair(
                kind="on",
                original=old_literal.value,
                translated=new_literal.value if new_literal is not None else None,
                original_line=index + 1,
                translated_line=target_index + 1 if target_index is not None else None,
            )
            index = target_index + 1 if target_index is not None else index + 1
            continue

        source = parse_original_comment(lines[index])
        if source is not None:
            original_literal, original_speaker = source
            target_index, translated_literal, translated_speaker = (
                _find_translation_after_original(lines, index)
            )
            kind = "cd" if original_speaker or translated_speaker else "tb"
            yield TranslationPair(
                kind=kind,
                original=original_literal.value,
                translated=(
                    translated_literal.value if translated_literal is not None else None
                ),
                original_line=index + 1,
                translated_line=target_index + 1 if target_index is not None else None,
                original_speaker=original_speaker,
                translated_speaker=translated_speaker,
            )
            index = target_index + 1 if target_index is not None else index + 1
            continue

        index += 1


def split_lines_keepends(text: str) -> list[str]:
    """兼容旧调用方的分行助手，同时避免对内容做隐式 strip。"""
    return text.splitlines(keepends=True)
