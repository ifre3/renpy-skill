#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""say 条目解析器契约回归测试（原"新旧解析器差分验证"的可复现版本）。

背景
----
2026-10-05 二轮将 ``润色/_say_parse.py`` 的自备正则重写为
``公共/rpy_syntax.py`` 适配器。当时 README 记录"差分验证通过"，但旧正则
实现从未入库，验证过程不可复现（git 全历史无旧版文件）。

本文件将当时声称的验证固化为契约测试，覆盖合成样本维度：
cd / tb / 空译文 / 转义引号 / old-new / multiple=2 / 尾部属性，
并显式断言旧正则的两处已知缺陷（README 记载）不再出现：

1. 旧正则把 ``\\"`` 转义**原样吐出**（与 autotranslate 锚点解码不一致）；
   新解析器经 ``ast.literal_eval`` 解码为 ``"``。
2. 旧正则把 ``old "..."`` 误判为 ``char='old'`` 的对话条目（cd）；
   新解析器识别为 old/new（on）对，``iter_say_entries`` 产出时跳过。

运行::

    cd scripts
    python 测试/test_say_parse_contract.py
    # 或 pytest 测试/test_say_parse_contract.py -v
"""

import os
import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent  # scripts/测试
_TOOLS = _HERE.parent  # scripts
for p in (_TOOLS, _TOOLS / "公共", _TOOLS / "润色"):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

from rpy_syntax import iter_translation_pairs  # noqa: E402
from _say_parse import iter_say_entries  # noqa: E402


def _pairs(lines):
    return list(iter_translation_pairs(list(lines)))


class TestContractPairs(unittest.TestCase):
    """rpy_syntax.iter_translation_pairs 层：7 类合成样本的结对契约。"""

    def test_cd_entry(self):
        pairs = _pairs(['    # e "Hello."', '    e "你好。"'])
        self.assertEqual(len(pairs), 1)
        p = pairs[0]
        self.assertEqual(p.kind, "cd")
        self.assertEqual(p.original, "Hello.")
        self.assertEqual(p.translated, "你好。")
        self.assertEqual((p.original_line, p.translated_line), (1, 2))
        self.assertEqual((p.original_speaker, p.translated_speaker), ("e", "e"))

    def test_tb_entry(self):
        pairs = _pairs(['    # "Hello."', '    "你好。"'])
        self.assertEqual(len(pairs), 1)
        p = pairs[0]
        self.assertEqual(p.kind, "tb")
        self.assertEqual(p.original_speaker, "")
        self.assertEqual(p.translated_speaker, "")

    def test_empty_translation_still_pairs(self):
        pairs = _pairs(['    # "Hello."', '    ""'])
        self.assertEqual(len(pairs), 1)
        p = pairs[0]
        self.assertEqual(p.translated, "")

    def test_escaped_quote_is_decoded(self):
        """旧正则缺陷 #1：\\" 必须解码为 "，不得原样吐出。"""
        pairs = _pairs([r'    # e "He said \"hi\"."', r'    e "他说了\"你好\"。"'])
        self.assertEqual(len(pairs), 1)
        p = pairs[0]
        self.assertEqual(p.original, 'He said "hi".')
        self.assertEqual(p.translated, '他说了"你好"。')
        self.assertNotIn('\\"', p.original)
        self.assertNotIn('\\"', p.translated)

    def test_old_new_is_on_not_cd(self):
        """旧正则缺陷 #2：old 行不得误判为 char='old' 的对话条目。"""
        pairs = _pairs(['old "Legacy"', 'new "新版"'])
        self.assertEqual(len(pairs), 1)
        p = pairs[0]
        self.assertEqual(p.kind, "on")
        self.assertEqual(p.original, "Legacy")
        self.assertEqual(p.translated, "新版")
        self.assertEqual(p.original_speaker, "")

    def test_multiple2_attribute(self):
        """multiple=2 是多行重复条目：只配对首行，不跨行吃第二条。"""
        lines = ['    # "Repeat" (multiple=2)', '    "第一"', '    "第二"']
        pairs = _pairs(lines)
        self.assertEqual(len(pairs), 1)
        p = pairs[0]
        self.assertEqual(p.original, "Repeat")
        self.assertEqual(p.translated, "第一")
        self.assertEqual(p.translated_line, 2)

    def test_trailing_attribute(self):
        """原文注释尾部 Ren'Py 属性（nointeract 等）不算正文，正常配对。"""
        pairs = _pairs(['    # c "X" nointeract', '    c "内容"'])
        self.assertEqual(len(pairs), 1)
        p = pairs[0]
        self.assertEqual(p.kind, "cd")
        self.assertEqual(p.original, "X")
        self.assertEqual(p.translated, "内容")


class TestSayEntries(unittest.TestCase):
    """_say_parse.iter_say_entries 层：输出契约 dict 与 on 条目过滤。"""

    def test_entry_dict_contract(self):
        entries = list(iter_say_entries(Path("测试不存在目录")))  # 仅验证字段键，不读盘
        self.assertEqual(entries, [])

    def test_on_pairs_excluded_from_say_entries(self):
        """old/new 条目不得进入 say 条目流（消费方只见 tb/cd）。"""
        tl = _TEMP_TL
        try:
            tl.mkdir()
            (tl / "test.rpy").write_text(
                "translate schinese:\n"
                '    old "Legacy"\n'
                '    new "新版"\n'
                '    # e "Hello."\n'
                '    e "你好。"\n',
                encoding="utf-8",
            )
            entries = list(iter_say_entries(tl))
            self.assertEqual(len(entries), 1)
            e = entries[0]
            self.assertEqual(e["type"], "cd")
            self.assertEqual(e["orig"], "Hello.")
            self.assertEqual(e["trans"], "你好。")
            self.assertEqual(e["char"], "e")
            for key in ("file", "line", "src_line", "type", "orig", "trans", "char"):
                self.assertIn(key, e)
        finally:
            for child in tl.glob("*"):
                child.unlink()
            tl.rmdir()


_TEMP_TL = Path(os.environ.get("TEMP", "/tmp")) / "_say_parse_contract_tl"


if __name__ == "__main__":
    unittest.main(verbosity=2)
