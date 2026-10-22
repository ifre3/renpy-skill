#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""名字栏（namebox）识别与字符串翻译查找的共享实现。

背景（2026-10-18，Dissonance_0.14 实测）
----------------------------------------
Ren'Py 项目把人名做成名字栏有两大类写法：

1. ``define e = Character("Eri", color="#fff")`` —— 标准写法。
2. ``define nih = "{color=#0f37f2}Niwa{/color}"``  —— 没有 ``Character()``，
   人名是裸字符串变量，直接当 say 的说话人用（``nih "..."``）。

第 2 类项目会让**只认 ``Character("Name")`` 的工具扫出 0 个角色**，
进而报出「所有名字都已翻译」的空集假绿灯。

更隐蔽的一层：引擎查字符串翻译是**全串精确匹配**。
``renpy/translation/__init__.py`` 的 ``StringTranslation.translate()``::

    new = self.translations.get(old, None)          # 整串精确
    if new is None:
        notags = re.sub(r"\\{\\#.*?\\}", "", old)      # 只剥离 {#...} 注释标签
        new = self.translations.get(notags, None)

也就是说 ``{color=#d599aa}Eri{/color}`` 只会命中同名整串的 ``old``，
``old "Eri"`` 命中不了它；反过来补条目时也**必须连颜色标签一起写进 new**，
否则名字栏会丢掉角色配色。

运行时链路（本模块结论的源码依据）
----------------------------------
``nih "台词"``
  → ``renpy/ast.py:583`` ``Say.execute`` → ``eval_who`` 求值出字符串
  → ``renpy/exports/sayexports.py:129-130`` ``isinstance(who, basestring)``
  → ``renpy/defaultstore.py:420-422`` ``say()`` 现场 ``who = Character(who)``
  → ``renpy/character.py:1444`` ``who = self.name``
  → ``character.py:1454`` ``prefix_suffix("who", ...)``
  → ``character.py:1348-1349`` ``substitute(s, translate=True)``
  → ``renpy/substitutions.py:344-345`` ``translate_string(s)``
  → ``renpy/translation/__init__.py:545`` 精确字典查找

所以两条铁律：裸字符串说话人**会**走字符串翻译通道；
但 key 必须是**含标签的完整串**。本模块把这两点固化成 ``lookup_translation``
与 ``splice_tags``，供 checks/ 与 translate/ 的名字栏工具共用。

本模块只做「识别 + 查找 + 生成条目」，不写盘、不备份。
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

from rpy_syntax import (
    encode_rpy_string_content,
    find_string_literal,
    iter_translation_pairs,
)

# ── 扫描时的跳过目录 ────────────────────────────────────────────────────
SKIP_DIR_HINTS = ("backup", ".git", "__pycache__", "saves", "cache", "tl")

# ── 识别用的正则 ────────────────────────────────────────────────────────
# Character("Name") / Character(_("Name"))；Character 与括号间允许空格。
CHAR_DEF_RE = re.compile(
    r"""^\s*define\s+([A-Za-z_]\w*)\s*=\s*Character\s*\(\s*(?:_?\(\s*)?["']([^"'\[\]{}%\\]+)["']"""
)
# define var = "字面量"（裸字符串说话人的载体）
DEFINE_STR_RE = re.compile(r"""^\s*define\s+([A-Za-z_]\w*)\s*=\s*([rR]?["'])""")
# 说话人用法：缩进后 var 直接跟字符串，即 `nih "台词"`
SAY_RE = re.compile(r"""^\s{1,}([A-Za-z_]\w*)\s+["']""")
# 内联说话人："Name" "台词"
INLINE_SAY_RE = re.compile(r"""^\s{1,}["']([^"'\[\]{}%\\]+)["']\s+["']""")

# 资源路径 define（图片/音频）不是人名
_ASSET_RE = re.compile(
    r"""^(?:images|audio|gui|common|video|sfx|music)/|\.(?:png|jpe?g|gif|webp|ogg|mp3|wav|opus|avi|webm|ttf|otf|rpy|rpyc)$""",
    re.IGNORECASE,
)
# 纯符号名（???、……、--）是有意的悬念标记，不该翻
_SYMBOL_ONLY_RE = re.compile(r"""^[^\w\u4e00-\u9fff]+$""")
# 文本标签本体：{color=#xxx} {/color} {i} {/i} {size=+10}
_TAG_RE = re.compile(r"\{(/?)([A-Za-z][A-Za-z0-9_]*)(?:=[^}]*)?\}")
# 引擎只剥离 {#...} 翻译注释标签（见模块 docstring 的源码依据）
_ANNOTATION_TAG_RE = re.compile(r"\{\#.*?\}")


@dataclass(frozen=True)
class NameDef:
    """一个会在名字栏显示的说话人定义。"""

    var: str                      # say 语句里用的变量名（内联写法为 ""）
    value: str                    # 引擎实际比对的完整串（**含** {color=} 标签）
    plain: str                    # 去掉文本标签后的裸名（进术语表用）
    source: str                   # "file.rpy:行号"
    kind: str = "define"          # define / character / inline
    say_lines: int = 0            # 该说话人的台词条数（排优先级）
    notes: Tuple[str, ...] = field(default=())   # 扫描期提示

    @property
    def tagged(self) -> bool:
        """裸名与完整串不同 ⇒ 定义里带了文本标签。"""
        return self.value != self.plain


# ── 文本标签处理 ────────────────────────────────────────────────────────

def strip_text_tags(text: str) -> str:
    """还原成玩家在名字栏看到的样子：去 ``{color=...}`` / ``{i}`` 标签，
    并把 ``{{`` / ``}}`` 转义还原成单大括号。

    用于从定义串推出「裸名」（进术语表、报告给人看）。注意引擎查字符串翻译时
    用的是**未还原**的原始串，所以这一步只影响 key 的推导，不影响匹配本身。
    """
    out: List[str] = []
    i = 0
    while i < len(text):
        if text[i] == "{":
            if text[i:i + 2] == "{{":          # 转义的开括号
                out.append("{")
                i += 2
                continue
            m = _TAG_RE.match(text, i)
            if m:
                i = m.end()
                continue
        elif text[i] == "}" and text[i:i + 2] == "}}":   # 转义的闭括号
            out.append("}")
            i += 2
            continue
        out.append(text[i])
        i += 1
    return "".join(out)


def _text_segments(value: str) -> List[Tuple[int, int]]:
    """返回非标签文本段的 ``(start, end)`` 半开区间。"""
    spans: List[Tuple[int, int]] = []
    pos = 0
    for m in _TAG_RE.finditer(value):
        if m.start() > pos:
            spans.append((pos, m.start()))
        pos = m.end()
    if pos < len(value):
        spans.append((pos, len(value)))
    return [(s, e) for s, e in spans if value[s:e].strip()]


def splice_tags(value: str, translation: str) -> Optional[str]:
    """把裸译名塞回带标签的骨架，**保留标签本体**（角色配色不丢）。

    ``splice_tags("{color=#d599aa}Eri{/color}", "绘里")``
    → ``"{color=#d599aa}绘里{/color}"``

    只有一个文本段时才做替换；多段（``{b}Fox{/b} the Fox``）语义有歧义，
    返回 ``None`` 交给调用方报告，而不是猜一个错答案。
    """
    if value == translation:
        return value
    segments = _text_segments(value)
    if len(segments) != 1:
        return None
    start, end = segments[0]
    return value[:start] + translation + value[end:]


# ── 字符串翻译查找 ──────────────────────────────────────────────────────

def lookup_translation(value: str, strings: Dict[str, str]) -> Optional[str]:
    """按引擎语义查字符串翻译：整串优先，其次剥离 ``{#...}`` 再查。

    镜像 ``renpy/translation/__init__.py:545-564``，**不做**标签剥离——
    引擎也不做。返回 ``None`` 表示没有条目。
    """
    hit = strings.get(value)
    if hit is not None:
        return hit
    notags = _ANNOTATION_TAG_RE.sub("", value)
    if notags != value:
        hit = strings.get(notags)
        if hit is not None:
            return hit
    return None


def load_tl_strings(tl_dir: str) -> Dict[str, str]:
    """读 ``tl/<lang>`` 下全部 ``old``→``new`` 映射（跳过备份）。"""
    result: Dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(tl_dir):
        dirnames[:] = [
            d for d in dirnames
            if not any(h in os.path.relpath(os.path.join(dirpath, d), tl_dir).lower()
                       for h in ("backup", "__pycache__", "bilingual_auto"))
        ]
        for fn in sorted(filenames):
            if not (fn.endswith(".rpy") and not fn.endswith(".rpy.bak")):
                continue
            try:
                with open(os.path.join(dirpath, fn), encoding="utf-8", errors="replace") as fh:
                    lines = fh.read().splitlines()
            except OSError:
                continue
            for pair in iter_translation_pairs(lines):
                if pair.kind == "on":
                    result[pair.original] = pair.translated or ""
    return result


# ── 扫描 ────────────────────────────────────────────────────────────────

def iter_rpy_files(game_dir: str) -> Iterator[str]:
    """遍历游戏脚本：排除 ``tl/``、备份、缓存目录与 ``.bak``。"""
    for dirpath, dirnames, filenames in os.walk(game_dir):
        dirnames[:] = [
            d for d in dirnames
            if not any(h in os.path.relpath(os.path.join(dirpath, d), game_dir).lower()
                       for h in SKIP_DIR_HINTS)
        ]
        for fn in sorted(filenames):
            if fn.endswith(".rpy") and not fn.endswith(".rpy.bak"):
                yield os.path.join(dirpath, fn)


def _read_lines(path: str) -> List[str]:
    try:
        with open(path, encoding="utf-8-sig", errors="replace") as fh:
            return fh.read().splitlines()
    except OSError:
        return []


def scan_namebox_names(game_dir: str) -> List[NameDef]:
    """扫出全部会在名字栏显示的说话人，三种写法一视同仁。

    * ``define e = Character("Eri", ...)``            → kind=character
    * ``define nih = "{color=#0f37f2}Niwa{/color}"``  → kind=define（**带标签**）
    * ``"Name" "台词"`` 内联说话人                     → kind=inline

    裸 ``define`` 只有**真的被当说话人用过**（``nih "..."``）才收；
    否则 ``define monday = "images/calender/monday.png"`` 这类资源会全被误收。
    返回按台词数降序排列。
    """
    files = sorted(iter_rpy_files(game_dir))
    defines: Dict[str, NameDef] = {}
    used: Dict[str, int] = {}
    inline: Dict[str, NameDef] = {}
    inline_counts: Dict[str, int] = {}

    for path in files:
        rel = os.path.relpath(path, game_dir).replace("\\", "/")
        for lineno, line in enumerate(_read_lines(path), 1):
            m = CHAR_DEF_RE.match(line)
            if m:
                var, name = m.group(1), m.group(2).strip()
                if name and var not in defines:
                    defines[var] = NameDef(var, name, name, f"{rel}:{lineno}", "character")
                continue

            m = SAY_RE.match(line)
            if m:
                var = m.group(1)
                used[var] = used.get(var, 0) + 1
                continue

            m = INLINE_SAY_RE.match(line)
            if m:
                name = m.group(1).strip()
                # 与 define 分支同一把尺子：纯符号（? / ??? / --）是悬念标记，
                # 不是名字，不该翻也不该报缺失。
                if name and not _SYMBOL_ONLY_RE.match(name):
                    inline_counts[name] = inline_counts.get(name, 0) + 1
                    inline.setdefault(
                        name, NameDef("", name, name, f"{rel}:{lineno}", "inline"))
                continue

            m = DEFINE_STR_RE.match(line)
            if m:
                # 必须从**引号本身**开始切：DEFINE_STR_RE 的 group(2) 就是引号，
                # 用 m.end() 会把定界引号切掉、find_string_literal 匹到收尾引号上。
                literal = find_string_literal(line[m.start(2):])
                if literal is None or not literal.closed:
                    continue
                value = literal.value
                plain = strip_text_tags(value).strip()
                var = m.group(1)
                if not plain or var in defines:
                    continue
                notes: List[str] = []
                if _ASSET_RE.match(value):
                    continue
                if "[" in plain:
                    notes.append("动态名（插值）")     # t = "[pn]"
                    continue
                if _SYMBOL_ONLY_RE.match(plain):
                    notes.append("悬念标记，保留原样")  # y = "???"
                    continue
                defines[var] = NameDef(
                    var, value, plain, f"{rel}:{lineno}", "define", notes=tuple(notes)
                )

    out: List[NameDef] = []
    for var, nd in defines.items():
        out.append(
            NameDef(nd.var, nd.value, nd.plain, nd.source, nd.kind,
                    say_lines=used.get(var, 0), notes=nd.notes)
        )
    out.extend(
        NameDef(nd.var, nd.value, nd.plain, nd.source, nd.kind,
                say_lines=inline_counts.get(nd.plain, 0), notes=nd.notes)
        for nd in inline.values()
    )

    # 同一条串可能既是 define 变量、又被内联说过（`define c = "Cashier"` +
    # `"Cashier" "..."`）。名字栏显示的是同一个串，**必须合并成一条**：
    # 否则生成两条 old 相同的条目，引擎 add_string_translation 会直接抛
    # "A translation for ... already exists"（translation/__init__.py:534）。
    merged: Dict[str, NameDef] = {}
    for nd in sorted(out, key=lambda n: (-n.say_lines, n.source)):
        prev = merged.get(nd.value)
        if prev is None:
            merged[nd.value] = nd
        elif nd.source not in prev.notes:
            merged[nd.value] = NameDef(
                prev.var, prev.value, prev.plain, prev.source, prev.kind,
                prev.say_lines,
                prev.notes + (f"同名来源: {nd.source}",),
            )

    result = sorted(merged.values(), key=lambda n: (-n.say_lines, n.plain.lower()))
    return result


# ── 生成条目 ────────────────────────────────────────────────────────────

def render_entry(old: str, new: str, comment: str = "") -> str:
    """渲染一条 ``old``/``new`` 对（保留标签，见 ``splice_tags``）。

    ``comment`` 传**不带** ``#`` 的纯文本（通常是来源位置），前缀由这里补。
    """
    lines = []
    if comment:
        lines.append(f"    # {comment}")
    lines.append(f'    old "{encode_rpy_string_content(old)}"')
    lines.append(f'    new "{encode_rpy_string_content(new)}"')
    lines.append("")
    return "\n".join(lines)


def render_strings_block(language: str, entries: Iterable[str], header: str = "") -> str:
    """渲染一个完整的 ``translate <lang> strings:`` 块。

    ``header`` 的每一行会变成 ``##`` 注释并放在 **translate 语句之前**——
    放在块内会让非缩进注释落进已开启的语句块，交给 SDK lint 判定更稳妥的做法是前置。
    """
    head = []
    if header:
        for line in header.splitlines():
            head.append(f"## {line}".rstrip())
        head.append("")
    head.append(f"translate {language} strings:")
    head.append("")
    return "\n".join(head + list(entries))