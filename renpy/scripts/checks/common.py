#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ren'Py 翻译检测工具集的共享模块。"""

import os
import re
import sys

# ── 编码处理 ──
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── 共享解析层 ──
# 字符串字面量的解析/解码统一走 shared/rpy_syntax.py：它能正确处理 \"
# \\\\ 等转义、单双引号与三引号。此前各检查器自带的 ``old "(.*)"/[^"]+``
# 弱正则会在含转义引号的条目上截断文本、误报「未翻」。
_TOOLS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SHARED_DIR = os.path.join(_TOOLS_DIR, "shared")
if _SHARED_DIR not in sys.path:
    sys.path.insert(0, _SHARED_DIR)

from rpy_syntax import (  # noqa: E402
    decode_quoted_literal,
    parse_new_line,
    parse_old_line,
)


def green(s):
    return f"\033[92m{s}\033[0m" if sys.stdout.isatty() else s


def red(s):
    return f"\033[91m{s}\033[0m" if sys.stdout.isatty() else s


def yellow(s):
    return f"\033[93m{s}\033[0m" if sys.stdout.isatty() else s


# ── 翻译函数排除模式 ──
TRANS_FUNC_PAT = r"_{1,3}\s*\("

# ── 跳过列表 ──
SKIP_PREFIX = ("fonts/", "gui/", "images/", "audio/", "video/", "tl/")
SKIP_SUFFIX = (
    ".ttf", ".otf", ".png", ".jpg", ".jpeg", ".gif", ".webp",
    ".mp3", ".ogg", ".wav", ".opus", ".flac", ".mp4", ".webm", ".ogv",
    ".rpy", ".rpym", ".py", ".txt",
)
SKIP_WORDS = {
    "left", "right", "center", "top", "bottom", "xfill", "yfill",
    "true", "false", "none", "window", "fullscreen", "default",
    "small", "full",
    "preferences", "save", "load", "history", "help", "about",
    "main_menu", "game_menu",
    "enter", "space", "escape", "tab", "ctrl",
    "keyboard", "mouse", "gamepad",
    "say", "choice", "input", "nvl",
    "before", "after",
    "vertical", "horizontal",
}
TEXT_KW = {"textbutton", "text", "label", "button"}
RENPY_FUNC_KW = {"renpy.input", "renpy.notify"}

# ── 项目绑定的自定义 screen 名 ──
#
# 语义：这些是**具体游戏自造的 screen 名**，Ren'Py 本身没有 `reward_button` /
# `end_screen_text` 这样的标准组件。换游戏时它们大概率不适用，留在代码里
# 只会造成两类误判：
#   1. 别人的项目里出现同名 screen → 被误当成「翻译检查项」，漏报真问题；
#   2. 自己的项目用了别的自定义 screen → 检测不到（真漏报）。
#
# 因此改为：内置清单只保留「Ren'Py 标准 gui 组件 + 本工具历史上验证过的名字」，
# 并支持从项目侧 JSON 追加/覆盖，不必改代码。
_BUILTIN_SCREEN_CALL_KW = (
    "game_menu",
    "heading",
    "settings_item",
    "tab_button",
)

_SCREEN_CALL_JSON = "renpy_screen_calls.json"
_EXTRA_SCREEN_CALL = []
_REPLACE_SCREEN_CALL = None


def _load_screen_call_kw():
    """读项目侧的 screen 名配置，返回 (extra, replace_whole_set)。

    `extra`     追加到内置清单
    `replace`   完全替换内置清单（用于「这游戏用自己的命名体系」）

    查找顺序：当前工作目录 → 环境变量 RENPY_SCREEN_CALL_KW 指向的路径。
    找不到就静默用内置值：这不是错误，只是检测面窄一些。
    """
    import json

    path = os.environ.get("RENPY_SCREEN_CALL_KW")
    if not path:
        cand = os.path.join(os.getcwd(), _SCREEN_CALL_JSON)
        path = cand if os.path.isfile(cand) else None
    if not path or not os.path.isfile(path):
        return [], None
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        print(f"[WARN] {_SCREEN_CALL_JSON} 读取失败，忽略：{exc}", file=sys.stderr)
        return [], None
    if isinstance(data, list):
        return [str(x) for x in data], None
    if isinstance(data, dict):
        return (
            [str(x) for x in data.get("extra", [])],
            [str(x) for x in data["replace"]] if "replace" in data else None,
        )
    return [], None


