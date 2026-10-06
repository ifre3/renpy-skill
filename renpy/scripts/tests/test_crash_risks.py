#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_crash_risks 检测器行为回归（此前 26KB 的最大检查器零测试覆盖）。

这些用例的价值在于**锁住误报边界**：崩溃检测器跑在别人游戏上，误报会让用户
失去对工具的信任，比漏报更伤。本文件用正例（该报）+ 反例（不该报）双向断言。

运行（仅标准库）::

    cd scripts/tests
    python -m unittest test_crash_risks -v
"""

import os
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_TOOLS = os.path.dirname(_HERE)
_CHECK = os.path.join(_TOOLS, "checks")
if _CHECK not in sys.path:
    sys.path.insert(0, _CHECK)

import check_crash_risks as crash  # noqa: E402


def _rules(findings):
    """Finding 的规则名字段是 category（不是 rule）。"""
    return {f.category for f in findings}


class TestCrashRuleDetection(unittest.TestCase):
    """每个检测器至少一条正例：声明了能查出来的就该真查出来。"""

    def test_map_multiple_unpack_flagged(self):
        lines = ["    x, y = map(f, a)"]
        self.assertIn("map_misuse", _rules(crash.check_map_misuse("t.rpy", lines)))

    def test_map_with_list_wrapper_not_flagged(self):
        """已有 list(...) 包裹的不该再报——否则满屏误报。"""
        lines = ["    x = list(map(f, a))"]
        self.assertEqual(_rules(crash.check_map_misuse("t.rpy", lines)), set())

    def test_bare_except_flagged(self):
        lines = ["    try:", "        pass", "    except:", "        pass"]
        self.assertIn("bare_except", _rules(crash.check_bare_except("t.rpy", lines)))

    def test_bare_except_with_exception_not_flagged(self):
        lines = ["    try:", "        pass", "    except Exception:", "        pass"]
        self.assertEqual(_rules(crash.check_bare_except("t.rpy", lines)), set())

    def test_globals_access_flagged(self):
        lines = ['    x = globals()["y"]']
        self.assertIn("globals_access", _rules(crash.check_globals_access("t.rpy", lines)))

    def test_globals_in_string_not_flagged(self):
        lines = ['    $ s = "globals()"']
        self.assertEqual(_rules(crash.check_globals_access("t.rpy", lines)), set())

    def test_unsafe_intconv_flagged(self):
        lines = ["    $ x = int(a / b)"]
        self.assertIn("unsafe_intconv", _rules(crash.check_unsafe_intconv("t.rpy", lines)))

    def test_intconv_without_try_flagged(self):
        """规则真相：intconv 查的是「无 try 保护的 int()/float()」，不是除零。"""
        lines = ['    $ x = int(ratio)']
        self.assertIn("unsafe_intconv", _rules(crash.check_unsafe_intconv("t.rpy", lines)))

    def test_intconv_inside_try_not_flagged(self):
        lines = [
            "    $ try:",
            "    $     x = int(ratio)",
            "    $ except ValueError:",
            "    $     x = 0",
        ]
        self.assertEqual(_rules(crash.check_unsafe_intconv("t.rpy", lines)), set())

    def test_intconv_of_literal_not_flagged(self):
        """int(len(x)) / int(3.5) 属安全模式清单，不该报。"""
        for line in ('    $ x = int(len(items))', '    $ y = int(3.5)'):
            with self.subTest(line=line):
                self.assertEqual(_rules(crash.check_unsafe_intconv("t.rpy", [line])), set())

    def test_div_zero_on_python_line_flagged(self):
        """除数用非标签名，避免撞上 RENPY_TAGS 白名单（b/i/s 等都是标签）。"""
        lines = ["    $ x = total_y / step_size"]
        self.assertIn("div_zero", _rules(crash.check_div_zero("t.rpy", lines)))

    def test_div_by_renpy_tag_name_not_flagged(self):
        """除数名撞 Ren'Py 标签（b = bold）时不报——这是白名单的既定行为。"""
        lines = ["    $ x = total_y / b"]
        self.assertEqual(_rules(crash.check_div_zero("t.rpy", lines)), set())

    def test_div_zero_ignored_outside_python_line(self):
        """非 $ 行不算 Python 除法——否则文本标签会误报。"""
        lines = ["    image chapter / images/bg"]
        self.assertEqual(_rules(crash.check_div_zero("t.rpy", lines)), set())

    def test_div_by_literal_zero_ignored(self):
        """除以字面量 0 是显式代码错误，不是本检测器的「可能为零」范畴。"""
        lines = ["    $ x = a / 0"]
        self.assertEqual(_rules(crash.check_div_zero("t.rpy", lines)), set())

    def test_div_with_zero_check_not_flagged(self):
        lines = [
            "    $ if step_size == 0:",
            "    $     x = 0",
            "    $ else:",
            "    $     x = total_y / step_size",
        ]
        self.assertEqual(_rules(crash.check_div_zero("t.rpy", lines)), set())

    def test_comments_never_flagged(self):
        """注释行不得产出任何 finding（所有检测器的共同不变量）。"""
        lines = [
            "    # x, y = map(f, a)",
            "    # except:",
            "    # $ x = a / b",
            '    # x = globals()["y"]',
            "    # x = int(a / b)",
        ]
        for name, fn in crash.ALL_CHECKERS:
            with self.subTest(checker=name):
                self.assertEqual(fn("t.rpy", lines), [])


