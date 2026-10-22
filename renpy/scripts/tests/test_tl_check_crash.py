#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tl_check 崩溃级规则的回归测试（2026-10-11 补）。

这些用例全部来自 Dissonance_0.14 汉化项目的真实损伤，且都经 Ren'Py 8.5.3
lint 确认：

1. **裸 % 未转义** —— 原文写 `99%%`，译文漏成 `99%确定`。引擎把 `%确`
   当转换说明符，抛 `Unknown string format code '%确'`，游戏当场崩。
   这条规则在补上之前完全漏检（旧注释写着「裸 % 是字面量不查」），
   是这次真机 lint 才暴露的覆盖缺口。

2. **BOM / 行尾不被 --fix 改写** —— tl_check 用 utf-8-sig 读却用 utf-8
   写，26 个文件里 22 个的 BOM 被静默剥掉；splitlines + join 又把全部
   CRLF 改成 LF。Ren'Py 能读，但属于用户没要求的改动，且不计入修复报告。

3. **伪插值 [非ASCII]** —— 译文里凭空出现的 `[嗯]` `[你]` 之类。见
   TestPseudoInterpolation：来自 Dissonance_0.14 汉化的 5 处真实闪退。

4. **术语一致性 / 语言分块判定**（2026-10-18 新增，默认关闭的可选维度）——
   规则取自 AiNiee 的 TranslationChecker，落到 tl_check 的 --glossary 与
   --lang-ratio 两个开关上，不在 `all` 里跑，也不要默认改变既有输出。

运行（仅标准库）::

    cd renpy/scripts/tests
    python -m unittest test_tl_check_crash -v
"""

import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_SDK = os.path.join(os.path.dirname(_HERE), "sdk")
_CHECK = os.path.join(os.path.dirname(_HERE), "checks")
_SHARED = os.path.join(os.path.dirname(_HERE), "shared")
for p in (_SDK, _CHECK, _SHARED):
    if p not in sys.path:
        sys.path.insert(0, p)

import tl_check as T  # noqa: E402


def _run(old, new):
    """跑 compare 并返回 (是否报崩溃, 报出的类别集合)。"""
    issues = []
    T.compare(old, new, "t", issues)
    kinds = {k for _, _lv, k, _ in issues}
    crashed = any(lv == "崩溃" for _, lv, _k, _ in issues)
    return crashed, kinds


class TestBarePercent(unittest.TestCase):
    """裸 % 未转义：真崩溃源，Ren'Py lint 报 Unknown string format code。"""

    # Dissonance 真实六例（原文 %% → 译文 %）
    REAL = [
        ("Or at least I'm 99%% certain I'm not.", "或者说，我九十九%确定自己不是。"),
        ("those odds will likely never be at 0%% completely", "可能性可能永远也不会降到0%，但"),
        ("it's not like my accuracy is 100%% when", "准确率也不是100%的"),
        ("she's puttin' in 100%% in times like this", "她都付出了100%的努力"),
        ("I'm like 90%% sure she'd accept it", "我大概90%确定她会接受"),
        ("and that 99%% of what happened is Sensei's fault", "而且99%的锅都在于老师"),
    ]

    def test_real_cases_all_crash(self):
        for old, new in self.REAL:
            with self.subTest(new=new[:24]):
                crashed, kinds = _run(old, new)
                self.assertTrue(crashed, msg=f"未报崩溃: {new}")
                self.assertIn("裸%未转义", kinds)

    def test_escaped_properly_is_clean(self):
        """译文正确写成 %% → 不报。"""
        crashed, kinds = _run("I'm 99%% certain.", "我九十九%%确定。")
        self.assertFalse(crashed)
        self.assertNotIn("裸%未转义", kinds)

    def test_source_not_escaped_is_exempt(self):
        """原作自己没转义（上游 bug）→ 译文照抄不背锅。"""
        crashed, kinds = _run("90% sure", "我90%确定")
        self.assertNotIn("裸%未转义", kinds)

    def test_named_format_spec_untouched(self):
        """%(name)s 走另一条规则，不在这里重复报。"""
        crashed, kinds = _run("Hi %(name)s", "你好%(name)s")
        self.assertNotIn("裸%未转义", kinds)

    def test_no_percent_is_clean(self):
        crashed, kinds = _run("no percent here", "没有百分号")
        self.assertFalse(crashed)


