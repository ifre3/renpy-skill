#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""checks/ 零覆盖检查器的契约回归（2026-10-05 补）。

背景：这批检查器直接跑在用户的游戏上，此前只有 check_crash_risks 有测试。
本文件的价值不在覆盖率，在**钉住实际契约**——这些函数被 CLI 直接调用，
签��或语义一变就是静默改变用户的报告内容。

## 顺带钉住一组已确认的结构性重复

`check_button_missing_translation.py`（565 行）内含 `check_ui` / `check_char` /
`check_char_var_no_t` / `check_interpolation_no_t` / `check_define_default_misuse` /
`check_renpy_func` / `check_screen_calls` / `check_menu_choices` /
`check_fstring_text` 九个函数，而 check_ui_text / check_translation_misuse /
check_func_text / check_auto_trans 四个模块各持一份**已分叉**的副本
（行数不同、返回容器不同：元组 vs 扁平 list）。

这些断言是任何后续合并的前置条件：谁要合并，先让本文件保持绿，
否则就是改变了用户拿到的报告。

运行（仅标准库）::

    cd renpy/scripts/tests
    python -m unittest test_checks_zoo -v
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

import check_auto_trans as auto  # noqa: E402
import check_button_missing_translation as btn  # noqa: E402
import check_duplicate_translations as dup  # noqa: E402
import check_func_text as func  # noqa: E402
import check_translation_misuse as misuse  # noqa: E402
import check_type_safety as typesafe  # noqa: E402
import check_ui_text as ui  # noqa: E402
import common  # noqa: E402

REL = "sample.rpy"


class TestTypeSafety(unittest.TestCase):
    """get_size() → randint 是真崩溃（float 传给 randint 抛 TypeError）。"""

    def scan(self, body):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "s.rpy"
            p.write_text("\n".join(body) + "\n", encoding="utf-8")
            rep = typesafe.Report()
            typesafe.scan_file(p, rep)
            return rep

    def test_get_size_into_randint_flagged(self):
        rep = self.scan([
            "$ w, h = renpy.get_size()",
            "$ x = random.randint(1, w)",
        ])
        self.assertTrue(rep.findings, "get_size() 宽度直接进 randint 必崩")

    def test_literal_args_never_flagged(self):
        """模块设计原则第一条：常量参数绝不报（否则满屏误报）。"""
        rep = self.scan(["$ x = random.randint(1, 100)"])
        self.assertEqual(rep.findings, [])

    def test_plain_python_line_without_dollar_ignored(self):
        """只有 `$` 行被当作 Python——这是契约，别把扫描面悄悄扩大。"""
        rep = self.scan([
            "    w, h = renpy.get_size()",
            "    x = random.randint(1, w)",
        ])
        self.assertEqual(rep.findings, [])

    def test_scan_file_silently_skips_non_path_input(self):
        """传 str 而非 Path 时会走 except 分支跳过（不是崩溃）。"""
        rep = typesafe.Report()
        typesafe.scan_file("not-a-path.rpy", rep)
        self.assertEqual(rep.findings, [])

    def test_rules_are_4tuples_with_named_group(self):
        """规则元组恒为 4 段：(pattern, tag, message, fix)，且首组须有命名捕获。"""
        self.assertGreaterEqual(len(typesafe.RULES), 2)
        for rule in typesafe.RULES:
            self.assertEqual(len(rule), 4, f"规则应含 4 段：{rule!r}")
            self.assertIn("(?P<", rule[0], "pattern 必须含命名捕获组")

    def test_count_takes_severity(self):
        rep = self.scan(["$ w, h = renpy.get_size()", "$ x = random.randint(1, w)"])
        sev = rep.findings[0].severity
        self.assertEqual(rep.count(sev), len(rep.findings))


class TestDuplicateTranslations(unittest.TestCase):
    """同一 old 在多个 tl 文件重复定义 → Ren'Py 拒绝加载该文件。"""

    def check(self, files):
        with tempfile.TemporaryDirectory() as d:
            by_file = {}
            for name, body in files.items():
                p = os.path.join(d, name)
                with open(p, "w", encoding="utf-8") as fh:
                    fh.write(body)
                by_file[p] = dup.load_old_strings(p)
            return dup.check_duplicates(by_file)

    def test_duplicate_old_across_files_flagged(self):
        r = self.check({
            "a.rpy": 'translate schinese:\n    old "Hello"\n    new "你好"\n',
            "b.rpy": 'translate schinese:\n    old "Hello"\n    new "喂"\n',
        })
        self.assertIn("Hello", r)

    def test_duplicate_result_carries_both_locations(self):
        r = self.check({
            "a.rpy": 'translate schinese:\n    old "Hello"\n    new "甲"\n',
            "b.rpy": 'translate schinese:\n    old "Hello"\n    new "乙"\n',
        })
        self.assertEqual(len(r["Hello"]), 2)
        for loc in r["Hello"]:
            self.assertIn("tl_file_full", loc)

    def test_distinct_old_not_flagged(self):
        r = self.check({
            "a.rpy": 'translate schinese:\n    old "A"\n    new "甲"\n',
            "b.rpy": 'translate schinese:\n    old "B"\n    new "乙"\n',
        })
        self.assertEqual(r, {})

    def test_old_match_is_case_sensitive(self):
        """Ren'Py 匹配 old 精确到大小写，故大小写不同不算重复。"""
        r = self.check({
            "a.rpy": 'translate schinese:\n    old "Hello"\n    new "甲"\n',
            "b.rpy": 'translate schinese:\n    old "hello"\n    new "乙"\n',
        })
        self.assertEqual(r, {})

    def test_single_quoted_old_supported(self):
        r = self.check({
            "a.rpy": "translate schinese:\n    old 'Hello'\n    new '甲'\n",
            "b.rpy": "translate schinese:\n    old 'Hello'\n    new '乙'\n",
        })
        self.assertIn("Hello", r)


