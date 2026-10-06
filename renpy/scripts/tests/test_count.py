"""用例总数自洽：测试自己数自己，断言等于文档里写的数字。

为什么需要这个文件：仓库维护约定 #6 要求「用例数与 scripts/README.md 一致」，
但用例数是自指的——没有任何测试能断言「我所在的这套测试有多少个」而不重新
发现一遍自己。历史漂移记录：

- `README.md:13` / `renpy/SKILL.md:68` 长期写 217，实际 280
- 真实总数 280 恰好等于各文件之和 172+9+23+13+7+29+27，那个不变量由
  `test_repo_consistency.py` 负责（不依赖运行，能指出是哪个文件没更新）

所以拆成两层：那一层查「文档内部是否自洽」，这一层查「文档是否等于现实」。
新增/删除测试后忘了改文档，这里会失败并打印实际数字。
"""

import os
import re
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))

# 与 test_repo_consistency.py 相同的提取点，三处必须同时命中
_DOC_PATTERNS = (
    ("README.md", "README.md", r"(\d+)\s*用例回归测试"),
    ("renpy/SKILL.md", os.path.join("renpy", "SKILL.md"), r"纯标准库[，,]\s*(\d+)\s*用例"),
    (
        "renpy/scripts/README.md",
        os.path.join("renpy", "scripts", "README.md"),
        r"当前\s*(\d+)\s*用例",
    ),
)


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class TestDocumentedTestCountIsReal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 只发现、不运行：discover() 返回 suite，countTestCases() 不执行任何用例
        suite = unittest.defaultTestLoader.discover(
            start_dir=_HERE, top_level_dir=_HERE
        )
        cls.actual = suite.countTestCases()

    def test_count_matches_every_doc(self):
        for label, rel, pat in _DOC_PATTERNS:
            with self.subTest(doc=label):
                text = _read(os.path.join(_REPO_ROOT, rel))
                m = re.search(pat, text)
                self.assertTrue(
                    m, f"{label} 找不到总用例数，正则需随文档更新"
                )
                self.assertEqual(
                    int(m.group(1)), self.actual,
                    f"{label} 写 {m.group(1)} 用例，实际 {self.actual}。"
                    f"改完记得同步另外两份文档，以及 scripts/README.md "
                    f"目录树里各测试文件的用例数（那个和不变量由 "
                    f"test_repo_consistency.py 校验）。",
                )

    def test_count_is_not_absurdly_small(self):
        """兜底：discover 静默返回空 suite 时（cwd 不对 / pattern 变了）
        上面的断言会以「0 == 0」的形式假通过。这里把它钉死。"""
        self.assertGreater(self.actual, 200, f"只发现 {self.actual} 个用例，discover 是不是没跑到 tests/？")


if __name__ == "__main__":
    unittest.main(verbosity=2)
