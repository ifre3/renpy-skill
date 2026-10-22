#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tag_repair 结构修复层回归测试。

这批用例锁的是**两类边界**，各自由正例 + 反例双向断言：

1. 修复正确性 —— 声明能修的形态必须真修好（tag_problems 为空）。
2. 不误伤 —— 本来就健康的句子一个字符都不许动。第 2 类比第 1 类更要紧：
   结构修复会重写标签，一旦在健康句上乱补 Through，就把原本正确的斜体、
   {size=} 参数毁掉了，而且用户很难察觉。

所以每个修复用例都配对一条"不该动"的相近句子，把边界钉住。

运行（仅标准库）::

    cd scripts/tests
    python -m unittest test_tag_repair -v
"""

import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SDK = os.path.join(os.path.dirname(_HERE), "sdk")
_CHECK = os.path.join(os.path.dirname(_HERE), "checks")
_SHARED = os.path.join(os.path.dirname(_HERE), "shared")
for p in (_SDK, _CHECK, _SHARED):
    if p not in sys.path:
        sys.path.insert(0, p)

import tag_repair as M  # noqa: E402


def repair(old, new):
    """返回修复后的译文串。"""
    got, _notes = M.repair_line(new, old)
    return got


class TestTagsRepaired(unittest.TestCase):
    """该修的形态必须修好。"""

    def test_orphan_close_gets_opener(self):
        got = repair('Right… {i}ripped{/i}.', '嗯……撕裂了{/i}。')
        self.assertFalse(M.tag_problems(got))
        self.assertIn('{i}', got)

    def test_malformed_open_angle_bracket(self):
        got = repair('... {i}Sensei{/i}.', '老师的{i>教{/i}。')
        self.assertEqual(got, '老师的{i}教{/i}。')

    def test_malformed_open_square_bracket(self):
        got = repair('{i}How far back?!{/i}', '{i]多久以前啊？{/i}')
        self.assertEqual(got, '{i}多久以前啊？{/i}')

    def test_chinese_inside_braces_becomes_literal(self):
        got = repair('{i}Haahhh…{/i}', '{我}哈啊啊啊……{/i}')
        self.assertFalse(M.tag_problems(got))
        self.assertIn('我', got)
        self.assertNotIn('{我}', got)

    def test_unclosed_tail_is_closed(self):
        got = repair('take things {i}too{/i} far', '把事情{i}搞{/i>太远了')
        self.assertFalse(M.tag_problems(got))

    def test_double_orphan_close(self):
        got = repair('{i}Haahhh…{/i}', '哈啊啊啊……{/i}{/i}')
        self.assertFalse(M.tag_problems(got))

    def test_nesting_mismatch(self):
        got = repair('{i}That {s}said{/s} now.{/i}', '{i}话虽如此{/s}现在.{/i}')
        self.assertFalse(M.tag_problems(got))


class TestInterpolationRestored(unittest.TestCase):
    """插值必须还原成原文变量 —— 否则引擎 KeyError。"""

    def test_case_is_restored(self):
        got = repair('…is that you, [pn]?', '……是你吗？[PN]')
        self.assertIn('[pn]', got)
        self.assertNotIn('[PN]', got)

    def test_translated_name_is_restored(self):
        got = repair("Atsuko's bond [atsuko_bond]!", '阿梓子的羁绊[阿梓子羁绊]！')
        self.assertIn('[atsuko_bond]', got)

    def test_misspelled_name_is_restored(self):
        got = repair("Chiyo's bond [chiyo_bond]!", '千与[chyo_bond]！')
        self.assertIn('[chiyo_bond]', got)


class TestHealthyUntouched(unittest.TestCase):
    """健康的句子必须原样返回 —— 这是最重要的一组断言。"""

    def test_plain_sentence(self):
        for old, new in [
            ('Hello [pn], ok?', '你好[pn]，好吗？'),
            ('{i}Hi{/i} [pn].', '{i}你好{/i}[pn]。'),
            ('{cps=3}...{/cps}', '{cps=3}……{/cps}'),
        ]:
            self.assertEqual(repair(old, new), new, msg=old)

    def test_sizeed_tag_with_empty_braces_is_kept(self):
        # {}{size} 属于已平衡（{} 不成标签），不许擅自改写
        old = '{i}Take care.{/i} {size=-10}[[Edited]{/size}'
        new = '{i}小心点哦。{/i} {size=-10}[[编辑]{}{size}'
        self.assertEqual(repair(old, new), new)

    def test_nested_properly_closed(self):
        # 真正已正确嵌套的句子：原样返回
        old = '{i}{b}That{/b} is time.{/i}'
        new = '{i}{b}时间会说明一切。{/b}{/i}'
        self.assertEqual(repair(old, new), new)

    def test_missing_tail_close_is_closed_not_realigned(self):
        """只缺句尾闭合时，补在句尾 —— 不许把闭合插进句子中间。

        曾经的行为：按原文 {b} 只裹 "That" 的比例做重排，把 {/b} 插到
        "时间" 之后（{i}{b}时间{/b}会说明一切。{/i}），把本来就通顺的
        中文改坏。缺失的是闭合而非开标签，正确修法是句尾补齐。
        """
        old = '{i}{b}That{/b} is time.{/i}'
        new = '{i}{b}时间会说明一切。{/i}'
        got = repair(old, new)
        self.assertEqual(got, '{i}{b}时间会说明一切。{/b}{/i}')
        self.assertFalse(M.tag_problems(got))
        # 中文一字未动
        self.assertIn('时间会说明一切。', got)

    def test_multiple_interps_untouched(self):
        old = '[a] and [b] and [a]'
        new = '[a]和[b]以及[a]'
        self.assertEqual(repair(old, new), new)

    def test_no_extra_pair_inserted(self):
        """修复结果里不许出现空标签对 {i}{/i} —— 那是定位失败的标志。"""
        cases = [
            ('Right… {i}ripped{/i}.', '嗯……撕裂了{/i}。'),
            ('{i}Haahhh…{/i}', '{我}哈啊啊啊……{/i}'),
            ('{i}That {s}said{/s} now.{/i}', '{i}话虽如此{/s}现在.{/i}'),
        ]
        for old, new in cases:
            got = repair(old, new)
            self.assertNotIn('{}', got.replace('{{', '').replace('}}', ''),
                             msg='%s -> %s' % (new, got))
            for name in ('i', 'b', 's', 'u'):
                self.assertNotIn('{%s}{/%s}' % (name, name), got,
                                 msg='空标签对 %s: %s' % (name, got))


class TestOldTextIsGroundTruth(unittest.TestCase):
    """原文有 bug 时不猜；没有原文时不动手。"""

    def test_original_having_bug_leaves_translation_alone(self):
        # 原文自己 {i}...{/b} 不平衡：译文无需背锅
        got = repair('{i}After all.{/b}', '{i}毕竟是这样。{/b}')
        self.assertEqual(got, '{i}毕竟是这样。{/b}')

    def test_missing_original_returns_unchanged(self):
        got, notes = M.repair_line('嗯……撕裂了{/i}。', None)
        self.assertEqual(got, '嗯……撕裂了{/i}。')
        self.assertEqual(notes, [])


class TestBalancedAfterRepair(unittest.TestCase):
    """全形态冒烟：修完必须平衡，且不丢原有的中文内容。"""

    CASES = [
        ('Right… {i}ripped{/i}.', '嗯……撕裂了{/i}。'),
        ('{i}Haahhh…{/i}', '{我}哈啊啊啊……{/i}'),
        ('take things {i}too{/i} far', '把事情{i}搞{/i>太远了'),
        ('{i}That {s}said{/s} now.{/i}', '{i}话虽如此{/s}现在.{/i}'),
        ('{b}Sayu— sit.{b}', '{b}Sayu——坐下吧。{/b}'),
        ('{i}{b}That{/b} told.{/i}', '{i}{b}时间会说明一切。{/i}'),
    ]

    def test_all_cases_balanced(self):
        for old, new in self.CASES:
            got = repair(old, new)
            self.assertFalse(M.tag_problems(got),
                             msg='原=%s 译=%s 结果=%s' % (old, new, got))

    def test_chinese_content_preserved(self):
        """译文里的汉字必须全部保留（不允许丢字）。"""
        import re as _re
        for old, new in self.CASES:
            got = repair(old, new)
            before = _re.findall(r'[\u4e00-\u9fff]', new)
            after = _re.findall(r'[\u4e00-\u9fff]', got)
            self.assertEqual(before, after,
                             msg='汉字被改动: %s -> %s' % (new, got))


if __name__ == "__main__":
    unittest.main()
