#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""plan_batches 回归：钉住三条硬约束（2026-10-11 Dissonance 0.14 实测）。

背景：``references/translation_polish.md`` 的策略一写了「~200 句/批」「在
polish_state.json 维护批次状态」，但此前没有任何脚本产出它们。plan_batches
把切批 / 场景分组 / 提示词装上下文 / 账本合成一次遍历，本文件钉住它
**不能退化**的三条：

1. **场景段不被劈开** —— 实测：tl 里 44,409 个块去哈希后 2,129 个场景名，
   但连续同场景段平均仅约 12 条、最长 223 条。所以「每场景一批」会切成
   3,659 批，比不切还糟；正确形态是**以场景为边界、按上限合并相邻场景**。
   只有单场景超上限才按条切，且必须标 ``split=True``。
2. **已 consumed 的批次不再产出** —— 落实「润色只做一轮，越润越差」。
3. **锚点齐全** —— 批次条目必须能直接进 ``autotranslate.py apply``，
   缺 file/line/type/orig 就会被安全网整批跳过。

外加账本不膨胀（重排未消费批次，而不是无限追加）。

2026-10-18 追加 `TestPolishStructureGate`：``merge_polish.py`` 的结构守恒门。
润色只该改措辞不该动结构，但管线里下游两步（merge、apply）都只核锚点，丢标签
要等回填完跑 tl_check 才发现。规则取自 AiNiee 润色阶段的 ResponseChecker。

运行::

    cd renpy/scripts/tests
    python -m unittest test_polish_batches -v
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_TOOLS = os.path.dirname(_HERE)
_POLISH = os.path.join(_TOOLS, "polish")
if _POLISH not in sys.path:
    sys.path.insert(0, _POLISH)

import merge_polish as M  # noqa: E402
import plan_batches as P  # noqa: E402


def _e(file, line, scene_hint=None, char="", orig="Hi", trans="嗨"):
    d = {"file": file, "line": line, "src_line": line + 1,
         "type": "cd" if char else "tb",
         "orig": orig, "trans": trans, "char": char}
    if scene_hint is not None:
        d["scene"] = scene_hint
    return d


class TestSceneSegmentation(unittest.TestCase):
    """以场景为边界切段，同一场景的多次出现算多段。"""

    def test_contiguous_same_scene_is_one_segment(self):
        entries = [_e("a.rpy", i, "scene_x") for i in range(1, 6)]
        segs = P.build_scene_segments(entries)
        self.assertEqual(len(segs), 1)
        self.assertEqual(len(segs[0][1]), 5)

    def test_scene_change_starts_new_segment(self):
        entries = ([_e("a.rpy", i, "s1") for i in range(1, 4)]
                   + [_e("a.rpy", i, "s2") for i in range(4, 7)])
        segs = P.build_scene_segments(entries)
        self.assertEqual(len(segs), 2)

    def test_same_scene_twice_is_two_segments(self):
        """场景在文件里出现两次 → 两个段，不硬合并（它们本来不连续）。"""
        entries = ([_e("a.rpy", i, "s1") for i in range(1, 4)]
                   + [_e("a.rpy", i, "s2") for i in range(4, 7)]
                   + [_e("a.rpy", i, "s1") for i in range(7, 10)])
        segs = P.build_scene_segments(entries)
        self.assertEqual(len(segs), 3)

    def test_file_change_starts_new_segment(self):
        entries = [_e("a.rpy", 1, "s1"), _e("b.rpy", 2, "s1")]
        self.assertEqual(len(P.build_scene_segments(entries)), 2)