class TestScreenCallKwContract(unittest.TestCase):
    """SCREEN_CALL_KW 的实际匹配面：只认带括号的调用。

    本组同时是一道防线——2026-10-05 外置 JSON 时默认清单被误收窄到只剩
    game_menu，导致 heading/settings_item/tab_button 三类静默失效，
    而 `func` 子命令没有任何提示。清单只增不减。
    """

    def test_all_four_builtin_names_fire(self):
        for kw in ("game_menu", "heading", "settings_item", "tab_button"):
            with self.subTest(kw=kw):
                r = func.check_screen_calls(['    %s("Chapter 1")' % kw], REL)
                self.assertEqual(len(r), 1, f"{kw} 应被检出")
                self.assertEqual(r[0]["screen"], kw)

    def test_use_prefix_also_matches(self):
        self.assertEqual(
            len(func.check_screen_calls(['    use heading("X")'], REL)), 1
        )

    def test_already_translated_not_flagged(self):
        self.assertEqual(
            func.check_screen_calls(['    heading(_("Chapter 1"))'], REL), []
        )

    def test_bare_keyword_without_parens_not_matched(self):
        """`heading "x"` 不是本规则的匹配面——别误以为漏报了。"""
        self.assertEqual(func.check_screen_calls(['    heading "X"'], REL), [])

    def test_comments_ignored(self):
        self.assertEqual(
            func.check_screen_calls(['    # heading("X")'], REL), []
        )


class TestRenpyFuncText(unittest.TestCase):
    def test_input_without_translation_flagged(self):
        self.assertEqual(
            len(func.check_renpy_func(['$ renpy.input("Name")'], REL)), 1
        )

    def test_notify_without_translation_flagged(self):
        self.assertEqual(
            len(func.check_renpy_func(['$ renpy.notify("Hi")'], REL)), 1
        )

    def test_translated_input_quiet(self):
        self.assertEqual(func.check_renpy_func(['$ renpy.input(_("Name"))'], REL), [])


class TestDuplicatedCheckerShapes(unittest.TestCase):
    """四个模块与 check_button_missing_translation 的分叉副本：锁住当前形态。"""

    SCREEN = ['screen confirm():', '    textbutton "Cancel":', '        action Return(False)']
    FSTRING = ['screen s():', '    text f"val {y}"']

    def test_ui_check_ui_returns_tuple_btn_returns_list(self):
        a = ui.check_ui(self.SCREEN, REL)
        b = btn.check_ui(self.SCREEN, REL)
        self.assertIsInstance(a, tuple)
        self.assertEqual(len(a), 2)
        self.assertIsInstance(b, list)

    def test_both_report_same_count_for_literal_button(self):
        a = ui.check_ui(self.SCREEN, REL)
        b = btn.check_ui(self.SCREEN, REL)
        total_a = sum(len(x) for x in a) if isinstance(a, tuple) else len(a)
        self.assertEqual(total_a, len(b))
        self.assertGreater(len(b), 0)

    def test_fstring_handled_by_dedicated_fn_not_check_ui(self):
        bugs, warns = ui.check_ui(self.FSTRING, REL)
        self.assertEqual(len(bugs), 0)
        self.assertEqual(len(warns), 0)
        self.assertEqual(len(ui.check_fstring_text(self.FSTRING, REL)), 1)
        self.assertEqual(len(btn.check_fstring_text(self.FSTRING, REL)), 1)

    def test_showtext_quiet_on_plain_screen(self):
        for f in (ui.check_showtext, btn.check_showtext):
            self.assertEqual(f(self.SCREEN, REL), [])

    def test_showtext_catches_renpy_show_text(self):
        for f in (ui.check_showtext, btn.check_showtext):
            self.assertEqual(len(f(['show text "Hello" at xalign 0.5'], REL)), 1)

    def test_char_var_needs_bang_t(self):
        bad = ['define c_p = Character("[player]")']
        good = ['define c_p = Character("[player]!", translate=True)']
        self.assertGreaterEqual(len(misuse.check_char_var_no_t(bad, REL)), 1)
        self.assertEqual(misuse.check_char_var_no_t(good, REL), [])
        self.assertGreaterEqual(len(btn.check_char_var_no_t(bad, REL)), 1)

    def test_translation_in_define_default_is_misuse(self):
        """_() 在 init 阶段返回原值，define/default 里用等于没翻译。"""
        bad = ['define start_label = _("Start")']
        self.assertGreaterEqual(len(misuse.check_define_default_misuse(bad, REL)), 1)
        self.assertGreaterEqual(len(btn.check_define_default_misuse(bad, REL)), 1)

    def test_auto_trans_handlers_return_lists(self):
        for f, sample in (
            (auto.check_char, ['define c_mc = Character("Me")']),
            (auto.check_menu_choices, ['menu:', '    "Play":', '        pass']),
        ):
            r = f(sample, REL)
            self.assertIsInstance(r, (list, tuple), f.__name__)


