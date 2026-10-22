#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_typography.py 契约回归（27 用例）。

只测确定性行为：字号下限、outline 阈值、硬编码 size、line_spacing 范围、
--no-tl 与 --severity 过滤。不启动游戏，不碰 SDK。
"""

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

import check_typography as ct  # noqa: E402

REL = "sample.rpy"


def _write(body, tl=False):
    """把 body 写进临时 game 目录（可选 game/tl/schinese），返回 game 目录。"""
    d = Path(tempfile.mkdtemp())
    game = d / "game"
    game.mkdir()
    sub = Path("tl") / "schinese" / REL if tl else Path(REL)
    target = game / sub
    if tl:
        target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(body) + "\n", encoding="utf-8")
    return d


class TestGuiSizeDefs(unittest.TestCase):
    """define gui.XXX_size = N 的可读性下限。"""

    def scan(self, body):
        d = _write(body)
        return ct.scan_file(d / "game" / REL)

    def test_text_size_below_floor_is_warning(self):
        findings = ct.scan_file(Path(_write(["define gui.text_size = 18"])) / "game" / REL)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "WARNING")
        self.assertIn("低于中文可读下限", findings[0].message)

    def test_text_size_at_floor_is_ok(self):
        findings = ct.scan_file(Path(_write(["define gui.text_size = 20"])) / "game" / REL)
        self.assertEqual(findings, [])

    def test_text_size_above_floor_is_ok(self):
        findings = ct.scan_file(Path(_write(["define gui.text_size = 28"])) / "game" / REL)
        self.assertEqual(findings, [])

    def test_name_size_below_floor_is_warning(self):
        findings = ct.scan_file(Path(_write(["define gui.name_text_size = 16"])) / "game" / REL)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "WARNING")

    def test_name_size_at_floor_is_ok(self):
        findings = ct.scan_file(Path(_write(["define gui.name_text_size = 18"])) / "game" / REL)
        self.assertEqual(findings, [])

    def test_other_sizes_below_floor_is_warning(self):
        for field in ("choice_button_text_size", "button_text_size", "history_text_size"):
            findings = ct.scan_file(
                Path(_write([f"define gui.{field} = 16"])) / "game" / REL)
            self.assertEqual(len(findings), 1, field)
            self.assertEqual(findings[0].severity, "WARNING", field)

    def test_multiple_size_defs_each_reported(self):
        body = [
            "define gui.text_size = 18",
            "define gui.name_text_size = 16",
        ]
        findings = ct.scan_file(Path(_write(body)) / "game" / REL)
        self.assertEqual(len(findings), 2)
        sevs = {f.severity for f in findings}
        self.assertEqual(sevs, {"WARNING"})


class TestHardcodedSize(unittest.TestCase):
    """style 块里硬编码 size → INFO（建议引用 gui 变量）。"""

    def scan(self, body):
        d = _write(body)
        return ct.scan_file(d / "game" / REL)

    def test_style_size_hardcoded_is_info(self):
        body = [
            "style say_dialogue:",
            "    size 28",
        ]
        findings = self.scan(body)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "INFO")
        self.assertIn("硬编码", findings[0].message)

    def test_define_not_flagged(self):
        body = ["define gui.text_size = 28"]
        findings = self.scan(body)
        self.assertEqual(findings, [])


class TestOutlineThreshold(unittest.TestCase):
    """outline 像素 > 4 → WARNING。"""

    def scan(self, body):
        d = _write(body)
        return ct.scan_file(d / "game" / REL)

    def test_outline_gt_4_is_warning(self):
        body = ["    outlines [(5, \"#000\", 0, 0)]"]
        findings = self.scan(body)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "WARNING")
        self.assertIn("outline", findings[0].message.lower())

    def test_outline_eq_4_is_ok(self):
        body = ["    outlines [(4, \"#000\", 0, 0)]"]
        findings = self.scan(body)
        self.assertEqual(findings, [])

    def test_outline_1_is_ok(self):
        body = ["    outlines [(1, \"#000\", 0, 0)]"]
        findings = self.scan(body)
        self.assertEqual(findings, [])


class TestLineSpacingRange(unittest.TestCase):
    """line_spacing 超出 1–12 → INFO。"""

    def scan(self, body):
        d = _write(body)
        return ct.scan_file(d / "game" / REL)

    def test_line_spacing_0_is_info(self):
        findings = self.scan(["    line_spacing 0"])
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "INFO")

    def test_line_spacing_13_is_info(self):
        findings = self.scan(["    line_spacing 13"])
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "INFO")

    def test_line_spacing_5_is_ok(self):
        findings = self.scan(["    line_spacing 5"])
        self.assertEqual(findings, [])


class TestNoTl(unittest.TestCase):
    """--no-tl 跳过 tl/ 目录。"""

    def scan_no_tl(self, body):
        d = _write(body, tl=True)
        return ct.scan_file(d / "game" / "tl" / "schinese" / REL)

    def test_tl_file_scanned_when_include_tl(self):
        body = ["define gui.text_size = 18"]
        findings = self.scan_no_tl(body)
        self.assertEqual(len(findings), 1)

    def test_no_tl_flag_respected_by_iter(self):
        d = _write(["define gui.text_size = 18"], tl=True)
        files = list(ct.iter_rpy(d / "game", include_tl=False))
        self.assertEqual(len(files), 0)


class TestSeverityFilter(unittest.TestCase):
    """--severity 只显示指定级别及以上。"""

    def scan_args(self, body, severity):
        d = _write(body)
        files = list(ct.iter_rpy(d / "game", include_tl=True))
        out = []
        for p in files:
            for f in ct.scan_file(p):
                if ct.SEVERITY_ORDER[f.severity] <= ct.SEVERITY_ORDER[severity]:
                    out.append(f)
        return out

    def test_severity_error_hides_warnings(self):
        body = ["define gui.text_size = 18"]  # WARNING
        out = self.scan_args(body, "ERROR")
        self.assertEqual(out, [])

    def test_severity_warning_shows_warning(self):
        body = ["define gui.text_size = 18"]  # WARNING
        out = self.scan_args(body, "WARNING")
        self.assertEqual(len(out), 1)

    def test_severity_info_shows_all(self):
        body = [
            "define gui.text_size = 18",      # WARNING
            "    line_spacing 0",              # INFO
        ]
        out = self.scan_args(body, "INFO")
        self.assertEqual(len(out), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