class TestBatchPlanning(unittest.TestCase):
    """合并相邻场景装满一批；不劈开段。"""

    def test_small_segments_are_merged(self):
        """实测常态：每段约 12 条，必须合并成 ~200 条一批。"""
        segs = [(("a.rpy", f"s{i}"), [_e("a.rpy", j, f"s{i}")
                                      for j in range(i * 20, i * 20 + 12)])
                for i in range(1, 21)]  # 20 段 × 12 = 240 条
        batches = P.plan(segs, 200)
        self.assertEqual(sum(len(b[0]) for b in batches), 240)
        self.assertGreater(len(batches), 1)
        for items, _scenes, split in batches:
            self.assertFalse(split)
            self.assertLessEqual(len(items), 200)

    def test_segment_not_split_across_batches(self):
        """一个 100 条的段必须整段进某批，不能被 200 上限劈开。"""
        big = [_e("a.rpy", i, "big") for i in range(1, 101)]
        segs = [(("a.rpy", "big"), big)]
        batches = P.plan(segs, 200)
        self.assertEqual(len(batches), 1)
        self.assertEqual(len(batches[0][0]), 100)

    def test_oversized_segment_is_split_and_flagged(self):
        """单场景超过上限才按条切，且每片都标 split=True。"""
        big = [_e("a.rpy", i, "huge") for i in range(1, 451)]
        segs = [(("a.rpy", "huge"), big)]
        batches = P.plan(segs, 200)
        self.assertEqual(len(batches), 3)
        self.assertEqual(sum(len(b[0]) for b in batches), 450)
        for items, scenes, split in batches:
            self.assertTrue(split, "被切开的大场景必须标 split=True")
            self.assertEqual(scenes, ["huge"])
            self.assertLessEqual(len(items), 200)

    def test_all_entries_preserved(self):
        segs = [(("a.rpy", f"s{i}"), [_e("a.rpy", j, f"s{i}")
                                      for j in range(i * 10, i * 10 + 7)])
                for i in range(1, 30)]
        batches = P.plan(segs, 200)
        got = [e["line"] for _it, _s, _sp in batches for e in _it]
        want = [e["line"] for _k, items in segs for e in items]
        self.assertEqual(sorted(got), sorted(want))


class TestApplyAnchors(unittest.TestCase):
    """批次条目必须能直接进 autotranslate apply。"""

    def test_entry_has_required_fields(self):
        e = _e("a.rpy", 12, char="t")
        out = P._entry_for_apply(e)
        for k in ("file", "line", "type", "orig", "trans"):
            self.assertIn(k, out)
        self.assertEqual(out["char"], "t")
        self.assertIsInstance(out["line"], int)

    def test_no_char_for_narration(self):
        out = P._entry_for_apply(_e("a.rpy", 1))
        self.assertNotIn("char", out)

    def test_new_trans_replaces(self):
        out = P._entry_for_apply(_e("a.rpy", 1), new_trans="润色后")
        self.assertEqual(out["trans"], "润色后")


class TestLedgerIdempotency(unittest.TestCase):
    """已 consumed 的批次不再产出；账本不膨胀。"""

    def _run(self, entries, out, state=None):
        pool = os.path.join(out, "pool.json")
        Path(pool).write_text(json.dumps(entries, ensure_ascii=False),
                              encoding="utf-8")
        if state is not None:
            Path(out, "polish_state.json").write_text(
                json.dumps(state, ensure_ascii=False), encoding="utf-8")
        argv = ["plan_batches.py", "--pool", pool, "-o", out,
                "--batch-size", "50"]
        old = sys.argv
        sys.argv = argv
        try:
            P.main()
        finally:
            sys.argv = old
        return json.loads(Path(out, "polish_state.json").read_text(encoding="utf-8"))

    def test_consumed_batch_not_reproduced(self):
        with tempfile.TemporaryDirectory() as d:
            entries = [_e("a.rpy", i, "s1") for i in range(1, 201)]
            st = self._run(entries, d)
            n_first = len(st["batches"])
            self.assertGreater(n_first, 1)
            # 标第一批为已完成
            st["batches"][0]["consumed"] = True
            st2 = self._run(entries, d, st)
            # 账本总量不变（未消费的重排，已消费的保留）
            self.assertEqual(len(st2["batches"]), n_first)
            consumed = [b for b in st2["batches"] if b["consumed"]]
            self.assertEqual(len(consumed), 1)

    def test_ledger_does_not_grow_on_rerun(self):
        """重跑不能无限追加——这是实现时真踩过的 bug。"""
        with tempfile.TemporaryDirectory() as d:
            entries = [_e("a.rpy", i, "s1") for i in range(1, 201)]
            st = self._run(entries, d)
            n = len(st["batches"])
            for _ in range(3):
                st = self._run(entries, d, st)
            self.assertEqual(len(st["batches"]), n,
                             "重复运行让账本膨胀了——未消费批次应被重排而非追加")

    def test_batch_files_written(self):
        with tempfile.TemporaryDirectory() as d:
            entries = [_e("a.rpy", i, "s1") for i in range(1, 201)]
            st = self._run(entries, d)
            for b in st["batches"]:
                self.assertTrue(Path(d, b["json"]).is_file())
                self.assertTrue(Path(d, b["prompt"]).is_file())


