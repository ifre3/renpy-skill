# -*- coding: utf-8 -*-
"""lang_names（语言码↔展示名映射）与 autotranslate 语言参数覆盖的契约。

回归背景（2026-10-31 第十一批）：autotranslate 的 target_language 写死
"Simplified Chinese" 且无覆盖入口，翻到非中文只能改源码；各检查器 -l
默认值各自硬编码。收口到 shared/lang_names.py 后，这里钉死映射与覆盖链。
"""

import importlib.util
import os
import sys
import unittest
from argparse import Namespace

_HERE = os.path.dirname(os.path.abspath(__file__))
_SHARED = os.path.join(os.path.dirname(_HERE), "shared")
if _SHARED not in sys.path:
    sys.path.insert(0, _SHARED)

import lang_names  # noqa: E402

_AUTOTRANSLATE = os.path.join(os.path.dirname(_HERE), "translate", "autotranslate.py")


def _load_autotranslate():
    """按文件路径加载 autotranslate 模块（requests 可缺，scan/apply 不依赖）。"""
    spec = importlib.util.spec_from_file_location("_autotranslate", _AUTOTRANSLATE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestLangNames(unittest.TestCase):
    def test_default_lang_is_single_source(self):
        """检查器与门面的默认语言都指向 lang_names.DEFAULT_LANG。"""
        import tool_registry as REG

        self.assertEqual(REG.DEFAULT_LANG, lang_names.DEFAULT_LANG)
        self.assertEqual(lang_names.DEFAULT_LANG, "schinese")

    def test_known_codes_map_to_display_names(self):
        cases = {
            "schinese": "Simplified Chinese",
            "tchinese": "Traditional Chinese",
            "japanese": "Japanese",
            "brazilian_portuguese": "Brazilian Portuguese",
            "korean": "Korean",
        }
        for code, name in cases.items():
            self.assertEqual(lang_names.lang_display_name(code), name)

    def test_unknown_code_passes_through(self):
        self.assertEqual(lang_names.lang_display_name("klingon"), "klingon")

    def test_resolve_language_code_case_insensitive(self):
        self.assertEqual(lang_names.resolve_language("japanese"), "Japanese")
        self.assertEqual(lang_names.resolve_language("  JAPANESE "), "Japanese")

    def test_resolve_language_free_text_passthrough(self):
        self.assertEqual(lang_names.resolve_language("Brazilian Portuguese"), "Brazilian Portuguese")
        self.assertIsNone(lang_names.resolve_language(None))
        self.assertEqual(lang_names.resolve_language(""), "")


class TestAutotranslateLangOverride(unittest.TestCase):
    def test_cli_overrides_win_and_resolve(self):
        """--source/--target-language 覆盖默认值，语言码自动转展示名。"""
        mod = _load_autotranslate()
        args = Namespace(
            api_url=None, api_key=None, model=None, max_chars=None,
            glossary=None, source_language="japanese", target_language="tchinese",
        )
        cfg = mod.load_config(args)
        self.assertEqual(cfg["source_language"], "Japanese")
        self.assertEqual(cfg["target_language"], "Traditional Chinese")

    def test_no_override_keeps_defaults(self):
        """不传参数时保持默认（env 未设置即写死的兜底值）。"""
        mod = _load_autotranslate()
        args = Namespace(
            api_url=None, api_key=None, model=None, max_chars=None,
            glossary=None, source_language=None, target_language=None,
        )
        cfg = mod.load_config(args)
        self.assertEqual(cfg["source_language"], "English")
        self.assertEqual(cfg["target_language"], "Simplified Chinese")


if __name__ == "__main__":
    unittest.main()
