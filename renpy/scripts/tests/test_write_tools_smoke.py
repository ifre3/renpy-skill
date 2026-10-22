#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""零覆盖写入类工具的冒烟契约（2026-10-11 补）。

背景：仓库审计发现三个**写盘**脚本零测试覆盖——
``names/make_glossary.py``（344 行）、``setup/setup_fonts.py``（315 行）、
``names/apply_glossary_body.py``（82 行），合计 741 行。对照之下
``urm_install.py``（486 行）有 29 个用例、``tag_repair.py``（965 行）有 20 个
——仓库自己证明了写工具该有测试。

本文件不追求行覆盖率，钉的是**冒烟契约**：

1. 给定最小合法输入，能跑完并产出预期产物（不静默空转）。
2. **不写脏数据**：不越出 -o 指定的路径、不改与本次无关的文件。
3. **不把源目录当输出目录**：这三个工具都吃目录，写错方向会污染用户项目。

运行::

    cd renpy/scripts/tests
    python -m unittest test_write_tools_smoke -v
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_TOOLS = os.path.dirname(_HERE)
_NAMES = os.path.join(_TOOLS, "names")
_SETUP = os.path.join(_TOOLS, "setup")
for _p in (_NAMES, _SETUP):
    if _p not in sys.path:
        sys.path.insert(0, _p)

PYTHON = sys.executable
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")

MINI_PROJECT = {
    "game/script.rpy": (
        'define e = Character("Eileen", who_font="DejaVuSans.ttf")\n'
        'label start:\n'
        '    e "Hello, [player]!"\n'
        '    "A narration."\n'
    ),
    "game/gui.rpy": 'define gui.text_font = "DejaVuSans.ttf"\n',
}
MINI_TL = {
    "game/tl/schinese/script.rpy": (
        'translate schinese start_1a2b3c4d:\n\n'
        '    # e "Hello, [player]!"\n'
        '    e "你好，[player]！"\n\n'
        '    # "A narration."\n'
        '    "一段旁白。"\n'
    ),
    # 名字框翻译：make_glossary 靠它取证人名译法；缺了会把人名报成「未翻译」
    # 并 rc=1（那是工具的正确行为，不是 bug）。
    "game/tl/schinese/strings.rpy": (
        'translate schinese strings:\n'
        '    old "Eileen"\n'
        '    new "艾琳"\n'
    ),
}


def _make_project(root, extra=None):
    for rel, text in MINI_PROJECT.items():
        p = Path(root) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    for rel, text in (extra or {}).items():
        p = Path(root) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return Path(root)


def _run(script, args, cwd=None):
    return subprocess.run(
        [PYTHON, script, *args], capture_output=True, text=True,
        encoding="utf-8", errors="replace", env=ENV, cwd=cwd, timeout=120)