class TestPromptContent(unittest.TestCase):
    """提示词必须自带禁改清单，否则 AI 会破坏标签/插值/百分号。"""

    def test_do_not_touch_present(self):
        items = [_e("a.rpy", 1, "s1", char="t")]
        md = P.render_prompt(1, items, ["s1"], False, [("t", 1)], [], None)
        self.assertIn("{tag}", md)
        self.assertIn("[var]", md)
        self.assertIn("%%", md)

    def test_split_flag_shows_warning(self):
        items = [_e("a.rpy", 1, "big")]
        md = P.render_prompt(1, items, ["big"], True, [], [], None)
        self.assertIn("同一场景", md)

    def test_prev_terms_carried_over(self):
        """跨批术语必须带过去，否则术语会漂移。"""
        items = [_e("a.rpy", 1, "s1")]
        md = P.render_prompt(2, items, ["s1"], False, [],
                             ["敦子→Atsuko"], None)
        self.assertIn("敦子→Atsuko", md)

    def test_prompt_lists_all_entries(self):
        items = [_e("a.rpy", i, "s1") for i in range(1, 11)]
        md = P.render_prompt(1, items, ["s1"], False, [], [], None)
        for e in items:
            self.assertIn(f"{e['file']}:{e['line']}", md)


class TestPromptIsScriptNotTable(unittest.TestCase):
    """提示词必须是「连续剧本 + 允许不改」，而不是逐行矫正表（2026-10-18）。

    背景：Dissonance 0.14 实测，旧版提示词有三个结构性问题——
    1. 渲染成 `| file:line | 角色 | 原文 | 译文 |` 表格，每行孤立，模型看不到
       前后句，遑论「上下文流畅」；
    2. 原文/译文一律截断到 90 字，实测 39.4% 的行原文被砍半，模型读半句无法
       判断语病与衔接；
    3. 角色定义是「去翻译腔/改口语/修正语法」三件事，等于鼓励逐行找茬，
       与本项目自己的结论「润色只做一轮、越润越差」相悖。
    """

    def _md(self, items):
        return P.render_prompt(1, items, ["s1"], False, [], [], None)

    def test_no_markdown_table(self):
        items = [_e("a.rpy", i, "s1") for i in range(1, 6)]
        md = self._md(items)
        self.assertNotIn("| file:line |", md)
        self.assertNotIn("|---|---|---|---|", md)

    def test_scene_heading_present(self):
        items = [_e("a.rpy", 1, "s1"), _e("a.rpy", 2, "s1"), _e("a.rpy", 3, "s2")]
        md = self._md(items)
        self.assertIn("s1", md)
        self.assertIn("s2", md)

    def test_long_line_not_truncated(self):
        """长句必须完整给出——审稿读半句没法判断通不通顺。

        只查剧本段：禁改清单里 `{cps=…}` 本身就带省略号，那是模板文本，
        与内容截断无关。译文在 Tier A/B 下都会给，原文只在 Tier B 给。
        """
        long_en = "A" * 300
        long_zh = "汉" * 300
        items = [_e("a.rpy", 1, "s1", orig=long_en, trans=long_zh)]
        md = self._md(items)
        script = md.split("## 剧本", 1)[-1]
        self.assertIn(long_zh, script)
        self.assertNotIn("…", script)


