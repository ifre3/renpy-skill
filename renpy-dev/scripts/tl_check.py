#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tl_check.py — Ren'Py 翻译文件静态质检器 v2
扫描 game/tl/<lang>/*.rpy，不启动游戏即可找出会崩溃或显示异常的问题。
覆盖两种翻译结构：
  A. 字符串翻译   old "..." / new "..."        （gui、common 的 strings 块）
  B. 对白翻译     translate 块内  # 原文行 + 译文对白行

检查项：
  1. %-格式串损坏   %(name)s 丢类型字符（如 %(name)啊 → ValueError 秒崩）
  2. [] 插值不匹配  新串缺/多 [var]（运行时 KeyError 或变量没被替换）
  3. {} 文本标签失衡 {i}{w}{font=...} 新旧不一致（标签失效/斜体泄漏）
  4. 空译文         old 非空而 new 为空串（对白消失）

跳过规则：new 与 old 完全相同的条目不查（strftime 等格式串通常原样保留）。

用法:
  python tl_check.py <项目根目录或game目录> [--lang schinese]

退出码: 0=无问题, 1=发现问题, 2=路径错误
"""

import argparse
import ast
import re
import sys
from pathlib import Path

VALID_FORMAT_TYPES = set("srdiouxXeEfFgGca%")
TRANSLATE_RE = re.compile(r"^translate\s+(\w+)(?:\s+(\w+))?\s*:\s*$")
# 对白行：可选说话人前缀（可带属性）+ 引号串；也支持 extend
DIALOGUE_RE = re.compile(
    r'^\s*(?:(?:extend\s+)?[A-Za-z_]\w*(?:\s+[a-z_]\w*)*\s+)?"((?:[^"\\]|\\.)*)"\s*$')
COMMENT_DLG_RE = re.compile(r'^\s*#\s*(?:(?:extend\s+)?[A-Za-z_]\w*(?:\s+[a-z_]\w*)*\s+)?"((?:[^"\\]|\\.)*)"\s*$')
STR_RE = re.compile(r'^\s*(old|new)\s+("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')\s*$')
PCT_RE = re.compile(r"%(\(([^)]*)\))?(.)")
INTERP_RE = re.compile(r"(?<!\[)\[([^\[\]]+)\](?!\])")
TAG_RE = re.compile(r"(?<!\{)\{([^{}]*)\}(?!\})")


def unescape(raw: str) -> str:
    try:
        return ast.literal_eval(raw)
    except Exception:
        return raw


def find_tl_dir(base: Path, lang: str):
    for cand in (base, base / "game"):
        tl = cand / "tl" / lang
        if tl.is_dir():
            return tl
    return None


def pct_specs(s: str):
    out, i = [], 0
    while True:
        m = PCT_RE.search(s, i)
        if not m:
            break
        if m.group(3) == "%":
            i = m.end()
            continue
        out.append((m.group(0), m.group(2), m.group(3)))
        i = m.end()
    return out


def interp_keys(s: str):
    return sorted({t.strip() for t in INTERP_RE.findall(s)})


def text_tags(s: str):
    return sorted(t.split("=")[0].strip().lower() for t in TAG_RE.findall(s))


def compare(old: str, new: str, ctx: str, issues: list):
    if old == new or not old:
        return
    # 4. 空译文
    if new.strip() == "":
        short = old[:36] + ("..." if len(old) > 36 else "")
        issues.append((ctx, "空译文", f'old="{short}"'))
        return
    # 1. %-格式串
    op, np_ = pct_specs(old), pct_specs(new)
    for idx, (full, name, tch) in enumerate(np_):
        if tch not in VALID_FORMAT_TYPES:
            hint = f'应改为 "{full[:-1]}s"' if name is not None else "检查机翻是否弄坏 % 转义"
            issues.append((ctx, "%格式字符非法",
                           f'"{full}" 类型字符是 U+{ord(tch):04X}({tch})，{hint}'))
    on = [(n, t) for _, n, t in op if n is not None]
    nn = [(n, t) for _, n, t in np_ if n is not None]
    if on != nn:
        issues.append((ctx, "%格式符新旧不匹配", f"old={on} new={nn}"))
    # 2. [] 插值
    oi, ni = interp_keys(old), interp_keys(new)
    if oi != ni:
        missing, extra = set(oi) - set(ni), set(ni) - set(oi)
        detail = ((f"缺 {sorted(missing)} " if missing else "") +
                  (f"多 {sorted(extra)}" if extra else "")).strip()
        issues.append((ctx, "[]插值不匹配", detail))
    # 3. {} 标签
    ot, nt = text_tags(old), text_tags(new)
    if ot != nt:
        issues.append((ctx, "{}标签失衡", f"old={ot} new={nt}"))


# ---- --fix 用：机械性修复规则（对原始行文本操作） ----
# 规则A: %(name) 后直接跟非ASCII/标点 → 补类型字符 s（机翻弄丢了 s，后面的字是正文）
RULE_MISSING_S = re.compile(r'%(\([A-Za-z_]\w*\))(?![srdiouxXeEfFgGca%])')
# 替换时必须保留前导 %：%(...)啊 → %(...)s啊
RULE_MISSING_S_SUB = r'%\1s'
# 规则C: 裸 % 后跟非ASCII字符 → %% 转义（如 "100%都" → "100%%都"）
RULE_BARE_PCT = re.compile(r'%(?=[^\x00-\x7f])')


def apply_fix_rules(line: str, old_text: str | None):
    """对一行译文应用机械修复，返回 (新行, 修复说明列表)。"""
    fixes = []
    # 规则B: %(中文变量)s → 用 old 里的原名还原
    for m in re.finditer(r'%\(([^)]*)\)', line):
        name = m.group(1)
        if not re.fullmatch(r'[A-Za-z_]\w*', name):
            orig = None
            if old_text:
                for om in re.finditer(r'%\(([A-Za-z_]\w*)\)', old_text):
                    orig = om.group(1)
                    break
            if orig:
                line = line.replace(m.group(0), f'%({orig})')
                fixes.append(f'%({name}) → %({orig})')
    new_line = RULE_MISSING_S.sub(RULE_MISSING_S_SUB, line)
    if new_line != line:
        fixes.append('补 %(...)s 类型字符')
        line = new_line
    new_line = RULE_BARE_PCT.sub('%%', line)
    if new_line != line:
        fixes.append('裸 % → %%')
        line = new_line
    return line, fixes


def check_file(path: Path, issues: list, do_fix=False):
    in_strings = False
    old, old_line, last_comment, last_comment_line = None, None, None, None

    lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    edits: dict = {}  # lineno -> new line

    def maybe_fix(lineno, raw_line, old_text, kind):
        if not do_fix:
            return
        fixed, fixes = apply_fix_rules(raw_line, old_text)
        if fixes:
            edits[lineno] = fixed
            issues.append((f"{path.name}:{lineno}", "已自动修复(" + kind + ")",
                           "；".join(fixes)))

    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()

        m = TRANSLATE_RE.match(stripped)
        if m:
            in_strings = (m.group(2) == "strings")
            old = last_comment = None
            continue
        if stripped.startswith("#") and not stripped.startswith("#!"):
            cm = COMMENT_DLG_RE.match(line)
            if cm:
                last_comment, last_comment_line = unescape('"' + cm.group(1) + '"'), lineno
            continue
        if not stripped:
            continue

        if in_strings:
            sm = STR_RE.match(line)
            if sm:
                kind, text = sm.group(1), unescape(sm.group(2))
                if kind == "old":
                    old, old_line = text, lineno
                else:
                    if old is not None:
                        compare(old, text, f"{path.name}:{old_line}", issues)
                        maybe_fix(lineno, line, old, "new行")
                    old = None
                continue

        # 对白译文行
        dm = DIALOGUE_RE.match(line)
        if dm and last_comment is not None:
            compare(last_comment, unescape('"' + dm.group(1) + '"'),
                    f"{path.name}:{last_comment_line}", issues)
            maybe_fix(lineno, line, last_comment, "对白")
            last_comment = None
        elif dm:
            # 译文行没有对应的 # 原文注释（少见），拿不到原文，跳过
            pass

    if edits:
        for ln, newline in edits.items():
            lines[ln - 1] = newline
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Ren'Py 翻译文件静态质检 v2")
    ap.add_argument("path", help="项目根目录或 game 目录")
    ap.add_argument("--lang", default="schinese")
    ap.add_argument("--fix", action="store_true",
                    help="自动修复机械性问题：%%(name)丢s、%%(变量名被翻译)、裸%%")
    args = ap.parse_args()

    tl = find_tl_dir(Path(args.path), args.lang)
    if not tl:
        print(f"[错误] 在 {args.path} 下找不到 tl/{args.lang}", file=sys.stderr)
        sys.exit(2)

    issues: list = []
    files = sorted(tl.glob("*.rpy"))
    for f in files:
        check_file(f, issues, do_fix=args.fix)

    print(f"扫描 {len(files)} 个文件: {tl}")
    if not issues:
        print("OK 未发现崩溃/显示隐患")
        sys.exit(0)

    by_type: dict = {}
    for ctx, typ, detail in issues:
        by_type.setdefault(typ, []).append((ctx, detail))
    for typ, items in by_type.items():
        print(f"\n== {typ} ({len(items)} 处) ==")
        for ctx, detail in items:
            print(f"  {ctx}: {detail}")
    print(f"\n共 {len(issues)} 处问题")
    sys.exit(1)


if __name__ == "__main__":
    main()