class TestPseudoInterpolation(unittest.TestCase):
    """伪插值 [中文]：2026-10-13 Dissonance_0.14 traceback 的真实闪退。

    tl/schinese 里译者把句首语气词写成了 `[嗯]`、`[你]`。Ren'Py 不管新旧
    是否匹配，任何 [...] 都交给 substitutions 当 Python 表达式 eval，
    于是 `NameError: name '嗯' is not defined`。原文那几句其实是**纯文本**，
    所以既有的 []插值不匹配 规则（新旧差集）虽然会报"多"，但只到显示级，
    这里把它升到崩溃级。
    """

    REAL = [
        # (原文, 译文) —— 5 处真实损伤的代表 3 例
        ("I suppose that's an option I have, but since this is Suzu...",
         "[嗯]这确实是我能想到的一个办法，不过既然我们说的是苏苏……"),
        ("What do you-{w} Oh. {w}Ohhhhh.....",
         "什么啊——噢。[哦]啊啊啊……"),
        ("{i}Yoshie's bond has deepened to [yoshie_bond]!{/i}",
         "{i}Yoshie和[你]的羁绊加深到了[yoshie_bond]！{/i}"),
    ]

    def test_real_cases_all_crash(self):
        for old, new in self.REAL:
            with self.subTest(new=new[:24]):
                crashed, kinds = _run(old, new)
                self.assertTrue(crashed, msg=f"漏检: {new[:30]}")
                self.assertIn("伪插值[非ASCII]", kinds)

    def test_bracket_escape_is_clean(self):
        """[[编辑] 是合法转义（输出字面 [），不能误报。"""
        crashed, kinds = _run(
            'mii "{i}Take care.{/i} {size=-10}[[Edited]{/size}"',
            'mii "{i}小心点哦。{/i} {size=-10}[[编辑]{/size}"',
        )
        self.assertFalse(crashed, msg=f"误报合法转义: {kinds}")
        self.assertNotIn("伪插值[非ASCII]", kinds)

    def test_real_interpolation_is_clean(self):
        """真变量名/带旗标/下标里的中文字符串字面量，都不算伪插值。"""
        for name, old, new in [
            ("真变量", "bond [yoshie_bond] pts", "羁绊 [yoshie_bond] 点"),
            ("!t旗标", "val [hp!t] pts", "值 [hp!t] 点"),
            ("下标含中文串", 'name [d["suzu"]] ah', '名 [d["苏苏"]] 啊'),
            ("带空格的属性", "v [player.name] x", "值 [player.name] 哦"),
        ]:
            with self.subTest(name=name):
                _crashed, kinds = _run(old, new)
                self.assertNotIn("伪插值[非ASCII]", kinds,
                                 msg=f"误报合法插值 {name}: {kinds}")


class TestFileRewriteKeepsEncoding(unittest.TestCase):
    """--fix 写回时必须保持 BOM 与行尾，不做静默改写。"""

    def _write(self, text, bom, crlf):
        d = tempfile.mkdtemp()
        game = Path(d) / "game" / "tl" / "schinese"
        game.mkdir(parents=True)
        body = text.replace("\n", "\r\n") if crlf else text
        p = game / "a_translated.rpy"
        raw = body.encode("utf-8")
        if bom:
            raw = b"\xef\xbb\xbf" + raw
        p.write_bytes(raw)
        return p

    def test_bom_and_crlf_preserved(self):
        for bom in (True, False):
            for crlf in (True, False):
                with self.subTest(bom=bom, crlf=crlf):
                    # 一行能被 --fix 改动的译文：花括号内带空格的标签
                    p = self._write(
                        'translate schinese x_1:\n\n'
                        '    # "{i}Hi{/i}"\n'
                        '    "{ i }你好{/i}"\n',
                        bom, crlf,
                    )
                    issues, untr = [], []
                    T.check_file(p, issues, untr, do_fix=True, label="a.rpy")
                    raw = p.read_bytes()
                    self.assertEqual(raw.startswith(b"\xef\xbb\xbf"), bom,
                                     msg="BOM 被改写")
                    self.assertEqual(b"\r\n" in raw, crlf,
                                     msg="行尾被改写")


