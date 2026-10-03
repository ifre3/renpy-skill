#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_renpy_tools.py — Ren'Py 翻译工具集单元测试

覆盖核心解析逻辑:
  - check_untranslated: has_real_text / is_renpy_tag_line / strip_renpy_tags / scan_file
  - check_translation_integrity: check_pair (变量/标签/转义符检查)
  - unify_name_translations: parse_blocks / _replace_name_in_dialogue
  - autotranslate: protect_rpy_tags / restore_rpy_tags / make_batches / parse_response

运行:
    cd tools
    python -m pytest 测试/test_renpy_tools.py -v
    # 或直接运行
    python 测试/test_renpy_tools.py
"""

import csv
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

# ── 路径设置 ──
_TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TRANSLATE = os.path.join(_TOOLS, "翻译相关")
_CHECK = os.path.join(_TOOLS, "错误检测")
_UNIFY = os.path.join(_TOOLS, "统一名称")
_BACKUP = os.path.join(_TOOLS, "公共")
for p in (_TRANSLATE, _CHECK, _UNIFY, _BACKUP, _TOOLS):
    if p not in sys.path:
        sys.path.insert(0, p)

import check_untranslated  # noqa: E402
import check_translation_integrity as integrity  # noqa: E402
import autotranslate  # noqa: E402
import rpy_syntax  # noqa: E402
from backup import atomic_write_text, create_bak  # noqa: E402


# ============================================================================
# check_untranslated 测试
# ============================================================================


class TestHasRealText(unittest.TestCase):
    def test_empty_string(self):
        self.assertFalse(check_untranslated.has_real_text(""))

    def test_ellipsis_only(self):
        self.assertFalse(check_untranslated.has_real_text("..."))
        self.assertFalse(check_untranslated.has_real_text("......"))

    def test_pure_numbers(self):
        self.assertFalse(check_untranslated.has_real_text("123"))

    def test_pure_tags(self):
        self.assertFalse(check_untranslated.has_real_text("{cps=10}"))
        self.assertFalse(check_untranslated.has_real_text("{w=1.0}"))
        self.assertFalse(check_untranslated.has_real_text("[c_name]"))

    def test_english_word(self):
        self.assertTrue(check_untranslated.has_real_text("Hello world"))
        self.assertTrue(check_untranslated.has_real_text("Hi"))

    def test_single_ascii_short(self):
        # 单字符 ASCII 不视为需翻译
        self.assertFalse(check_untranslated.has_real_text("A"))

    def test_cjk_text(self):
        self.assertTrue(check_untranslated.has_real_text("你好世界"))
        self.assertTrue(check_untranslated.has_real_text("Hello 你好"))

    def test_stuttered(self):
        # S-so, I-I 等口吃
        self.assertTrue(check_untranslated.has_real_text("S-so sorry"))

    def test_mixed_tags_and_text(self):
        self.assertTrue(check_untranslated.has_real_text("{b}Hello{/b}"))
        self.assertTrue(check_untranslated.has_real_text("[name] arrived."))

    # game/path 注释由 is_renpy_tag_line 检测，has_real_text 不负责
    # 已在 TestIsRenpyTagLine.test_game_comment 中覆盖


class TestStripRenpyTags(unittest.TestCase):
    def test_strip_curly_tags(self):
        self.assertEqual(check_untranslated.strip_renpy_tags("{b}text{/b}"), "text")

    def test_strip_square_brackets(self):
        self.assertEqual(check_untranslated.strip_renpy_tags("[name]"), "")

    def test_mixed(self):
        # strip_renpy_tags 末尾有 .strip()，尾空格会被裁掉
        self.assertEqual(check_untranslated.strip_renpy_tags("{b}Hi [name]{/b}"), "Hi")

    def test_no_tags(self):
        self.assertEqual(
            check_untranslated.strip_renpy_tags("plain text"), "plain text"
        )

    def test_nested_tags(self):
        self.assertEqual(
            check_untranslated.strip_renpy_tags("{color=#f}{b}text{/b}{/color}"), "text"
        )


class TestIsRenpyTagLine(unittest.TestCase):
    def test_pure_tag_line(self):
        self.assertTrue(check_untranslated.is_renpy_tag_line("{cps=10}"))
        self.assertTrue(check_untranslated.is_renpy_tag_line("{w=1.0}{nw}"))

    def test_game_comment(self):
        self.assertTrue(check_untranslated.is_renpy_tag_line("# game/script.rpy:42"))

    def test_c_var(self):
        self.assertTrue(check_untranslated.is_renpy_tag_line("[c_variable]"))

    def test_real_text(self):
        self.assertFalse(check_untranslated.is_renpy_tag_line("Hello world"))
        self.assertFalse(check_untranslated.is_renpy_tag_line("{b}Hello{/b}"))


class TestScanFile(unittest.TestCase):
    """测试 scan_file。使用 _make_temp_rpy 创建临时文件，tearDown 清理。"""

    def setUp(self):
        self._temp_files = []

    def tearDown(self):
        for p in self._temp_files:
            try:
                os.unlink(p)
            except OSError:
                pass

    def _make_temp_rpy(self, content):
        """创建临时 .rpy 文件，返回路径字符串。"""
        fd, path = tempfile.mkstemp(suffix=".rpy", prefix="test_")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        self._temp_files.append(path)
        return path

    def test_empty_translation_tb(self):
        """translate block 空译文"""
        content = 'translate schinese test_block:\n\n    # "Hello world"\n    ""\n'
        path = self._make_temp_rpy(content)
        items = check_untranslated.scan_file(path, strict=True)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["type"], "tb")
        self.assertEqual(items[0]["orig"], "Hello world")
        self.assertTrue(items[0]["empty"])

    def test_empty_translation_cd(self):
        """角色对话空译文 c_xxx "" """
        content = (
            'translate schinese test_block:\n\n    # c_mc "Good morning"\n    c_mc ""\n'
        )
        path = self._make_temp_rpy(content)
        items = check_untranslated.scan_file(path, strict=True)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["type"], "cd")
        self.assertEqual(items[0]["char"], "c_mc")
        self.assertEqual(items[0]["orig"], "Good morning")

    def test_empty_translation_on(self):
        """old/new 空译文"""
        content = 'translate strings test_block:\n    old "Save Game"\n    new ""\n'
        path = self._make_temp_rpy(content)
        items = check_untranslated.scan_file(path, strict=True)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["type"], "on")
        self.assertEqual(items[0]["orig"], "Save Game")

    def test_already_translated(self):
        """已翻译条目不出现在 strict 模式"""
        content = (
            'translate schinese test_block:\n\n    # "Hello world"\n    "你好世界"\n'
        )
        path = self._make_temp_rpy(content)
        items = check_untranslated.scan_file(path, strict=True)
        self.assertEqual(len(items), 0)

    def test_same_in_non_strict(self):
        """原文=译文在 non-strict 模式被检出"""
        content = 'translate schinese test_block:\n\n    # "Hello"\n    "Hello"\n'
        path = self._make_temp_rpy(content)
        items = check_untranslated.scan_file(path, strict=False)
        self.assertEqual(len(items), 1)
        self.assertFalse(items[0]["empty"])

    def test_same_chinese_is_skipped_in_strict_mode(self):
        content = 'translate schinese test_block:\n\n    # "你好"\n    "你好"\n'
        path = self._make_temp_rpy(content)
        self.assertEqual(check_untranslated.scan_file(path, strict=True), [])
        self.assertEqual(len(check_untranslated.scan_file(path, strict=False)), 1)

    def test_csv_keeps_character_name(self):
        content = 'translate schinese block:\n    # mmc "Hello"\n    mmc ""\n'
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test.rpy")
            with open(path, "w", encoding="utf-8") as stream:
                stream.write(content)
            output = os.path.join(tmp, "out.csv")
            count = check_untranslated.export_csv([path], tmp, output, strict=True)
            self.assertEqual(count, 1)
            with open(output, encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(rows[0]["char"], "mmc")

    def test_skip_tag_lines(self):
        """纯标签行不被检出"""
        content = 'translate schinese test_block:\n\n    # "{cps=10}"\n    ""\n'
        path = self._make_temp_rpy(content)
        items = check_untranslated.scan_file(path, strict=True)
        self.assertEqual(len(items), 0)

    def test_multiple_types(self):
        """混合 tb + cd + on 类型"""
        content = (
            "translate schinese block1:\n"
            "\n"
            '    # "Hello"\n'
            '    ""\n'
            "\n"
            '    # c_mc "Hi there"\n'
            '    c_mc ""\n'
            "\n"
            "translate strings block2:\n"
            '    old "Save"\n'
            '    new ""\n'
        )
        path = self._make_temp_rpy(content)
        items = check_untranslated.scan_file(path, strict=True)
        types = sorted(i["type"] for i in items)
        self.assertEqual(types, ["cd", "on", "tb"])


# ============================================================================
# check_translation_integrity 测试
# ============================================================================


class TestCheckPair(unittest.TestCase):
    def test_no_errors(self):
        """正确翻译无错误"""
        errors = integrity.check_pair(
            "Hello [name]", "你好 [name]", 1, "test.rpy", "dialogue"
        )
        self.assertEqual(len(errors), 0)

    def test_lost_variable(self):
        """译文丢失变量"""
        errors = integrity.check_pair("Hi [name]", "嗨", 1, "test.rpy", "dialogue")
        types = [e["type"] for e in errors]
        self.assertIn("LOST_VAR", types)

    def test_extra_variable(self):
        """译文新增变量"""
        errors = integrity.check_pair("Hi", "嗨 [name]", 1, "test.rpy", "dialogue")
        types = [e["type"] for e in errors]
        self.assertIn("EXTRA_VAR", types)

    def test_translated_variable(self):
        """变量名被翻译 [day] -> [一天]"""
        errors = integrity.check_pair(
            "Today is [day]", "今天是 [一天]", 1, "test.rpy", "dialogue"
        )
        types = [e["type"] for e in errors]
        self.assertIn("VAR_TRANSLATED", types)

    def test_lost_tag(self):
        """译文丢失标签"""
        errors = integrity.check_pair(
            "{b}Important{/b}", "重要", 1, "test.rpy", "dialogue"
        )
        types = [e["type"] for e in errors]
        self.assertIn("LOST_TAG", types)

    def test_lost_escape(self):
        """译文丢失 [[ 转义"""
        errors = integrity.check_pair("Value [[0]]", "值 0", 1, "test.rpy", "dialogue")
        types = [e["type"] for e in errors]
        self.assertIn("LOST_ESCAPE", types)

    def test_flag_mismatch(self):
        """译文删除原文已有的 !t 标志"""
        errors = integrity.check_pair("[name!t]", "[name]", 1, "test.rpy", "dialogue")
        types = [e["type"] for e in errors]
        self.assertIn("FLAG_MISMATCH", types)

    def test_adding_translation_flag_is_allowed(self):
        """译文主动增加 !t 以翻译变量值是合法修复，不应误报。"""
        errors = integrity.check_pair("[name]", "[name!t]", 1, "test.rpy", "dialogue")
        self.assertNotIn("FLAG_MISMATCH", [e["type"] for e in errors])
        self.assertEqual(autotranslate.validate_translation("[name]", "[name!t]"), [])

    def test_escape_broken(self):
        """\\n 被拆成字面换行"""
        errors = integrity.check_pair(
            "Line1\\nLine2", "第一行\n第二行", 1, "test.rpy", "dialogue"
        )
        types = [e["type"] for e in errors]
        self.assertIn("ESCAPE_BROKEN", types)

    def test_tags_preserved(self):
        """标签保留正确"""
        errors = integrity.check_pair(
            "{b}Hello{/b} {i}world{/i}",
            "{b}你好{/b} {i}世界{/i}",
            1,
            "test.rpy",
            "dialogue",
        )
        self.assertEqual(len(errors), 0)

    def test_var_with_t_flag(self):
        """带 !t 的变量正确保留"""
        errors = integrity.check_pair(
            "[name!t] says hello", "[name!t] 说你好", 1, "test.rpy", "dialogue"
        )
        self.assertEqual(len(errors), 0)


# ============================================================================
# autotranslate 测试
# ============================================================================


class TestProtectRestoreTags(unittest.TestCase):
    def test_protect_curly(self):
        protected, pmap = autotranslate.protect_rpy_tags("{b}text{/b}")
        self.assertEqual(protected, "{{P1}}text{{P2}}")
        self.assertEqual(pmap, {"P1": "{b}", "P2": "{/b}"})

    def test_protect_square(self):
        protected, pmap = autotranslate.protect_rpy_tags("[name]")
        self.assertEqual(protected, "{{P1}}")
        self.assertEqual(pmap, {"P1": "[name]"})

    def test_protect_var_with_flag(self):
        """!t 标志被隐藏在占位词中"""
        protected, pmap = autotranslate.protect_rpy_tags("[c_mc_name!t]")
        self.assertEqual(protected, "{{P1}}")
        self.assertEqual(pmap, {"P1": "[c_mc_name!t]"})

    def test_protect_dedup(self):
        """相同标签字符串映射到同一编号"""
        protected, pmap = autotranslate.protect_rpy_tags("{i}a{/i} {i}b{/i}")
        self.assertEqual(protected, "{{P1}}a{{P2}} {{P1}}b{{P2}}")
        self.assertEqual(len(pmap), 2)

    def test_restore_curly(self):
        pmap = {"P1": "{b}", "P2": "{/b}"}
        self.assertEqual(
            autotranslate.restore_rpy_tags("{{P1}}text{{P2}}", pmap),
            "{b}text{/b}",
        )

    def test_restore_square(self):
        pmap = {"P1": "[name]"}
        self.assertEqual(autotranslate.restore_rpy_tags("{{P1}}", pmap), "[name]")

    def test_restore_var_with_flag(self):
        pmap = {"P1": "[c_mc_name!t]"}
        self.assertEqual(
            autotranslate.restore_rpy_tags("hi {{P1}}", pmap),
            "hi [c_mc_name!t]",
        )

    def test_round_trip(self):
        original = "{b}Hi [name]{/b} {color=#fff}text{/color}"
        protected, pmap = autotranslate.protect_rpy_tags(original)
        restored = autotranslate.restore_rpy_tags(protected, pmap)
        self.assertEqual(restored, original)

    def test_plain_text_unchanged(self):
        text = "Hello world 123"
        protected, pmap = autotranslate.protect_rpy_tags(text)
        self.assertEqual(protected, text)
        self.assertEqual(pmap, {})
        restored = autotranslate.restore_rpy_tags(protected, pmap)
        self.assertEqual(restored, text)


class TestMakeBatches(unittest.TestCase):
    def test_single_batch(self):
        entries = [{"orig": "short"}]
        batches = autotranslate.make_batches(entries, 1000)
        self.assertEqual(len(batches), 1)
        self.assertEqual(len(batches[0]), 1)

    def test_split_batches(self):
        entries = [{"orig": "a" * 600}, {"orig": "b" * 600}]
        batches = autotranslate.make_batches(entries, 1000)
        self.assertEqual(len(batches), 2)

    def test_single_large_entry(self):
        entries = [{"orig": "x" * 2000}]
        batches = autotranslate.make_batches(entries, 1000)
        self.assertEqual(len(batches), 1)

    def test_empty_entries(self):
        batches = autotranslate.make_batches([], 1000)
        self.assertEqual(len(batches), 0)

    def test_exact_boundary(self):
        entries = [{"orig": "a" * 500}, {"orig": "b" * 500}]
        batches = autotranslate.make_batches(entries, 1000)
        self.assertEqual(len(batches), 1)


class TestParseResponse(unittest.TestCase):
    def test_json_array(self):
        resp = '[{"id": 0, "text": "你好"}, {"id": 1, "text": "世界"}]'
        batch = [{"orig": "hello"}, {"orig": "world"}]
        results = autotranslate.parse_response(resp, batch)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0][1], "你好")
        self.assertEqual(results[1][1], "世界")

    def test_markdown_wrapped(self):
        resp = '```json\n[{"id": 0, "text": "嗨"}]\n```'
        batch = [{"orig": "hi"}]
        results = autotranslate.parse_response(resp, batch)
        self.assertEqual(results[0][1], "嗨")

    def test_json_embedded_in_text(self):
        resp = 'Here are translations: [{"id": 0, "text": "你好"}] done.'
        batch = [{"orig": "hello"}]
        results = autotranslate.parse_response(resp, batch)
        self.assertEqual(results[0][1], "你好")

    def test_parse_failure(self):
        resp = "Sorry, I cannot translate this."
        batch = [{"orig": "hello"}]
        results = autotranslate.parse_response(resp, batch)
        self.assertEqual(len(results), 1)
        self.assertIsNone(results[0][1])

    def test_string_id_is_accepted(self):
        resp = '[{"id": "0", "text": "你好"}]'
        batch = [{"orig": "hello"}]
        results = autotranslate.parse_response(resp, batch)
        self.assertEqual(results[0][1], "你好")

    def test_missing_id(self):
        resp = '[{"id": 0, "text": "你好"}]'
        batch = [{"orig": "hello"}, {"orig": "world"}]
        results = autotranslate.parse_response(resp, batch)
        self.assertEqual(results[0][1], "你好")
        self.assertIsNone(results[1][1])


class TestValidateTranslation(unittest.TestCase):
    def test_valid_translation(self):
        issues = autotranslate.validate_translation("Hello [name]", "你好 [name]")
        self.assertEqual(len(issues), 0)

    def test_none_translation(self):
        issues = autotranslate.validate_translation("Hello", None)
        self.assertEqual(len(issues), 1)

    def test_empty_translation(self):
        issues = autotranslate.validate_translation("Hello", "")
        self.assertEqual(len(issues), 1)

    def test_missing_tag(self):
        issues = autotranslate.validate_translation("{b}Hello{/b}", "你好")
        # 丢失标签 + 开闭标签数量不一致 = 3 条
        self.assertGreaterEqual(len(issues), 1)
        self.assertTrue(any("丢失标签" in i for i in issues))

    def test_missing_variable(self):
        issues = autotranslate.validate_translation("Hi [name]", "嗨")
        self.assertEqual(len(issues), 1)
        self.assertIn("丢失变量", issues[0])


class TestEscapeForRpy(unittest.TestCase):
    def test_plain_text(self):
        self.assertEqual(autotranslate.escape_for_rpy("hello"), "hello")

    def test_quotes(self):
        self.assertEqual(autotranslate.escape_for_rpy('say "hi"'), 'say \\"hi\\"')

    def test_backslash(self):
        self.assertEqual(autotranslate.escape_for_rpy("a\\b"), "a\\\\b")

    def test_newline(self):
        self.assertEqual(autotranslate.escape_for_rpy("line1\nline2"), "line1\\nline2")


# ============================================================================
# 共享语法解析、完整性检测与安全回填回归测试
# ============================================================================


class TestRpySyntax(unittest.TestCase):
    def test_arbitrary_speaker_and_escaped_quote(self):
        lines = [
            r'    # e "He said \"hi\""',
            r'    e "他说\"喂\""',
        ]
        pairs = list(rpy_syntax.iter_translation_pairs(lines))
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0].kind, "cd")
        self.assertEqual(pairs[0].original_speaker, "e")
        self.assertEqual(pairs[0].translated_speaker, "e")
        self.assertEqual(pairs[0].original, 'He said "hi"')
        self.assertEqual(pairs[0].translated, '他说"喂"')

    def test_single_quoted_old_new(self):
        lines = [r"    old 'It\'s ready'", r"    new '准备好了'"]
        pairs = list(rpy_syntax.iter_translation_pairs(lines))
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0].kind, "on")
        self.assertEqual(pairs[0].original, "It's ready")
        self.assertEqual(pairs[0].translated, "准备好了")

    def test_single_quote_replacement_preserves_quote_style(self):
        line = r"    new 'It\'s ready'"
        literal = rpy_syntax.parse_new_line(line)
        self.assertIsNotNone(literal)
        replaced = rpy_syntax.replace_literal_content(line, literal, "已准备好")
        self.assertEqual(replaced, "    new '已准备好'")
        line = r"    new 'Quote: \"hi\"'"
        literal = rpy_syntax.parse_new_line(line)
        replaced = rpy_syntax.replace_literal_content(
            line, literal, "引号：\"嗨\""
        )
        self.assertEqual(replaced, "    new '引号：\"嗨\"'")

    def test_missing_target_is_reported(self):
        pairs = list(rpy_syntax.iter_translation_pairs(['    # e "Hello"']))
        self.assertEqual(len(pairs), 1)
        self.assertIsNone(pairs[0].translated)
        self.assertIsNone(pairs[0].translated_line)

    def test_target_preserves_say_attributes(self):
        lines = ['    # e "Hello"', '    e "" with dissolve']
        entry = {"line": 1, "type": "cd", "char": "e", "orig": "Hello"}
        target, literal = autotranslate.find_target_line(lines, entry)
        self.assertEqual(target, 1)
        replaced = autotranslate.replace_literal_content(
            lines[target], literal, "你好"
        )
        self.assertEqual(replaced, '    e "你好" with dissolve')

    def test_stale_anchor_is_rejected(self):
        lines = ['    # e "Changed original"', '    e ""']
        entry = {"line": 1, "type": "cd", "char": "e", "orig": "Hello"}
        self.assertFalse(autotranslate.entry_anchor_matches(lines, entry))
        self.assertEqual(autotranslate.find_target_line(lines, entry)[0], -1)

    def test_safe_project_path_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as base:
            inside = autotranslate.safe_project_path(base, "chapters/a.rpy")
            self.assertIsNotNone(inside)
            self.assertIsNone(autotranslate.safe_project_path(base, "../outside.rpy"))
            self.assertIsNone(autotranslate.safe_project_path(base, base + "/abs.rpy"))


class TestNameboxSynchronizer(unittest.TestCase):
    @staticmethod
    def _load_sync():
        import importlib.util

        path = os.path.join(_TRANSLATE, "sync_namebox_translation.py")
        spec = importlib.util.spec_from_file_location("sync_namebox_translation", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_empty_existing_name_is_updated_not_duplicated(self):
        sync = self._load_sync()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "strings.rpy")
            with open(path, "w", encoding="utf-8") as stream:
                stream.write(
                    'translate schinese strings:\n\n'
                    '    old "Hina"\n'
                    '    new ""\n'
                )
            count = sync.append_translations(
                path,
                [("game/characters.rpy", 10, "Hina", "雏")],
                "schinese",
            )
            self.assertEqual(count, 1)
            with open(path, encoding="utf-8") as stream:
                content = stream.read()
            self.assertEqual(content.count('old "Hina"'), 1)
            self.assertIn('new "雏"', content)
            self.assertTrue(os.path.isfile(path + ".bak"))

    def test_new_name_is_escaped(self):
        sync = self._load_sync()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "strings.rpy")
            with open(path, "w", encoding="utf-8") as stream:
                stream.write('translate schinese strings:\n\n    new "Ready"\n')
            count = sync.append_translations(
                path,
                [("game/characters.rpy", 10, 'A"Name', '译"名')],
                "schinese",
            )
            self.assertEqual(count, 1)
            with open(path, encoding="utf-8") as stream:
                content = stream.read()
            self.assertIn(r'old "A\"Name"', content)
            self.assertIn(r'new "译\"名"', content)


class TestSourcePatchSafety(unittest.TestCase):
    @staticmethod
    def _load_patcher():
        import importlib.util

        path = os.path.join(_TRANSLATE, "patch_renpy_say.py")
        spec = importlib.util.spec_from_file_location("patch_renpy_say", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_non_source_files_are_never_rewritten(self):
        patcher = self._load_patcher()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "asset.png")
            data = b"Hello\x00binary"
            with open(path, "wb") as stream:
                stream.write(data)
            matched, missed = patcher.process_file(
                path,
                [("asset.png", "Hello", "你好")],
                dry_run=False,
            )
            self.assertEqual((matched, missed), (0, 0))
            with open(path, "rb") as stream:
                self.assertEqual(stream.read(), data)

    def test_source_replacement_is_atomic_and_backed_up(self):
        patcher = self._load_patcher()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "script.rpy")
            with open(path, "w", encoding="utf-8") as stream:
                stream.write('renpy.say(None, "Hello")\n')
            matched, missed = patcher.process_file(
                path,
                [("script.rpy", '"Hello"', '"你好"')],
                dry_run=False,
            )
            self.assertEqual((matched, missed), (1, 0))
            with open(path, encoding="utf-8") as stream:
                self.assertIn('"你好"', stream.read())
            with open(path + ".bak", encoding="utf-8") as stream:
                self.assertIn('"Hello"', stream.read())


class TestMissingTagFixer(unittest.TestCase):
    @staticmethod
    def _load_fixer():
        import importlib.util

        path = os.path.join(_TRANSLATE, "fix_missing_tags.py")
        spec = importlib.util.spec_from_file_location("fix_missing_tags", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_arbitrary_speaker_is_parsed_and_fixed(self):
        fixer = self._load_fixer()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test.rpy")
            content = '    # mmc "{i}really{/i} important"\n    mmc "真的重要"\n'
            with open(path, "w", encoding="utf-8") as stream:
                stream.write(content)
            with open(path, encoding="utf-8") as stream:
                lines = stream.readlines()
            issues = fixer.extract_tag_issues(lines, path, "test.rpy")
            self.assertEqual(len(issues), 1)
            category, new_cn, _confidence = fixer.classify_and_fix(issues[0])
            self.assertEqual(category, "D_i_mapped")
            self.assertEqual(new_cn, "{i}真的{/i}重要")
            fixes, manual = fixer.apply_fixes(issues, tmp, dry_run=False)
            self.assertEqual(len(fixes), 1)
            self.assertEqual(manual, [])
            with open(path, encoding="utf-8") as stream:
                self.assertIn('mmc "{i}真的{/i}重要"', stream.read())
            self.assertTrue(os.path.isfile(path + ".bak"))


class TestImprovedScanningAndIntegrity(unittest.TestCase):
    def test_scan_arbitrary_speaker_name(self):
        content = 'translate schinese block:\n    # mmc "Hello"\n    mmc ""\n'
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test.rpy")
            with open(path, "w", encoding="utf-8") as stream:
                stream.write(content)
            items = check_untranslated.scan_file(path, strict=True)
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["type"], "cd")
            self.assertEqual(items[0]["char"], "mmc")

    def test_duplicate_variable_count_is_checked(self):
        errors = integrity.check_pair(
            "[name] and [name]", "你好 [name]", 1, "test.rpy"
        )
        self.assertIn("LOST_VAR", [error["type"] for error in errors])

    def test_repeated_tag_count_is_checked(self):
        errors = integrity.check_pair(
            "{b}one{/b} {b}two{/b}", "{b}中文{/b}", 1, "test.rpy"
        )
        self.assertIn("LOST_TAG", [error["type"] for error in errors])

    def test_changed_tag_parameter_is_reported(self):
        errors = integrity.check_pair(
            "{color=#fff}text{/color}", "{color=#000}文本{/color}", 1, "test.rpy"
        )
        self.assertIn("EXTRA_TAG", [error["type"] for error in errors])

    def test_escaped_brackets_are_not_variables(self):
        errors = integrity.check_pair("[[name]] and {{literal}}", "[[名字]] and {{字面}}", 1, "x.rpy")
        self.assertEqual(errors, [])

    def test_mismatched_tag_nesting(self):
        errors = integrity.check_pair(
            "{b}bold{/b}", "{b}{i}粗体{/b}{/i}", 1, "x.rpy"
        )
        self.assertIn("TAG_MISMATCH", [error["type"] for error in errors])

    def test_standard_and_custom_paired_tags(self):
        cases = [
            ("{font=foo.ttf}文字{/font}", "{font=foo.ttf}文本{/font}"),
            ("{cps=2}...{/cps}", "{cps=2}……{/cps}"),
            ("{glitch}text{/glitch}", "{glitch}文本{/glitch}"),
        ]
        for original, translated in cases:
            with self.subTest(original=original):
                self.assertEqual(integrity.check_pair(original, translated, 1, "x.rpy"), [])
                self.assertEqual(
                    autotranslate.validate_translation(original, translated), []
                )

    def test_check_file_arbitrary_speaker_and_missing_target(self):
        content = (
            'translate schinese one:\n'
            '    # mmc "Hello [name!t]"\n'
            '    mmc "你好"\n'
            '\n'
            'translate schinese two:\n'
            '    # e "Missing target"\n'
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test.rpy")
            with open(path, "w", encoding="utf-8") as stream:
                stream.write(content)
            types = [error["type"] for error in integrity.check_file(path, "test.rpy")]
            self.assertIn("LOST_VAR", types)
            self.assertIn("COUNT_MISMATCH", types)

    def test_speaker_mismatch(self):
        content = '    # e "Hello"\n    c_mc "你好"\n'
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test.rpy")
            with open(path, "w", encoding="utf-8") as stream:
                stream.write(content)
            types = [error["type"] for error in integrity.check_file(path, "test.rpy")]
            self.assertIn("SPEAKER_MISMATCH", types)


class TestProtectionAndJsonApply(unittest.TestCase):
    def test_escape_tokens_round_trip(self):
        original = r"C:\games\file [[name]] {{literal}}"
        protected, mapping = autotranslate.protect_rpy_tags(original)
        self.assertNotIn("[[name]]", protected)
        self.assertNotIn("{{literal}}", protected)
        self.assertEqual(autotranslate.restore_rpy_tags(protected, mapping), original)
        self.assertEqual(autotranslate.validate_translation(original, original), [])

    def test_complex_renpy_interpolation_round_trip(self):
        original = "值 [player.names[0]] / [score / max_score:.1%] / [mood!t]"
        protected, mapping = autotranslate.protect_rpy_tags(original)
        self.assertNotIn("[player.names[0]]", protected)
        self.assertNotIn("[score / max_score:.1%]", protected)
        self.assertNotIn("[mood!t]", protected)
        self.assertEqual(autotranslate.restore_rpy_tags(protected, mapping), original)
        self.assertEqual(autotranslate.validate_translation(original, original), [])

    def test_complex_interpolation_loss_is_detected(self):
        errors = integrity.check_pair(
            "Name [player.names[0]]", "名字", 1, "test.rpy"
        )
        self.assertIn("LOST_VAR", [error["type"] for error in errors])

    def test_bracket_in_tag_parameter_is_not_interpolation(self):
        original = "{a=[url]}documentation{/a}"
        self.assertEqual(integrity.check_pair(original, original, 1, "x.rpy"), [])
        protected, mapping = autotranslate.protect_rpy_tags(original)
        self.assertNotIn("[url]", protected)
        self.assertEqual(autotranslate.restore_rpy_tags(protected, mapping), original)

    def _write_fixture(self, tmp, target='    e "" with dissolve'):
        path = os.path.join(tmp, "test.rpy")
        with open(path, "w", encoding="utf-8") as stream:
            stream.write('    # e "Hello [name!t]"\n' + target + "\n")
        return path

    def test_json_apply_is_anchor_checked_and_atomic(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_fixture(tmp)
            json_path = os.path.join(tmp, "translations.json")
            with open(json_path, "w", encoding="utf-8") as stream:
                json.dump(
                    [{
                        "file": "test.rpy",
                        "line": 1,
                        "type": "cd",
                        "char": "e",
                        "orig": "Hello [name!t]",
                        "trans": "你好 [name!t]",
                    }],
                    stream,
                    ensure_ascii=False,
                )
            rc = autotranslate._apply_from_json(tmp, json_path)
            self.assertEqual(rc, 0)
            with open(os.path.join(tmp, "test.rpy"), encoding="utf-8") as stream:
                updated = stream.read()
            self.assertIn('e "你好 [name!t]" with dissolve', updated)
            self.assertTrue(os.path.isfile(os.path.join(tmp, "test.rpy.bak")))

    def test_json_apply_preserves_crlf(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_fixture(tmp)
            with open(path, "rb+") as stream:
                data = stream.read().replace(b"\n", b"\r\n")
                stream.seek(0)
                stream.write(data)
                stream.truncate()
            json_path = os.path.join(tmp, "translations.json")
            with open(json_path, "w", encoding="utf-8") as stream:
                json.dump(
                    [{
                        "file": "test.rpy",
                        "line": 1,
                        "type": "cd",
                        "char": "e",
                        "orig": "Hello [name!t]",
                        "trans": "你好 [name!t]",
                    }],
                    stream,
                    ensure_ascii=False,
                )
            self.assertEqual(autotranslate._apply_from_json(tmp, json_path), 0)
            with open(path, "rb") as stream:
                data = stream.read()
            self.assertIn(b"\r\n", data)
            self.assertEqual(data.replace(b"\r\n", b"").find(b"\n"), -1)

    def test_json_apply_does_not_overwrite_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_fixture(tmp, '    e "Old translation" with dissolve')
            json_path = os.path.join(tmp, "translations.json")
            with open(json_path, "w", encoding="utf-8") as stream:
                json.dump(
                    [{
                        "file": "test.rpy",
                        "line": 1,
                        "type": "cd",
                        "char": "e",
                        "orig": "Hello [name!t]",
                        "trans": "你好 [name!t]",
                    }],
                    stream,
                    ensure_ascii=False,
                )
            rc = autotranslate._apply_from_json(tmp, json_path)
            self.assertEqual(rc, 1)
            with open(os.path.join(tmp, "test.rpy"), encoding="utf-8") as stream:
                self.assertIn("Old translation", stream.read())

            rc = autotranslate._apply_from_json(tmp, json_path, overwrite=True)
            self.assertEqual(rc, 0)
            with open(os.path.join(tmp, "test.rpy"), encoding="utf-8") as stream:
                self.assertIn("你好 [name!t]", stream.read())


class TestAtomicWrite(unittest.TestCase):
    def test_backup_is_created_once_and_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "script.rpy")
            with open(path, "w", encoding="utf-8") as stream:
                stream.write("original\n")
            atomic_write_text(path, "first\n", backup=True)
            self.assertEqual(autotranslate.atomic_write_text(path, "second\n", backup=True), None)
            with open(path, encoding="utf-8") as stream:
                self.assertEqual(stream.read(), "second\n")
            with open(path + ".bak", encoding="utf-8") as stream:
                self.assertEqual(stream.read(), "original\n")

    def test_crlf_input_is_not_doubled(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "script.rpy")
            with open(path, "wb") as stream:
                stream.write(b"one\r\ntwo\r\n")
            atomic_write_text(
                path,
                "one\r\ntwo\r\n",
                backup=False,
                newline="\r\n",
            )
            with open(path, "rb") as stream:
                data = stream.read()
            self.assertEqual(data, b"one\r\ntwo\r\n")
            self.assertNotIn(b"\r\r\n", data)

    def test_invalid_backup_path_blocks_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "script.rpy")
            with open(path, "w", encoding="utf-8") as stream:
                stream.write("original\n")
            os.mkdir(path + ".bak")
            with self.assertRaises(OSError):
                atomic_write_text(path, "must-not-write\n", backup=True)
            with open(path, encoding="utf-8") as stream:
                self.assertEqual(stream.read(), "original\n")

    def test_backup_failure_blocks_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "script.rpy")
            with open(path, "w", encoding="utf-8") as stream:
                stream.write("original\n")
            with mock.patch("backup.shutil.copy2", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    create_bak(path)
                with self.assertRaises(OSError):
                    atomic_write_text(path, "must-not-write\n", backup=True)
            with open(path, encoding="utf-8") as stream:
                self.assertEqual(stream.read(), "original\n")


class TestUnifiedCli(unittest.TestCase):
    @staticmethod
    def _load_cli():
        import importlib.util

        path = os.path.join(_TOOLS, "renpy-tools-cli.py")
        spec = importlib.util.spec_from_file_location("renpy_tools_cli", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_child_arguments_are_forwarded_verbatim(self):
        cli = self._load_cli()
        with mock.patch.object(cli, "run_script", return_value=7) as runner:
            rc = cli.main(["integrity", "MyGame", "-l", "schinese"])
        self.assertEqual(rc, 7)
        runner.assert_called_once_with("integrity", ["MyGame", "-l", "schinese"])

    def test_all_returns_failure(self):
        cli = self._load_cli()
        # 批次脚本数随 CHECK_GROUP / CRASH_GROUP 变化，按实际数量构造返回码，
        # 避免新增检查器后这里的固定列表长度失配（曾因加入 charname 而报 StopIteration）。
        total = len(cli.CHECK_GROUP) + len(cli.CRASH_GROUP)
        codes = [0] * total
        codes[1] = 1
        with mock.patch.object(cli, "run_script", side_effect=codes):
            rc = cli.main(["all", "MyGame", "-l", "schinese"])
        self.assertEqual(rc, 1)


# ============================================================================
# unify_name_translations 测试 (parse_blocks + _replace_name_in_dialogue)
# ============================================================================


class TestParseBlocks(unittest.TestCase):
    def test_dialogue_block(self):
        """c_xxx 对话块"""
        lines = [
            '# c_mc "Hello world"',
            'c_mc "你好世界"',
        ]
        # 需要动态导入，因为模块名含中文
        unify = _import_unify()
        blocks = unify.parse_blocks(lines)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["en"], 'c_mc "Hello world"')
        self.assertEqual(blocks[0]["cn"], "你好世界")

    def test_narration_block(self):
        """纯叙述块"""
        lines = [
            '# "It was a dark night."',
            '"那是一个黑暗的夜晚。"',
        ]
        unify = _import_unify()
        blocks = unify.parse_blocks(lines)
        self.assertEqual(len(blocks), 1)
        self.assertIn("dark night", blocks[0]["en"])
        self.assertEqual(blocks[0]["cn"], "那是一个黑暗的夜晚。")

    def test_old_new_block(self):
        """old/new strings 块"""
        lines = [
            '    old "Save Game"',
            '    new "保存游戏"',
        ]
        unify = _import_unify()
        blocks = unify.parse_blocks(lines)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["en"], "Save Game")
        self.assertEqual(blocks[0]["cn"], "保存游戏")

    def test_multiple_blocks(self):
        lines = [
            '# c_a "Hello"',
            'c_a "你好"',
            '# c_b "Goodbye"',
            'c_b "再见"',
        ]
        unify = _import_unify()
        blocks = unify.parse_blocks(lines)
        self.assertEqual(len(blocks), 2)

    def test_empty_lines_between(self):
        """注释和译文之间有空行"""
        lines = [
            '# "Hello"',
            "",
            '"你好"',
        ]
        unify = _import_unify()
        blocks = unify.parse_blocks(lines)
        self.assertEqual(len(blocks), 1)

    def test_escaped_quote_is_not_truncated(self):
        lines = [
            r'    # c_mc "Tomori said \"hello\""',
            r'    c_mc "秀说\"你好\""',
        ]
        unify = _import_unify()
        blocks = unify.parse_blocks(lines)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["en"], r'c_mc "Tomori said \"hello\""')
        self.assertEqual(blocks[0]["cn"], '秀说"你好"')
        new_line, count = unify._replace_name_in_dialogue(
            lines[1], "秀说", "灯里"
        )
        self.assertEqual(count, 1)
        self.assertEqual(new_line, r'    c_mc "灯里\"你好\""')

    def test_translate_header_skip(self):
        """跳过 translate schinese xxx: 声明行"""
        lines = [
            "translate schinese block_1:",
            "",
            '    # "Hello"',
            '    "你好"',
        ]
        unify = _import_unify()
        blocks = unify.parse_blocks(lines)
        self.assertEqual(len(blocks), 1)

    def test_skip_interleaved_comments(self):
        """注释行后紧跟续注释行，不应把续注释当翻译行"""
        lines = [
            "# game/script.rpy:42",
            '    # e "Hello, [name]!"',
            '    e "你好，[name]！"',
        ]
        unify = _import_unify()
        blocks = unify.parse_blocks(lines)
        self.assertEqual(len(blocks), 1)
        # 翻译内容应来自 e "..." 行，而非注释行
        self.assertEqual(blocks[0]["cn"], "你好，[name]！")


class TestReplaceNameInDialogue(unittest.TestCase):
    def test_replace_in_speaker_line(self):
        """speaker 简写对话行替换（e "..." / m "..." 等格式）"""
        unify = _import_unify()
        line = '    e "修，你好吗？"'
        new_line, count = unify._replace_name_in_dialogue(line, "修", "秀")
        self.assertEqual(count, 1)
        self.assertIn("秀", new_line)
        self.assertNotIn("修", new_line)
        # 保留 speaker 前缀
        self.assertTrue(new_line.startswith('    e "'))

    def test_replace_in_speaker_line_cjk_boundary(self):
        """speaker 简写行的 CJK 边界保护"""
        unify = _import_unify()
        line = '    m "去休息一下"'
        new_line, count = unify._replace_name_in_dialogue(line, "修", "秀")
        self.assertEqual(count, 0)
        self.assertEqual(new_line, line)

    def test_replace_in_c_xxx_line(self):
        """c_xxx 对话行替换（名字后跟标点，不触发 CJK 边界保护）"""
        unify = _import_unify()
        line = '    c_mc "修，你好"'
        new_line, count = unify._replace_name_in_dialogue(line, "修", "秀")
        self.assertEqual(count, 1)
        self.assertIn("秀", new_line)
        self.assertNotIn("修", new_line)

    def test_replace_in_narration_line(self):
        """叙述行替换（名字后跟标点）"""
        unify = _import_unify()
        line = '    "修走了过来"'
        # "修" 后跟 "走"(CJK)，边界保护触发 -> 不替换
        new_line, count = unify._replace_name_in_dialogue(line, "修", "秀")
        self.assertEqual(count, 0)
        # 改用名字后跟标点的场景
        line2 = '    "修，别走"'
        new_line2, count2 = unify._replace_name_in_dialogue(line2, "修", "秀")
        self.assertEqual(count2, 1)
        self.assertIn("秀", new_line2)

    def test_replace_in_new_line(self):
        """new 译文行替换（名字后跟标点）"""
        unify = _import_unify()
        line = '    new "修的房间"'
        # "修" 后跟 "的"(CJK)，边界保护触发 -> 不替换
        new_line, count = unify._replace_name_in_dialogue(line, "修", "秀")
        self.assertEqual(count, 0)
        # 改用名字后跟标点的场景
        line2 = '    new "修·笔记"'
        new_line2, count2 = unify._replace_name_in_dialogue(line2, "修", "秀")
        self.assertEqual(count2, 1)

    def test_cjk_boundary_protection(self):
        """CJK 边界保护: 修 前后是 CJK 时不替换"""
        unify = _import_unify()
        # "休息" 中 "修" 前无字后有 CJK -> 不替换
        line = '    c_mc "去休息一下"'
        new_line, count = unify._replace_name_in_dialogue(line, "修", "秀")
        self.assertEqual(count, 0)
        self.assertEqual(new_line, line)

    def test_no_match(self):
        """无匹配返回原行"""
        unify = _import_unify()
        line = '    c_mc "你好"'
        new_line, count = unify._replace_name_in_dialogue(line, "修", "秀")
        self.assertEqual(count, 0)
        self.assertEqual(new_line, line)

    def test_non_dialogue_line(self):
        """非对话行不替换"""
        unify = _import_unify()
        line = "translate schinese block_1:"
        new_line, count = unify._replace_name_in_dialogue(line, "修", "秀")
        self.assertEqual(count, 0)
        self.assertEqual(new_line, line)

    def test_first_match_only(self):
        """只替换首次出现（名字后跟标点避免 CJK 边界保护）"""
        unify = _import_unify()
        line = '    c_mc "修修，你好"'
        new_line, count = unify._replace_name_in_dialogue(line, "修修", "秀")
        self.assertEqual(count, 1)

    def test_long_name_no_boundary_check(self):
        """长名 (>2字) 不做 CJK 边界检查"""
        unify = _import_unify()
        line = '    "伊卡里来了"'
        new_line, count = unify._replace_name_in_dialogue(line, "伊卡里", "伊卡莉")
        self.assertEqual(count, 1)
        self.assertIn("伊卡莉", new_line)


# ============================================================================
# TestParseBlocksSourcePath — 源文件路径跳过
# ============================================================================


class TestParseBlocksSourcePath(unittest.TestCase):
    """parse_blocks 必须跳过 # game/xxx.rpy:23 源路径注释行"""

    def test_skip_source_path(self):
        """源路径注释不被当作英文原文"""
        lines = [
            "# game/events/tomori.rpy:23",
            "translate schinese block_1:",
            '    # "And apparently Tomori works here now?"',
            '    "而且显然灯里现在在这里工作？"',
        ]
        unify = _import_unify()
        blocks = unify.parse_blocks(lines)
        self.assertEqual(len(blocks), 1)
        self.assertIn("apparently Tomori", blocks[0]["en"])
        self.assertNotIn("game/events", blocks[0]["en"])

    def test_skip_multiple_source_paths(self):
        """连续多个源路径注释都被跳过"""
        lines = [
            "# game/events/nami.rpy:10",
            "translate schinese block_a:",
            '    # "Nami is here."',
            '    "奈美在这里。"',
            "",
            "# game/events/nami.rpy:11",
            "translate schinese block_b:",
            '    # "Nami left."',
            '    "奈美离开了。"',
        ]
        unify = _import_unify()
        blocks = unify.parse_blocks(lines)
        self.assertEqual(len(blocks), 2)
        self.assertIn("Nami is here", blocks[0]["en"])
        self.assertIn("Nami left", blocks[1]["en"])


# ============================================================================
# TestIsNameReference — 角色名引用检测
# ============================================================================


class TestIsNameReference(unittest.TestCase):
    """is_name_reference 的边界情况"""

    def test_match_dialogue(self):
        """英文对话行中的角色名"""
        unify = _import_unify()
        self.assertTrue(
            unify.is_name_reference("And apparently Tomori works here", "Tomori")
        )
        self.assertTrue(unify.is_name_reference("Nami enters the room.", "Nami"))

    def test_no_match_source_path(self):
        """源文件路径中的角色名不匹配"""
        unify = _import_unify()
        self.assertFalse(unify.is_name_reference("game/events/tomori.rpy:23", "Tomori"))
        self.assertFalse(unify.is_name_reference("game/events/nami.rpy:45", "Nami"))

    def test_no_match_speaker_prefix(self):
        """c_tomori 不是 Tomori 的引用（\b 边界保护）"""
        unify = _import_unify()
        self.assertFalse(unify.is_name_reference('c_tomori "Hello"', "Tomori"))
        self.assertFalse(unify.is_name_reference('c_nami "Welcome"', "Nami"))

    def test_ren_not_renpy(self):
        """Ren 不匹配 Ren'Py"""
        unify = _import_unify()
        self.assertFalse(unify.is_name_reference("Ren'Py", "Ren"))

    def test_ren_possessive(self):
        """Ren's（所有格）匹配"""
        unify = _import_unify()
        self.assertTrue(unify.is_name_reference("Ren's room", "Ren"))

    def test_empty_line(self):
        unify = _import_unify()
        self.assertFalse(unify.is_name_reference("", "Tomori"))
        self.assertFalse(unify.is_name_reference(None, "Tomori"))

    def test_case_insensitive(self):
        unify = _import_unify()
        self.assertTrue(unify.is_name_reference("tomori is here", "Tomori"))
        self.assertTrue(unify.is_name_reference("TOMORI!", "Tomori"))


# ============================================================================
# TestStep1Collect — Step 1 收集流程
# ============================================================================


class TestStep1Collect(unittest.TestCase):
    """step1_collect 端到端测试"""

    def test_collect_name_refs(self):
        """收集应记录所有角色名引用，不做分类"""
        import tempfile

        glossary = {"Tomori": "灯里", "Nami": "奈美"}
        lines = [
            "# game/events/test.rpy:1",
            "translate schinese block_1:",
            '    # "Tomori is here."',
            '    "灯里在这里。"',
            "",
            "# game/events/test.rpy:2",
            "translate schinese block_2:",
            '    # "Nami said hello to Tomori."',
            '    "奈美对Tomori说了你好。"',
            "",
            "# game/events/test.rpy:3",
            "translate schinese block_3:",
            '    # "Tomori smiled."',
            '    "她笑了。"',
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            tl_dir = os.path.join(tmpdir, "tl", "schinese")
            os.makedirs(tl_dir)
            with open(os.path.join(tl_dir, "test.rpy"), "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            out_path = os.path.join(tmpdir, "collection.json")

            unify = _import_unify()
            result = unify.step1_collect(glossary, tl_dir, out_path)

            # 收集到 4 条角色名引用（Tomori ×3 + Nami ×1）
            self.assertEqual(result["total_name_refs"], 4)
            self.assertEqual(result["total_blocks"], 3)

            # 验证引用数据结构（不做分类判断）
            tomori_refs = [r for r in result["refs"] if r["en_name"] == "Tomori"]
            self.assertEqual(len(tomori_refs), 3)
            for ref in tomori_refs:
                self.assertNotIn("status", ref)  # 收集阶段不分类
                self.assertEqual(ref["standard"], "灯里")

            nami_refs = [r for r in result["refs"] if r["en_name"] == "Nami"]
            self.assertEqual(len(nami_refs), 1)

            # 术语表也应保存
            self.assertEqual(result["glossary"], glossary)


class TestStep2Classify(unittest.TestCase):
    """step2_classify 端到端测试"""

    def test_variant_grouping(self):
        """分类应正确发现变体并按角色名归组"""
        import tempfile

        glossary = {"Tomori": "灯里", "Nami": "奈美"}
        lines = [
            "# game/events/test.rpy:1",
            "translate schinese block_1:",
            '    # "Tomori is here."',
            '    "灯里在这里。"',  # ok
            "",
            "# game/events/test.rpy:2",
            "translate schinese block_2:",
            '    # "Nami said hello to Tomori."',
            '    "奈美对Tomori说了你好。"',  # Tomori 英文变体
            "",
            "# game/events/test.rpy:3",
            "translate schinese block_3:",
            '    # "Tomori smiled."',
            '    "托莫里笑了。"',  # Tomori 中文变体
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            tl_dir = os.path.join(tmpdir, "tl", "schinese")
            os.makedirs(tl_dir)
            with open(os.path.join(tl_dir, "test.rpy"), "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            collection_path = os.path.join(tmpdir, "collection.json")
            classification_path = os.path.join(tmpdir, "classification.json")

            unify = _import_unify()
            # Step 1: 收集
            unify.step1_collect(glossary, tl_dir, collection_path)
            # Step 2: 分类
            result = unify.step2_classify(collection_path, classification_path)

            names = result["names"]

            # v6 严格模式：Tomori 3 refs -> 1 ok + 1 英文变体 + 1 omitted。
            # 中文“托莫里”不做高误报滑窗猜测，应留给人工/LLM 审核。
            t = names["Tomori"]
            self.assertEqual(t["ok_count"], 1)
            self.assertIn("Tomori", t["variants"])
            self.assertEqual(t["variants"]["Tomori"]["count"], 1)
            self.assertNotIn("托莫里", t["variants"])
            self.assertEqual(t["omitted_count"], 1)
            self.assertEqual(t["omitted_refs"][0]["cn_text"], "托莫里笑了。")

            # Nami: 1 ref -> 1 ok
            n = names["Nami"]
            self.assertEqual(n["ok_count"], 1)
            self.assertEqual(len(n["variants"]), 0)

            # 汇总
            self.assertEqual(result["totals"]["ok"], 2)
            self.assertEqual(result["totals"]["variant_occurrences"], 1)
            self.assertEqual(result["totals"]["variant_kinds"], 1)
            self.assertEqual(result["totals"]["omitted"], 1)

    def test_english_variant(self):
        """译文保留英文名时应识别为变体"""
        import tempfile

        glossary = {"Tomori": "灯里"}
        lines = [
            '# "Tomori is here."',
            '"Tomori在这里。"',
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            tl_dir = os.path.join(tmpdir, "tl", "schinese")
            os.makedirs(tl_dir)
            with open(os.path.join(tl_dir, "test.rpy"), "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            collection_path = os.path.join(tmpdir, "collection.json")
            classification_path = os.path.join(tmpdir, "classification.json")

            unify = _import_unify()
            unify.step1_collect(glossary, tl_dir, collection_path)
            result = unify.step2_classify(collection_path, classification_path)

            t = result["names"]["Tomori"]
            self.assertEqual(t["ok_count"], 0)
            self.assertIn("Tomori", t["variants"])
            self.assertEqual(t["variants"]["Tomori"]["count"], 1)
            occ = t["variants"]["Tomori"]["occurrences"][0]
            self.assertIn("file", occ)
            self.assertIn("line", occ)
            self.assertIn("cn_text", occ)


# ============================================================================
# 辅助函数# 辅助函数
# ============================================================================


def _temp_rpy(content):
    """已废弃：使用 TestScanFile._make_temp_rpy 代替。"""
    raise NotImplementedError("Use TestScanFile._make_temp_rpy instead")


def _import_unify():
    """动态导入 unify_name_translations 模块。"""
    import importlib

    spec = importlib.util.spec_from_file_location(
        "unify_name_translations",
        os.path.join(_UNIFY, "unify_name_translations.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _import_autotranslate():
    """动态导入 autotranslate 模块。"""
    import importlib

    spec = importlib.util.spec_from_file_location(
        "autotranslate",
        os.path.join(_TRANSLATE, "autotranslate.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestApplyGlossary(unittest.TestCase):
    """术语表预替换测试"""

    def setUp(self):
        self.at = _import_autotranslate()

    def test_basic_replace(self):
        """英文人名应替换为中文译名"""
        glossary = {"Tomori": "灯里", "Nami": "奈美"}
        text = 'Tomori walked to Nami.'
        result = self.at.apply_glossary(text, glossary)
        self.assertEqual(result, '灯里 walked to 奈美.')

    def test_no_substr_match(self):
        """单词边界保护：不误伤子串"""
        glossary = {"Li": "莉", "Ren": "莲"}
        # Li 不应匹配 Like 中的 Li
        text = "I like this, Ren said."
        result = self.at.apply_glossary(text, glossary)
        self.assertNotIn('莉', result)  # Like 不被误伤
        self.assertIn('莲', result)   # Ren 被替换

    def test_case_sensitive(self):
        """大小写敏感：只替换精确匹配"""
        glossary = {"Tomori": "灯里"}
        text = "Tomori is here. tomori is not."
        result = self.at.apply_glossary(text, glossary)
        self.assertEqual(result, "灯里 is here. tomori is not.")

    def test_multiple_occurrences(self):
        """同一人名多次出现都替换"""
        glossary = {"Yui": "优衣"}
        text = "Yui said Yui is tired."
        result = self.at.apply_glossary(text, glossary)
        self.assertEqual(result, "优衣 said 优衣 is tired.")

    def test_after_tag_protect(self):
        """在标签保护之后替换，不误伤标签占位词"""
        glossary = {"Tomori": "灯里"}
        text = '{{P1}}Tomori{{P2}} is here.'
        result = self.at.apply_glossary(text, glossary)
        self.assertEqual(result, '{{P1}}灯里{{P2}} is here.')

    def test_possessive(self):
        """所有格 's 不影响替换"""
        glossary = {"Tomori": "灯里"}
        text = "Tomori's bag is here."
        result = self.at.apply_glossary(text, glossary)
        self.assertEqual(result, "灯里's bag is here.")

    def test_empty_glossary(self):
        """空术语表不改文本"""
        text = "Tomori is here."
        result = self.at.apply_glossary(text, {})
        self.assertEqual(result, text)

    def test_load_glossary_dict_format(self):
        """加载 {en: zh} 格式术语表"""
        import tempfile
        glossary = {"Tomori": "灯里", "Nami": "奈美"}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(glossary, f, ensure_ascii=False)
            path = f.name
        result = self.at.load_glossary(path)
        self.assertEqual(result, glossary)
        os.unlink(path)

    def test_load_glossary_list_format(self):
        """加载 [{en, zh}] 列表格式术语表"""
        import tempfile
        glossary = [{"en": "Tomori", "zh": "灯里"}, {"en": "Nami", "zh": "奈美"}]
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(glossary, f, ensure_ascii=False)
            path = f.name
        result = self.at.load_glossary(path)
        self.assertEqual(result, {"Tomori": "灯里", "Nami": "奈美"})
        os.unlink(path)


# ============================================================================
# 入口
# ============================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
