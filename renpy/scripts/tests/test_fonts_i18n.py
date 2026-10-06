# -*- coding: utf-8 -*-
"""check_fonts / check_i18n / shared/rpa_index 契约回归。

回归背景（2026-10-06，AfterDark 0.26 实测）：
- check_assets 的音频/字体检查不做 basename 回退，RPA 打包游戏误报 1566 条缺失；
- tl_check 只扫 tl 顶层，子目录（Girls Scripts/ 等）全部漏检；
- {chaos}/{bt} 这类项目自定义动态标签被当成"未知标签"误报崩溃级；
- 发行版把字体放 renpy/common（DejaVuSans）和 .rpa 里，磁盘-only 检查必误报。

本文件用临时项目 fixture 钉住 check_fonts / check_i18n 的判定边界，
以及 rpa_index 的名字提取（RPA-3.0 XOR / 只取名字不碰数据）。
"""

import importlib.util
import io
import os
import pickle
import shutil
import sys
import tempfile
import unittest
import zlib
from contextlib import redirect_stdout
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_TOOLS = os.path.dirname(_HERE)
_SDK = os.path.join(_TOOLS, "sdk")
_SHARED = os.path.join(_TOOLS, "shared")
if _SHARED not in sys.path:
    sys.path.insert(0, _SHARED)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _ToolCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fonts = _load("_check_fonts", os.path.join(_SDK, "check_fonts.py"))
        cls.i18n = _load("_check_i18n", os.path.join(_SDK, "check_i18n.py"))

    def _run_tool(self, mod, path):
        """跑工具 main()，返回 (exit_code, stdout)。argparse 吃 sys.argv。"""
        old_argv = sys.argv
        sys.argv = ["prog", str(path)]
        buf = io.StringIO()
        try:
            with redirect_stdout(buf):
                rc = mod.main()
        finally:
            sys.argv = old_argv
        return rc, buf.getvalue()


class TestCheckFonts(_ToolCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="fonts_check_"))
        self.game = self.root / "game"
        (self.game / "fonts").mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _script(self, line):
        (self.game / "script.rpy").write_text(line + "\n", encoding="utf-8")

    def test_missing_font_ref_fails(self):
        self._script('define gui.text_font = "fonts/ghost.ttf"')
        rc, out = self._run_tool(self.fonts, self.root)
        self.assertEqual(rc, 1)
        self.assertIn("ghost.ttf", out)

    def test_present_font_passes(self):
        (self.game / "fonts" / "real.ttf").write_bytes(b"\0")
        self._script('define gui.text_font = "fonts/real.ttf"')
        rc, out = self._run_tool(self.fonts, self.root)
        self.assertEqual(rc, 0)
        self.assertIn("所有引用的字体文件都存在", out)

    def test_basename_fallback(self):
        """引用带目录前缀、磁盘上只有 basename → 不误报。"""
        (self.game / "fonts" / "real.ttf").write_bytes(b"\0")
        self._script('define gui.text_font = "fonts/sub/real.ttf"')
        rc, out = self._run_tool(self.fonts, self.root)
        self.assertEqual(rc, 0)

    def test_engine_common_font_counts(self):
        """renpy/common/DejaVuSans.ttf 是引擎自带，加载路径可达 → 不报缺失。"""
        (self.root / "renpy" / "common").mkdir(parents=True)
        (self.root / "renpy" / "common" / "DejaVuSans.ttf").write_bytes(b"\0")
        self._script('define gui.text_font = "DejaVuSans.ttf"')
        rc, _ = self._run_tool(self.fonts, self.root)
        self.assertEqual(rc, 0)

    def test_cjk_lang_without_font_warns(self):
        """有 schinese 翻译但全项目无 CJK 字体 → 显示级问题，退出码 1。"""
        tl = self.game / "tl" / "schinese"
        tl.mkdir(parents=True)
        (tl / "script_translated.rpy").write_text(
            'translate schinese strings:\n    old "Start"\n    new "开始"\n',
            encoding="utf-8")
        (self.game / "fonts" / "latin.ttf").write_bytes(b"\0")
        self._script('define gui.text_font = "fonts/latin.ttf"')
        rc, out = self._run_tool(self.fonts, self.root)
        self.assertEqual(rc, 1)
        self.assertIn("未发现任何 CJK 字体引用", out)

    def test_cjk_lang_with_tl_override_passes(self):
        """语言目录里做了字体覆盖（fonts/*.otf 引用）→ 接入成立。"""
        tl = self.game / "tl" / "schinese"
        tl.mkdir(parents=True)
        (self.game / "fonts" / "NotoSansSC-Regular.otf").write_bytes(b"\0")
        (tl / "style.rpy").write_text(
            'translate schinese style:\n    font "fonts/NotoSansSC-Regular.otf"\n',
            encoding="utf-8")
        rc, out = self._run_tool(self.fonts, self.root)
        self.assertEqual(rc, 0)
        self.assertIn("已接入 CJK 字体", out)

    def test_junk_none_lang_dir_flagged(self):
        """tl/None 垃圾目录（工具残留）要点名，且不进语言接入判定。"""
        (self.game / "tl" / "None").mkdir(parents=True)
        rc, out = self._run_tool(self.fonts, self.root)
        self.assertIn("垃圾语言目录", out)
        self.assertNotIn("None         非CJK语言", out)

    def test_runtime_font_machinery_warned(self):
        """屏幕层 `font persistent.*` 运行时求值会压掉 translate 级覆盖 → 必须预警。

        AfterDark 0.26 实测：对白走 font persistent.pref_text_font，
        汉化字体补丁出现「按钮正常、对白异常」。"""
        (self.game / "fonts" / "latin.ttf").write_bytes(b"\0")
        (self.game / "screens.rpy").write_text(
            'text what id "what" font persistent.pref_text_font\n',
            encoding="utf-8")
        rc, out = self._run_tool(self.fonts, self.root)
        self.assertEqual(rc, 1)
        self.assertIn("运行时字体", out)

    def test_language_aware_runtime_font_not_flagged(self):
        """已做语言感知适配（font 表达式含 _preferences.language）→ 不再预警。"""
        (self.game / "fonts" / "latin.ttf").write_bytes(b"\0")
        (self.game / "screens.rpy").write_text(
            'text what font ("a.ttf" if _preferences.language == "schinese" else persistent.pref_text_font)\n',
            encoding="utf-8")
        rc, out = self._run_tool(self.fonts, self.root)
        self.assertNotIn("检测到", out)


