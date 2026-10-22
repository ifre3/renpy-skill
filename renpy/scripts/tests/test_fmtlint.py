#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fmtlint（`checks/lint_rpy.py`）回归：钉住 2026-10-11 归位时修掉的三处误报。

背景：这 395 行（lint_rpy + lint_report）此前住在 checks/ 却不入 CLI、不入
all，自动化链路永远跑不到。归位时按真实项目（Dissonance 0.14，44k 对话对）
实测纠了三类错判——本文件把每条都钉成断言，防止被人"顺手改回去"：

1. **BOM 不再算问题**：tl 文件普遍带 UTF-8 BOM（实测 27/27），引擎与
   tl_check 都按 utf-8-sig 读。报成 E004 会让检查器在任何合规项目上恒定
   返回 1 —— 与「退出码 1 = 查出了问题」冲突。
2. **E011 长度比是排版级**：0.3 阈值按同语系定的。英→中天然压缩，长度比
   中位数 0.333、P10 0.25，30% 句子落在 <0.3（实测 674 组）。必须打印但不
   进退出码；真漏翻看 `untranslated`。
3. **E009 分级**：手写正则把 `[[Edited]` 转义、`{cps=3}` 标签参数、
   中文语气词括号 `[嗯]`、`!s` 转换标志全部误判。改用共享解析层后剩 6 条，
   逐条核实：4 条是译者风格（E009b，提示级），2 条真问题（E009）——
   `[你]`（原文有插值）、`[cps=3]`（标签名写进正文）。
4. **逐行扫描不能只挂 `new ` 分支**：tl 文件 44k 对话对里 old/new 只有 857
   组，其余全是「原文注释 + 译文行」。挂在 new 分支会漏掉 98% 的译文。

运行::

    cd renpy/scripts/tests
    python -m unittest test_fmtlint -v
