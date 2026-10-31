#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""源脚本 ↔ tl 目录覆盖对照：找出没有对应译文的源脚本。

check_untranslated 只保证「tl 目录里没有空译文」，不保证「每个源脚本都有
译文文件」——机翻管线（AiNiee 等）常只导出部分文件，剩下的一半对白在
运行时仍是英文，而上面的检查会报全绿（AfterDark 实测：124 个源脚本只有
70 个 tl 文件，check_untranslated 却 OK）。本检查器补上这个盲区。

原理：Ren'Py 的 tl 生成约定是文件镜像——`game/foo/bar.rpy` 的译文落在
`game/tl/<lang>/foo/bar_translated.rpy`。对源侧与 tl 侧各枚举一次 .rpy，
按相对路径求差集即可，不依赖游戏的任何自定义结构。文件名里夹空格等怪癖
（源 `1hallway2_screen .rpy` vs tl 去掉空格）做一次归一化兜底匹配。

边界（有意不做）：
- 只查文件级覆盖，不查 label 级——文件存在但内容被删空属于 tlcheck 的语义层；
- 字符串行数只是**线索提示**（简单引号行计数），不是精确对白数；
- 运行时动态构造的文本（init python 的 Text() 等）任何覆盖检查都看不见。

用法:
  python check_tl_coverage.py <游戏目录> [-l schinese]

退出码: 0 = 覆盖完整（或缺口均无可翻译内容）；1 = 存在带内容的覆盖缺口。
"""

import argparse
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_TOOLS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (os.path.join(_TOOLS_DIR, "shared"),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from lang_names import DEFAULT_LANG  # noqa: E402
from base_checker import (  # noqa: E402
    PROJECT, BaseChecker, CheckContext, find_game_dir, iter_rpy,
)


class TlCoverageChecker(BaseChecker):
    """源↔tl 文件覆盖对照。"""

    name = "tlcoverage"
    summary = "源脚本↔tl覆盖对照：找出没有对应译文的源脚本（untranslated 的盲区）"
    takes = PROJECT
    requires_tl = True


#: 门面发现用的实例（契约见 shared/base_checker.py）
CHECKER = TlCoverageChecker()


# 字符串线索行：含双引号字面量、非注释、非纯 define/default/image 声明。
_HINT_LINE = re.compile(r'^\s*(["\']|[A-Za-z_][\w \t]*\s+["\'])')
_DECL_LINE = re.compile(r'^\s*(define|default|image|transform|style|layer)\b')


def _norm(rel):
    """归一化键：小写 + 去空格，兜底匹配「源/TL 命名怪癖」。"""
    return rel.lower().replace(" ", "")


def _map_tl_rel(rel_in_tl):
    """tl 内相对路径 → 源侧相对路径：去掉 Ren'Py 的 _translated 后缀。"""
    if rel_in_tl.endswith("_translated.rpy"):
        rel_in_tl = rel_in_tl[: -len("_translated.rpy")] + ".rpy"
    return rel_in_tl


def list_tl_files(tl_dir):
    """tl/<lang>/ 下全部 .rpy，返回 [(映射后的源侧路径, 原始路径, tl 内相对路径)]。"""
    out = []
    for dirpath, dirnames, filenames in os.walk(tl_dir):
        dirnames[:] = [d for d in dirnames if d not in ("cache", "__pycache__")]
        for fn in filenames:
            if not fn.endswith(".rpy"):
                continue
            full = os.path.join(dirpath, fn)
            rel_in_tl = os.path.relpath(full, tl_dir).replace(os.sep, "/")
            out.append((_map_tl_rel(rel_in_tl), full, rel_in_tl))
    return out


def run_check(game_dir, tl_dir, lang, out=sys.stdout):
    """执行对照，返回退出码。逻辑与 argparse 解耦以便复用。"""
    sources = iter_rpy(game_dir)
    tl_files = list_tl_files(tl_dir)

    src_set = {}
    for p in sources:
        rel = os.path.relpath(p, game_dir).replace(os.sep, "/")
        src_set[_norm(rel)] = rel

    tl_keys = {_norm(rel) for rel, _, _ in tl_files}
    # tl 侧自产文件（common.rpy / 引擎串）没有源对应，单独列出作参考
    tl_only = sorted(
        (rel_in_tl for mapped, _, rel_in_tl in tl_files
         if _norm(mapped) not in src_set),
        key=str.lower,
    )

    gaps = []       # [(源相对路径, 线索行数)]
    hint_total = 0
    for p in sources:
        rel = os.path.relpath(p, game_dir).replace(os.sep, "/")
        if _norm(rel) in tl_keys:
            continue
        hint = count_hint_lines(p)
        gaps.append((rel, hint))
        hint_total += hint

    covered = len(src_set) - len(gaps)
    out.write("\n" + "=" * 50 + "\n")
    out.write(f"源脚本(不含tl/): {len(src_set)} 个  tl/{lang} 文件: {len(tl_files)} 个  "
              f"有对应译文: {covered} 个\n")
    out.write("=" * 50 + "\n")

    if tl_only:
        out.write(f"\n[INFO] tl 侧 {len(tl_only)} 个文件无源对应（common/引擎串，正常）:\n")
        for rel in tl_only[:5]:
            out.write(f"  - {rel}\n")
        if len(tl_only) > 5:
            out.write(f"  ... 还有 {len(tl_only) - 5} 个\n")

    if not gaps:
        out.write("\n[OK] 所有源脚本都有对应译文文件。\n")
        return 0

    out.write(f"\n[!!] {len(gaps)} 个源脚本没有对应译文文件"
              f"（合计约 {hint_total} 行含字符串）:\n")
    for rel, hint in sorted(gaps, key=lambda x: -x[1]):
        out.write(f"  !! {rel:<50} ~{hint} 行含字符串\n")
    out.write("\n这些文件的对白/界面在运行时仍是原文语言——check_untranslated\n"
              "只扫 tl 目录内部，看不见它们。补法：用 SDK 跑\n"
              "  renpy.py <项目> translate <lang> --ascii\n"
              "生成缺失骨架后再走翻译管线，或用 AiNiee 等工具补齐这几个文件。\n")
    return 1 if hint_total > 0 else 0


def count_hint_lines(path):
    """含字符串字面量的行数（线索用，非精确对白数）。"""
    n = 0
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                s = line.split("#", 1)[0].rstrip()
                if not s or _DECL_LINE.match(s):
                    continue
                if _HINT_LINE.match(s) and '"' in s:
                    n += 1
    except OSError:
        pass
    return n


def main():
    ap = argparse.ArgumentParser(
        description="源脚本 ↔ tl 目录覆盖对照（untranslated 的盲区）")
    ap.add_argument("project", help="游戏根目录（含 game/）或 game 目录")
    ap.add_argument("-l", "--language", default=DEFAULT_LANG,
                    help="目标语言（默认 schinese，对应 game/tl/<lang>）")
    args = ap.parse_args()

    game_dir = find_game_dir(args.project)
    if not game_dir:
        print(f"[ERR] 找不到 game 目录：{args.project}", file=sys.stderr)
        return 2
    tl_dir = os.path.join(game_dir, "tl", args.language)
    if not os.path.isdir(tl_dir):
        print(f"[ERR] 不存在 {tl_dir}——还没有该语言的译文，先跑 setup_i18n。",
              file=sys.stderr)
        return 2
    return run_check(game_dir, tl_dir, args.language)


if __name__ == "__main__":
    sys.exit(main())
