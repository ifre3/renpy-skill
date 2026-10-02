#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tl_check.py — Ren'Py 翻译文件静态质检器 v3
扫描 game/tl/<lang>/*.rpy，不启动游戏即可找出会崩溃或显示异常的问题。
覆盖两种翻译结构：
  A. 字符串翻译   old "..." / new "..."        （gui、common 的 strings 块）
  B. 对白翻译     translate 块内  # 原文行 + 译文对白行

问题分级（v3）：
  [崩溃] 会让 Ren'Py 抛异常：未知文本标签({REDACTED})、关闭无开放标签、
         关闭不接受关闭的标签({/w})、未闭合大括号、%(name)s 丢类型字符。
         依据引擎源码行为模拟（renpy/text/text.py + extras.py）：
         标签大小写敏感、花括号内空格不剥离、config.safe_text=False
         （默认）时未知标签直接 raise。项目若开启 safe_text 自动降级。
  [显示] 不崩溃但显示错误：标签新旧不一致、全角伪标签(【i】)、空译文、
         [] 插值不匹配
  [提示] 不影响运行：new 与 old 完全相同的未翻译行、裸 %（Ren'Py 8 对白
         不做 % 格式化，裸 % 是字面量，通常安全；--fix 也不再动它）

用法:
  python tl_check.py <项目根目录或game目录> [--lang schinese] [--fix] [--max-examples N]

退出码: 0=无崩溃/显示问题(可有提示级), 1=有崩溃或显示问题, 2=路径错误
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

# renpy/text/extras.py text_tags 注册表（tag → 是否接受关闭标签）
KNOWN_TAGS = {
    "p", "space", "vspace", "w", "fast", "done", "nw", "a", "b", "i", "u",
    "s", "plain", "font", "size", "color", "outlinecolor", "alpha", "k",
    "rt", "art", "rb", "cps", "vert", "horiz", "alt", "noalt", "instance",
    "shader", "image",
}
NO_CLOSE_TAGS = {"done", "image", "p", "w", "fast", "nw", "space", "vspace"}
TAG_VALUE_PREFIXES = ("axis:", "feature:")

# 全角伪标签：译者把 {i} 打成 【i】/【/i]（显示为字面文字，不崩溃但出错样）
PSEUDO_TAG_RE = re.compile(r"【\s*/?\s*([iBUSW])\s*[】\]]")

# --fix：花括号内带空格/大写的简单标签规范化，如 { i }→{i}、{/ i }→{/i}、{/B}→{/b}
RULE_SPACED_TAG = re.compile(r"\{\s*(/\s*)?([iBUSW])\s*\}")
RULE_MISSING_S = re.compile(r'%(\([A-Za-z_]\w*\))(?![srdiouxXeEfFgGca%])')
RULE_MISSING_S_SUB = r'%\1s'


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


def detect_safe_text(game_dir: Path) -> bool:
    """扫描 game/*.rpy 是否有 config.safe_text = True（有则未知标签不崩溃）。"""
    for p in game_dir.glob("*.rpy"):
        try:
            if re.search(r"config\.safe_text\s*=\s*True", p.read_text(encoding="utf-8", errors="ignore")):
                return True
        except OSError:
            continue
    return False


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


def tokenize_tags(s: str):
    """模拟 Ren'Py 的 {{ 转义与 {} 标签切分。
    返回 [(inner, closed)]，closed=False 表示到串尾都没有 '}'。"""
    tokens, i, n = [], 0, len(s)
    while True:
        c = s.find("{", i)
        if c < 0:
            return tokens
        j = s.find("}", c)
        if j < 0:
            tokens.append((s[c:], False))
            return tokens
        inner = s[c + 1:j]
        if inner.startswith("{") or inner == "":
            i = j + 1  # {{ → 字面 {，不产生标签
            continue
        tokens.append((inner, True))
        i = j + 1


def tag_names(s: str):
    """归一化标签名集合（用于新旧一致性比较，只看用了哪些标签不看配对）。"""
    return {inner.split("=", 1)[0].strip().lower()
            for inner, closed in tokenize_tags(s)
            if closed and not inner.startswith("#")}


