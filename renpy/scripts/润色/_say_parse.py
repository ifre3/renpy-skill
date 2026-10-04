# -*- coding: utf-8 -*-
"""tl 文件 say 条目解析共用模块（润色工具族的依赖）。

条目结构::

    {"file": 相对tl_dir路径, "line": 原文注释行号, "src_line": 译文行号,
     "type": "tb"/"cd", "orig": 原文, "trans": 译文, "char": 角色变量(cd才有)}

结构与 ``autotranslate.py scan`` 兼容，可直接作为 ``apply --overwrite`` 的锚点。

解析统一走 ``公共/rpy_syntax.py``（与 autotranslate / tl_check 同一解析层，
正确处理转义、单双引号、任意角色变量、``# game/`` 路径注释），本模块只做
条目字典适配；old/new（on）条目不在此产出，与旧版正则行为一致。
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "公共"))
from rpy_syntax import iter_translation_pairs  # noqa: E402


def iter_say_entries(tl_dir):
    """遍历 tl 目录所有 .rpy，yield say 条目 dict（tb/cd；空译文仍产出，调用方过滤）。"""
    for f in sorted(Path(tl_dir).glob("*.rpy")):
        lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        for pair in iter_translation_pairs(lines):
            if pair.kind == "on" or pair.translated is None or pair.translated_line is None:
                continue
            char = pair.translated_speaker or pair.original_speaker
            yield {
                "file": f.name, "line": pair.original_line,
                "src_line": pair.translated_line,
                "type": "cd" if char else "tb",
                "orig": pair.original, "trans": pair.translated,
                "char": char,
            }


def strip_tags(s):
    """剥掉 {…} 文本标签并去首尾空白，用于同文比较。"""
    return re.sub(r"\{[^}]*\}", "", s).strip()
