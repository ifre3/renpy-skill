# -*- coding: utf-8 -*-
"""注册表与门面分发回归（shared/tool_registry.py，2026-10-06 引入）。

背景：门面 `renpy-tools-cli.py` 过去有两张手写表——`TOOL_SCRIPTS`（33 项
子命令→路径）与 `TOOL_DESC`（33 项描述），外加两个硬编码集合
`NEEDS_TL_DIR` / `TL_DIR_TOOLS`。这套描述会漂且漂了不报错：`check_i18n.py`
漏声明 `-l`，`all` 把 `-l` 原样转发给每个检查器 → argparse rc=2 被归一成失败项
→ `all` 在任何项目上恒定返回 1（假阳性，CHANGELOG 十五轮）。

现在元数据由各脚本的 CHECKER 自报，注册表读之。本文件钉住三件事：
1. **通用防复发护栏**：每个注册检查器都能吃下 `all` 的透传参数（`-l <lang>`）。
   这条断言就是当初漏掉的那一类问题的通用解药——不是补一个脚本，是让漏一个就红。
2. 注册表自身自洽：路径存在、子命令名与 CHECKER.name 一致、分组不重不漏。
3. `NEEDS_TL_DIR` / `TL_DIR_TOOLS` 的语义从脚本派生，与实测行为一致。
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.dirname(_HERE)

for _p in (_SCRIPTS, os.path.join(_SCRIPTS, "shared")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import tool_registry as REG  # noqa: E402

PYTHON = sys.executable
#: all 会原样转发给每个子脚本的参数（_split_all_args 的 value_opts 同一套）
PASSTHROUGH = ["-l", "schinese"]


class TestRegistrySelfConsistency(unittest.TestCase):
    def test_every_tool_path_exists(self):
        missing = [n for n in REG.TOOL_SCRIPTS
                   if not os.path.isfile(REG.script_path(n))]
        self.assertEqual(missing, [], f"注册表指向不存在的脚本：{missing}")

    def test_every_tool_has_a_summary(self):
        """描述取自 CHECKER.summary 或 TOOL_DESC，两者都不许缺。"""
        empty = [n for n in REG.TOOL_SCRIPTS if not REG.summary(n).strip()]
        self.assertEqual(empty, [], f"这些工具没有描述：{empty}")

    def test_every_checker_name_matches_its_subcommand(self):
        """子命令名与 CHECKER.name 必须一致，否则 `all` 报告与文档全错位。"""
        for name in REG.CHECKER_NAMES:
            with self.subTest(tool=name):
                self.assertEqual(REG.load_checker(name).name, name)

    def test_checker_module_names_are_unique(self):
        """同名模块会互相覆盖 sys.modules（load_checker 用importlib）。"""
        mods = [os.path.splitext(os.path.basename(REG.TOOL_SCRIPTS[n]))[0]
                for n in REG.TOOL_SCRIPTS]
        dupes = {m for m in mods if mods.count(m) > 1}
        self.assertEqual(dupes, set(), f"脚本重名会让 import 缓存串味：{sorted(dupes)}")

    def test_groups_partition_the_all_group(self):
        groups = (REG.CHECK_GROUP + REG.CRASH_GROUP + REG.I18N_GROUP
                  + REG.STRUCT_GROUP + ["untranslated"])
        self.assertEqual(len(groups), len(set(groups)),
                         f"all 分组有重复项：{groups}")
        self.assertEqual(set(groups), set(REG.ALL_GROUP),
                         "all 分组之并必须等于 ALL_GROUP")

    def test_every_group_member_is_a_registered_tool(self):
        for grp in ("CHECK_GROUP", "CRASH_GROUP", "I18N_GROUP", "STRUCT_GROUP",
                    "FIX_GROUP", "SETUP_GROUP"):
            unknown = [n for n in getattr(REG, grp) if n not in REG.TOOL_SCRIPTS]
            self.assertEqual(unknown, [], f"{grp} 里有未注册工具：{unknown}")

    def test_only_three_groups_exist(self):
        """分组只有三类：有分组的 + 其余（list 输出第三段「其他」兜住）。

        加新分组时这条会提醒同步 list 的展示逻辑——否则工具会从 list 里消失。
        """
        grouped = (set(REG.ALL_GROUP) | set(REG.FIX_GROUP)
                   | set(REG.SETUP_GROUP))
        ungrouped = [n for n in REG.TOOL_SCRIPTS if n not in grouped]
        self.assertEqual(
            sorted(ungrouped), sorted(["lint", "namebox", "linear", "urm"]),
            "「其他」段的成员变了：这些是既不属于 all 也不属于写入类的工具"
            "（lint 调 SDK、namebox/urm 需显式指定、linear 是独立模式）",
        )


class TestCheckerRegistryMetadata(unittest.TestCase):
    def test_all_checkers_declare_contract(self):
        for name in REG.CHECKER_NAMES:
            with self.subTest(tool=name):
                ck = REG.load_checker(name)
                self.assertTrue(ck.name and ck.summary)
                self.assertIn(ck.takes, ("project", "tl_dir"))

    def test_tl_dir_takers_imply_requires_tl(self):
        """吃 tl_dir 却没声明 requires_tl 是逻辑矛盾，契约层已在类定义处拦。"""
        for name in REG.all_takes_tl_dir():
            with self.subTest(tool=name):
                self.assertTrue(REG.requires_tl(name))

    def test_only_untranslated_takes_tl_dir(self):
        """现状快照：all 里唯一吃 tl_dir 的是 untranslated（位置参数就是 tl 目录）。

        将来新增吃 tl_dir 的检查器时这条会提醒同步 TL_DIR 相关测试。
        """
        self.assertEqual(REG.all_takes_tl_dir(), ["untranslated"])

    def test_requires_tl_matches_measured_behaviour(self):
        """requires_tl=True 的检查器，缺 tl 目录时输出必须与「有 tl 目录」不同。

        判据是**差异**而非退出码：历史集合是从门面的 NEEDS_TL_DIR 继承来的，
        而其中 `button` 实测在无 tl 时也能报（WARN 级"按钮文本未被 translate
        strings 捕获"是源码层判断，不读 tl）——所以它在语义上**不**依赖 tl。
        逐个实跑对比有无 tl 的输出：完全一致 = 声明错了。
        """
        need = [n for n in REG.ALL_GROUP if REG.requires_tl(n)]
        self.assertEqual(
            sorted(need),
            sorted(["charname", "integrity", "duplicate", "untranslated"]),
            "requires_tl 集合变了。button 已从名单移出（实测不依赖 tl 目录，"
            "见 test_button_checker_does_not_require_tl）；同步本条与 "
            "test_only_untranslated_takes_tl_dir",
        )

        root = tempfile.mkdtemp(prefix="notl_")
        game = os.path.join(root, "game")
        os.makedirs(game)
        with open(os.path.join(game, "script.rpy"), "w", encoding="utf-8") as fh:
            fh.write('label start:\n    textbutton "Cancel"\n    "Hello"\n')
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
                   PYTHONIOENCODING="utf-8")

        def run(name, target):
            return subprocess.run(
                [PYTHON, REG.script_path(name), target, *PASSTHROUGH],
                capture_output=True, text=True, encoding="utf-8",
                env=env, timeout=120)

        tl = os.path.join(game, "tl", "schinese")
        try:
            for name in need:
                if REG.takes_tl_dir(name):
                    continue  # untranslated 直接吃 tl_dir，缺目录必然报错
                # 先测「有 tl」：建目录 + 一个空 strings 块
                os.makedirs(tl, exist_ok=True)
                strings = os.path.join(tl, "strings.rpy")
                with open(strings, "w", encoding="utf-8") as fh:
                    fh.write("translate schinese strings:\n")
                with_tl = run(name, game)
                # 再测「无 tl」：整个目录挪走，不是删文件
                shutil.move(tl, tl + "_hidden")
                without = run(name, game)
                shutil.move(tl + "_hidden", tl)
                self.assertNotEqual(
                    without.stdout, with_tl.stdout,
                    f"{name} 有无 tl 目录输出完全相同——它不依赖 tl 目录，"
                    f"requires_tl 应为 False",
                )
                os.remove(strings)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_button_checker_does_not_require_tl(self):
        """button 是个反直觉的例外，单独钉住，避免以后被"顺手改回去"。

        它检测的是「按钮文本有没有进 translate strings 块」，判据在源码层，
        读的是 .rpy 而不是 tl/ 目录 —— 所以无 tl 时照样能报 WARN。
        门面过去把它算进 NEEDS_TL_DIR，导致无 tl 项目上白跳一项。
        """
        self.assertFalse(
            REG.requires_tl("button"),
            "button 实测不依赖 tl 目录（判据在源码层），requires_tl 应为 False",
        )

    def test_non_tl_checkers_run_without_tl_dir(self):
        """反面对照：requires_tl=False 的检查器在无 tl 项目上必须能正常出报告。"""
        root = tempfile.mkdtemp(prefix="notl_ok_")
        game = os.path.join(root, "game")
        os.makedirs(game)
        with open(os.path.join(game, "script.rpy"), "w", encoding="utf-8") as fh:
            fh.write('label start:\n    "Hello"\n')
        try:
            for name in REG.ALL_GROUP:
                if REG.requires_tl(name) or name == "langcheck":
                    continue  # langcheck 无 game/ 之外的依赖，另测
                env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
                           PYTHONIOENCODING="utf-8")
                proc = subprocess.run(
                    [PYTHON, REG.script_path(name), game, *PASSTHROUGH],
                    capture_output=True, text=True, encoding="utf-8",
                    env=env, timeout=180)
                self.assertNotEqual(
                    proc.returncode, 2,
                    f"{name} 在无 tl 的最小项目上退出码 2（参数/路径错误）：\n"
                    f"{proc.stdout[-300:]}{proc.stderr[-300:]}",
                )
        finally:
            shutil.rmtree(root, ignore_errors=True)


class TestPassthroughCompatibility(unittest.TestCase):
    """防复发护栏：每个注册检查器都必须吃下 `all` 的透传参数。

    当初 `check_i18n.py` 缺 `-l` → argparse rc=2 → `all` 恒假阳性。这里用
    `--help` 探测（快、不需要真实项目），任一检查器漏参数就红。
    """

    def test_every_checker_accepts_lang_flag(self):
        """每个检查器都真吃下 `-l`（不给项目也不报错）。

        注意不能用「--help 输出里含 -l」当判据：`check_crash_risks.py` 用
        `argparse.SUPPRESS` 隐藏了它（故意不让用户以为能筛语言），help 里看不到
        但参数是接受的。所以改为实跑 `-l schinese` + 一个不存在的项目——
        argparse 的「unrecognized arguments」会出现，而路径错误不会。
        """
        offenders = []
        for name in REG.CHECKER_NAMES:
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
                       PYTHONIOENCODING="utf-8")
            proc = subprocess.run(
                [PYTHON, REG.script_path(name),
                 os.path.join(tempfile.gettempdir(), "__no_such_game__"),
                 *PASSTHROUGH],
                capture_output=True, text=True, encoding="utf-8",
                env=env, timeout=120)
            output = proc.stdout + proc.stderr
            if "unrecognized arguments" in output:
                offenders.append(f"{name}: {output.strip()[-120:]}")
        self.assertEqual(
            offenders, [],
            "这些检查器不接受 all 的透传参数 -l/--language，all 会因此假阳性："
            f"{offenders}",
        )

    def test_every_checker_declares_lang_flag_in_source(self):
        """源码层面对照：`-l` 必须被 add_argument 声明，不能靠碰巧不报错。

        上一条验行为，这条验声明——`check_i18n.py` 当初就是既没声明也没人测，
        两层都加上才不会再漏。
        """
        offenders = []
        for name in REG.CHECKER_NAMES:
            path = REG.script_path(name)
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            if '"-l"' not in text:
                offenders.append(f"{name}: {os.path.basename(path)}")
        self.assertEqual(offenders, [], f"这些检查器没声明 -l：{offenders}")

    def test_every_checker_accepts_lang_flag_with_value(self):
        """真带值跑一遍：`-l schinese` 不能触发 argparse 报错。"""
        offenders = []
        root = tempfile.mkdtemp(prefix="langflag_")
        game = os.path.join(root, "game")
        os.makedirs(game)
        with open(os.path.join(game, "script.rpy"), "w", encoding="utf-8") as fh:
            fh.write('label start:\n    "Hello"\n')
        try:
            for name in REG.CHECKER_NAMES:
                env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
                           PYTHONIOENCODING="utf-8")
                target = game
                if REG.takes_tl_dir(name):
                    tl = os.path.join(game, "tl", "schinese")
                    os.makedirs(tl, exist_ok=True)
                    target = tl
                proc = subprocess.run(
                    [PYTHON, REG.script_path(name), target, *PASSTHROUGH],
                    capture_output=True, text=True, encoding="utf-8",
                    env=env, timeout=180)
                if proc.returncode == 2 and "unrecognized arguments" in (
                        proc.stdout + proc.stderr):
                    offenders.append(f"{name}: {proc.stderr.strip()[:120]}")
                elif "unrecognized arguments" in (proc.stdout + proc.stderr):
                    offenders.append(f"{name}: unrecognized arguments")
        finally:
            shutil.rmtree(root, ignore_errors=True)
        self.assertEqual(offenders, [], f"透传参数报错：{offenders}")


class TestFacadeUsesRegistry(unittest.TestCase):
    """门面必须真的读注册表，而不是自己还留一份手写表。"""

    def setUp(self):
        self.cli_path = os.path.join(_SCRIPTS, "renpy-tools-cli.py")

    def _load_facade(self):
        if _SCRIPTS not in sys.path:
            sys.path.insert(0, _SCRIPTS)
        import renpy_tools_cli  # noqa: F401  (模块名带连字符，走文件路径导入)

    def _import_facade(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "renpy_tools_cli_mod", self.cli_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_facade_tool_scripts_match_registry(self):
        mod = self._import_facade()
        for name, path in mod.TOOL_SCRIPTS.items():
            with self.subTest(tool=name):
                self.assertEqual(os.path.normpath(path),
                                 os.path.normpath(REG.script_path(name)))

    def test_facade_desc_matches_registry(self):
        mod = self._import_facade()
        for name, desc in mod.TOOL_DESC.items():
            with self.subTest(tool=name):
                self.assertEqual(desc, REG.summary(name))

    def test_facade_needs_tl_dir_is_derived(self):
        """NEEDS_TL_DIR 里的检查器部分必须来自 CHECKER.requires_tl。"""
        mod = self._import_facade()
        derived = set(REG.all_requires_tl()) | REG.TL_DIR_WRITERS
        self.assertEqual(mod.NEEDS_TL_DIR, derived)

    def test_facade_tl_dir_tools_is_derived(self):
        mod = self._import_facade()
        self.assertEqual(mod.TL_DIR_TOOLS, set(REG.all_takes_tl_dir()))

    def test_facade_all_group_matches_registry(self):
        mod = self._import_facade()
        self.assertEqual(list(mod.ALL_GROUP), list(REG.ALL_GROUP))

    def test_list_output_mentions_every_tool(self):
        proc = subprocess.run([PYTHON, self.cli_path, "list"],
                              capture_output=True, text=True,
                              encoding="utf-8", timeout=120,
                              env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        self.assertEqual(proc.returncode, 0)
        for name in REG.TOOL_SCRIPTS:
            with self.subTest(tool=name):
                self.assertIn(name, proc.stdout, f"list 输出漏了 {name}")


class TestChecksDirectoryIsCanonical(unittest.TestCase):
    """只读检查器都该在 checks/（2026-10-06 把 3 个 tl 侧检查器从 translate/ 归位）。"""

    def test_no_checker_left_in_translate_dir(self):
        translate_dir = os.path.join(_SCRIPTS, "translate")
        strays = [fn for fn in os.listdir(translate_dir)
                  if fn.endswith(".py") and (fn.startswith("check_")
                                              or fn.startswith("lint_"))]
        self.assertEqual(
            strays, [],
            f"translate/ 里还有检查器：{strays}。只读检查器归checks/，"
            f"translate/ 留给写入类工具",
        )

    def test_every_registered_checker_lives_in_expected_dir(self):
        expected = {
            "checks": {"ui", "misuse", "func", "auto", "duplicate", "button",
                       "label", "type", "integrity", "untranslated", "charname",
                       "crash"},
            "sdk": {"fontcheck", "langcheck"},
        }
        for name in REG.CHECKER_NAMES:
            rel = REG.TOOL_SCRIPTS[name].replace("\\", "/")
            grp = rel.split("/")[0]
            with self.subTest(tool=name):
                self.assertEqual(grp, expected_by_name(name),
                                 f"{name} 在 {grp}/，注册表约定 "
                                 f"{expected_by_name(name)}/")

    def test_translate_dir_only_holds_writers(self):
        """translate/ 剩什么不重要，重要的是它不含 check_*/lint_*（上一条已钉）。"""
        translate_dir = os.path.join(_SCRIPTS, "translate")
        self.assertTrue(os.path.isdir(translate_dir))
        readme = os.path.join(translate_dir, "README.md")
        self.assertTrue(os.path.isfile(readme), "translate/README.md 应仍在")


def expected_by_name(name):
    if name in ("fontcheck", "langcheck"):
        return "sdk"
    return "checks"


if __name__ == "__main__":
    unittest.main(verbosity=2)