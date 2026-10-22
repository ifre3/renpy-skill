#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_typography.py — Ren'Py 字号与排版合理性静态检查（只读）。

回答三个问题，不启动游戏：
  1. 中文字号是否过低（正文<20、名字/UI<18 极易不可读）
  2. outline 描边像素是否远大于字号（字号放大后 outline 不改会“发毛/缩圈”）
  3. style 块里是否硬编码了 size 数值（应引用 gui.XXX_size 变量，否则重新生成 GUI 会被覆盖）

用法:
  python check_typography.py <项目根目录或game目录> [--no-tl]
  python check_typography.py <项目> --severity WARNING

退出码: 0=无问题, 1=查出了问题, 2=路径错误
"""

import argparse
import os
import re
import sys
from pathlib import Path

# 契约层在 shared/（跨组共享，故按相对路径加入 sys.path）
_SHARED_CONTRACT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "../shared")
if _SHARED_CONTRACT_DIR not in sys.path:
    sys.path.insert(0, _SHARED_CONTRACT_DIR)

from base_checker import PROJECT, BaseChecker  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── 可读性阈值 ──
MIN_TEXT_SIZE = 20          # 对白正文最小字号
MIN_UI_SIZE = 18            # 名字/选项/按钮/历史最小字号
MAX_OUTLINE_RATIO = 0.30    # outline 像素占字号比例上限（0.30 = 30%）

# ── 正则 ──
# define gui.text_size = 28 / gui.name_text_size = 22 ...
GUI_SIZE_DEF_RE = re.compile(
    r'define\s+gui\.(text_size|name_text_size|choice_button_text_size|button_text_size|history_text_size)\s*=\s*(\d+)'
)
# style xxx: ... size 28 （硬编码，建议引用 gui 变量）
STYLE_SIZE_RE = re.compile(r'\bsize\s+(\d+)\b')
# line_spacing 5
LINE_SPACING_RE = re.compile(r'\bline_spacing\s+(\d+)\b')
# outlines [(2, "#000", 0, 0)] 取首个像素值
OUTLINE_RE = re.compile(r'outlines\s*\[\s*\(\s*(\d+)')

# 字号字段的中文说明
SIZE_LABEL = {
    "text_size": "对白正文 (gui.text_size)",
    "name_text_size": "角色名字 (gui.name_text_size)",
    "choice_button_text_size": "选项按钮 (gui.choice_button_text_size)",
    "button_text_size": "UI 按钮 (gui.button_text_size)",
    "history_text_size": "历史回放 (gui.history_text_size)",
}

SEVERITY_ORDER = {"ERROR": 0, "WARNING": 1, "INFO": 2}
SEVERITY_SYMBOL = {"ERROR": "!!", "WARNING": "!", "INFO": "."}


class Finding:
    def __init__(self, file, line_no, line, category, severity, message, suggestion=""):
        self.file = file
        self.line_no = line_no
        self.line = line.strip()[:120]
        self.category = category
        self.severity = severity
        self.message = message
        self.suggestion = suggestion

    def __str__(self):
        sym = SEVERITY_SYMBOL.get(self.severity, ".")
        return f"[{self.severity}] {sym} {self.file}:{self.line_no}  {self.message}"


def find_game_dir(base: Path):
    if (base / "game").is_dir():
        return base / "game"
    if base.name == "game" and base.is_dir():
        return base
    return None


def iter_rpy(game_dir, include_tl=True):
    """遍历 .rpy，默认进入 tl/；跳过引擎/缓存/存档目录。"""
    skip = ("renpy", "lib", "cache", "saves")
    out = []
    for dirpath, dirnames, filenames in os.walk(game_dir):
        dirnames[:] = [d for d in dirnames if d not in skip]
        if not include_tl and os.path.basename(dirpath) == "tl":
            dirnames[:] = []
            continue
        for fn in filenames:
            if fn.endswith(".rpy"):
                out.append(Path(dirpath) / fn)
    return out


def scan_file(path):
    """返回单文件的 Finding 列表。"""
    findings = []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return findings

    rel = path  # 调用方再做相对化
    for lineno, line in enumerate(text.splitlines(), 1):
        # 去注释
        code = line.split("#", 1)[0]

        # 1. 字号定义是否过低
        m = GUI_SIZE_DEF_RE.search(code)
        if m:
            field, val = m.group(1), int(m.group(2))
            floor = MIN_TEXT_SIZE if field == "text_size" else MIN_UI_SIZE
            if val < floor:
                findings.append(Finding(
                    rel, lineno, line, "GUI_SIZE_TOO_SMALL", "WARNING",
                    f"{SIZE_LABEL[field]} = {val} 低于中文可读下限 {floor}",
                    f"改为 {floor} 或更大，见 references/typography.md"))
            continue

        # 2. style 块里硬编码 size（info，建议引用 gui 变量）
        if STYLE_SIZE_RE.search(code) and "define" not in code:
            m = STYLE_SIZE_RE.search(code)
            findings.append(Finding(
                rel, lineno, line, "HARDCODED_SIZE", "INFO",
                f"style 块里硬编码 size {m.group(1)}，建议引用 gui.XXX_size 变量",
                "改为 size gui.text_size 等，避免重新生成 GUI 时被覆盖"))
            continue

        # 3. outline 像素是否过大（绝对值 > 4 即警告，绝大多数中文场景 outline 不该超过 4）
        m = OUTLINE_RE.search(code)
        if m:
            px = int(m.group(1))
            if px > 4:
                findings.append(Finding(
                    rel, lineno, line, "OUTLINE_TOO_THICK", "WARNING",
                    f"outline 像素 {px} 偏大，字号放大后易出现“发毛/缩圈”",
                    "按字号取 1–4（≤20 取1，28–32 取2–3，34+ 取3–4），见 references/typography.md"))
            continue

        # 4. line_spacing 范围提示（仅提示，不与字号关联，降低误报）
        m = LINE_SPACING_RE.search(code)
        if m:
            val = int(m.group(1))
            if val < 1 or val > 12:
                findings.append(Finding(
                    rel, lineno, line, "LINE_SPACING_RANGE", "INFO",
                    f"line_spacing {val} 超出常见范围 1–12，中文建议字号的 15%–20%",
                    "按字号调整，见 references/typography.md"))
            continue

    return findings


def main():
    ap = argparse.ArgumentParser(description="Ren'Py 字号与排版合理性静态检查")
    ap.add_argument("path", help="项目根目录或 game 目录")
    ap.add_argument("--no-tl", action="store_true", help="跳过 tl/ 翻译目录")
    # 兼容 `all` 透传的 -l/--language（与 check_fonts.py 一致，不参与本检查逻辑）
    ap.add_argument("-l", "--language", "--lang", dest="lang", default=None,
                    help="兼容 all 透传（当前不参与检查逻辑）")
    ap.add_argument("--severity", choices=["ERROR", "WARNING", "INFO"],
                    default="INFO", help="只显示指定级别及以上（默认 INFO）")
    args = ap.parse_args()

    game_dir = find_game_dir(Path(args.path))
    if not game_dir:
        print("[错误] 未找到 game/ 目录: %s" % args.path, file=sys.stderr)
        return 2

    min_sev = SEVERITY_ORDER[args.severity]
    files = iter_rpy(game_dir, include_tl=not args.no_tl)

    all_findings = []
    for p in sorted(files):
        for f in scan_file(p):
            if SEVERITY_ORDER[f.severity] <= min_sev:
                all_findings.append((p, f))

    # 汇总统计
    by_file = {}
    for p, f in all_findings:
        by_file.setdefault(p, []).append(f)

    print("=" * 60)
    print("🔤 字号与排版合理性检查（%d 个 .rpy 文件）" % len(files))
    print("=" * 60)

    if not all_findings:
        print("\n✅ 未发现字号/排版合理性问题")
        print("检查完成，问题总数: 0")
        return 0

    problems = 0
    for p in sorted(by_file):
        rel = os.path.relpath(p, game_dir)
        print(f"\n📄 {rel}")
        for f in by_file[p]:
            print(f"   {f}")
            problems += 1

    print(f"\n检查完成，问题总数: {problems}")
    print("💡 建议优先处理 ERROR/WARNING；INFO 仅供参考。")
    print("参考: references/typography.md（字体大小与排版实战手册）")
    return 1


class TypographyChecker(BaseChecker):
    """字号与排版合理性检查（门面子命令 typography）。"""

    name = "typography"
    summary = "字号与排版合理性检查（中文字号下限、outline 比例、硬编码 size）"
    takes = PROJECT
    requires_tl = False


#: 门面发现用的实例（契约见 shared/base_checker.py）
CHECKER = TypographyChecker()


if __name__ == "__main__":
    sys.exit(main())