def _write_min_xlsx(path, rows):
    """用标准库造一个最小 xlsx（sharedStrings + sheet1），验证零依赖读取。"""
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    shared, index = [], {}
    for row in rows:
        for cell in row:
            if cell not in index:
                index[cell] = len(shared)
                shared.append(cell)
    sst = ('<?xml version="1.0" encoding="UTF-8"?>'
           f'<sst xmlns="{ns}">'
           + "".join(f"<si><t>{c}</t></si>" for c in shared)
           + "</sst>")
    body = []
    for r, row in enumerate(rows, 1):
        cells = "".join(
            f'<c r="{"ABCDEFGH"[i]}{r}" t="s"><v>{index[c]}</v></c>'
            for i, c in enumerate(row)
        )
        body.append(f'<row r="{r}">{cells}</row>')
    sheet = ('<?xml version="1.0" encoding="UTF-8"?>'
             f'<worksheet xmlns="{ns}"><sheetData>'
             + "".join(body) + "</sheetData></worksheet>")
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("xl/sharedStrings.xml", sst)
        z.writestr("xl/worksheets/sheet1.xml", sheet)


class TestGlossaryConsistency(unittest.TestCase):
    """--glossary 术语一致性：原文命中词条、译文却没出现定稿译名。"""

    def _terms(self, data, suffix=".jsonl"):
        d = tempfile.mkdtemp()
        p = Path(d) / ("g" + suffix)
        if suffix == ".jsonl":
            p.write_text(
                "\n".join(json.dumps(r, ensure_ascii=False) for r in data),
                encoding="utf-8")
        else:
            p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return T.load_glossary_terms(str(p))

    def _kinds(self, old, new, terms):
        issues = []
        T.compare(old, new, "t:1", issues, terms=terms)
        return issues

    def test_missing_term_is_reported(self):
        terms = self._terms([{"src": "Eileen", "dst": "艾琳"}])
        issues = self._kinds("Eileen smiled at me.", "她朝我笑了笑。", terms)
        self.assertIn("术语未落实", {k for _, _lv, k, _ in issues})
        self.assertTrue(any(lv == "术语" for _, lv, _, _ in issues))

    def test_present_term_is_clean(self):
        terms = self._terms([{"src": "Eileen", "dst": "艾琳"}])
        issues = self._kinds("Eileen smiled.", "艾琳朝我笑了笑。", terms)
        self.assertNotIn("术语未落实", {k for _, _lv, k, _ in issues})

    def test_whole_word_boundary(self):
        """术语 Ann 不能命中原文里的 Announce——整词边界是必需的。"""
        terms = self._terms([{"src": "Ann", "dst": "安"}])
        issues = self._kinds("Announce the plan to everyone.", "向大家宣布计划。", terms)
        self.assertNotIn("术语未落实", {k for _, _lv, k, _ in issues})

    def test_case_insensitive(self):
        terms = self._terms([{"src": "Eileen", "dst": "艾琳"}])
        issues = self._kinds("EILEEN is here.", "她来了。", terms)
        self.assertIn("术语未落实", {k for _, _lv, k, _ in issues})

    def test_single_letter_ascii_term_dropped(self):
        self.assertEqual(self._terms([{"src": "I", "dst": "我"}]), [])

    def test_rows_without_dst_are_dropped(self):
        """资格待定（dst 空）的词条没有「定稿译名」可核对，直接丢。"""
        self.assertEqual(self._terms([{"src": "Eileen", "dst": ""}]), [])

    def test_flat_json_loader(self):
        terms = self._terms({"Eileen": "艾琳"}, suffix=".json")
        self.assertEqual([(s, d) for s, d, _ in terms], [("Eileen", "艾琳")])

    def test_xlsx_is_read_by_stdlib(self):
        """AiNiee 三栏 xlsx（原文|译文|备注）：零依赖读取，表头不当词条。"""
        d = tempfile.mkdtemp()
        p = Path(d) / "术语表.xlsx"
        _write_min_xlsx(p, [["原文", "译文", "备注"],
                            ["Eileen", "艾琳", ""],
                            ["Suzu", "苏苏", "简称"]])
        terms = T.load_glossary_terms(str(p))
        self.assertEqual([(s, dst) for s, dst, _ in terms],
                         [("Eileen", "艾琳"), ("Suzu", "苏苏")])

    def test_missing_glossary_file_is_fail_closed(self):
        """显式点名的输入读不到就报错退出，不能静默变绿。"""
        with self.assertRaises(SystemExit):
            T.load_glossary_terms(os.path.join(tempfile.mkdtemp(), "nope.json"))

    def test_cli_end_to_end(self):
        """走一遍 main：命中缺失术语 → 退出码 1（术语级计入退出码）。"""
        d = tempfile.mkdtemp()
        tl = Path(d) / "game" / "tl" / "schinese"
        tl.mkdir(parents=True)
        (tl / "a.rpy").write_text(
            'translate schinese a_1:\n\n    # "Eileen smiled."\n    "她笑了笑。"\n',
            encoding="utf-8")
        g = Path(d) / "g.jsonl"
        g.write_text(json.dumps({"src": "Eileen", "dst": "艾琳"}, ensure_ascii=False),
                     encoding="utf-8")
        with self.assertRaises(SystemExit) as cm:
            _main([str(Path(d) / "game"), "--lang", "schinese",
                   "--glossary", str(g)])
        self.assertEqual(cm.exception.code, 1)