class TestMakeGlossary(unittest.TestCase):
    """make_glossary：能从项目里取出 Character 人名，产物落在 -o。

    注意它需要 tl/<lang> 目录存在（取证的是 tl 侧的 strings 配对），
    没有时报「找不到 tl/schinese」并 rc=2 —— 这也是一条契约。
    """

    def test_produces_draft_json(self):
        with tempfile.TemporaryDirectory() as d:
            proj = _make_project(d, MINI_TL)
            out = Path(d) / "glossary.json"
            r = _run(os.path.join(_NAMES, "make_glossary.py"),
                     [str(proj), "-o", str(out), "--lang", "schinese"])
            self.assertEqual(r.returncode, 0,
                             f"make_glossary 失败:\n{r.stdout}\n{r.stderr}")
            self.assertTrue(out.is_file(), f"没产出草稿: {out}")
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            self.assertIsInstance(data, (list, dict),
                                  f"草稿结构不是 list/dict: {type(data)}")

    def test_missing_tl_dir_exits_nonzero(self):
        """没有 tl/<lang> 时要明确报错，不能静默产出空草稿。"""
        with tempfile.TemporaryDirectory() as d:
            proj = _make_project(d)  # 无 MINI_TL
            r = _run(os.path.join(_NAMES, "make_glossary.py"),
                     [str(proj), "-o", str(Path(d) / "g.json")])
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("tl", (r.stdout + r.stderr).lower())

    def test_does_not_write_into_source_dir(self):
        """纯取证模式（--no-xlsx）产物只在 -o；项目目录不新增文件。

        默认模式会在游戏根目录落 术语表.xlsx（AiNiee 三栏，见
        test_default_xlsx_written_to_project_root），那是新交付契约；
        本用例钉的是 --no-xlsx 下「不越出 -o、不改与本次无关的文件」。
        """
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            proj = _make_project(root / "proj", MINI_TL)
            before = {str(p) for p in proj.rglob("*")}
            out = root / "out_glossary.json"
            _run(os.path.join(_NAMES, "make_glossary.py"),
                 [str(proj), "-o", str(out), "--no-xlsx"])
            after = {str(p) for p in proj.rglob("*")}
            self.assertEqual(before, after,
                             "make_glossary --no-xlsx 在项目目录里写了东西")

    def test_default_xlsx_written_to_project_root(self):
        """默认生成 AiNiee 三栏 xlsx 到游戏根目录（原文|译文|备注）。

        mini 项目只有 Eileen 一人：草稿 1 条 → xlsx 表头 + 1 数据行；
        AiNiee 导入按列序读、跳过表头，所以表头必须占第一行。
        """
        with tempfile.TemporaryDirectory() as d:
            proj = _make_project(d, MINI_TL)
            out = Path(d) / "g.json"
            r = _run(os.path.join(_NAMES, "make_glossary.py"),
                     [str(proj), "-o", str(out), "--lang", "schinese"])
            self.assertEqual(r.returncode, 0,
                             f"make_glossary 失败:\n{r.stdout}\n{r.stderr}")
            xlsx = proj / "术语表.xlsx"
            self.assertTrue(xlsx.is_file(), f"默认没在游戏根目录生成 xlsx: {xlsx}")
            from openpyxl import load_workbook
            ws = load_workbook(xlsx).active
            headers = [ws.cell(1, c).value for c in (1, 2, 3)]
            self.assertEqual(headers, ["原文", "译文", "备注"],
                             f"表头不是 AiNiee 三栏: {headers}")
            self.assertEqual(ws.max_row, 2, "mini 项目应只有 1 条数据行")
            self.assertEqual(ws.cell(2, 1).value, "Eileen")
            self.assertEqual(ws.cell(2, 2).value, "艾琳")

    def test_finalize_generates_full_xlsx(self):
        """--finalize 读 AI 定稿 JSONL → 完整版 xlsx（备注列取 info）。

        不需要 tl（定稿在手即可），产物在游戏根目录，备注仅翻译辅助极简信息。
        """
        with tempfile.TemporaryDirectory() as d:
            proj = _make_project(d, MINI_TL)
            final = Path(d) / "glossary_full.jsonl"
            final.write_text(
                '{"src": "Eri Kagamine", "dst": "镜音绘里", "info": "绘里全名"}\n'
                '{"src": "Taria", "dst": "塔莉亚", "info": "女性名"}\n',
                encoding="utf-8")
            r = _run(os.path.join(_NAMES, "make_glossary.py"),
                     [str(proj), "--finalize", str(final)])
            self.assertEqual(r.returncode, 0,
                             f"--finalize 失败:\n{r.stdout}\n{r.stderr}")
            xlsx = proj / "术语表.xlsx"
            self.assertTrue(xlsx.is_file(), f"finalize 没生成 xlsx: {xlsx}")
            from openpyxl import load_workbook
            ws = load_workbook(xlsx).active
            self.assertEqual(ws.max_row, 3, "定稿 2 条 → 表头 + 2 数据行")
            self.assertEqual(ws.cell(2, 3).value, "绘里全名")
            self.assertEqual(ws.cell(3, 3).value, "女性名")

    def test_finalize_requires_src(self):
        """定稿文件全无 src 时 fail-closed（rc=2），不产出空表。"""
        with tempfile.TemporaryDirectory() as d:
            proj = _make_project(d)
            final = Path(d) / "empty.jsonl"
            final.write_text('{"dst": "塔莉亚", "info": "女性名"}\n', encoding="utf-8")
            r = _run(os.path.join(_NAMES, "make_glossary.py"),
                     [str(proj), "--finalize", str(final)])
            self.assertEqual(r.returncode, 2, f"应 fail-closed: {r.stdout}\n{r.stderr}")
            self.assertFalse((proj / "术语表.xlsx").exists(),
                             "空定稿不该产出 xlsx")

    def test_missing_path_exits_nonzero(self):
        r = _run(os.path.join(_NAMES, "make_glossary.py"),
                 ["/nonexistent/xyz_project"])
        self.assertNotEqual(r.returncode, 0)


