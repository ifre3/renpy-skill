"""CLI 门面契约：每个子命令的 --help 都必须成功返回。

回归背景：`remove_translated` / `patch_android_tablet` 把 `--help` 当成
「未知操作 / 路径不存在」处理并 exit 1。门面把参数原样转发，导致上层
批量探测可用性时会把这两个正常工具误判为不可用。
"""

import os
import subprocess
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_TOOLS = os.path.dirname(_HERE)
_CLI = os.path.join(_TOOLS, "renpy-tools-cli.py")

# 与 renpy-tools-cli.py 的 TOOL_SCRIPTS 保持一致（这里显式列出，
# 目的是让「新增子命令却忘了写测试」变成一次可见的失败）
ALL_SUBCOMMANDS = [
    "ui", "misuse", "func", "auto", "duplicate", "button", "label", "type",
    "lint", "integrity", "untranslated", "charname", "namebox", "crash",
    "fontcheck", "langcheck",
    "linear", "fixtags", "fixcomments", "patchsay", "i18n", "lang", "fonts",
    "langbtn", "perfpanel", "rmsuffix", "urm", "unrpyc", "tablet", "optimize",
]


def _run(args):
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run(
        [sys.executable, _CLI, *args], capture_output=True, env=env
    )


class TestCliSurface(unittest.TestCase):
    def test_subcommand_list_matches_cli(self):
        """测试清单与代码里的 TOOL_SCRIPTS 一致（防止漏测新增项）。"""
        import importlib.util

        spec = importlib.util.spec_from_file_location("_cli", _CLI)
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        self.assertEqual(sorted(cli.TOOL_SCRIPTS), sorted(ALL_SUBCOMMANDS))
        self.assertEqual(len(ALL_SUBCOMMANDS), 30)

    def test_list_succeeds(self):
        r = _run(["list"])
        self.assertEqual(r.returncode, 0, r.stderr.decode("utf-8", "replace")[:300])
        self.assertIn("all", r.stdout.decode("utf-8", "replace"))

    def test_unknown_command_is_rejected(self):
        r = _run(["no_such_command"])
        self.assertEqual(r.returncode, 2)
        self.assertIn("未知命令", r.stdout.decode("utf-8", "replace"))

    def test_list_rejects_extra_args(self):
        r = _run(["list", "extra"])
        self.assertEqual(r.returncode, 2)

    def test_every_subcommand_help_succeeds(self):
        for name in ALL_SUBCOMMANDS:
            with self.subTest(cmd=name):
                r = _run([name, "--help"])
                self.assertEqual(
                    r.returncode, 0,
                    f"{name} --help 返回 {r.returncode}: "
                    f"{r.stderr.decode('utf-8', 'replace')[:200]}",
                )

    def test_no_subcommand_shows_help(self):
        r = _run([])
        self.assertEqual(r.returncode, 0)

    def test_root_help_flag(self):
        r = _run(["--help"])
        self.assertEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)