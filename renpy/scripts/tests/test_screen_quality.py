#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""screen_quality.py 硬性质校筛行的契约与误报边界回归。

覆盖维度（规则经验移植自 LinguaGacha，见 screen_quality.py 模块注释）：

1. 外文残留：夹生词命中（2026-10-06 用户截图例句固化为回归样本）+
   单字母 / 2-4 字大写缩写 / 免翻短语 / 事件编号 四类豁免边界
2. 假名残片：假名必报、汉字不报（与 tl_check 口径一致）
3. 半角标点：!?/, 命中、千分位豁免、无中文正文不判
4. 相似度漏翻：包含快判、Jaccard 阈值两侧、整句照抄不重复报
5. 语言门控：ja 目标假名合法、en 目标不查拉丁残留
6. CLI 端到端：真实 tl 目录 → 退出码与锚点 JSON

运行（仅用标准库）::

    cd scripts/tests
    python -m unittest test_screen_quality -v
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent          # scripts/tests
_TOOLS = _HERE.parent                           # scripts
for p in (_TOOLS, _TOOLS / "polish"):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

import screen_quality as sq  # noqa: E402


def _entry(orig, trans, **kw):
    e = {"file": "test.rpy", "line": 10, "src_line": 11, "type": "cd",
         "orig": orig, "trans": trans, "char": "e"}
    e.update(kw)
    return e


class TestForeignResidue(unittest.TestCase):
    """外文残留：聚合报证据 + 四类豁免。"""

    def test_screenshot_sentence_hits_hysterical(self):
        """2026-10-06 用户截图例句：夹生词必须命中（本仓库的回归锚点）。"""
        frags = sq.foreign_residue_fragments(
            "诺拉开始 hysterical 地大笑，吸引了屋里所有人的目光，让你有点不好意思。")
        self.assertEqual(frags, ["hysterical"])

    def test_single_letter_exempt(self):
        """单字母证据不足：A 班、X 光不报（LG 豁免规则）。"""
        self.assertEqual(sq.foreign_residue_fragments("A 班的同学去照 X 光。"), [])

    def test_uppercase_abbrev_exempt(self):
        """2-4 字全大写缩写豁免：HP/RPG/OK。混合大小写短词（Alt）不在豁免内。"""
        self.assertEqual(
            sq.foreign_residue_fragments("HP 归零了，RPG 游戏里这样玩才 OK。"), [])
        self.assertEqual(sq.foreign_residue_fragments("按 Alt 键"), ["Alt"])

    def test_lowercase_long_word_reported(self):
        """小写长词（hysterical 形态）必报——豁免只为缩写与单字母开洞。"""
        self.assertEqual(sq.foreign_residue_fragments("她拿了 rifle 和 ammunition"),
                         ["rifle", "ammunition"])

    def test_exempt_phrases(self):
        """免翻短语在拆段前剔除：DejaVu Sans / Ren'Py / renpy 不得拆词误报。"""
        self.assertEqual(sq.foreign_residue_fragments("字体用 DejaVu Sans，Ren'Py 引擎"), [])
        self.assertEqual(sq.foreign_residue_fragments("renpy 处理了它"), [])

    def test_event_code_exempt(self):
        """EV 事件编号豁免（LG rule-prefilter）。"""
        self.assertEqual(sq.foreign_residue_fragments("EV12 开启"), [])


class TestKana(unittest.TestCase):
    """假名残片：与 tl_check 同口径。"""

    def test_kana_reported(self):
        self.assertEqual(sq.kana_fragments("你没想？そりゃ当然没想"), ["そりゃ"])

    def test_kanji_not_reported(self):
        """纯汉字行不算假名残留：先輩 不报（tl_check 口径，と/は 这类假名才会命中）。"""
        self.assertEqual(sq.kana_fragments("先輩"), [])
        self.assertEqual(sq.kana_fragments("最近如何"), [])

    def test_kana_dedupe(self):
        """同片段去重；顿号打断连续段，各自成证据（tl_check kana_runs 同行为）。"""
        self.assertEqual(sq.kana_fragments("そりゃ、そりゃそうだ"), ["そりゃ", "そりゃそうだ"])


class TestHalfPunct(unittest.TestCase):
    """半角标点：!?/, 命中与豁免。"""

    def test_halfwidth_question(self):
        self.assertEqual(sq.half_punct_hits("真的吗?"), {"?"})

    def test_thousands_separator_exempt(self):
        self.assertEqual(sq.half_punct_hits("拾到 1,000 金币"), set())

    def test_comma_reported(self):
        self.assertEqual(sq.half_punct_hits("你好,世界"), {","})

    def test_no_cjk_no_report(self):
        """无中文正文的行不判（英文行合法用半角标点）。"""
        self.assertEqual(sq.half_punct_hits("Hello, world!"), set())