class TestDollarMarkerAwareness(unittest.TestCase):
    """``$`` 行内语句标记的识别（2026-10-05 修）。

    Ren'Py 里 ``$ try:`` 与顶格``try:`` 等价。原实现只按顶格匹配 try，
    导致所有写成 ``$`` 形式的 try 块被误判为「无保护」，全局刷误报。
    """

    def test_globals_in_dollar_try_not_flagged(self):
        lines = ["    $ try:", '    $     x = globals()["y"]']
        self.assertEqual(_rules(crash.check_globals_access("t.rpy", lines)), set())

    def test_intconv_in_dollar_try_not_flagged(self):
        lines = ["    $ try:", "    $     x = int(ratio)", "    $ except ValueError:", "    $     x = 0"]
        self.assertEqual(_rules(crash.check_unsafe_intconv("t.rpy", lines)), set())

    def test_globals_still_flagged_without_try(self):
        lines = ['    $ x = globals()["y"]']
        self.assertIn("globals_access", _rules(crash.check_globals_access("t.rpy", lines)))

    def test_try_substring_identifier_does_not_count_as_try(self):
        """``try_count = 0`` 这类含 try 子串的行不算 try 块。

        原实现用 `"try" in line`，任何含 try 的标识符都会把后续代码
        误判为已保护，造成漏报。
        """
        lines = ["    $ try_count = 0", '    $     x = globals()["y"]']
        self.assertIn("globals_access", _rules(crash.check_globals_access("t.rpy", lines)))

    def test_strip_stmt_marker(self):
        self.assertEqual(crash._strip_stmt_marker("    $ try:"), "try:")
        self.assertEqual(crash._strip_stmt_marker("    try:"), "try:")
        self.assertEqual(crash._strip_stmt_marker("$ x = 1"), "x = 1")


class TestCrashFileWalking(unittest.TestCase):
    def test_find_rpy_files_skips_tl_by_default(self):
        """tl 目录是译文，检查器跑两遍只会刷屏，默认必须跳过。"""
        with tempfile.TemporaryDirectory() as root:
            game = os.path.join(root, "game")
            os.makedirs(os.path.join(game, "tl", "schinese"))
            with open(os.path.join(game, "script.rpy"), "w", encoding="utf-8") as fh:
                fh.write('label start:\n    "hi"\n')
            with open(os.path.join(game, "tl", "schinese", "script.rpy"), "w", encoding="utf-8") as fh:
                fh.write('translate schinese:\n    old "hi"\n    new "你好"\n')

            default = {os.path.normpath(p) for p in crash.find_rpy_files(root)}
            self.assertTrue(default)
            self.assertFalse(any("tl" in p.split(os.sep) for p in default))

            with_tl = {os.path.normpath(p) for p in crash.find_rpy_files(root, skip_tl=False)}
            self.assertTrue(any("tl" in p.split(os.sep) for p in with_tl))

    def test_find_rpy_files_excludes_engine_by_default(self):
        """引擎自带 rpyc 噪声大，默认不扫。"""
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "game"))
            os.makedirs(os.path.join(root, "renpy", "common"))
            with open(os.path.join(root, "game", "a.rpy"), "w", encoding="utf-8") as fh:
                fh.write("label start:\n    pass\n")
            with open(os.path.join(root, "renpy", "common", "b.rpy"), "w", encoding="utf-8") as fh:
                fh.write("init python:\n    pass\n")

            default = {os.path.normpath(p) for p in crash.find_rpy_files(root)}
            self.assertTrue(any("game" in p.split(os.sep) for p in default))
            self.assertFalse(any("renpy" in p.split(os.sep) for p in default))


if __name__ == "__main__":
    unittest.main(verbosity=2)