"""

import os
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_TOOLS = os.path.dirname(_HERE)
_CHECKS = os.path.join(_TOOLS, "checks")
_SHARED = os.path.join(_TOOLS, "shared")
for _p in (_CHECKS, _SHARED):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import lint_rpy as L  # noqa: E402


def _write(d, name, text, bom=False):
    path = os.path.join(d, name)
    data = text.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    with open(path, "wb") as fh:
        fh.write(data)
    return path


class TestBomIsNotAnIssue(unittest.TestCase):
    """BOM 是 tl 文件的常态，不能算 E004。"""

    def test_bom_file_reports_no_e004(self):
        with tempfile.TemporaryDirectory() as d:
            p = _write(d, "a.rpy",
                       'translate schinese x_1:\n\n    # "Hi"\n    "嗨"\n',
                       bom=True)
            codes = [c for c, _ln, _m in L.check_file(p, "schinese")]
            self.assertNotIn("E004", codes)

    def test_unreadable_file_still_reports_e004(self):
        """真正的编码故障仍要报：这里用一个目录当文件，必然读失败。"""
        with tempfile.TemporaryDirectory() as d:
            codes = [c for c, _ln, _m in L.check_file(d, "schinese")]
            self.assertIn("E004", codes)


class TestSeverityGrading(unittest.TestCase):
    """只有真问题进退出码；排版噪音只展示。"""

    def test_cosmetic_codes_do_not_affect_exit_code(self):
        """超长行 + 长度比异常 → 退出码仍为 0。"""
        with tempfile.TemporaryDirectory() as d:
            # 一行 250 字符（E010）+ 英→中短译文（E011）
            long_en = "A" * 240
            _write(d, "a.rpy",
                   'translate schinese x_1:\n\n'
                   f'    # "{long_en}"\n'
                   '    "短"\n')
            rc, total = L._scan_and_report(d, "schinese")
            self.assertEqual(rc, 0, "排版级问题不该让退出码变成 1")
            self.assertGreater(total, 0, "排版级问题仍应打印出来")

    def test_e010_and_e011_are_cosmetic(self):
        self.assertEqual(L.SEVERITY["E010"], "cosmetic")
        self.assertEqual(L.SEVERITY["E011"], "cosmetic")

    def test_real_problems_are_problem_level(self):
        for code in ("E001", "E002", "E003", "E004", "E005", "E008", "E009"):
            with self.subTest(code=code):
                self.assertEqual(L.SEVERITY[code], "problem")

    def test_bracketed_plain_word_is_cosmetic(self):
        self.assertEqual(L.SEVERITY["E009b"], "cosmetic")


class TestInlineVarGrading(unittest.TestCase):
    """E009 的误报边界——每条都来自真实项目的实测核实。"""

    def test_escaped_brackets_not_flagged(self):
        """`[[Edited]` 是 Ren'Py 转义方括号，不是插值。

        注意：`_inline_var_level` 收到的已是解析层剥掉外层括号后的内容，
        判转义的正确位置是解析层（`iter_bracket_groups` 跳过 `[[`），
        所以这里断言它根本不出现在 `_inline_vars` 的结果里。
        """
        for text in ("[[Edited]", "[[编辑]"):
            with self.subTest(text=text):
                items = L._inline_vars(text)
                self.assertEqual([lv for _i, lv in items if lv], [])

    def test_conversion_flags_are_valid(self):
        """!t/!q/!i/!u/!s/!c/!l 都是合法转换标志；!s 早期被漏判。"""
        for inner in ("config.version!t", "control!s", "x!q", "y!i",
                      "z!u", "a!c", "b!l", "plain_var"):
            with self.subTest(inner=inner):
                self.assertIsNone(L._inline_var_level(inner, True))

    def test_tag_arg_is_real_problem(self):
        """`[cps=3]` —— 标签名被写进正文，会显示出来，是真缺陷。"""
        self.assertEqual(L._inline_var_level("cps=3", False), "E009")

    def test_mood_bracket_without_orig_interp_is_cosmetic(self):
        """中文台词里括语气词 `[嗯]`：原文无插值时是译者风格。"""
        self.assertEqual(L._inline_var_level("嗯", False), "E009b")

    def test_mood_bracket_with_orig_interp_stays_problem(self):
        """原文有插值时译文多出括号，不能排除译者把插值改坏了，不降级。"""
        self.assertEqual(L._inline_var_level("你", True), "E009")

    def test_text_tag_params_not_flagged(self):
        """`{cps=3}` 标签参数内的方括号由解析层 mask，不当插值报。"""
        items = L._inline_vars("{cps=3}…{/cps}")
        self.assertEqual([lv for _i, lv in items if lv], [])


class TestScansAllTranslationForms(unittest.TestCase):
    """tl 文件绝大多数是「原文注释+译文行」，不是 old/new。"""

    def test_comment_form_is_scanned(self):
        """注释形式的译文行也要被 E009 扫到（不能只挂 new 分支）。"""
        with tempfile.TemporaryDirectory() as d:
            p = _write(d, "a.rpy",
                       'translate schinese x_1:\n\n'
                       '    # "Hello"\n'
                       '    "你好[cps=3]"\n')
            codes = [c for c, _ln, _m in L.check_file(p, "schinese")]
            self.assertIn("E009", codes,
                          "注释形式的译文行漏扫了——tl 文件 98% 是这个形态")

    def test_old_new_form_is_scanned_too(self):
        with tempfile.TemporaryDirectory() as d:
            p = _write(d, "a.rpy",
                       'translate schinese strings:\n'
                       '    old "Hello"\n'
                       '    new "你好[cps=3]"\n')
            codes = [c for c, _ln, _m in L.check_file(p, "schinese")]
            self.assertIn("E009", codes)


class TestCheckerContract(unittest.TestCase):
    """fmtlint 必须走检查器契约，否则门面和 all 发现不了它。"""

    def test_has_checker(self):
        ck = getattr(L, "CHECKER", None)
        self.assertIsNotNone(ck, "lint_rpy 没有模块级 CHECKER")
        self.assertEqual(ck.name, "fmtlint")
        self.assertEqual(ck.takes, "tl_dir")
        self.assertTrue(ck.requires_tl)
        self.assertTrue(ck.read_only)

    def test_registered(self):
        sys.path.insert(0, _SHARED)
        import tool_registry as REG
        self.assertIn("fmtlint", REG.TOOL_SCRIPTS)
        self.assertIn("fmtlint", REG.ALL_GROUP)
        self.assertEqual(REG.script_path("fmtlint"),
                         os.path.join(_CHECKS, "lint_rpy.py"))

    def test_exit_code_on_missing_dir(self):
        rc, total = L.run_fmtlint("/nonexistent/path/xyz", "schinese")
        self.assertEqual(rc, 2)
        self.assertEqual(total, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
