"""仓库自洽性契约：文档说的必须等于代码里有的。

背景：这仓库的文档密度很高（SKILL.md 入口 + 3 份 README + 18 个 references + CHANGELOG），而「代码改了、文档没改」是这里唯一会反复发生的缺陷类型。已发生过的
实例：

- `README.md:13` 与 `renpy/SKILL.md:68` 写「27 子命令 / 217 用例」，
  实际是 28 / 280。`renpy/scripts/README.md` 写对了，但它是三份文档里 Agent
  最少读的那份。
- 分发用的 zip 是 2026-10-03 打的旧版（双技能 + 中文目录 + 陈旧 __pycache__），
  工作区早已合并成单技能、目录名全 ASCII。没有任何检查能发现这件事。

所以这里不测业务逻辑，只测「文档 ↔ 现实」的一致性。全部纯标准库。
"""

import importlib.util
import os
import re
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))          # scripts/tests
_TOOLS = os.path.dirname(_HERE)                            # scripts
_SKILL_ROOT = os.path.dirname(_TOOLS)                      # renpy
_REPO_ROOT = os.path.dirname(_SKILL_ROOT)                  # 仓库根

_README = os.path.join(_REPO_ROOT, "README.md")
_SKILL_MD = os.path.join(_SKILL_ROOT, "SKILL.md")
_SCRIPTS_README = os.path.join(_TOOLS, "README.md")
_CLI = os.path.join(_TOOLS, "renpy-tools-cli.py")

# 9 个分组目录：代码里靠 import 路径硬编码，macOS 的 NFD 归一化会打穿中文名，
# 所以必须是 ASCII（README.md 维护约定 #5）。
EXPECTED_GROUP_DIRS = {
    "sdk", "checks", "translate", "polish",
    "names", "linear", "setup", "shared", "tests",
}


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _md_links(text):
    """抽出 markdown 链接目标里的 .md（跳过纯锚点）。"""
    return {
        m.group(1)
        for m in re.finditer(r"\]\(([^)#]+\.md)\)", text)
    }


def _tree_block(text):
    """取出 scripts/README.md 里那段 ```scripts/ 目录树代码块。"""
    m = re.search(r"```\nscripts/\n(.*?)\n```", text, re.S)
    return m.group(1) if m else ""


def _load_cli():
    """按 test_cli_surface.py 同样的方式加载带横杠文件名的 CLI 门面。"""
    spec = importlib.util.spec_from_file_location("_cli_consistency", _CLI)
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    return cli


# —— 全库数字声明扫描（2026-10-21）——
#
# 上面那几个「数字一致」用例只盯三份文档（root README / SKILL.md / scripts/README），
# 网外面的 md 照样会漂。本组把扫描面扩到全库 md 里所有写死的数字声明，已经抓到：
#
# - `renpy/scripts/checks/README.md`「不再手写 34 项表」，实际 35
# - `renpy/references/namebox_translation.md`「22 用例」，实际 28
# - `README.md`「16 个分场景参考」，实际 18
#
# 不扫的文件及理由：
# - `CHANGELOG.md`：按日期倒序的流水，历史条目本就该保持写它那天的口径
# - `cache/`、`tmp/`、`.zcode/`：本机留档区与过程文件，不是仓库结构
_NOT_SCANNED_DIRS = {"cache", "tmp", ".zcode", "__pycache__"}
_NOT_SCANNED_FILES = {"CHANGELOG.md"}

# 简单声明：正则第 1 组是文档写的数字，末项是它对应的真值来源 key。
# 「子命令数」要求上下文里出现入口/门面字样——否则「autotranslate.py 4 子命令」
# 这种**某个脚本自己的**子命令数会被误当成顶层门面的数。
_SIMPLE_NUMBER_RULES = (
    ("子命令数", r"(\d+)\s*项表", "subcommands"),
    (
        "子命令数",
        r"(?:统一 CLI 入口|CLI 门面|门面)[^\n]{0,40}?(\d+)\s*(?:个\s*)?子命令",
        "subcommands",
    ),
    ("all 检查项数", r"(\d+)\s*项全只读", "all_checks"),
    ("all 检查项数", r"(\d+)\s*项(?:只读)?检查", "all_checks"),
    ("references 数", r"(\d+)\s*个分场景参考", "references"),
)