class TestCheckI18n(_ToolCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="i18n_check_"))
        self.game = self.root / "game"
        self.game.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _script(self, text):
        (self.game / "script.rpy").write_text(text, encoding="utf-8")

    def test_no_tl_dir_passes_with_hint(self):
        self._script("label start:\n    return\n")
        rc, out = self._run_tool(self.i18n, self.root)
        self.assertEqual(rc, 0)
        self.assertIn("未启用多语言", out)

    def test_wired_language_passes(self):
        tl = self.game / "tl" / "schinese"
        tl.mkdir(parents=True)
        (tl / "common.rpy").write_text(
            'translate schinese strings:\n    old "Are you sure?"\n    new "你确定？"\n',
            encoding="utf-8")
        self._script('textbutton "中文" action Language("schinese")')
        rc, out = self._run_tool(self.i18n, self.root)
        self.assertEqual(rc, 0)
        self.assertIn("有切换入口", out)

    def test_language_target_without_tl_dir_fails(self):
        """Language("japanese") 但没有 tl/japanese → 显示级问题。"""
        self._script('textbutton "日本語" action Language("japanese")')
        rc, out = self._run_tool(self.i18n, self.root)
        self.assertEqual(rc, 1)
        self.assertIn("没有对应 tl 目录", out)

    def test_tl_without_entry_point_fails(self):
        """有翻译、无按钮、无自定义切换 → 玩家切不过去（fix_lang_button 的对象）。"""
        tl = self.game / "tl" / "schinese"
        tl.mkdir(parents=True)
        (tl / "common.rpy").write_text(
            'translate schinese strings:\n    old "x"\n    new "x"\n', encoding="utf-8")
        rc, out = self._run_tool(self.i18n, self.root)
        self.assertEqual(rc, 1)
        self.assertIn("没有切换入口", out)

    def test_custom_switch_suppresses_entry_warning(self):
        """代码里自己改 _preferences.language 的项目不算"没有入口"。"""
        tl = self.game / "tl" / "schinese"
        tl.mkdir(parents=True)
        (tl / "common.rpy").write_text(
            'translate schinese strings:\n    old "x"\n    new "x"\n', encoding="utf-8")
        self._script('$renpy.change_language(_preferences.language or "schinese")')
        self._script('if _preferences.language == "schinese":\n    pass')
        rc, out = self._run_tool(self.i18n, self.root)
        self.assertEqual(rc, 0)
        self.assertIn("自定义切换", out)

    def test_default_language_without_tl_dir_fails(self):
        """config.language 指向不存在的语言 → 启动即回退，显示级问题。"""
        self._script('define config.language = "korean"')
        rc, out = self._run_tool(self.i18n, self.root)
        self.assertEqual(rc, 1)
        self.assertIn("没有 tl 目录", out)

    def test_missing_strings_block_is_hint_only(self):
        """无 strings 块只影响引擎自带界面文案，属提示级，不进退出码。"""
        tl = self.game / "tl" / "schinese"
        tl.mkdir(parents=True)
        (tl / "script.rpy").write_text(
            'translate schinese start_5a1b2c3d:\n\n    # e "Hi"\n    e "嗨"\n',
            encoding="utf-8")
        self._script('textbutton "中文" action Language("schinese")')
        rc, out = self._run_tool(self.i18n, self.root)
        self.assertEqual(rc, 0)
        self.assertIn("无 strings 块", out)

    def test_junk_none_lang_dir_flagged(self):
        (self.game / "tl" / "None").mkdir(parents=True)
        rc, out = self._run_tool(self.i18n, self.root)
        self.assertIn("垃圾语言目录", out)
        self.assertEqual(rc, 1)


