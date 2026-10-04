#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
tl_check.py — Ren'Py 翻译文件静态质检器 v3
扫描 game/tl/<lang>/*.rpy，不启动游戏即可找出会崩溃或显示异常的问题。
覆盖两种翻译结构：
  A. 字符串翻译   old "..." / new "..."        （gui、common 的 strings 块）
  B. 对白翻译     translate 块内  # 原文行 + 译文对白行

问题分级（v3）：
  [崩溃] 会让 Ren'Py 抛异常：未知文本标签({REDACTED})、关闭无开放标签、
         关闭不接受关闭的标签({/w})、未闭合大括号、未闭合 [（渲染时抛
         "String ends with an open format operation"）、%(name)s 丢类型字符。
         依据引擎源码行为模拟（renpy/text/text.py + extras.py）：
         标签大小写敏感、花括号内空格不剥离、config.safe_text=False
         （默认）时未知标签直接 raise。项目若开启 safe_text 自动降级。
  [显示] 不崩溃但显示错误：标签新旧不一致、全角伪标签(【i】)、空译文、
         [] 插值不匹配、译文新增换行符（原文的 \n 转义被展开/擅自断行）、
         残留日文假名（译文夹 そりゃ 这类残片；--lang 以 ja 开头时自动跳过）
  [提示] 不影响运行：new 与 old 完全相同的未翻译行、裸 %（Ren'Py 8 对白
         不做 % 格式化，裸 % 是字面量，通常安全；--fix 也不再动它）

鲁棒性说明：
  - 说话人识别支持带点表达式（mc.name，Lab Rats 2 类游戏占台词两成）、
    下标（the_group[0]）、引号字面量（"Janitor"，动态角色名）——以前只认
    \w+ 时这类台词整段漏检。
  - 插值提取用 公共/rpy_syntax.iter_bracket_groups（嵌套感知、字符串感知、
    遮蔽 {a=[url]} 标签参数），[len(x[i])] 提取完整外层而不是内层碎片；
    rpy_syntax 不可用时退回单层正则。
  - 原文本身未闭合/不平衡时豁免译文——那是源头错误，译文保持原样不背锅。
  - --fix --add-tflag：给译文中与原文一致的裸插值补 !t 旗标（值先过
    strings 表，中文名经 [mc.name] 显示时必须）；思路来自 renpy-translator
    项目的 add_tflag，代码为独立重写。

用法:
  python tl_check.py <项目根目录或game目录> [--lang schinese] [--fix]
                     [--add-tflag] [--max-examples N]

退出码: 0=无崩溃/显示问题(可有提示级), 1=有崩溃或显示问题, 2=路径错误
"""

import argparse
import ast
import os
import re
import sys
from pathlib import Path

# 公共/rpy_syntax 提供嵌套+字符串感知的插值扫描；不可用时退回单层正则
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "公共"))
try:
    from rpy_syntax import iter_bracket_groups as _iter_bracket_groups
    from rpy_syntax import find_string_literal, replace_literal_content
except ImportError:  # 独立拷贝运行时退化为内置实现
    _iter_bracket_groups = None
    find_string_literal = None
    replace_literal_content = None

VALID_FORMAT_TYPES = set("srdiouxXeEfFgGca%")
TRANSLATE_RE = re.compile(r"^translate\s+(\w+)(?:\s+(\w+))?\s*:\s*$")
# 说话人前缀：标识符（可带点/下标：mc.name、the_group[0]）、引号字面量
# （"Janitor"，动态角色名），可带小写属性前缀（e happy），支持 extend
_SPEAKER_PREFIX = (
    r'(?:(?:extend\s+)?'
    r'(?:[A-Za-z_][A-Za-z0-9_.\[\]]*|"(?:[^"\\]|\\.)*")'
    r'(?:\s+[a-z_]\w*)*\s+)?'
)
# 对白行：说话人前缀 + 引号串
DIALOGUE_RE = re.compile(r'^\s*' + _SPEAKER_PREFIX + r'"((?:[^"\\]|\\.)*)"\s*$')
COMMENT_DLG_RE = re.compile(r'^\s*#\s*' + _SPEAKER_PREFIX + r'"((?:[^"\\]|\\.)*)"\s*$')
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

# 日文假名（平假名 U+3041-309F + 片假名/长音符 U+30A0-30FF）。汉字不算——
# 中日共用汉字，"先輩"这类词译不译见仁见智，报了就是噪音；假名在中文译文
# 里几乎必然是机翻残留（如"你没想？そりゃ当然没想"）
KANA_RE = re.compile(r"[\u3041-\u30FF]+")


def has_kana(s: str) -> bool:
    return KANA_RE.search(s) is not None


def kana_runs(s: str) -> list:
    """文本中的假名连续片段（去重保序，最多取前 5 段用于展示）。"""
    seen, out = set(), []
    for m in KANA_RE.finditer(s):
        frag = m.group(0)
        if frag not in seen:
            seen.add(frag)
            out.append(frag)
    return out[:5]

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
    """提取插值表达式集合（strip 归一）。优先用 rpy_syntax 的嵌套感知扫描
    （[len(x[i])] 提取完整外层，且遮蔽 {a=[url]} 标签参数）；不可用时退回
    单层正则。"""
    if _iter_bracket_groups is not None:
        return sorted({c.strip() for c, _ in _iter_bracket_groups(s) if c.strip()})
    return sorted({t.strip() for t in INTERP_RE.findall(s)})


def _split_interp_flags(expr: str):
    """把插值表达式拆成 (核心, 尾部旗标串)：'x!t' → ('x', '!t')。

    只剥表达式末尾的旗标链；[x != y] 这类以标识符结尾的不受影响，
    [x:.1f] 无 ! 也不受影响。"""
    m = re.search(r"(?:![a-z]+)+$", expr)
    if m:
        return expr[:m.start()].rstrip(), expr[m.start():]
    return expr, ""


def brackets_unbalanced(s: str) -> bool:
    """未闭合 [ 检测（[[ 转义先跳过，孤立 ] 视为字面字符）。

    Ren'Py 渲染未闭合的 [ 时直接抛 "String ends with an open format
    operation"。嵌套合法（[len(x[i])] 深度归零）。"""
    depth = 0
    i = 0
    while i < len(s):
        if s.startswith("[[", i):
            i += 2
            continue
        if s[i] == "[":
            depth += 1
        elif s[i] == "]" and depth > 0:
            depth -= 1
        i += 1
    return depth > 0


def _tflag_expr(expr: str):
    """判定插值可否补 !t：可补返回补好旗标的表达式，不可补返回 None。

    不可补：带顶层格式规格（[x:.1f]——!t 把值变成字符串后 format 必炸）；
    含花括号占位（[{0}] 是 .format 的字面文本，加 !t 会被当变量 eval）；
    旗标链已含 t（幂等）；含裸 ! 的复杂表达式（Ren'Py 按 ! 切旗标，
    无法安全追加）。可补：无旗标（→ expr!t）/ 有旗标无 t（追加链尾）。"""
    depth = 0
    for ch in expr:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        elif ch == ":" and depth == 0:
            return None
    if "{" in expr or "}" in expr:
        return None
    if "!" not in expr:
        return expr + "!t"
    for m in re.finditer(r"!([a-zA-Z])", expr):
        flags = expr[m.end() - 1:]
        if re.fullmatch(r"[a-z]+", flags):
            return None if "t" in flags else expr + "t"
    return None


def add_t_flags(text: str, allowed=None):
    """给文本里每个最外层插值补 !t 旗标（值通道翻译），返回 (新文本, 是否改动)。

    [x] 的值渲染时原样插入；[x!t] 的值先过 strings 表查找——游戏把名字
    存在变量里（[mc.name] → "Luna"）而 strings 表有 old "Luna" 时，必须
    补 !t 中文名才会生效。嵌套感知（[d[_return][0]] → [d[_return][0]!t]）；
    [[ 转义不动；未闭合的尾部不动。allowed 给定时只补该集合内的表达式
    （防给译文误造的插值上旗标）。"""
    t = text.replace("[[", "\x00")
    inserts = []  # (起点, 终点, 替换片段)
    depth = 0
    start = -1
    for i, ch in enumerate(t):
        if ch == "[":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "]" and depth > 0:
            depth -= 1
            if depth == 0:
                expr = t[start + 1:i]
                stripped = expr.strip()
                if stripped and (allowed is None or stripped in allowed):
                    fixed = _tflag_expr(stripped)
                    if fixed is not None and fixed != stripped:
                        lead = expr[:len(expr) - len(expr.lstrip())]
                        trail = expr[len(expr.rstrip()):]
                        inserts.append((start, i, lead + fixed + trail))
                start = -1
    if not inserts:
        return text, False
    # 自后向前插入，保持前部偏移有效
    for pos, end, repl in reversed(inserts):
        t = t[:pos + 1] + repl + t[end:]
    return t.replace("\x00", "[["), True


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


def compare(old: str, new: str, ctx: str, issues: list, kana_check=True):
    """old==new 的条目走未翻译统计，这里只查差异问题。"""
    if not old.strip():
        return  # old 为空串的配对（如语音占位行）没有参照物
    # 空译文
    if new.strip() == "":
        short = old[:36] + ("..." if len(old) > 36 else "")
        issues.append((ctx, "显示", "空译文", f'old="{short}"'))
        return
    # 0. 未闭合 [（崩溃级；原文本身未闭合是源头错误，豁免译文）
    if brackets_unbalanced(new) and not brackets_unbalanced(old):
        issues.append((ctx, "崩溃", "未闭合[插值",
                       '译文存在未闭合的 [，渲染该句时引擎抛 "String ends with '
                       'an open format operation"；字面方括号应写成 [['))
    # 0.5 新增换行符（显示级）：AI 把原文的 \n 转义"贴心"展开/擅自加断行，
    # 计数式判定——译文换行数超过原文即为违规；原文有换行而译文合并断行
    # 不拦（中英文排版允许不同断行）。
    if new.count("\n") > old.count("\n"):
        issues.append((ctx, "显示", "新增换行符",
                       '译文包含原文没有的换行。原文的 \\n 转义应原样保留，'
                       '不要展开成真实换行或另起断行'))
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
    # 2. [] 插值：剥掉尾部旗标（!t/!q…）后比核心表达式——译文给插值补
    #    !t 是合法修复（见 --add-tflag），删掉原文旗标才是真问题（值通道断）
    o_map: dict = {}
    for k in interp_keys(old):
        core, fl = _split_interp_flags(k)
        o_map.setdefault(core, set()).add(fl)
    n_map: dict = {}
    for k in interp_keys(new):
        core, fl = _split_interp_flags(k)
        n_map.setdefault(core, set()).add(fl)
    missing = set(o_map) - set(n_map)
    extra = set(n_map) - set(o_map)
    if missing or extra:
        detail = ((f"缺 {sorted(missing)} " if missing else "") +
                  (f"多 {sorted(extra)}" if extra else "")).strip()
        issues.append((ctx, "显示", "[]插值不匹配", detail))
    lost_flags = [c for c in set(o_map) & set(n_map)
                  if any(o_map[c]) and not any(n_map[c])]
    if lost_flags:
        shown = "、".join(f"[{c}]" for c in sorted(lost_flags)[:3])
        issues.append((ctx, "显示", "插值旗标丢失",
                       f"{shown} 原文带旗标（如 !t 值通道），译文不能删掉"))
    # 3. {} 标签：先查崩溃级（引擎行为），再查新旧差异（显示级）。
    #    原文本身有未闭合大括号时豁免译文的同类问题——源头错误不背锅
    probs = tag_problems(new)
    if any(not closed for _, closed in tokenize_tags(old)):
        probs = [(frag, typ) for frag, typ in probs if typ != "未闭合大括号"]
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
    # 5. 残留日文假名（显示级）：整句译了但夹着假名残片（new==old 的整句
    #    未翻译在 compare 之前已被拦截，走到这里的都值得报）。目标语言是
    #    日语（--lang ja…）时假名是正文，不查。
    if kana_check:
        runs = kana_runs(new)
        if runs:
            issues.append((ctx, "显示", "残留日文假名",
                           "译文含假名残片 " + "、".join(f'"{r}"' for r in runs)
                           + "，机翻/人工漏翻；若是刻意保留的日文台词请人工确认"))


# ---- --fix 用：机械性修复规则（对原始行文本操作） ----

def apply_fix_rules(line: str, old_text: str | None, add_tflag=False):
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
    # 规则E: --add-tflag 给与原文一致的裸插值补 !t（值通道过 strings 表）。
    # 用 find_string_literal 定位首个字面量并取未转义值处理，写回时重新
    # 编码，避免 \n/\" 等转义与 [[ 假插值干扰扫描。allowed 取自 old，
    # 防止给译文误造的插值上旗标。
    if add_tflag and find_string_literal is not None:
        lit = find_string_literal(line)
        if lit is not None and lit.closed:
            allowed = set(interp_keys(old_text)) if old_text else set()
            new_value, changed = add_t_flags(lit.value, allowed)
            if changed:
                line = replace_literal_content(line, lit, new_value)
                fixes.append('补 !t 旗标（插值值通道过 strings 表）')
    return line, fixes


def check_file(path: Path, issues: list, untranslated: list, do_fix=False,
               do_tflag=False, kana_check=True):
    in_strings = False
    old, old_line, last_comment, last_comment_line = None, None, None, None

    lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    edits: dict = {}  # lineno -> new line

    def maybe_fix(lineno, raw_line, old_text, kind):
        if not do_fix:
            return
        fixed, fixes = apply_fix_rules(raw_line, old_text, add_tflag=do_tflag)
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
                        if old == text and (latin_words(old) or (kana_check and has_kana(old))):
                            untranslated.append((f"{path.name}:{lineno}", old[:60]))
                        else:
                            compare(old, text, f"{path.name}:{lineno}", issues, kana_check)
                        maybe_fix(lineno, line, old, "new行")
                    old = None
                continue

        # 对白译文行
        dm = DIALOGUE_RE.match(line)
        if dm and last_comment is not None:
            new_text = unescape('"' + dm.group(1) + '"')
            if last_comment == new_text and (latin_words(last_comment) or (kana_check and has_kana(last_comment))):
                untranslated.append((f"{path.name}:{lineno}", new_text[:60]))
            else:
                compare(last_comment, new_text, f"{path.name}:{lineno}", issues, kana_check)
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
    ap.add_argument("--add-tflag", action="store_true",
                    help="配合 --fix：给译文中与原文一致的裸插值补 !t 旗标（值先过 strings 表，中文名经 [mc.name] 显示时必需）")
    ap.add_argument("--max-examples", type=int, default=15,
                    help="每类问题最多打印的明细条数（默认 15，其余只计总数）")
    args = ap.parse_args()

    if args.add_tflag and not args.fix:
        print("[错误] --add-tflag 需要与 --fix 一起使用", file=sys.stderr)
        sys.exit(2)

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
    # 假名检查只对非日语目标语言有意义（--lang ja* 时假名是正文）
    kana_check = not args.lang.lower().startswith("ja")
    for f in files:
        check_file(f, issues, untranslated, do_fix=args.fix,
                   do_tflag=args.add_tflag, kana_check=kana_check)

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