# 「N 用例」要分归属：同一行里出现测试模块名就指那个文件的用例数，否则是全量总数。
# 两种写法都要认——目录树里是 `test_x.py`，回归命令里是模块名 `test_x`（无 .py）。
_TEST_FILE_REF = re.compile(r"(test_\w+)(?:\.py)?\b")
_USE_CASE = re.compile(r"(\d+)\s*用例")

_RULE_NAMES = ("子命令数", "all 检查项数", "references 数", "总用例数", "单文件用例数")


def _iter_scanned_md():
    for root, dirs, files in os.walk(_REPO_ROOT):
        dirs[:] = sorted(d for d in dirs if d not in _NOT_SCANNED_DIRS)
        for name in sorted(files):
            if name.endswith(".md") and name not in _NOT_SCANNED_FILES:
                yield os.path.join(root, name)


def _rel(path):
    return os.path.relpath(path, _REPO_ROOT).replace(os.sep, "/")


def _scan_text(rel, text, truth, per_file):
    """扫一份文档，返回 (违规列表, 各规则命中次数)。

    拆成纯函数是为了能喂合成文本做反证（见 TestNoStaleNumbersInProse）：
    只有「覆盖率断言」时，正则命中而比较逻辑写错也能全绿。
    """
    violations, coverage = [], {}
    for lineno, line in enumerate(text.splitlines(), 1):
        for name, pat, key in _SIMPLE_NUMBER_RULES:
            for hit in re.findall(pat, line):
                coverage[name] = coverage.get(name, 0) + 1
                want = truth[key]
                if int(hit) != want:
                    violations.append(f"{rel}:{lineno} [{name}] 写 {hit}，实际 {want}")

        for hit in _USE_CASE.findall(line):
            ref = _TEST_FILE_REF.search(line)
            if ref:
                name, detail = "单文件用例数", f"{ref.group(1)}.py"
                want = per_file.get(ref.group(1))
                if want is None:
                    violations.append(
                        f"{rel}:{lineno} [{name}] 提到 {detail}，但没这个测试模块"
                    )
                    continue
            else:
                name, detail, want = "总用例数", "全量", truth["cases_total"]
            coverage[name] = coverage.get(name, 0) + 1
            if int(hit) != want:
                violations.append(
                    f"{rel}:{lineno} [{name}] {detail} 写 {hit}，实际 {want}"
                )

        # 省略写法：`python -m unittest test_x -v  # 说明（179）`——「用例」二字
        # 被省掉时上面那条正则扫不到（已发生过 176≠179 的漂移）。仅认「同行有
        # test 模块名 + 全角括号数字」的形态，避免把无关的（60 个）误当用例数。
        if not _USE_CASE.search(line):
            m = re.search(r"(test_\w+)(?:\.py)?\b.*?[（](\d+)\s*[）]", line)
            if m:
                name = "单文件用例数"
                want = per_file.get(m.group(1))
                coverage[name] = coverage.get(name, 0) + 1
                if want is None:
                    violations.append(
                        f"{rel}:{lineno} [{name}] 提到 {m.group(1)}.py，但没这个测试模块"
                    )
                elif int(m.group(2)) != want:
                    violations.append(
                        f"{rel}:{lineno} [{name}] {m.group(1)}.py 写 {m.group(2)}，实际 {want}"
                    )
    return violations, coverage


def _discover_counts():
    """只发现、不运行：返回 (用例总数, {测试模块名: 用例数})。"""
    suite = unittest.defaultTestLoader.discover(start_dir=_HERE, top_level_dir=_HERE)
    per_file, stack = {}, [suite]
    while stack:
        node = stack.pop()
        if isinstance(node, unittest.TestSuite):
            stack.extend(list(node))
        else:
            mod = type(node).__module__
            per_file[mod] = per_file.get(mod, 0) + 1
    return suite.countTestCases(), per_file