_extra, _replace = _load_screen_call_kw()
SCREEN_CALL_KW = set(_replace) if _replace is not None else set(_BUILTIN_SCREEN_CALL_KW)
SCREEN_CALL_KW |= set(_EXTRA_SCREEN_CALL) | set(_extra)


def screen_call_kw_source():
    """给报告用：这批 screen 名是从哪来的（内置 / JSON extra / JSON replace）。"""
    if _replace is not None:
        return "json:replace"
    if _extra:
        return "builtin+json:extra"
    return "builtin"


def should_skip(s):
    if not s:
        return True
    if s.lower() in SKIP_WORDS:
        return True
    if any(s.startswith(p) for p in SKIP_PREFIX):
        return True
    if any(s.endswith(suf) for suf in SKIP_SUFFIX):
        return True
    if re.fullmatch(r"\[.*?\]", s):
        return True
    return False


def scan_files(project):
    game = (
        os.path.join(project, "game")
        if os.path.isdir(os.path.join(project, "game"))
        else project
    )
    files = []
    for root, dirs, fnames in os.walk(game):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "tl"]
        files.extend(os.path.join(root, f) for f in fnames if f.endswith(".rpy"))
    return sorted(files)


def load_trans(tl_dir, lang):
    """加载 tl/<lang>/ 的 old→new 映射，两侧均为解码后的运行时文本。

    解析统一走 shared/rpy_syntax.py（正确处理 ``\\\"`` 等转义），键与
    各检查器源侧抽取（同样解码后）一致；不再用 ``old "(.*)"`` 弱正则。
    """
    trans = {}
    lang_dir = os.path.join(tl_dir, lang)
    if not os.path.isdir(lang_dir):
        return trans

    for root, dirs, files in os.walk(lang_dir):
        for f in files:
            if not f.endswith(".rpy"):
                continue
            try:
                with open(os.path.join(root, f), "r", encoding="utf-8") as fh:
                    last = None
                    for line in fh:
                        old_lit = parse_old_line(line)
                        if old_lit is not None:
                            last = old_lit.value
                            continue
                        new_lit = parse_new_line(line)
                        if new_lit is not None and last is not None:
                            trans[last] = new_lit.value
                            last = None
            except Exception:
                continue
    return trans


def print_items(items, trans, title, limit=80, severity="info"):
    total = len(items)
    covered = sum(1 for i in items if i["text"] in trans)
    tag = {"bug": red("BUG"), "warn": yellow("WARN"), "info": "INFO"}[severity]
    print(f"\n  [ {tag} {title} ]  共 {total}  已翻 {covered}  未翻 {total - covered}")
    for i in items[:limit]:
        t = i["text"]
        f = os.path.basename(i["file"])
        extra = ""
        if "func" in i:
            extra = f" [{i['func']}]"
        elif "screen" in i:
            extra = f" [{i['screen']}]"
        elif "note" in i:
            extra = f" ({i['note']})"
        if "context" in i:
            extra += f'  ← "{i["context"]}"'
        if t in trans:
            print(f'    {green("OK")} L{i["line"]:>5d} {f:22s} "{t}"{extra} -> "{trans[t]}"')
        else:
            print(f'    {red("!!")} L{i["line"]:>5d} {f:22s} "{t}"{extra}')
    if len(items) > limit:
        print(f"    ... 还有 {len(items) - limit} 条")