def tag_problems(s: str):
    """按引擎真实行为分析一个字符串里的标签，返回 [(片段, 类型)]。
    引擎规则：名字不 strip、大小写敏感；未知开标签 raise；关闭标签弹出
    时不校验名字，但栈空时 raise；不接受关闭的标签关闭时 raise；
    只有"接受关闭"的标签才进栈（w/p/image 等不进栈）。"""
    problems = []
    stack = []
    for inner, closed in tokenize_tags(s):
        if not closed:
            problems.append(("{" + inner[:30], "未闭合大括号"))
            continue
        if inner.startswith("#"):
            continue  # {#注释}
        name = inner.split("=", 1)[0]
        if name.startswith("/"):
            open_name = name[1:]
            if open_name in NO_CLOSE_TAGS:
                problems.append(("{" + inner + "}", "标签不接受关闭"))
            elif not stack:
                problems.append(("{" + inner + "}", "关闭无开放标签"))
            else:
                stack.pop()
        elif name.startswith(TAG_VALUE_PREFIXES):
            stack.append(name)
        elif name in KNOWN_TAGS:
            if name not in NO_CLOSE_TAGS:
                stack.append(name)
        else:
            problems.append(("{" + inner + "}", "未知文本标签"))
    return problems


def latin_words(s: str):
    """是否含 ≥3 连续拉丁字母（用于未翻译判定）。"""
    return re.search(r"[A-Za-z]{3,}", s) is not None


def compare(old: str, new: str, ctx: str, issues: list):
    """old==new 的条目走未翻译统计，这里只查差异问题。"""
    if not old.strip():
        return  # old 为空串的配对（如语音占位行）没有参照物
    # 空译文
    if new.strip() == "":
        short = old[:36] + ("..." if len(old) > 36 else "")
        issues.append((ctx, "显示", "空译文", f'old="{short}"'))
        return
    # 1. %(name)s 丢类型字符（真崩溃源；裸 % 是字面量不查）
    op, np_ = pct_specs(old), pct_specs(new)
    for full, name, tch in np_:
        if name is not None and tch not in VALID_FORMAT_TYPES:
            issues.append((ctx, "崩溃", "%(name)s丢类型字符",
                           f'"{full}" 类型字符是 U+{ord(tch):04X}({tch})，应改为 "{full[:-1]}s"'))
    on = [(n, t) for _, n, t in op if n is not None]
    nn = [(n, t) for _, n, t in np_ if n is not None]
    if on != nn:
        issues.append((ctx, "崩溃", "%(name)s格式符新旧不匹配", f"old={on} new={nn}"))
    # 2. [] 插值
    oi, ni = interp_keys(old), interp_keys(new)
    if oi != ni:
        missing, extra = set(oi) - set(ni), set(ni) - set(oi)
        detail = ((f"缺 {sorted(missing)} " if missing else "") +
                  (f"多 {sorted(extra)}" if extra else "")).strip()
        issues.append((ctx, "显示", "[]插值不匹配", detail))
    # 3. {} 标签：先查崩溃级（引擎行为），再查新旧差异（显示级）
    probs = tag_problems(new)
    for frag, typ in probs:
        issues.append((ctx, "崩溃", typ, frag))
    crash_here = any(lv == "崩溃" for _, lv, _, _ in issues[-len(probs):]) if probs else False
    if not crash_here:
        ot, nt = tag_names(old), tag_names(new)
        if ot != nt:
            issues.append((ctx, "显示", "{}标签新旧不一致", f"old={sorted(ot)} new={sorted(nt)}"))
    # 4. 全角伪标签
    for pm in PSEUDO_TAG_RE.finditer(new):
        letter = pm.group(1).lower()
        slash = "/" in pm.group()
        fixed = ("{/" + letter) if slash else ("{" + letter + "}")
        issues.append((ctx, "显示", "全角伪标签", f'"{pm.group()}" 是字面文字，应改为 "{fixed}"'))


# ---- --fix 用：机械性修复规则（对原始行文本操作） ----

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
    # 规则D: 花括号内空格/大写的简单标签规范化 { i }→{i}、{/ i }→{/i}、{/B}→{/b}
    def _norm_tag(m):
        return ("{/" if m.group(1) else "{") + m.group(2).lower() + "}"
    new_line = RULE_SPACED_TAG.sub(_norm_tag, line)
    if new_line != line:
        fixes.append('标签规范化（去空格/转小写）')
        line = new_line
    new_line = RULE_MISSING_S.sub(RULE_MISSING_S_SUB, line)
    if new_line != line:
        fixes.append('补 %(...)s 类型字符')
        line = new_line
    return line, fixes


