#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""names/make_glossary.py 的人名取证：define + 颜色标签写法（2026-10-13）。

Dissonance_0.14 完全不用 Character()，25 个角色全写成::

    define nih = "{color=#0f37f2}Niwa{/color}"   #hirai

于是 scan_characters 返回 0 个、人名候选整个丢掉，术语表草稿里只剩 UI
字符串（"About"→"关于" 之类）。这里补上该写法的识别并锁住边界。

边界取舍：只认整值就是单个 color 标签包起来的纯字面量——拼接、插值、
多标签套嵌的动态名依然跳过（那类名是运行时才知道的，取进来是噪音）。

运行（仅标准库）::

    cd renpy/scripts/tests
    python -m unittest test_names_glossary -v
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_NAMES = os.path.join(os.path.dirname(_HERE), "names")
for p in (_NAMES,):
    if p not in sys.path:
        sys.path.insert(0, p)

import make_glossary as G  # noqa: E402


def _mkdir(lines: dict):
    """按 {相对路径: 内容} 建临时 game 目录，返回 Path。"""
    root = Path(tempfile.mkdtemp()) / "game"
    root.mkdir(parents=True)
    for rel, text in lines.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return root


class TestScanCharacters(unittest.TestCase):
    """scan_characters 同时认 Character() 与 define+颜色标签两种写法。"""

    def test_define_color_tag_is_recognized(self):
        game = _mkdir({
            "script.rpy": (
                'define nih = "{color=#0f37f2}Niwa{/color}"   #hirai\n'
                'define atk = "{color=#a23c25}Atsuko{/color}" #kuno\n'
            ),
        })
        found = G.scan_characters(game)
        self.assertEqual(sorted(found), ["Atsuko", "Niwa"])
        self.assertIn("script.rpy:1", found["Niwa"])

    def test_character_call_still_works(self):
        """既有 Character() 写法不受影响。"""
        game = _mkdir({"c.rpy": 'define e = Character("Eri", color="#fff")\n'})
        self.assertEqual(sorted(G.scan_characters(game)), ["Eri"])

    def test_both_styles_coexist(self):
        game = _mkdir({
            "s.rpy": 'define nih = "{color=#fff}Niwa{/color}"\n',
            "c.rpy": 'define e = Character("Eri")\n',
        })
        self.assertEqual(sorted(G.scan_characters(game)), ["Eri", "Niwa"])

    def test_dynamic_names_skipped(self):
        """插值/拼接/绕变量构造的名字不收——运行时才知道，收进来是噪音。"""
        game = _mkdir({
            "d.rpy": (
                'define t = "[pn]"\n'                              # 玩家自定义名
                'define n1 = "{color=#fff}" + pname + "{/color}"\n'  # 拼接
                'define n2 = "{color=#fff}{who}{/color}"\n'        # 嵌套插值
                'define n3 = "Stranger"\n'                         # 无标签，非人名约定
            ),
        })
        found = G.scan_characters(game)
        self.assertEqual(found, {}, msg=f"动态名被误收: {found}")

    def test_tl_dir_not_scanned(self):
        """tl/ 下的同名定义不该混进来（那边是译文侧，取进来会污染对照）。

        只在 tl/ 放文件时已过滤掉 tl → 等价于无源码（见下一条断言）；所以这里补一个源码側存在、tl 側也存在的组合来隔离验证。"""
        # 组合：源码有 Eri，tl 里还有一个 Niwa —— 结果只应有 Eri
        game = _mkdir({
            "c.rpy": 'define e = Character("Eri")\n',
            "tl/schinese/x.rpy": 'define nih = "{color=#fff}Niwa{/color}"\n',
        })
        self.assertEqual(sorted(G.scan_characters(game)), ["Eri"])

    def test_no_source_returns_none(self):
        """纯 .rpyc 发行版：无源码返回 None 以便上层提示反编译。"""
        self.assertIsNone(G.scan_characters(_mkdir({"only.txt": "x"})))


if __name__ == "__main__":
    unittest.main(verbosity=2)
