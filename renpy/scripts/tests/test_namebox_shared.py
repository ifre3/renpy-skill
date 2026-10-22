#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""shared/namebox.py 的名字栏识别与**引擎等价**的翻译查找（2026-10-18）。

背景：Dissonance_0.14 完全不用 ``Character()``，人名是带颜色标签的裸 define::

    define nih = "{color=#0f37f2}Niwa{/color}"
    nih "Ready."

只认 ``Character("Name")`` 的工具会扫出 0 个名字并误报「全部已翻译」。

更隐蔽的一层：引擎查字符串翻译是**全串精确匹配**
（``renpy/translation/__init__.py:545-564``），只剥离 ``{#...}`` 注释标签。
所以 ``old "Eri"`` 命中不了 ``{color=#d599aa}Eri{/color}``——这正是
之前误判「16 个已翻译」的原因。本模块把引擎语义原样实现并锁死。

运行（仅标准库）::

    cd renpy/scripts/tests
    python -m unittest test_namebox_shared -v
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_SHARED = os.path.join(os.path.dirname(_HERE), "shared")
if _SHARED not in sys.path:
    sys.path.insert(0, _SHARED)

import namebox as N  # noqa: E402


def _game(lines: dict) -> Path:
    root = Path(tempfile.mkdtemp()) / "game"
    root.mkdir(parents=True)
    for rel, text in lines.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return root


class TestStripTextTags(unittest.TestCase):
    """strip_text_tags：去文本标签但保留内容与转义。"""

    def test_removes_color_and_style(self):
        self.assertEqual(
            N.strip_text_tags("{color=#0f37f2}Niwa{/color}"), "Niwa")
        self.assertEqual(N.strip_text_tags("{i}NOT ME{/i}"), "NOT ME")

    def test_nested_tags(self):
        self.assertEqual(
            N.strip_text_tags("{color=#d17aff}{i}NOT SAYURI{/i}{/color}"),
            "NOT SAYURI")

    def test_escaped_braces_kept(self):
        self.assertEqual(N.strip_text_tags("a{{b}}c"), "a{b}c")

    def test_plain_unchanged(self):
        self.assertEqual(N.strip_text_tags("Iito"), "Iito")


class TestSpliceTags(unittest.TestCase):
    """splice_tags：译名塞回骨架，**标签必须保留**（角色配色靠它）。"""

    def test_color_tag_preserved(self):
        self.assertEqual(
            N.splice_tags("{color=#d599aa}Eri{/color}", "绘里"),
            "{color=#d599aa}绘里{/color}")

    def test_nested_tags_preserved_in_order(self):
        self.assertEqual(
            N.splice_tags("{color=#d17aff}{i}NOT SAYURI{/i}{/color}", "不是小百合"),
            "{color=#d17aff}{i}不是小百合{/i}{/color}")

    def test_untagged_is_identity(self):
        self.assertEqual(N.splice_tags("Iito", "饭户"), "饭户")

    def test_multiple_text_segments_is_ambiguous(self):
        """两段文本语义有歧义（{b}Fox{/b} the Fox），不猜，返回 None。"""
        self.assertIsNone(N.splice_tags("{b}Fox{/b} the Fox", "狐狸"))


class TestLookupTranslation(unittest.TestCase):
    """lookup_translation 必须与引擎 translate() 同语义。"""

    def setUp(self):
        self.strings = {
            "Eri": "绘里",                                  # 菜单键，非名字栏
            "{#weekday}Monday": "周一",                     # 注释标签会被剥离
            "{color=#0f37f2}Niwa{/color}": "{color=#0f37f2}丹羽{/color}",
        }

    def test_tagged_string_needs_tagged_entry(self):
        """核心回归：裸名条目命中不了带标签串。"""
        self.assertIsNone(N.lookup_translation("{color=#d599aa}Eri{/color}",
                                              self.strings))

    def test_exact_tagged_match(self):
        self.assertEqual(
            N.lookup_translation("{color=#0f37f2}Niwa{/color}", self.strings),
            "{color=#0f37f2}丹羽{/color}")

    def test_bare_name_match(self):
        self.assertEqual(N.lookup_translation("Eri", self.strings), "绘里")

    def test_annotation_tag_is_stripped_like_engine(self):
        self.assertEqual(N.lookup_translation("{#weekday}Monday", self.strings),
                         "周一")

    def test_missing_returns_none(self):
        self.assertIsNone(N.lookup_translation("Vi", self.strings))


class TestScanNameboxNames(unittest.TestCase):
    """三类写法一视同仁，且不把资源/动态名收进来。"""

    def test_define_color_tag_detected(self):
        game = _game({
            "script.rpy": 'define nih = "{color=#0f37f2}Niwa{/color}"  #hirai\n'
                          'define vi = "Vi"\n'
                          'label start:\n    nih "Ready."\n    vi "Hello."\n',
        })
        found = {n.var: n for n in N.scan_namebox_names(str(game))}
        self.assertEqual(found["nih"].value, "{color=#0f37f2}Niwa{/color}")
        self.assertEqual(found["nih"].plain, "Niwa")
        self.assertTrue(found["nih"].tagged)
        self.assertEqual(found["nih"].say_lines, 1)
        self.assertFalse(found["vi"].tagged)

    def test_character_style_still_detected(self):
        game = _game({"c.rpy": 'define e = Character("Eri", color="#fff")\n'})
        found = N.scan_namebox_names(str(game))
        self.assertEqual([(n.var, n.plain, n.kind) for n in found],
                         [("e", "Eri", "character")])

    def test_inline_speaker_detected(self):
        game = _game({"p.rpy": 'label s:\n    "Ailing Man" "Uggghhhhhh..."\n'})
        found = N.scan_namebox_names(str(game))
        self.assertEqual([(n.plain, n.kind) for n in found],
                         [("Ailing Man", "inline")])

    def test_inline_symbol_name_skipped(self):
        """内联纯符号名（"?"）是悬念标记，与 define 分支同一把尺子，不该报缺失。"""
        game = _game({"p.rpy": 'label s:\n    "?" "..."\n    "???" "..."\n'})
        self.assertEqual(N.scan_namebox_names(str(game)), [])

    def test_asset_defines_skipped(self):
        """define monday = "images/..." 不是说话人，不能混进名字栏。"""
        game = _game({
            "script.rpy": 'define monday = "images/calender/monday.png"\n'
                          'define nih = "{color=#fff}Niwa{/color}"\n'
                          'label s:\n    nih "Hi."\n',
        })
        found = {n.var for n in N.scan_namebox_names(str(game))}
        self.assertEqual(found, {"nih"})

    def test_dynamic_and_symbol_defines_skipped(self):
        game = _game({
            "script.rpy": 'define t = "[pn]"\n'      # 玩家自定义名
                          'define y = "???"\n'        # 悬念标记
                          'define n = "{color=#fff}" + x + "{/color}"\n',
        })
        self.assertEqual(N.scan_namebox_names(str(game)), [])

    def test_tl_dir_excluded(self):
        game = _game({
            "script.rpy": 'define e = Character("Eri")\n',
            "tl/schinese/x.rpy": 'define n = Character("Niwa")\n',
        })
        found = N.scan_namebox_names(str(game))
        self.assertEqual([n.plain for n in found], ["Eri"])

    def test_sorted_by_say_lines_desc(self):
        game = _game({
            "script.rpy": 'define a = Character("A")\n'
                          'define b = Character("B")\n'
                          'label s:\n' + '    a "x"\n' * 5 + '    b "y"\n' * 2,
        })
        found = N.scan_namebox_names(str(game))
        self.assertEqual([(n.plain, n.say_lines) for n in found],
                         [("A", 5), ("B", 2)])

    def test_duplicate_display_string_merged(self):
        """同一串既是 define 变量又被内联说过 → 合并成一条。

        否则会生成两条 old 相同的条目，引擎 add_string_translation 直接抛
        "A translation for ... already exists"（translation/__init__.py:534），
        游戏启动即崩。实测 Dissonance_0.14 的 Cashier 就是这种情况。
        """
        game = _game({
            "script.rpy": 'define c = "Cashier"\n',
            "eve.rpy": 'label s:\n    "Cashier" "Welcome."\n',
        })
        found = N.scan_namebox_names(str(game))
        values = [n.value for n in found]
        self.assertEqual(len(values), len(set(values)), f"旧串重复: {values}")
        self.assertEqual(values, ["Cashier"])

    def test_merge_keeps_highest_priority_source(self):
        game = _game({
            "script.rpy": 'define c = "Cashier"\n',
            "eve.rpy": 'label s:\n' + '    "Cashier" "Hi."\n' * 3,
        })
        found = N.scan_namebox_names(str(game))
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].say_lines, 3)
        self.assertTrue(any("同名来源" in note for note in found[0].notes))

    def test_no_source_returns_empty(self):
        game = _game({"only.txt": "x"})
        self.assertEqual(N.scan_namebox_names(str(game)), [])


