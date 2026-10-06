# -*- coding: utf-8 -*-
"""检查器契约层回归（shared/base_checker.py，2026-10-06 引入）。

背景：门面 `renpy-tools-cli.py` 过去用两张手写表（TOOL_SCRIPTS / TOOL_DESC，各
33 项）加两个硬编码集合（NEEDS_TL_DIR / TL_DIR_TOOLS）描述"有哪些检查器、各自吃
什么"。这套描述会漂且漂了不报错——`check_i18n.py` 漏声明 `-l/--language`，
而 `all` 把 `-l` 原样转发给每个检查器，于是它在任何项目上都撞 argparse rc=2、
被门面归一成失败项，`all` 恒定返回 1（假阳性，见 CHANGELOG 十五轮）。

契约层把这些元数据搬进各脚本自己的 `CHECKER`。本文件钉住三件事：
1. 两个样板检查器确实声明了完整契约（name/summary/takes 非空且合法）；
2. `applies_to()` 按 `takes` 正确判定——这正是 NEEDS_TL_DIR 的替代品；
3. **检查器只读**：checks/ 与 tl 侧检查器源码里不得出现写操作原语。

第 3 条原本只是口头约定（tools_boundaries.md），这里变成可执行的断言。
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.dirname(_HERE)

for _p in (_SCRIPTS, os.path.join(_SCRIPTS, "checks"),
           os.path.join(_SCRIPTS, "translate"), os.path.join(_SCRIPTS, "shared")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from base_checker import (  # noqa: E402
    PROJECT,
    TL_DIR,
    BaseChecker,
    CheckContext,
    find_game_dir,
    iter_rpy,
    skip_dirs,
)
import check_crash_risks  # noqa: E402
import check_untranslated  # noqa: E402

# 样板检查器：结构侧一个、tl 侧一个。扩大样板时同步这里。
EXEMPLARS = (check_crash_risks.CHECKER, check_untranslated.CHECKER)

# 写操作原语：检查器契约禁止出现。只扫 .py，md 文档除外。
#
# 范围是 check_*.py + lint_*.py，不是整个目录——translate/ 下还住着
# fix_missing_tags / fix_translation_comments / patch_renpy_say /
# sync_namebox_translation 这些写入类工具（它们该有自己的写入生命周期契约，
# 见 base_checker docstring 第 3 条与 CHANGELOG 十五轮）。
WRITE_PRIMITIVES = (
    "atomic_write_text",
    "ensure_bak",
    "create_bak",
    "os.replace",
    "shutil.copy",
    "shutil.move",
    ".write_text(",
    ".write_bytes(",
    "open(",  # 需配写模式才算，见 _has_write_call
)
CHECKER_DIRS = ("checks", "translate")
CHECKER_PREFIXES = ("check_", "lint_")


class TestCheckerContractShape(unittest.TestCase):
    """契约字段完整性：缺字段要在类定义时就炸（__init_subclass__ 已实现），这里钉住现状。"""

    def test_exemplars_declare_full_contract(self):
        for ck in EXEMPLARS:
            with self.subTest(checker=ck.name):
                self.assertIsInstance(ck, BaseChecker)
                self.assertTrue(ck.name, "name 不许空")
                self.assertTrue(ck.summary, "summary 不许空")
                self.assertIn(ck.takes, (PROJECT, TL_DIR))

    def test_exemplars_are_read_only(self):
        for ck in EXEMPLARS:
            with self.subTest(checker=ck.name):
                self.assertTrue(ck.read_only, f"{ck.name} 是检查器，契约要求只读")

    def test_names_are_unique(self):
        names = [ck.name for ck in EXEMPLARS]
        self.assertEqual(len(names), len(set(names)), f"name 撞车：{names}")

    def test_exemplars_cover_both_takes(self):
        """样板必须一头一尾：吃项目的一个、吃 tl 目录的一个。

        只有一种 takes 的样板会让 applies_to 的另一半永远没被测到。
        """
        takes = {ck.takes for ck in EXEMPLARS}
        self.assertEqual(takes, {PROJECT, TL_DIR}, f"样板覆盖不全：{takes}")

    def test_missing_contract_field_raises_at_class_creation(self):
        """没声明 name/summary 的子类必须在 class 语句处就 TypeError，不能拖到运行期。"""
        with self.assertRaises(TypeError):
            class _NoName(BaseChecker):
                summary = "有描述没名字"

                def run(self, ctx):
                    return 0

        with self.assertRaises(TypeError):
            class _BadTakes(BaseChecker):
                name = "x"
                summary = "y"
                takes = "whatever"

                def run(self, ctx):
                    return 0


class TestAppliesTo(unittest.TestCase):
    """applies_to 是 NEEDS_TL_DIR / TL_DIR_TOOLS 两个硬编码集合的替代品。"""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="applies_")
        self.game = os.path.join(self.root, "game")
        os.makedirs(self.game)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_project_checker_applies_without_tl(self):
        ck = check_crash_risks.CHECKER
        ctx = CheckContext(project=self.game, tl_dir=None)
        self.assertTrue(ck.applies_to(ctx), "崩溃检测不吃 tl，没翻译也该跑")

    def test_tl_checker_skipped_when_no_tl_dir(self):
        """对应门面旧行为「跳过：无 <lang> 翻译目录」——由检查器自己声明。"""
        ck = check_untranslated.CHECKER
        ctx = CheckContext(project=self.game, tl_dir=None)
        self.assertFalse(ck.applies_to(ctx), "无 tl 目录时 untranslated 必须被跳过")

    def test_tl_checker_applies_with_tl_dir(self):
        tl = os.path.join(self.game, "tl", "schinese")
        os.makedirs(tl)
        ck = check_untranslated.CHECKER
        ctx = CheckContext(project=self.game, tl_dir=tl)
        self.assertTrue(ck.applies_to(ctx))

    def test_missing_project_not_applicable(self):
        ck = check_crash_risks.CHECKER
        ctx = CheckContext(project=os.path.join(self.root, "nope"), tl_dir=None)
        self.assertFalse(ck.applies_to(ctx), "项目目录不存在时不该声称能跑")

    def test_from_project_resolves_tl_dir(self):
        tl = os.path.join(self.game, "tl", "schinese")
        os.makedirs(tl)
        ctx = CheckContext.from_project(self.root, "schinese")
        self.assertEqual(ctx.project, Path(self.game), "应从 <项目> 落到 game/")
        self.assertTrue(ctx.has_tl_dir())

    def test_from_project_accepts_game_dir_directly(self):
        ctx = CheckContext.from_project(self.game, "schinese")
        self.assertEqual(ctx.project, Path(self.game))

    def test_from_project_leaves_tl_none_when_absent(self):
        ctx = CheckContext.from_project(self.root, "schinese")
        self.assertIsNone(ctx.tl_dir)
        self.assertFalse(ctx.has_tl_dir())


class TestRunParityWithCli(unittest.TestCase):
    """CHECKER.run(ctx) 与 CLI 退出码必须一致——门面改走 run() 后不能改语义。"""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="parity_")
        self.game = os.path.join(self.root, "game")
        os.makedirs(self.game)
        self.script = os.path.join(self.game, "script.rpy")
        with open(self.script, "w", encoding="utf-8") as fh:
            fh.write('label start:\n    "hi"\n')

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _cli(self, args):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
                   PYTHONIOENCODING="utf-8")
        return subprocess.run([sys.executable] + args, capture_output=True,
                              text=True, encoding="utf-8", env=env, timeout=120)

    def test_crash_risks_cli_and_run_agree_on_clean_project(self):
        path = os.path.join(_SCRIPTS, "checks", "check_crash_risks.py")
        rc_cli = self._cli([path, self.game]).returncode
        rc_run = check_crash_risks.CHECKER.run(
            CheckContext.from_project(self.root))
        self.assertEqual(rc_run, rc_cli, "契约入口与 CLI 对同一项目结论不一致")

    def test_crash_risks_cli_still_exits_nonzero_on_missing_dir(self):
        """目录不存在必须仍报 1（原实现 sys.exit(1)，重构后 return 1）。"""
        path = os.path.join(_SCRIPTS, "checks", "check_crash_risks.py")
        rc = self._cli([path, os.path.join(self.root, "nope")]).returncode
        self.assertEqual(rc, 1, "路径错误应退出 1")
        self.assertEqual(
            check_crash_risks.run_scan(os.path.join(self.root, "nope")), 1,
            "run_scan 对不存在目录应返回 1",
        )

    def test_crash_risks_cli_flags_critical_findings(self):
        """有 CRITICAL 时 CLI 必须退出 1（这是 run() 返回码的语义基准）。

        builtin_shadow 是三个 CRITICAL 检测器之一：给 str 这类内置名赋值。
        """
        with open(os.path.join(self.game, "risky.rpy"), "w", encoding="utf-8") as fh:
            fh.write('label risky:\n    str = "shadow"\n')
        path = os.path.join(_SCRIPTS, "checks", "check_crash_risks.py")
        rc = self._cli([path, self.game]).returncode
        self.assertEqual(rc, 1, "有 CRITICAL 风险时退出码应为 1")

    def test_crash_risks_warning_only_exits_zero(self):
        """WARNING 级不该触发非零退出——除零检测器是 WARNING。"""
        with open(self.script, "w", encoding="utf-8") as fh:
            fh.write("label start:\n    $ x = total_y / step_size\n")
        path = os.path.join(_SCRIPTS, "checks", "check_crash_risks.py")
        rc = self._cli([path, self.game]).returncode
        self.assertEqual(rc, 0, "仅 WARNING 时退出码应为 0")


class TestCheckersAreReadOnly(unittest.TestCase):
    """把「检查器不写文件」从口头约定变成断言（契约第 3 条）。

    口径（比"零写操作"精确，否则断言会逼着人藏代码）：
    - 硬红线：`shared/backup.py` 的备份/原子写原语、以及 os.replace 一类
      静默改写工程的写法，检查器里不许出现。
    - 允许：写**用户点名的导出路径**（`--output` / `--csv` / `--json`），
      如 check_untranslated --csv、check_charname_translation --stub。
      这是用户主动要求的产物，不是"检查顺手改了文件"。
    - 判据：每个写调用都必须挂在某个 argparse 开关的 dest 上。
    """

    #: 绝不豁免的原语：备份/原子写意味着"改工程文件"
    STRICT_PRIMITIVES = (
        "atomic_write_text",
        "ensure_bak",
        "create_bak",
        "create_bak_multi",
        "os.replace",
        "shutil.copy",
        "shutil.move",
    )
    #: 豁免但必须挂在 args.* 上的导出开关 dest（--stub 是必带路径式，不带 dest）
    EXPORT_DESTS = ("output", "csv_path", "json_path", "out_path", "stub")

    def _sources(self):
        for grp in CHECKER_DIRS:
            d = os.path.join(_SCRIPTS, grp)
            if not os.path.isdir(d):
                continue
            for fn in sorted(os.listdir(d)):
                if fn.endswith(".py") and fn.startswith(CHECKER_PREFIXES):
                    yield grp, fn, os.path.join(d, fn)

    def test_checker_file_set_is_not_empty(self):
        """范围写空了这条测试就是假通过——把扫描集合钉住。"""
        found = [f"{g}/{f}" for g, f, _ in self._sources()]
        self.assertGreaterEqual(len(found), 15, f"只扫到 {len(found)} 个：{found}")

    def test_no_strict_write_primitives(self):
        offenders = []
        for grp, fn, path in self._sources():
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            for prim in self.STRICT_PRIMITIVES:
                if prim in text:
                    offenders.append(f"{grp}/{fn}: {prim}")
        self.assertEqual(offenders, [],
                         f"检查器出现备份/原子写原语：{offenders}")

    def test_every_write_op_is_gated_behind_an_export_flag(self):
        """每个写调用都必须来自 argparse 开关，不能是工程路径。

        解析两处放宽，都是既有合理写法，不是新开口子：
        - `write_stub(path, ...)` 这类辅助函数体，路径由调用方从开关传入；
          按函数名认（write_/export_/dump_/save_ 前缀）。
        - `io.open(args.json_path, "w").write(...)` 这类**单行链式**调用，
          路径与写在同一行——按行内出现 args.<dest> 认。
        其余仍须在调用点上方窗口内见 args.<dest>。
        """
        offenders = []
        write_re = re.compile(r'(?:^|\W)(?:io\.)?open\([^)]*,\s*[\'"][rwax]?[wax+]')
        def_re = re.compile(r'^\s*def\s+(\w+)')
        helper_re = re.compile(r'^(write_|export_|dump_|save_)', re.I)
        for grp, fn, path in self._sources():
            with open(path, encoding="utf-8") as fh:
                lines = fh.readlines()
            enclosing = None  # 当前所在函数名（None = 模块层）
            for i, line in enumerate(lines, 1):
                m = def_re.match(line)
                if m:
                    enclosing = m.group(1)
                    continue
                if not write_re.search(line):
                    continue
                # 辅助函数体：路径由调用方从开关传入，函数体内看不到 args.*
                if enclosing and helper_re.match(enclosing):
                    continue
                # 链式单行：路径与写同行
                if any(f"args.{d}" in line for d in self.EXPORT_DESTS):
                    continue
                # 否则看调用点窗口
                window = "".join(lines[max(0, i - 21):i])
                if not any(f"args.{dest}" in window for dest in self.EXPORT_DESTS):
                    offenders.append(f"{grp}/{fn}:{i} {line.strip()}")
        self.assertEqual(offenders, [],
                         f"写调用没挂在导出开关上：{offenders}")

    def test_write_helpers_all_receive_path_parameters(self):
        """被豁免的导出辅助函数必须把路径当参数收，不能自己拼工程路径。

        这是上一条的对照：豁免的是"路径来源"，不是"随便写"。这些函数签名里
        应能看到 path / out_path 之类参数。
        """
        checked = 0
        write_re = re.compile(r'(?:^|\W)(?:io\.)?open\([^)]*,\s*[\'"][rwax]?[wax+]')
        def_re = re.compile(r'^\s*def\s+((?:write_|export_|dump_|save_)\w*)\s*\(([^)]*)\)')
        for grp, fn, path in self._sources():
            with open(path, encoding="utf-8") as fh:
                lines = fh.readlines()
            for i, line in enumerate(lines, 1):
                sig = def_re.match(line)
                if not sig:
                    continue
                body = lines[i - 1:i + 20]
                if not any(write_re.search(b) for b in body):
                    continue
                checked += 1
                params = sig.group(2)
                self.assertTrue(
                    re.search(r'\b(path|out_path|output|csv_path|json_path)\b', params),
                    f"{grp}/{fn}:{i} {sig.group(1)}() 里写了文件，但签名({params.strip()})"
                    f"没收路径参数——路径来源就没法审计了",
                )
        self.assertGreater(checked, 0, "没扫到任何导出辅助函数，规则可能已失效")

    def test_stub_helper_is_only_called_under_explicit_flag(self):
        """check_charname_translation 的 --stub 会写 .rpy 骨架，确认它不是默认行为。

        该开关是"必带路径"式（`--stub <路径>`，不是 store_true）：不传就没有
        路径可写，天然 opt-in。这里断言两件事——参数必带、且调用点判空。
        """
        path = os.path.join(_SCRIPTS, "checks", "check_charname_translation.py")
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn('"--stub"', text, "应有 --stub 开关")
        self.assertNotIn('"--stub", action="store_true"', text,
                         "--stub 是必带路径式，不该是 store_true")
        # 调用点必须判空：只有显式给了路径才写
        m = re.search(r'if args\.stub:\n(?:.*\n){0,8}?.*write_stub\(', text)
        self.assertIsNotNone(m, "调用点应有 `if args.stub:` 且分支内调 write_stub(")

    def test_no_fix_switch(self):
        """--fix 不属于检查器：需要写的是 fix_* 那类脚本，且它们有自己的写入契约。"""
        offenders = []
        for grp, fn, path in self._sources():
            with open(path, encoding="utf-8") as fh:
                if '"--fix"' in fh.read():
                    offenders.append(f"{grp}/{fn}")
        self.assertEqual(offenders, [], f"检查器不该有 --fix：{offenders}")

    def test_writers_are_excluded_by_design(self):
        """反向确认：写入类工具确实存在、确实带写入开关，不在检查器扫描范围内。

        钉这条是为了防止有人为了让上面的断言变绿，把 fix_* 改名成 check_*.py
        —— 那是把工具藏起来，不是解决问题。开关名按各脚本实际约定（--apply 或
        --execute），这里只要求"存在一个显式写入开关"。
        """
        writers = ("translate/fix_missing_tags.py",
                   "translate/fix_translation_comments.py",
                   "translate/patch_renpy_say.py",
                   "translate/sync_namebox_translation.py")
        for rel in writers:
            path = os.path.join(_SCRIPTS, *rel.split("/"))
            with self.subTest(tool=rel):
                self.assertTrue(os.path.isfile(path), f"{rel} 应存在")
                self.assertFalse(os.path.basename(rel).startswith(CHECKER_PREFIXES),
                                 f"{rel} 不该叫 check_*/lint_*")
                with open(path, encoding="utf-8") as fh:
                    text = fh.read()
                self.assertTrue('"--apply"' in text or '"--execute"' in text,
                                f"{rel} 应有显式写入开关（--apply/--execute）")


class TestSharedIterHelpers(unittest.TestCase):
    """iter_rpy / skip_dirs / find_game_dir：各检查器自己那份遍历早晚会漂，收进 shared 同源。"""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="iter_")
        for rel in ("game/tl/schinese", "game/renpy/common", "game/cache",
                    "game/saves", "game/images"):
            os.makedirs(os.path.join(self.root, rel), exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _touch(self, rel):
        path = Path(self.root, rel, "x.rpy")
        path.write_text("label x:\n    pass\n", encoding="utf-8")
        return path

    def test_skips_engine_cache_saves_and_tl_by_default(self):
        game = Path(self.root, "game")
        self._touch("game")
        self._touch("game/tl/schinese")
        self._touch("game/renpy/common")
        self._touch("game/cache")
        self._touch("game/saves")
        found = iter_rpy(game)
        self.assertEqual(len(found), 1,
                         f"只该有 game/x.rpy，实际 {[str(p) for p in found]}")
        self.assertEqual(found[0], game / "x.rpy")

    def test_include_tl_and_engine_switches(self):
        game = Path(self.root, "game")
        self._touch("game")
        self._touch("game/tl/schinese")
        self._touch("game/renpy/common")
        with_tl = iter_rpy(game, include_tl=True)
        self.assertTrue(any("schinese" in str(p) for p in with_tl),
                        "include_tl=True 时应进 tl/")

    def test_skip_dirs_is_extensible(self):
        self.assertEqual(skip_dirs("assets")[0], "renpy")
        self.assertIn("assets", skip_dirs("assets"))

    def test_find_game_dir(self):
        root = Path(self.root)
        self.assertEqual(find_game_dir(root), root / "game")
        self.assertEqual(find_game_dir(root / "game"), root / "game")
        self.assertIsNone(find_game_dir(root / "game" / "tl"))


if __name__ == "__main__":
    unittest.main(verbosity=2)