class TestLanguageRatio(unittest.TestCase):
    """--lang-ratio 语言分块判定（纯启发式，只做块级判定）。"""

    ZH = "她笑了笑，什么也没说。"
    EN = "She smiled and said nothing at all."

    def _rows(self, n_zh, n_en, prefix="a.rpy"):
        return [(f"{prefix}:{i}", self.ZH if i <= n_zh else self.EN)
                for i in range(1, n_zh + n_en + 1)]

    def test_english_block_under_chinese_target_is_reported(self):
        issues = T.lang_ratio_issues(self._rows(0, 6), "zh", 0.75)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0][2], "语言不匹配")
        self.assertEqual(issues[0][1], "显示")

    def test_chinese_block_is_clean(self):
        self.assertEqual(T.lang_ratio_issues(self._rows(6, 0), "zh", 0.75), [])

    def test_one_stray_line_is_diluted(self):
        """19 中 + 1 英 = 95% ≥ 阈值：单行误判不该刷屏。"""
        self.assertEqual(T.lang_ratio_issues(self._rows(19, 1), "zh", 0.75), [])

    def test_short_block_is_skipped(self):
        """样本不足不判——4 行都报出来就是噪音。"""
        self.assertEqual(T.lang_ratio_issues(self._rows(0, 4), "zh", 0.75), [])

    def test_kana_block_is_not_chinese(self):
        rows = [(f"a.rpy:{i}", "そりゃそうだよね、そうだよ。") for i in range(1, 6)]
        self.assertEqual(len(T.lang_ratio_issues(rows, "zh", 0.75)), 1)

    def test_lines_without_language_info_are_ignored(self):
        rows = [(f"a.rpy:{i}", "100%") for i in range(1, 6)]
        self.assertEqual(T.lang_ratio_issues(rows, "zh", 0.75), [])

    def test_latin_family_accepts_english(self):
        self.assertEqual(T.lang_ratio_issues(self._rows(0, 6), "latin", 0.75), [])

    def test_language_family_mapping(self):
        self.assertEqual(T.target_lang_family("schinese"), "zh")
        self.assertEqual(T.target_lang_family("tchinese"), "zh")
        self.assertEqual(T.target_lang_family("japanese"), "ja")
        self.assertEqual(T.target_lang_family("english"), "latin")
        self.assertIsNone(T.target_lang_family("russian"))


def _main(argv):
    old = sys.argv
    sys.argv = ["tl_check.py"] + argv
    try:
        T.main()
    finally:
        sys.argv = old


if __name__ == "__main__":
    unittest.main(verbosity=2)