class TestAllArgPassthrough(_ToolCase):
    """回归：统一 CLI 的 all 会把 -l/--language 原样转发给每个检查器
    （house 约定，见 check_crash_risks.py 同名参数），两个新工具必须
    接受该参数而不是 argparse 报错 rc=2 被门面归一成 1。
    2026-10-06 冒烟实测：LostInYou/FriendshipClub 的 all 中 fontcheck/
    langcheck 因此零输出退出。"""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="passthru_"))
        (self.root / "game").mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _run_tool(self, mod, extra):
        old_argv = sys.argv
        sys.argv = ["prog", str(self.root)] + extra
        buf = io.StringIO()
        try:
            with redirect_stdout(buf):
                rc = mod.main()
        finally:
            sys.argv = old_argv
        return rc, buf.getvalue()

    def test_check_fonts_accepts_lang_flag(self):
        rc, _ = self._run_tool(self.fonts, ["-l", "schinese"])
        self.assertEqual(rc, 0)

    def test_check_i18n_accepts_lang_flag(self):
        rc, _ = self._run_tool(self.i18n, ["-l", "schinese"])
        self.assertEqual(rc, 0)


class TestRpaIndex(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rpa_index_"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make_rpa(self, path, names, key=0x42424242):
        """只写索引不写数据：archive_names 只读名字，offset 不会被解引用。"""
        index = {n: [(0 ^ key, 1 ^ key)] for n in names}
        blob = zlib.compress(pickle.dumps(index))
        body_offset = 24  # 头行之后随便留一段
        header = ("RPA-3.0 %x %x\n" % (body_offset, key)).encode()
        data = header + b"\0" * (body_offset - len(header)) + blob
        Path(path).write_bytes(data)

    def test_rpa30_xor_names_extracted(self):
        from rpa_index import archive_names
        game = self.tmp / "game"
        game.mkdir()
        self._make_rpa(game / "archive.rpa", ["images/bg room.png", "audio/Music/Cafe.mp3"])
        names, errors = archive_names(game)
        self.assertEqual(errors, [])
        self.assertIn("images/bg room.png", names)
        self.assertIn("audio/music/cafe.mp3", names)  # 小写归一化

    def test_broken_archive_is_skipped_with_error(self):
        from rpa_index import archive_names
        game = self.tmp / "game"
        game.mkdir()
        (game / "bad.rpa").write_bytes(b"NOTRPA nothing here\n")
        names, errors = archive_names(game)
        self.assertEqual(names, set())
        self.assertEqual(len(errors), 1)
        self.assertIn("bad.rpa", errors[0])

    def test_names_by_ext_filter(self):
        from rpa_index import names_by_ext
        got = names_by_ext({"a.PNG", "b.mp3", "c/dejavusans.ttf"}, {".png", ".ttf"})
        self.assertEqual(got, {"a.png", "c/dejavusans.ttf"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