def check_file(path: Path, issues: list, untranslated: list, do_fix=False):
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
            issues.append((f"{path.name}:{lineno}", "修复", "已自动修复(" + kind + ")",
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
                        if old == text and latin_words(old):
                            untranslated.append((f"{path.name}:{lineno}", old[:60]))
                        else:
                            compare(old, text, f"{path.name}:{lineno}", issues)
                        maybe_fix(lineno, line, old, "new行")
                    old = None
                continue

        # 对白译文行
        dm = DIALOGUE_RE.match(line)
        if dm and last_comment is not None:
            new_text = unescape('"' + dm.group(1) + '"')
            if last_comment == new_text and latin_words(last_comment):
                untranslated.append((f"{path.name}:{lineno}", new_text[:60]))
            else:
                compare(last_comment, new_text, f"{path.name}:{lineno}", issues)
            maybe_fix(lineno, line, last_comment, "对白")
            last_comment = None
        # 译文行没有对应的 # 原文注释（少见），拿不到原文，跳过

    if edits:
        for ln, newline in edits.items():
            lines[ln - 1] = newline
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Ren'Py 翻译文件静态质检 v3")
    ap.add_argument("path", help="项目根目录或 game 目录")
    ap.add_argument("--lang", default="schinese")
    ap.add_argument("--fix", action="store_true",
                    help="自动修复机械性问题：%%(name)丢s、%%(变量名被翻译)、花括号内空格/大写的简单标签")
    ap.add_argument("--max-examples", type=int, default=15,
                    help="每类问题最多打印的明细条数（默认 15，其余只计总数）")
    args = ap.parse_args()

    base = Path(args.path)
    tl = find_tl_dir(base, args.lang)
    if not tl:
        print(f"[错误] 在 {args.path} 下找不到 tl/{args.lang}", file=sys.stderr)
        sys.exit(2)

    game_dir = tl.parent.parent  # tl/<lang> → game
    safe_text = detect_safe_text(game_dir)

    issues: list = []          # (ctx, 级别, 类型, 明细)
    untranslated: list = []    # (ctx, 文本)
    files = sorted(list(tl.glob("*.rpy")) + list(tl.glob("*.rpym")))
    for f in files:
        check_file(f, issues, untranslated, do_fix=args.fix)

    # 项目开启 safe_text 时，未知标签显示为字面文字，不崩溃 → 降级
    if safe_text:
        issues = [(c, "显示" if lv == "崩溃" and t == "未知文本标签" else lv, t, d)
                  for c, lv, t, d in issues]

    print(f"扫描 {len(files)} 个文件: {tl}"
          + ("（检测到 config.safe_text=True，未知标签降级为显示级）" if safe_text else ""))

    if untranslated:
        print(f"\n== [提示] 未翻译 new==old ({len(untranslated)} 处) ==")
        for ctx, txt in untranslated[:args.max_examples]:
            print(f"  {ctx}: {txt}")
        if len(untranslated) > args.max_examples:
            print(f"  ... 其余 {len(untranslated) - args.max_examples} 条省略")

    if not issues:
        print("\nOK 未发现崩溃/显示隐患"
              + (f"（另有 {len(untranslated)} 处未翻译）" if untranslated else ""))
        sys.exit(0)

    order = {"崩溃": 0, "显示": 1, "修复": 2}
    by_type: dict = {}
    for ctx, lv, typ, detail in issues:
        by_type.setdefault((lv, typ), []).append((ctx, detail))
    for (lv, typ), items in sorted(by_type.items(), key=lambda kv: (order.get(kv[0][0], 3), kv[0][1])):
        print(f"\n== [{lv}] {typ} ({len(items)} 处) ==")
        for ctx, detail in items[:args.max_examples]:
            print(f"  {ctx}: {detail}")
        if len(items) > args.max_examples:
            print(f"  ... 其余 {len(items) - args.max_examples} 条省略")

    n_crash = sum(1 for _, lv, _, _ in issues if lv == "崩溃")
    print(f"\n共 {len(issues)} 处问题"
          + (f"（其中崩溃级 {n_crash} 处）" if n_crash else "（无崩溃级）"))
    sys.exit(1)


if __name__ == "__main__":
    main()
