# -*- coding: utf-8 -*-
"""check_tl_coverage 契约回归：源↔tl 文件覆盖对照。

背景（2026-10-25，AfterDark 实测）：机翻管线只导出部分 tl 文件时，
`check_untranslated` 对「tl 目录内部」报全绿，玩家却满屏英文——
124 个源脚本只有 70 个有译文。本检查器按 Ren'Py 的 tl 文件镜像约定
（`foo/bar.rpy` → `tl/<lang>/foo/bar_translated.rpy`）求差集。
这里钉住匹配规则与退出码语义，防止后续改坏。

运行（仅标准库）::

    cd renpy/scripts/tests
    python -m unittest test_tl_coverage -v
"""

import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_TOOLS = os.path.dirname(_HERE)
_CHECKS = os.path.join(_TOOLS, "checks")
if _CHECKS not in sys.path:
    sys.path.insert(0, _CHECKS)

import check_tl_coverage as cov  # noqa: E402


def build_game(root, sources, tl_files):
    """在 root 下搭一个最小游戏树：sources/tl_files 都是相对 game 的路径列表。"""
    game = Path(root) / "game"
    for rel in sources:
        p = game / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('label start:\n    "Hello world"\n', encoding="utf-8")
    for rel in tl_files:
        p = game / "tl" / "schinese" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('translate schinese strings:\n    old "Hello world"\n'
                     '    new "你好世界"\n', encoding="utf-8")
    return game


def run(game):
    buf = io.StringIO()
    rc = cov.run_check(str(game), str(game / "tl" / "schinese"), "schinese", out=buf)
    return rc, buf.getvalue()


class TestTlCoverage(unittest.TestCase):
    def test_full_coverage_is_ok(self):
        with tempfile.TemporaryDirectory() as d:
            rc, out = run(build_game(d, ["script.rpy", "sub/ch1.rpy"],
                                     ["script_translated.rpy", "sub/ch1_translated.rpy"]))
            self.assertEqual(rc, 0)
            self.assertIn("[OK]", out)

    def test_gap_is_reported_with_exit_1(self):
        with tempfile.TemporaryDirectory() as d:
            rc, out = run(build_game(d, ["script.rpy", "Qte.rpy"],
                                     ["script_translated.rpy"]))
            self.assertEqual(rc, 1)
            self.assertIn("Qte.rpy", out)
            self.assertNotIn("[OK]", out)

    def test_empty_gap_file_does_not_fail(self):
        """缺口文件里没有可翻译内容 → 提示但不判失败（退出码 0）。"""
        with tempfile.TemporaryDirectory() as d:
            game = build_game(d, ["script.rpy"], ["script_translated.rpy"])
            (game / "credits.rpy").write_text("define bonus = 1\n", encoding="utf-8")
            rc, out = run(game)
            self.assertEqual(rc, 0)
            self.assertIn("credits.rpy", out)

    def test_translated_suffix_maps_across_subdirs(self):
        """子目录 + _translated 后缀都要对上，不能丢目录结构。"""
        with tempfile.TemporaryDirectory() as d:
            rc, _ = run(build_game(d, ["Girls Scripts/Autumn.rpy"],
                                   ["Girls Scripts/Autumn_translated.rpy"]))
            self.assertEqual(rc, 0)

    def test_space_in_filename_normalized(self):
        """源文件名带空格（`1hallway2_screen .rpy`）而 tl 侧不带 → 兜底匹配。"""
        with tempfile.TemporaryDirectory() as d:
            rc, _ = run(build_game(d, ["School Scripts/1hallway2_screen .rpy"],
                                   ["School Scripts/1hallway2_screen_translated.rpy"]))
            self.assertEqual(rc, 0)

    def test_tl_only_file_is_info_not_gap(self):
        """common_translated.rpy 这类 tl 自产文件不进缺口清单。"""
        with tempfile.TemporaryDirectory() as d:
            rc, out = run(build_game(d, ["script.rpy"], ["script_translated.rpy",
                                                         "common_translated.rpy"]))
            self.assertEqual(rc, 0)
            self.assertIn("common_translated.rpy", out)
            self.assertIn("[INFO]", out)

    def test_hint_excludes_define_lines(self):
        """define/default/style 声明行不算可翻译线索。"""
        with tempfile.TemporaryDirectory() as d:
            game = build_game(d, ["script.rpy"], ["script_translated.rpy"])
            (game / "defs.rpy").write_text(
                'define e = Character("Eileen")\n'
                'default save_name = "1"\n'
                'image bg room = "room.png"\n'
                '"Real dialogue"\n', encoding="utf-8")
            rc, out = run(game)
            self.assertEqual(rc, 1)
            self.assertIn("~1 行含字符串", out)

    def test_checker_contract(self):
        self.assertEqual(cov.CHECKER.name, "tlcoverage")
        self.assertEqual(cov.CHECKER.takes, cov.PROJECT)
        self.assertTrue(cov.CHECKER.requires_tl)
        self.assertTrue(cov.CHECKER.read_only)


if __name__ == "__main__":
    unittest.main(verbosity=2)