class TestTierSplit(unittest.TestCase):
    """Tier A 只给译文、Tier B 才给原文（2026-10-18）。

    依据：语病/语序/冗余/语气靠译文就能判断；语义/术语/完整性必须对照原文，
    否则是瞎猜（实测教训：把 `私室` 猜成「包厢」）。
    """

    def _md(self, items):
        return P.render_prompt(1, items, ["s1"], False, [], [], None)

    def test_plain_chinese_is_tier_a(self):
        self.assertEqual(P.classify_entry({"orig": "Hello there.", "trans": "你好啊。"})[0], "A")

    def test_foreign_residue_is_tier_b(self):
        tier, reasons = P.classify_entry(
            {"orig": "I call the one and only Absuko...",
             "trans": "我拨通了那位唯一的 Absuko……"})
        self.assertEqual(tier, "B")
        self.assertTrue(reasons)

    def test_kana_is_tier_b(self):
        tier, _ = P.classify_entry({"orig": "こんにちは", "trans": "こんにちは"})
        self.assertEqual(tier, "B")

    def test_suspiciously_short_is_tier_b(self):
        """译文远短于原文 → 疑似漏译，必须对照原文。"""
        tier, reasons = P.classify_entry({
            "orig": "I went to the store and bought some bread and milk for breakfast",
            "trans": "我去了商店。"})
        self.assertEqual(tier, "B")
        self.assertTrue(any("漏译" in r for r in reasons))

    def test_placeholder_is_tier_a(self):
        """纯占位行无可审内容，不该升级到 Tier B 白白带原文。"""
        self.assertEqual(P.classify_entry({"orig": "...", "trans": "..."})[0], "A")

    def test_tier_a_hides_original(self):
        md = self._md([_e("a.rpy", 1, "s1", orig="Secret English line here.",
                          trans="普通中文句子。")])
        script = md.split("## 剧本", 1)[-1]
        self.assertNotIn("Secret English line", script)

    def test_tier_b_shows_original_and_marker(self):
        md = self._md([_e("a.rpy", 1, "s1", orig="I call the one and only Absuko...",
                          trans="我拨通了那位唯一的 Absuko……")])
        script = md.split("## 剧本", 1)[-1]
        self.assertIn("Absuko", script)
        self.assertIn("⚠", script)

    def test_tags_do_not_trigger_tier_b(self):
        """{tag} [插值] 不该被当成外文残留。"""
        tier, _ = P.classify_entry({
            "orig": "Hi", "trans": "{i}你好{/i}，[name]！"})
        self.assertEqual(tier, "A")

    def test_allows_unchanged(self):
        """提示词必须给「不修改」留出口，并允许省略未改动行。"""
        items = [_e("a.rpy", 1, "s1")]
        md = self._md(items)
        self.assertIn("保持原样", md)
        self.assertIn("只列出", md)

    def test_editor_framing_not_fix_three_things(self):
        """角色定义应是审稿人通读，而不是「做三件事」的矫正清单。"""
        items = [_e("a.rpy", 1, "s1")]
        md = self._md(items)
        self.assertIn("审稿", md)
        self.assertIn("连贯", md)


class TestUnchangedLinesDropped(unittest.TestCase):
    """merge_polish：模型输出了「与旧译文相同」的行 → 不回填。"""

    def _merge(self, pool_trans, new_trans):
        d = tempfile.mkdtemp()
        pool = Path(d) / "pool.json"
        fixes = Path(d) / "fixes.json"
        out = Path(d) / "batch.json"
        pool.write_text(json.dumps(
            [{"file": "a.rpy", "line": 10, "type": "tb", "orig": "Hi",
              "trans": pool_trans}], ensure_ascii=False), encoding="utf-8")
        fixes.write_text(json.dumps({"a.rpy:10": new_trans}, ensure_ascii=False),
                         encoding="utf-8")
        rc = M.main(["--pool", str(pool), "--fixes", str(fixes), "-o", str(out)])
        return rc, json.loads(out.read_text(encoding="utf-8"))

    def test_identical_translation_dropped(self):
        """模型判断「不用改」并原样输出 → 不入批次（回填与否等价，且污染 diff）。"""
        rc, entries = self._merge("嗨", "嗨")
        self.assertEqual(rc, 0)
        self.assertEqual(entries, [])

    def test_genuine_edit_kept(self):
        rc, entries = self._merge("嗨", "嗨呀")
        self.assertEqual(rc, 0)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["trans"], "嗨呀")


class TestSceneMap(unittest.TestCase):
    """场景 label 回扫（去哈希 + 上溯匹配原文注释行）。"""

    def test_label_hash_stripped(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "a.rpy").write_text(
                'translate schinese foo_1a2b3c4d:\n\n    # "Hi"\n    "嗨"\n',
                encoding="utf-8")
            m = P.load_scene_map(d)
            self.assertIn(("a.rpy", 1), m)
            self.assertEqual(m[("a.rpy", 1)], "foo")

    def test_attach_scenes_finds_label_above(self):
        """原文注释在 label 行下面 2 行：必须能上溯找到。"""
        scene_map = {("a.rpy", 1): "foo"}
        entries = [_e("a.rpy", 3)]
        P.attach_scenes(entries, scene_map)
        self.assertEqual(entries[0]["scene"], "foo")

    def test_missing_tl_dir_degrades_gracefully(self):
        self.assertEqual(P.load_scene_map("/nonexistent/xyz"), {})