class TestSetupFonts(unittest.TestCase):
    """setup_fonts：四个子命令都要能跑，config 产物落在指定路径。"""

    def test_detect_runs_and_reports_fonts(self):
        with tempfile.TemporaryDirectory() as d:
            proj = _make_project(d)
            r = _run(os.path.join(_SETUP, "setup_fonts.py"),
                     ["detect", "--path", str(proj)])
            self.assertEqual(r.returncode, 0,
                             f"detect 失败:\n{r.stdout}\n{r.stderr}")
            self.assertTrue(r.stdout.strip(), "detect 没有任何输出")

    def test_list_runs_without_project(self):
        r = _run(os.path.join(_SETUP, "setup_fonts.py"), ["list"])
        self.assertEqual(r.returncode, 0, f"list 失败:\n{r.stderr}")

    def test_config_writes_only_to_target(self):
        """config 生成的 .rpy 不能散落在项目根。"""
        with tempfile.TemporaryDirectory() as d:
            proj = _make_project(d)
            before = {str(p.relative_to(proj)) for p in proj.rglob("*.rpy")}
            r = _run(os.path.join(_SETUP, "setup_fonts.py"),
                     ["config", "--path", str(proj)])
            self.assertEqual(r.returncode, 0,
                             f"config 失败:\n{r.stdout}\n{r.stderr}")
            new = {str(p.relative_to(proj)) for p in proj.rglob("*.rpy")} - before
            for rel in new:
                self.assertIn("font", rel.lower(),
                              f"config 新增了非字体文件: {rel}")

    def test_missing_path_exits_nonzero(self):
        """路径不存在时不能凭空建目录再报成功（2026-10-11 修）。"""
        with tempfile.TemporaryDirectory() as d:
            missing = str(Path(d) / "does_not_exist")
            r = _run(os.path.join(_SETUP, "setup_fonts.py"),
                     ["detect", "--path", missing])
            self.assertNotEqual(r.returncode, 0,
                                "不存在的路径应报错退出，不能静默成功")
            self.assertFalse(Path(missing).exists(),
                             "detect 凭空创建了项目目录——检测命令不该有写副作用")


class TestApplyGlossaryBody(unittest.TestCase):
    """apply_glossary_body：按术语表改正文，产物是 apply 批次，不直接写 tl。"""

    def test_produces_apply_batch(self):
        with tempfile.TemporaryDirectory() as d:
            proj = _make_project(d, MINI_TL)
            tl_dir = proj / "game" / "tl" / "schinese"
            glossary = Path(d) / "g.json"
            glossary.write_text(json.dumps({"Eileen": "艾琳"},
                                           ensure_ascii=False), encoding="utf-8")
            out = Path(d) / "name_fix.json"
            r = _run(os.path.join(_NAMES, "apply_glossary_body.py"),
                     [str(tl_dir), "-g", str(glossary), "-o", str(out)])
            self.assertEqual(r.returncode, 0,
                             f"apply_glossary_body 失败:\n{r.stdout}\n{r.stderr}")
            self.assertTrue(out.is_file(), f"没产出批次: {out}")
            items = json.loads(out.read_text(encoding="utf-8-sig"))
            self.assertIsInstance(items, list)

    def test_does_not_modify_tl_files(self):
        """它只产出批次 JSON，回填由 autotranslate apply 负责。"""
        with tempfile.TemporaryDirectory() as d:
            proj = _make_project(d, MINI_TL)
            tl_dir = proj / "game" / "tl" / "schinese"
            src = tl_dir / "script.rpy"
            before = src.read_bytes()
            glossary = Path(d) / "g.json"
            glossary.write_text(json.dumps({"Eileen": "艾琳"},
                                           ensure_ascii=False), encoding="utf-8")
            _run(os.path.join(_NAMES, "apply_glossary_body.py"),
                 [str(tl_dir), "-g", str(glossary),
                  "-o", str(Path(d) / "n.json")])
            self.assertEqual(src.read_bytes(), before,
                             "apply_glossary_body 直接改了 tl 文件")

    def test_missing_glossary_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as d:
            proj = _make_project(d, MINI_TL)
            tl_dir = proj / "game" / "tl" / "schinese"
            r = _run(os.path.join(_NAMES, "apply_glossary_body.py"),
                     [str(tl_dir), "-g", str(Path(d) / "nope.json"),
                      "-o", str(Path(d) / "n.json")])
            self.assertNotEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
