#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""外置配置加载器的回归（2026-10-05 新增，零测试覆盖的两个 loader）。

被测对象：
- checks/common.py: SCREEN_CALL_KW 从内置常量改为读 renpy_screen_calls.json
- names/unify_name_translations.py: SKIP_FILES 改为读 renpy_skip_files.json

迁移动机：这两份清单原本是**具体游戏**的产物文件名/自造 screen 名，
留在代码里会造成「换游戏时恰好同名 → 被静默跳过」这类难以察觉的漏处理。
外置后「改代码」降级为「改 JSON」，且必须用测试锁住加载语义。
"""

import importlib
import json
import os
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_TOOLS = os.path.dirname(_HERE)
for p in (_TOOLS, os.path.join(_TOOLS, "checks"), os.path.join(_TOOLS, "names")):
    if p not in sys.path:
        sys.path.insert(0, p)

# 环境变量必须在 import 前设好 loader 才会读；各用例用 helper 自行控制
_ENV_KEYS = ("RENPY_SCREEN_CALL_KW", "RENPY_SKIP_FILES")


class _LoaderCase(unittest.TestCase):
    def setUp(self):
        for k in _ENV_KEYS:
            os.environ.pop(k, None)
        self._cwd = os.getcwd()
        self._tmp = tempfile.TemporaryDirectory()
        os.chdir(self._tmp.name)

    def tearDown(self):
        os.chdir(self._cwd)
        self._tmp.cleanup()
        for k in _ENV_KEYS:
            os.environ.pop(k, None)

    def write_json(self, name, payload):
        path = os.path.join(self._tmp.name, name)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)
        return path

    def reload(self, modname):
        """强制重载模块，让 loader 重新读配置。"""
        if modname in sys.modules:
            return importlib.reload(sys.modules[modname])
        return importlib.import_module(modname)


class TestScreenCallKwConfig(_LoaderCase):
    MOD = "common"

    def test_builtin_default_is_minimal(self):
        """默认清单覆盖已验证的自定义 screen 名，不因外置机制而缩水。

        回归背景：外置 JSON 时曾把默认收窄到只剩 game_menu，导致
        heading / settings_item / tab_button 三类调用静默失效——
        `func` 子命令对这类游戏报不出东西，且没有任何提示。
        收窄必须是「加」而不是「减」：增量的部分交给 JSON。
        """
        common = self.reload(self.MOD)
        self.assertEqual(
            common.SCREEN_CALL_KW,
            {"game_menu", "heading", "settings_item", "tab_button"},
        )
        self.assertEqual(common.screen_call_kw_source(), "builtin")

    def test_json_list_appends_to_builtin(self):
        self.write_json("renpy_screen_calls.json", ["reward_button", "my_panel"])
        common = self.reload(self.MOD)
        self.assertEqual(
            common.SCREEN_CALL_KW,
            set(common._BUILTIN_SCREEN_CALL_KW) | {"reward_button", "my_panel"},
        )
        self.assertIn("game_menu", common.SCREEN_CALL_KW)
        self.assertEqual(common.screen_call_kw_source(), "builtin+json:extra")

    def test_json_replace_overrides_builtin(self):
        self.write_json("renpy_screen_calls.json", {"replace": ["my_menu"]})
        common = self.reload(self.MOD)
        self.assertEqual(common.SCREEN_CALL_KW, {"my_menu"})
        self.assertEqual(common.screen_call_kw_source(), "json:replace")

    def test_env_var_path_takes_precedence_over_cwd(self):
        other = os.path.join(self._tmp.name, "sub")
        os.makedirs(other, exist_ok=True)
        path = os.path.join(other, "custom.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(["from_env"], fh)
        os.environ["RENPY_SCREEN_CALL_KW"] = path
        common = self.reload(self.MOD)
        self.assertIn("from_env", common.SCREEN_CALL_KW)

    def test_malformed_json_falls_back_to_builtin(self):
        """坏 JSON 不能让工具整体崩掉——退回内置清单并继续。"""
        with open("renpy_screen_calls.json", "w", encoding="utf-8") as fh:
            fh.write("{ this is not json")
        common = self.reload(self.MOD)
        self.assertEqual(
            common.SCREEN_CALL_KW, set(common._BUILTIN_SCREEN_CALL_KW)
        )

    def test_unexpected_shape_falls_back(self):
        """写成数字/字符串的怪形状也不能崩。"""
        self.write_json("renpy_screen_calls.json", 42)
        common = self.reload(self.MOD)
        self.assertEqual(
            common.SCREEN_CALL_KW, set(common._BUILTIN_SCREEN_CALL_KW)
        )

    def test_example_file_is_valid_and_documents_itself(self):
        """随仓库的 .example 必须能被 loader 读懂，且带使用说明。"""
        example = os.path.join(_TOOLS, "checks", "renpy_screen_calls.json.example")
        self.assertTrue(os.path.isfile(example), "缺少 example 文件")
        with open(example, encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertIn("_readme", data)
        self.assertIn("replace", data)


class TestSkipFilesConfig(_LoaderCase):
    MOD = "unify_name_translations"

    def _get(self):
        mod = self.reload(self.MOD)
        return mod._load_skip_files()

    def test_default_is_standard_file_only(self):
        """内置只留 defaultlanguage.rpy（Ren'Py 标准文件）。"""
        self.assertEqual(self._get(), {"defaultlanguage.rpy"})

    def test_json_list_appends(self):
        self.write_json("renpy_skip_files.json", ["my_names.rpy"])
        self.assertEqual(
            self._get(), {"defaultlanguage.rpy", "my_names.rpy"}
        )

    def test_json_replace_drops_builtin(self):
        self.write_json("renpy_skip_files.json", {"replace": ["only.rpy"]})
        self.assertEqual(self._get(), {"only.rpy"})

    def test_malformed_json_falls_back(self):
        with open("renpy_skip_files.json", "w", encoding="utf-8") as fh:
            fh.write("not json at all")
        self.assertEqual(self._get(), {"defaultlanguage.rpy"})

    def test_collect_files_respects_config_at_call_time(self):
        """跳过清单在 collect_files 调用时求值，不在 import 时固化。

        回归意义：用户在 v6 流程中途改配置（这正是本工具的常见用法——
        收集完看报告再决定加哪些跳过项），必须立刻生效而不必重启进程。
        """
        mod = self.reload(self.MOD)
        tl = os.path.join(self._tmp.name, "tl")
        os.makedirs(tl)
        for name in ("a.rpy", "defaultlanguage.rpy", "b.rpy"):
            with open(os.path.join(tl, name), "w", encoding="utf-8") as fh:
                fh.write('translate schinese:\n    old "x"\n    new "y"\n')

        before = {os.path.basename(p) for p in mod.collect_files(tl)}
        self.assertEqual(before, {"a.rpy", "b.rpy"})

        self.write_json("renpy_skip_files.json", ["a.rpy"])
        after = {os.path.basename(p) for p in mod.collect_files(tl)}
        self.assertEqual(after, {"b.rpy"}, "改配置后 collect_files 必须重新读取")

    def test_example_file_is_valid_and_documents_itself(self):
        example = os.path.join(_TOOLS, "names", "renpy_skip_files.json.example")
        self.assertTrue(os.path.isfile(example), "缺少 example 文件")
        with open(example, encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertIn("_readme", data)
        self.assertIn("replace", data)


if __name__ == "__main__":
    unittest.main(verbosity=2)