class TestDocsMatchCode(unittest.TestCase):
    """文档里写的数字 == 代码里实际的数字。"""

    def setUp(self):
        self.cli = _load_cli()
        self.n = len(self.cli.TOOL_SCRIPTS)
        self.readme = _read(_README)
        self.skill = _read(_SKILL_MD)
        self.scripts_readme = _read(_SCRIPTS_README)

    def test_subcommand_count_is_consistent_across_docs(self):
        """凡写出「N 子命令」的文档，那个 N 必须等于 TOOL_SCRIPTS 的长度。

        允许的写法：`28 个子命令` / `28 子命令`。SKILL.md 目前不声明子命令数
        （它讲的是「12 项只读检查」，另一回事），所以不强制它写——但要求至少两处
        声明，这样跨文档互校才有意义；将来谁往 SKILL.md 里补了数字，会被自动校验。
        """
        pat = re.compile(r"(\d+)\s*(?:个\s*)?子命令")
        found = {}
        for label, text in (
            ("README.md", self.readme),
            ("renpy/SKILL.md", self.skill),
            ("renpy/scripts/README.md", self.scripts_readme),
        ):
            for hit in pat.findall(text):
                found.setdefault(label, set()).add(int(hit))

        self.assertGreaterEqual(
            len(found), 2,
            f"只有 {sorted(found)} 声明了子命令数，少于两处就无法跨文档互校"
            f"（正则可能需要更新）",
        )
        for label, nums in sorted(found.items()):
            self.assertEqual(
                len(nums), 1,
                f"{label} 写了多个互相矛盾的子命令数：{sorted(nums)}",
            )
            self.assertEqual(
                next(iter(nums)), self.n,
                f"{label} 写的子命令数 {next(iter(nums))} != "
                f"TOOL_SCRIPTS 实际 {self.n}",
            )

    def test_per_file_test_counts_sum_to_total(self):
        """scripts/README.md 里各测试文件的用例数之和 == 它声明的总数。

        280 = 172 + 9 + 23 + 13 + 7 + 29 + 27。这个不变量不依赖运行测试就能查，
        比单看总数更能指出「是哪个文件的数字没更新」。
        """
        block = _tree_block(self.scripts_readme)
        self.assertTrue(block, "scripts/README.md 的目录树代码块没找到")

        per_file = {}
        for line in block.splitlines():
            m = re.search(r"(test_\w+)\.py", line)
            if not m:
                continue
            n = re.search(r"（(\d+)\s*用例", line)
            self.assertTrue(
                n, f"目录树里 {m.group(1)}.py 那行没写用例数: {line.strip()!r}"
            )
            per_file[m.group(1)] = int(n.group(1))

        self.assertTrue(per_file, "目录树里一个 test_*.py 都没解析到")
        total = re.search(r"当前\s*(\d+)\s*用例", self.scripts_readme)
        self.assertTrue(total, "scripts/README.md 找不到「当前 N 用例」")

        detail = ", ".join(f"{k}={v}" for k, v in sorted(per_file.items()))
        self.assertEqual(
            sum(per_file.values()), int(total.group(1)),
            f"各文件用例数之和 {sum(per_file.values())} != "
            f"声明总数 {total.group(1)}（{detail}）",
        )

    def test_total_test_count_agrees_across_docs(self):
        """三份文档的「总用例数」必须一致。

        这里只做文档间互校（无法在测试内部断言自身用例数——那是 test_count.py
        的活）。提取不到就报错，不静默跳过。
        """
        pats = (
            ("README.md", self.readme, r"(\d+)\s*用例回归测试"),
            ("renpy/SKILL.md", self.skill, r"纯标准库[，,]\s*(\d+)\s*用例"),
            ("renpy/scripts/README.md", self.scripts_readme, r"当前\s*(\d+)\s*用例"),
        )
        nums = {}
        for label, text, pat in pats:
            m = re.search(pat, text)
            self.assertTrue(m, f"{label} 找不到总用例数，正则需随文档更新")
            nums[label] = int(m.group(1))
        self.assertEqual(
            len(set(nums.values())), 1,
            f"三份文档的总用例数不一致：{nums}",
        )