class TestEscapeAwareExtraction(unittest.TestCase):
    """转义回归（2026-10-06）：checks/ 的字符串抽取与 load_trans 统一走
    shared/rpy_syntax 解码。

    此前 ``old "(.*)"/[^"]+`` 弱正则会在 ``textbutton "He said \\"stop\\"
    loudly.":`` 这类含转义引号的行上截断文本，既污染报告又误报「未翻」。
    契约：源侧抽取（各检查器）与翻译侧加载（load_trans）的键值都必须是
    解码后的运行时文本——任何一侧退回弱正则，本类都会变红。
    """

    ESC = 'He said \\"stop\\" loudly.'          # rpy 源里的样子
    ESC_DECODED = 'He said "stop" loudly.'      # 解码后应为的样子

    def test_decode_quoted_literal(self):
        f = common.decode_quoted_literal
        self.assertEqual(f('"He said \\"hi\\""'), 'He said "hi"')
        self.assertEqual(f("'a \\'b'"), "a 'b")  # 尾部 ' 是闭合引号，不是内容
        self.assertEqual(f('"plain"'), "plain")
        # 未闭合/非字面量：原样退回，不抛异常
        self.assertEqual(f('"unclosed'), '"unclosed')
        self.assertEqual(f("no quotes"), "no quotes")

    def test_load_trans_decodes_escapes(self):
        with tempfile.TemporaryDirectory() as d:
            lang = Path(d) / "schinese"
            lang.mkdir()
            (lang / "x.rpy").write_text(
                'old "He said \\"stop\\" loudly."\n'
                'new "他说\\"停\\"了一声。"\n'
                'old "Plain"\n'
                'new "简单"\n',
                encoding="utf-8",
            )
            trans = common.load_trans(d, "schinese")
        self.assertIn(self.ESC_DECODED, trans, "转义条目必须以解码后的原文为键")
        self.assertEqual(trans[self.ESC_DECODED], '他说"停"了一声。')
        self.assertEqual(trans["Plain"], "简单")
        self.assertNotIn(self.ESC, trans, "不允许残留未解码的原文键")

    def test_ui_text_full_string_with_escaped_quotes(self):
        bug, info = ui.check_ui(
            ['textbutton "He said \\"stop\\" loudly." action Jump("a")'], REL
        )
        self.assertEqual(bug, [])
        self.assertEqual(len(info), 1)
        self.assertEqual(info[0]["text"], self.ESC_DECODED)

    def test_func_text_full_string_with_escaped_quotes(self):
        res = func.check_renpy_func(['renpy.notify("He said \\"stop\\" loudly.")'], REL)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["text"], self.ESC_DECODED)

    def test_auto_menu_choices_escaped(self):
        res = auto.check_menu_choices(
            ["menu:", '    "He said \\"stop\\" loudly.":', "        jump end"], REL
        )
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["text"], self.ESC_DECODED)

    def test_button_showtext_escaped(self):
        res = btn.check_showtext(['show text "He said \\"hi\\" now"'], REL)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["text"], 'He said "hi" now')

    def test_button_char_escaped(self):
        res = btn.check_char(['define h = Character("A \\"b\\" C")'], REL)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["text"], 'A "b" C')

    def test_misuse_define_default_escaped(self):
        res = misuse.check_define_default_misuse(['define x = _("He said \\"hi\\"")'], REL)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["text"], 'He said "hi"')

    def test_duplicate_old_escaped(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.rpy"
            p.write_text(
                "# game/script.rpy:12\n"
                'old "He said \\"stop\\" loudly."\n',
                encoding="utf-8",
            )
            entries = dup.load_old_strings(str(p))
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["old"], self.ESC_DECODED)

    def test_plain_strings_unchanged(self):
        """回归护栏：不含转义的普通输入，行为与修复前一致。"""
        bug, info = ui.check_ui(['textbutton "Cancel" action Return(1)'], REL)
        self.assertEqual([e["text"] for e in info], ["Cancel"])
        res = func.check_renpy_func(['renpy.notify("Saved!")'], REL)
        self.assertEqual(res[0]["text"], "Saved!")


if __name__ == "__main__":
    unittest.main(verbosity=2)