class TestRender(unittest.TestCase):
    """生成格式：注释前缀只一层，且表头必须在 translate 语句**之前**。"""

    def test_comment_prefix_not_doubled(self):
        out = N.render_entry("Eri", "绘里", comment="game/script.rpy:3")
        self.assertIn("# game/script.rpy:3", out)
        self.assertNotIn("# #", out)

    def test_header_precedes_translate_statement(self):
        out = N.render_strings_block(
            "schinese",
            [N.render_entry("Eri", "绘里")],
            header="角色名字框中文\n第二行",
        )
        lines = out.splitlines()
        idx_translate = lines.index("translate schinese strings:")
        for marker in ("## 角色名字框中文", "## 第二行"):
            self.assertLess(lines.index(marker), idx_translate,
                            "表头注释落在 translate 语句之后会落进已开启的语句块")

    def test_entry_escapes_quotes(self):
        out = N.render_entry('A"Name', '译"名')
        self.assertIn(r'old "A\"Name"', out)
        self.assertIn(r'new "译\"名"', out)


class TestLoadTlStrings(unittest.TestCase):
    def test_reads_old_new_pairs(self):
        game = _game({
            "tl/schinese/a.rpy": (
                "translate schinese strings:\n\n"
                '    old "Eri"\n    new "绘里"\n\n'
                '    old "Kaya"\n    new ""\n'
            ),
            "tl/schinese/a.rpy.bak": 'old "Ghost"\n    new "幽灵"\n',
        })
        got = N.load_tl_strings(str(game / "tl" / "schinese"))
        self.assertEqual(got, {"Eri": "绘里", "Kaya": ""})


if __name__ == "__main__":
    unittest.main(verbosity=2)