class TestReferentialIntegrity(unittest.TestCase):
    """链接、目录、脚本清单三者互指不缺。"""

    def test_markdown_links_resolve(self):
        """所有 .md 链接必须能落到真实文件。

        全库扫描（除 CHANGELOG 与留档目录）：不只查入口文档——18 个 references
        与 6 个分组 README 内部的交叉链接曾经不在扫描面里，属盲区。
        """
        checked = 0
        for path in _iter_scanned_md():
            base = os.path.dirname(path)
            for link in _md_links(_read(path)):
                target = os.path.normpath(os.path.join(base, link))
                self.assertTrue(
                    os.path.isfile(target),
                    f"{_rel(path)} 里的死链 [{link}]({link}) -> {target}",
                )
                checked += 1
        self.assertGreater(checked, 0, "一条 .md 链接都没解析到，正则该更新了")

    def test_every_reference_is_indexed_from_skill_md(self):
        """references/ 下每个文件都必须被 SKILL.md 索引。

        反向也重要：SKILL.md 是唯一入口，references 里躺着一份没人知道存在的
        知识，等于白写。
        """
        ref_dir = os.path.join(_SKILL_ROOT, "references")
        on_disk = {
            f for f in os.listdir(ref_dir)
            if f.endswith(".md") and f != "README.md"   # README.md 是索引本体
        }
        self.assertTrue(on_disk, "references/ 是空的？")
        linked = {
            os.path.basename(l)
            for l in _md_links(_read(_SKILL_MD))
            if l.startswith("references/")
            and os.path.basename(l) != "README.md"
        }
        self.assertEqual(
            on_disk - linked, set(),
            f"这些 references 没被 SKILL.md 索引：{sorted(on_disk - linked)}",
        )
        self.assertEqual(
            linked - on_disk, set(),
            f"SKILL.md 索引了不存在的 references：{sorted(linked - on_disk)}",
        )

    def test_reference_names_are_ascii_and_regular(self):
        """references/ 文件名合规：ASCII、小写、仅 [a-z0-9_]（README.md 豁免）。

        命名规则唯一出处：references/README.md。
        """
        ref_dir = os.path.join(_SKILL_ROOT, "references")
        bad = [
            f for f in os.listdir(ref_dir)
            if f != "README.md"
            and not re.fullmatch(r"[a-z0-9_]+\.md", f)
        ]
        self.assertEqual(
            bad, [],
            f"references 文件名不合命名契约（见 references/README.md）：{bad}",
        )

    def test_group_dirs_are_ascii_and_complete(self):
        """分组目录：全 ASCII，且不多不少就是这 9 个。

        __pycache__ 是跑过 CLI/测试后的字节码缓存，不算分组目录，
        否则「跑完脚本再跑测试」必误报。
        """
        found = {
            d for d in os.listdir(_TOOLS)
            if d != "__pycache__"
            and os.path.isdir(os.path.join(_TOOLS, d))
        }
        self.assertEqual(
            found, EXPECTED_GROUP_DIRS,
            f"分组目录与约定不符。多出：{sorted(found - EXPECTED_GROUP_DIRS)}；"
            f"缺少：{sorted(EXPECTED_GROUP_DIRS - found)}",
        )
        non_ascii = sorted(d for d in found if not d.isascii())
        self.assertEqual(
            non_ascii, [],
            f"分组目录名必须 ASCII（macOS NFD 会打穿 import）：{non_ascii}",
        )

    def test_group_dirs_are_documented(self):
        """scripts/README.md 的目录树必须提到每个分组目录。"""
        block = _tree_block(_read(_SCRIPTS_README))
        self.assertTrue(block, "scripts/README.md 的目录树代码块没找到")
        documented = set(re.findall(r"([a-z_]+)/", block))
        missing = EXPECTED_GROUP_DIRS - documented
        self.assertEqual(missing, set(), f"目录树漏掉分组目录：{sorted(missing)}")

    def test_scripts_are_documented_bidirectionally(self):
        """目录树列出的 .py 必须存在；磁盘上的 .py 必须被列出。

        漏写 = Agent 不知道有这工具；多写 = 文档承诺了不存在的东西。
        """
        block = _tree_block(_read(_SCRIPTS_README))
        self.assertTrue(block, "scripts/README.md 的目录树代码块没找到")
        listed = set(re.findall(r"([A-Za-z0-9_-]+\.py)", block))
        self.assertTrue(listed, "目录树里一个 .py 都没解析到")

        on_disk = set()
        for root, dirs, files in os.walk(_TOOLS):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            on_disk.update(f for f in files if f.endswith(".py"))

        self.assertEqual(
            listed - on_disk, set(),
            f"目录树列了磁盘上没有的脚本：{sorted(listed - on_disk)}",
        )
        self.assertEqual(
            on_disk - listed, set(),
            f"磁盘上有脚本没写进目录树：{sorted(on_disk - listed)}",
        )