class TestSimilarity(unittest.TestCase):
    """相似度漏翻：LG 同口径（包含快判 + Jaccard 0.8）。"""

    def test_containment_untranslated(self):
        self.assertTrue(sq.is_similar(
            "毎日完璧な計画を立てるのが趣味だ", "毎日完璧な計画を立てるのが趣味だよ"))

    def test_identical_not_similar(self):
        """整句照抄不在此报——未翻译通道是 screen_suspicious/check_untranslated 的活。"""
        self.assertFalse(sq.is_similar("一模一样的句子", "一模一样的句子"))

    def test_proper_translation_not_similar(self):
        self.assertFalse(sq.is_similar("Hello.", "你好。"))

    def test_jaccard_above_threshold(self):
        """单字之差的局部漏翻：Jaccard 越过 0.8。"""
        self.assertTrue(sq.is_similar(
            "毎日完璧な計画を立てるのが趣味だ", "毎日完璧な計画を立てるのが趣味さ"))

    def test_jaccard_below_threshold(self):
        self.assertFalse(sq.is_similar("我是山上的石头", "你是水里的鱼儿"))


class TestEntryIssues(unittest.TestCase):
    """条目级集成：语言门控与双通道。"""

    def test_empty_trans_skipped(self):
        """空译文归专项工具（check_untranslated/tl_check），此处不报。"""
        self.assertEqual(sq.entry_issues(_entry("Hello.", "")), ([], False))

    def test_lang_japanese_kana_allowed_but_chinese_reports(self):
        e = _entry("もちろん、そうだ", "もちろん、就是这样")
        hits_ja, _ = sq.entry_issues(e, "japanese")
        hits_zh, _ = sq.entry_issues(e, "schinese")
        self.assertEqual(hits_ja, [])
        self.assertTrue(any(h.startswith("假名残片") for h in hits_zh))

    def test_english_target_no_residue_check(self):
        """en 目标不查拉丁残留（整行都是拉丁是正常译文形态）。"""
        hits, unt = sq.entry_issues(_entry("Darling!", "You got it, darling!"), "english")
        self.assertEqual(hits, [])
        self.assertFalse(unt)

    def test_similarity_goes_to_untranslated_channel(self):
        """含假名的漏翻行双通道都进：hits 报假名残片 + untranslated 报疑似漏翻。"""
        e = _entry("毎日完璧な計画を立てるのが趣味だ", "毎日完璧な計画を立てるのが趣味だよ")
        hits, unt = sq.entry_issues(e, "schinese")
        self.assertTrue(unt)
        self.assertTrue(any(h.startswith("假名残片") for h in hits))


class TestCli(unittest.TestCase):
    """CLI 端到端：真实 tl 目录。"""

    def _make_tl(self, root, body):
        tl = root / "tl" / "schinese"
        tl.mkdir(parents=True)
        (tl / "script.rpy").write_text(
            "translate schinese:\n\n" + body, encoding="utf-8")
        return tl

    def test_end_to_end_screenshot_sentence(self):
        """截图例句走完整管线：退出码 1 + 锚点齐全 + 命中 hysterical。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tl = self._make_tl(
                root,
                '    # e "Nora bursts out laughing hysterically."\n'
                '    e "诺拉开始 hysterical 地大笑，吸引了屋里所有人的目光。"\n'
                '    # e "See you."\n'
                '    e "回头见。"\n')
            out = root / "quality_candidates.json"
            r = subprocess.run(
                [sys.executable, str(_TOOLS / "polish" / "screen_quality.py"),
                 str(tl), "-o", str(out)],
                capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(len(data), 1)
            hit = data[0]
            self.assertEqual(hit["trans"], "诺拉开始 hysterical 地大笑，吸引了屋里所有人的目光。")
            self.assertIn("hysterical", hit["hits"][0])
            for key in ("file", "line", "orig", "trans"):
                self.assertIn(key, hit)
            unt = json.loads((root / "quality_untranslated.json").read_text(encoding="utf-8"))
            self.assertEqual(unt, [])

    def test_clean_project_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tl = self._make_tl(
                root,
                '    # e "See you."\n'
                '    e "回头见。"\n')
            out = root / "quality_candidates.json"
            r = subprocess.run(
                [sys.executable, str(_TOOLS / "polish" / "screen_quality.py"),
                 str(tl), "-o", str(out)],
                capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(json.loads(out.read_text(encoding="utf-8")), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
