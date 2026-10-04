#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ren'Py 翻译检测工具集的共享模块。"""

import os
import re
import sys

# ── 编码处理 ──
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


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
SCREEN_CALL_KW = {
    "heading", "settings_item", "tab_button",
    "end_screen_text", "reward_button", "game_menu",
}
RENPY_FUNC_KW = {"renpy.input", "renpy.notify"}


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
    trans = {}
    lang_dir = os.path.join(tl_dir, lang)
    if not os.path.isdir(lang_dir):
        return trans
    old_dq = re.compile(r'^\s*old\s+"(.*)"\s*$')
    new_dq = re.compile(r'^\s*new\s+"(.*)"\s*$')
    old_sq = re.compile(r"^\s*old\s+'(.*)'\s*$")
    new_sq = re.compile(r"^\s*new\s+'(.*)'\s*$")

    def _match(line, *patterns):
        for p in patterns:
            m = p.match(line)
            if m:
                return m.group(1)
        return None

    for root, dirs, files in os.walk(lang_dir):
        for f in files:
            if not f.endswith(".rpy"):
                continue
            try:
                with open(os.path.join(root, f), "r", encoding="utf-8") as fh:
                    last = None
                    for line in fh:
                        val = _match(line, old_dq, old_sq)
                        if val is not None:
                            last = val
                            continue
                        val = _match(line, new_dq, new_sq)
                        if val is not None and last is not None:
                            trans[last] = val
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