class TestLicenseIsPresent(unittest.TestCase):
    """scripts/README.md 末尾声称 MIT，仓库就得真有 LICENSE。"""

    def test_license_file_exists(self):
        for name in ("LICENSE", "LICENSE.md", "LICENSE.txt"):
            if os.path.isfile(os.path.join(_REPO_ROOT, name)):
                break
        else:
            self.fail("仓库根没有 LICENSE 文件，但 scripts/README.md 声称 MIT License")

    def test_license_is_mit(self):
        text = _read(os.path.join(_REPO_ROOT, "LICENSE"))
        self.assertIn("MIT License", text)
        self.assertIn("WITHOUT WARRANTY OF ANY KIND", text)


class TestNoStaleNumbersInProse(unittest.TestCase):
    """全库 md 里写死的数字，都必须等于代码里的实际值。

    与上面两组的分工：`TestDocsMatchCode` 查三份主文档的「总用例数 / 子命令数」，
    这里查**其余所有 md**（含各分组 README、每个 reference、根级评审文档）里的
    数字声明。一个数字只该有一处真值，但声明点会到处长。
    """

    def _scan_repo(self):
        cli = _load_cli()
        total, per_file = _discover_counts()
        ref_dir = os.path.join(_SKILL_ROOT, "references")
        truth = {
            "subcommands": len(cli.TOOL_SCRIPTS),
            "all_checks": len(cli.ALL_GROUP),
            # 计数不含 README.md——它是分类契约本体，不是分场景参考
            "references": len([
                f for f in os.listdir(ref_dir)
                if f.endswith(".md") and f != "README.md"
            ]),
            "cases_total": total,
        }
        violations, coverage = [], {}
        for path in _iter_scanned_md():
            found, hits = _scan_text(_rel(path), _read(path), truth, per_file)
            violations.extend(found)
            for name, n in hits.items():
                coverage[name] = coverage.get(name, 0) + n
        return violations, coverage

    def test_every_number_in_prose_matches_code(self):
        violations, coverage = self._scan_repo()
        self.assertEqual(
            violations, [],
            "文档里的数字与代码不符（改完代码请一并改这些声明点）：\n  "
            + "\n  ".join(violations),
        )
        # 覆盖率兜底：正则失效或声明被删时，上面那条断言会以「空 == 空」假通过。
        for name in _RULE_NAMES:
            self.assertGreater(
                coverage.get(name, 0), 0,
                f"规则「{name}」一处都没扫到——正则失效、或该声明被整体删掉，"
                f"扫描已在空转（coverage={coverage}）",
            )

    def test_scanner_flags_a_wrong_number(self):
        """反证：扫描器必须真的会报错。

        用明显假数字构造（90/80/70/60/7），避免与仓库真实值混淆；
        文本里每条都写错，要求逐条报出且五条规则全覆盖。
        """
        truth = {"subcommands": 90, "all_checks": 80, "references": 70, "cases_total": 60}
        per_file = {"test_demo": 7}
        text = "\n".join((
            "统一 CLI 入口（89 个子命令）",          # 子命令数
            "一键检测（79 项只读检查）",              # all 检查项数
            "（69 个分场景参考）",                    # references 数
            "当前 59 用例",                           # 总用例数
            "test_demo.py ── 契约（5 用例）",         # 单文件用例数
        ))
        violations, coverage = _scan_text("synthetic.md", text, truth, per_file)
        self.assertEqual(
            len(violations), 5,
            f"应报 5 条，实报 {len(violations)} 条：{violations}",
        )
        for name in _RULE_NAMES:
            self.assertGreater(
                coverage.get(name, 0), 0,
                f"合成文本没覆盖规则「{name}」，该规则形同未测",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