class TestPolishStructureGate(unittest.TestCase):
    """merge_polish 的结构守恒门：润色稿不能破坏标签/插值/换行。

    基线是**润色前译文**（与 AiNiee 的 PolisherTask 同口径），不是英文原文——
    这样判据收窄成「这次润色有没有引入新损伤」，历史遗留的结构损伤不会卡住整批。
    判据与 checks/tl_check.py 同口径：只拦「丢/多结构 token」与「换行数增加」；
    润色前译文有换行而润色后合并断行不拦（中英排版允许不同断行）。
    """

    def _merge(self, prev_trans, new_trans, orig="Hi there"):
        d = tempfile.mkdtemp()
        pool = Path(d) / "pool.json"
        fixes = Path(d) / "fixes.json"
        out = Path(d) / "batch.json"
        pool.write_text(json.dumps(
            [{"file": "a.rpy", "line": 10, "type": "tb", "orig": orig,
              "trans": prev_trans}], ensure_ascii=False), encoding="utf-8")
        fixes.write_text(json.dumps({"a.rpy:10": new_trans}, ensure_ascii=False),
                         encoding="utf-8")
        rc = M.main(["--pool", str(pool), "--fixes", str(fixes), "-o", str(out)])
        return rc, json.loads(out.read_text(encoding="utf-8"))

    def test_clean_polish_passes(self):
        rc, entries = self._merge(
            '她说："{i}你好{/i} [name]！"', '她轻声说："{i}你好呀{/i} [name]！"')
        self.assertEqual(rc, 0)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["trans"], '她轻声说："{i}你好呀{/i} [name]！"')

    def test_lost_tag_is_rejected(self):
        """润色把 {i}/{/i} 润丢了 → 不入批次（否则整句失衡会 raise）。"""
        rc, entries = self._merge('"{i}你好{/i}"', '"你好呀"')
        self.assertEqual(rc, 1)
        self.assertEqual(entries, [])

    def test_added_interpolation_is_rejected(self):
        """润色凭空加了 [嗯] → 引擎当 Python 表达式 eval（NameError）。"""
        rc, entries = self._merge('"嗨"', '"嗨 [嗯]"')
        self.assertEqual(rc, 1)
        self.assertEqual(entries, [])

    def test_single_line_split_is_rejected(self):
        rc, entries = self._merge('"嗨"', '"嗨\\n你好"')
        self.assertEqual(rc, 1)
        self.assertEqual(entries, [])

    def test_empty_translation_is_rejected(self):
        rc, entries = self._merge('"嗨"', "   ")
        self.assertEqual(rc, 1)
        self.assertEqual(entries, [])

    def test_merged_newline_is_allowed(self):
        """润色前译文有换行、润色合并成一行：不拦（与 tl_check「新增换行符」同口径）。"""
        rc, entries = self._merge('"第一行\\n第二行"', '"第一行第二行"')
        self.assertEqual(rc, 0)
        self.assertEqual(len(entries), 1)

    def test_percent_format_preserved(self):
        rc, entries = self._merge('"99%%确定，%(who)s"', '"有99%%的把握，%(who)s"')
        self.assertEqual(rc, 0)
        self.assertEqual(len(entries), 1)

    def test_dropped_percent_escape_is_rejected(self):
        """润色把 %% 润成单个 % → 引擎抛 Unknown string format code。"""
        rc, entries = self._merge('"99%%确定"', '"99%确定"')
        self.assertEqual(rc, 1)
        self.assertEqual(entries, [])

    def test_preexisting_damage_does_not_block(self):
        """历史遗留的结构损伤（原文有 {i} 而译文早就丢了）不该卡住润色。

        这道门只管「这次润色引入了什么」，结构修复是 tl_check --fix --settle 的活。
        """
        rc, entries = self._merge('"你好 [name]"', '"你好呀 [name]"',
                                  orig='"{i}Hi{/i} [name]"')
        self.assertEqual(rc, 0)
        self.assertEqual(len(entries), 1)

    def test_missing_anchor_still_only_warns(self):
        """原有行为不变：无锚点只警告、退出码仍是 0。"""
        d = tempfile.mkdtemp()
        pool = Path(d) / "pool.json"
        fixes = Path(d) / "fixes.json"
        out = Path(d) / "batch.json"
        pool.write_text("[]", encoding="utf-8")
        fixes.write_text(json.dumps({"a.rpy:99": "嗨"}), encoding="utf-8")
        rc = M.main(["--pool", str(pool), "--fixes", str(fixes), "-o", str(out)])
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out.read_text(encoding="utf-8")), [])

    def test_structure_diff_helper_reports_both_directions(self):
        problems = M.structure_diff('"{i}x{/i} [a]"', '"{i}х{/i} [a] [b]"')
        self.assertTrue(any("多" in p for p in problems), problems)


if __name__ == "__main__":
    unittest.main(verbosity=2)
