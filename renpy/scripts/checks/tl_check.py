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

可选检查（默认关闭，显式传参才跑；思路取自 AiNiee 的 TranslationChecker）：
  --glossary <术语表>   术语一致性：原文命中词条、译文却没出现定稿译名 →
                        [术语] 术语未落实。支持 .xlsx（三栏 原文|译文|备注，
                        zipfile+ElementTree 零依赖读取）/ .jsonl / .json。
  --lang-ratio <阈值>   语言不匹配分块判定：按 20 行分块统计「看得出是目标
                        语言」的行占比，低于阈值 → [显示] 语言不匹配。
                        纯启发式（假名/谚文/CJK/拉丁字母），不是语言模型，
                        所以只做块级判定，单行误判会被窗口稀释。

鲁棒性说明：
  - 说话人识别支持带点表达式（mc.name，Lab Rats 2 类游戏占台词两成）、
    下标（the_group[0]）、引号字面量（"Janitor"，动态角色名）——以前只认
    \w+ 时这类台词整段漏检。
  - 插值提取用 shared/rpy_syntax.iter_bracket_groups（嵌套感知、字符串感知、
    遮蔽 {a=[url]} 标签参数），[len(x[i])] 提取完整外层而不是内层碎片；
    rpy_syntax 不可用时退回单层正则。
  - 原文本身未闭合/不平衡时豁免译文——那是源头错误，译文保持原样不背锅。
  - --fix --add-tflag：给译文中与原文一致的裸插值补 !t 旗标（值先过
    strings 表，中文名经 [mc.name] 显示时必须）；思路来自 renpy-translator
    项目的 add_tflag，代码为独立重写。

用法:
  python tl_check.py <项目根目录或game目录> [--lang schinese] [--fix]
                     [--add-tflag] [--max-examples N]
                     [--glossary 术语表.xlsx] [--lang-ratio 0.75]

退出码: 0=无崩溃/显示/术语问题(可有提示级), 1=有, 2=路径或输入错误
"""

import argparse
import ast
import json
import os
import re
import sys
from pathlib import Path

# shared/rpy_syntax 提供嵌套+字符串感知的插值扫描；不可用时退回单层正则
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shared"))
# 检查器契约层（门面据此发现 name/summary/takes/requires_tl）
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shared"))
try:
    from base_checker import PROJECT, BaseChecker
except ImportError:  # 独立拷贝运行时降级：无 CHECKER，门面也发现不了它
    PROJECT, BaseChecker = "project", object
try:
    from lang_names import DEFAULT_LANG
except ImportError:  # 独立拷贝运行时降级
    DEFAULT_LANG = "schinese"
# 同目录模块（tag_repair 等）在被当作脚本直接启动时也要能 import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from rpy_syntax import iter_bracket_groups as _iter_bracket_groups
    from rpy_syntax import find_string_literal, replace_literal_content
except ImportError:  # 独立拷贝运行时退化为内置实现
    _iter_bracket_groups = None
    find_string_literal = None
    replace_literal_content = None
# 写回安全网：--fix 落盘前确保同目录 .bak（fail-closed），与其余写工具一致
try:
    from backup import atomic_write_text as _atomic_write_text
except ImportError:  # 独立拷贝运行时退化为直接写
    _atomic_write_text = None

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


# 项目自定义标签的注册形态：
#   config.custom_text_tags["name"] = fn      （新旧两种引擎写法）
#   renpy.register_text_tag("name")           （7.4+ 推荐写法）
#   config.self_closing_custom_text_tags["name"] = fn（不接受关闭的自定义标签）
_CUSTOM_TAG_RES = (
    re.compile(r'config\.custom_text_tags\s*\[\s*["\'](\w+)["\']\s*\]'),
    re.compile(r'renpy\.register_text_tag\(\s*["\'](\w+)["\']'),
)
_SELF_CLOSING_RES = re.compile(r'config\.self_closing_custom_text_tags\s*\[\s*["\'](\w+)["\']\s*\]')


def detect_custom_tags(game_dir: Path):
    """收集项目 .rpy 里注册的自定义文本标签。

    动态文本游戏（kinetic_text_tags 类）会注册 {chaos}/{bt} 这类标签，
    不识别的话每次都报"未知标签/关闭无开放标签"误报——实测 AfterDark
    0.26 一次 5 处全是这种。返回 (tags, self_closing)。"""
    tags, self_closing = set(), set()
    for p in game_dir.rglob("*.rpy"):
        if "tl" in p.parts:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for rx in _CUSTOM_TAG_RES:
            tags.update(rx.findall(text))
        self_closing.update(_SELF_CLOSING_RES.findall(text))
    return tags - self_closing, self_closing


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


def _old_escapes_pct(old: str) -> bool:
    """原文里是否把字面百分号写成了 %%。

    用于区分「译文漏转义（翻译引入的崩溃）」和「原作自己就没转义
    （上游 bug，译文照抄不算错）」。原文出现 %% 即证明这个 % 是字面量，
    作者知道要转义 —— 译文漏掉一个 % 就是翻译的锅。
    """
    return "%%" in (old or "")


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


# ---- 术语一致性（--glossary）：原文命中词条 → 译文必须含定稿译名 ----

# 表头行（AI 定稿/AiNiee 导出的首行）不该被当成词条
_GLOSSARY_HEADER = {"原文", "源文", "source", "src", "term", "en"}
_GLOSSARY_HEADER_DST = {"译文", "dst", "translation", "zh", "new"}
# 纯 ASCII 词条走整词边界匹配；含非 ASCII（日文/符号）的走子串
_ASCII_TERM_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 .,_'\-&!?]*$")


def _xlsx_col_index(ref: str) -> int:
    """xlsx 单元格引用 'B7' → 1（0 基列号）。"""
    n = 0
    for ch in ref:
        if not ch.isalpha():
            break
        n = n * 26 + (ord(ch.upper()) - 64)
    return n - 1


def read_xlsx_rows(path: Path):
    """零依赖读 xlsx 首个工作表 → [[cell, ...], ...]；读不出返回 None。

    xlsx 本质是 zip + XML，用标准库（zipfile + ElementTree）就能读，不必
    为此引入 openpyxl 依赖——本套工具的定位是纯标准库。只认常规形态：
    sharedStrings 索引字符串、内联字符串、数字/普通文本。
    """
    import xml.etree.ElementTree as ET
    import zipfile

    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    try:
        with zipfile.ZipFile(path) as z:
            names = set(z.namelist())
            shared = []
            if "xl/sharedStrings.xml" in names:
                root = ET.fromstring(z.read("xl/sharedStrings.xml"))
                for si in root.iter(f"{ns}si"):
                    shared.append("".join(t.text or "" for t in si.iter(f"{ns}t")))
            sheet = next(
                (n for n in sorted(names)
                 if n.startswith("xl/worksheets/") and n.endswith(".xml")),
                None,
            )
            if sheet is None:
                return None
            root = ET.fromstring(z.read(sheet))
            rows = []
            for row in root.iter(f"{ns}row"):
                cells: dict = {}
                for i, c in enumerate(row.findall(f"{ns}c")):
                    ref = c.get("r") or ""
                    col = _xlsx_col_index(ref) if ref else i
                    ctype = c.get("t")
                    if ctype == "inlineStr":
                        holder = c.find(f"{ns}is")
                        value = ("" if holder is None else
                                 "".join(t.text or "" for t in holder.iter(f"{ns}t")))
                    else:
                        v = c.find(f"{ns}v")
                        raw = (v.text or "") if v is not None and v.text else ""
                        if ctype == "s" and raw.isdigit() and int(raw) < len(shared):
                            value = shared[int(raw)]
                        else:
                            value = raw
                    cells[col] = value
                if cells:
                    rows.append([cells.get(i, "") for i in range(max(cells) + 1)])
            return rows
    except Exception:  # zip/Xml 结构不符一律当读不出，交给调用方报错
        return None


def load_glossary_terms(path):
    """读术语表 → [(src, dst, matcher)]（去重保序）。

    --glossary 是用户显式点名的输入，读不出就 fail-closed 退出——静默跳过
    会让检查变成假绿。空 dst 的行（资格待定）丢弃：没有「定稿译名」就无从
    核对一致性。单字母 ASCII 词条（I/a）匹配面太宽，一律不收。
    """
    p = Path(path)
    if not p.is_file():
        print(f"[错误] 术语表不存在: {path}", file=sys.stderr)
        sys.exit(2)

    rows = []
    if p.suffix.lower() == ".xlsx":
        table = read_xlsx_rows(p)
        if table is None:
            print(f"[错误] 读不出 xlsx 术语表: {path}"
                  f"（可将它在表格软件里另存为 JSON/JSONL 后再传 --glossary）",
                  file=sys.stderr)
            sys.exit(2)
        for r in table:
            src = (r[0] if len(r) > 0 else "").strip()
            dst = (r[1] if len(r) > 1 else "").strip()
            if not src:
                continue
            if src.lower() in _GLOSSARY_HEADER or dst.lower() in _GLOSSARY_HEADER_DST:
                continue  # 表头行
            rows.append((src, dst))
    else:
        try:
            text = p.read_text(encoding="utf-8-sig", errors="replace")
        except OSError as e:
            print(f"[错误] 读术语表失败 {path}: {e}", file=sys.stderr)
            sys.exit(2)
        if p.suffix.lower() == ".jsonl":
            objs = []
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    objs.append(json.loads(line))
                except ValueError:
                    continue
        else:
            try:
                data = json.loads(text)
            except ValueError as e:
                print(f"[错误] 术语表不是合法 JSON/JSONL: {path} ({e})", file=sys.stderr)
                sys.exit(2)
            if isinstance(data, dict):
                rows.extend((str(k).strip(), str(v or "").strip())
                            for k, v in data.items())
                objs = []
            else:
                objs = data if isinstance(data, list) else []
        for o in objs:
            if not isinstance(o, dict):
                continue
            src = str(o.get("src") or o.get("en") or o.get("old") or "").strip()
            dst = str(o.get("dst") or o.get("zh") or o.get("new") or "").strip()
            if src:
                rows.append((src, dst))

    terms, seen = [], set()
    for src, dst in rows:
        if not src or not dst or src in seen:
            continue
        if len(src) < 2 and src.isascii():  # "I"/"a" 这类匹配面过宽
            continue
        seen.add(src)
        terms.append((src, dst, _term_matcher(src)))
    return terms


def _term_matcher(src: str):
    """词条匹配器：纯 ASCII 走整词边界、大小写不敏感；其余走原样子串。

    整词边界是必需的——术语表里的 "Ann" 不能命中原文的 "Announce"
    （与 AiNiee 术语检查的 whole_word 选项同一目的）。
    """
    if _ASCII_TERM_RE.match(src):
        return re.compile(r"(?<![0-9A-Za-z])" + re.escape(src) + r"(?![0-9A-Za-z])",
                          re.IGNORECASE)
    return re.compile(re.escape(src))


def check_terms(old: str, new: str, ctx: str, issues: list, terms):
    """术语一致性：原文命中词条、译文却没出现定稿译名 → [术语] 术语未落实。

    只查「原文有、译名没有」这一个方向：译名出现即达标，不追究位置，也不
    追究是否带括注（"艾琳（Eileen）" 仍算用了定稿译名）。
    """
    if not terms or not old.strip() or not new.strip():
        return
    old_lower = old.lower()
    for src, dst, matcher in terms:
        if dst in new:
            continue
        # 廉价预筛，避免大术语表 × 大工程时做几十万次正则：命中必须包含首字符，
        # 且不可能比原文还长（两条都只可能漏掉不可能命中的词条，不会漏报）
        if len(src) > len(old) or src[0].lower() not in old_lower:
            continue
        if matcher.search(old):
            issues.append((ctx, "术语", "术语未落实",
                           f'原文含 "{src}"，译文未见定稿译名 "{dst}"'))


def compare(old: str, new: str, ctx: str, issues: list, kana_check=True,
            terms=None, lang_rows=None):
    """old==new 的条目走未翻译统计，这里只查差异问题。"""
    if not old.strip():
        return  # old 为空串的配对（如语音占位行）没有参照物
    # 空译文
    if new.strip() == "":
        short = old[:36] + ("..." if len(old) > 36 else "")
        issues.append((ctx, "显示", "空译文", f'old="{short}"'))
        return
    # 语言分块判定的样本：new==old 的未翻译行不进（那是「未翻译」通道的活），
    # 空译文也不进（没有可判定的内容）
    if lang_rows is not None:
        lang_rows.append((ctx, new))
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
    # 1b. 裸 % 后跟非合法类型字符 —— 真崩溃源。
    #     Ren'Py 对白走 `%` 格式化（renpy/text/text.py 的 Text 会做
    #     substitute），"90%确定" 里 %确 被当成转换说明符 →
    #     "Unknown string format code '%确'"。字面百分号必须写成 %%。
    #     判据：原文里同样的 % 是 %% 转义，译文却漏成一个 → 必然崩。
    #     原文自己就没转义（原作 bug）时豁免，译文不背锅。
    for full, name, tch in np_:
        if name is not None:
            continue                      # %(name)x 由上面两条规则覆盖
        # 原文用 %% 说明这个 % 是字面量 → 译文漏成一个就该报；
        # 原文自己没转义（原作 bug）时豁免，译文照抄不背锅。
        if tch not in VALID_FORMAT_TYPES and _old_escapes_pct(old):
            issues.append((ctx, "崩溃", "裸%未转义",
                           f'"{full}" 会被引擎当作格式串解析并抛 '
                           f'"Unknown string format code \'{full}\'"；'
                           f'字面百分号应写成 "%%"'))
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
    # 2.5 崩溃级：译文里凭空出现的 [中文] 之类伪插值。上面的"多"只做新旧差集，
    #     但引擎不比对——任何 [...] 都会被 renpy.substitutions 当 Python 表达式
    #     eval。译者想把语气词"嗯"写成 [嗯] 就会 NameError 闪退（原句是纯文本
    #     时应直接写 嗯，字面方括号须转义成 [[）。这里用"非 ASCII 标识符"判定：
    #     合法的插值核心只会是变量/属性/下标等 ASCII 组合。
    for core in set(n_map):
        base = core.split("!")[0].strip()
        if not base:
            continue
        # 剥掉字符串字面量与数字后仍有非 ASCII 字母 → 必是伪插值
        stripped = re.sub(r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'', "", base)
        stripped = re.sub(r"\d+(?:\.\d+)?", "", stripped)
        if re.search(r"[^\x00-\x7F]", stripped):
            issues.append((ctx, "崩溃", "伪插值[非ASCII]",
                           f'[{core}] 会被当作 Python 表达式求值而抛 NameError；'
                           f'想输出字面方括号请写成 [[，只想加语气词则去掉括号'))
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
    # 6. 术语一致性（--glossary 才跑；放在最后，不影响上面 crash_here 的切片判定）
    check_terms(old, new, ctx, issues, terms)


# ---- 语言不匹配分块判定（--lang-ratio，默认关闭） ----
# 用字符集做启发式语言判定，不引入语言模型：本套工具是纯标准库零依赖定位。
_HANGUL_RE = re.compile(r"[\u1100-\u11ff\uac00-\ud7af]")
_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_LATIN_RE = re.compile(r"[A-Za-z]")

# --lang 值 → 语言族；不在表内的目标语言不做该项（别的语言没有可靠启发式）
_TARGET_LANG_FAMILY = {
    "schinese": "zh", "simplified_chinese": "zh", "chinese": "zh",
    "tchinese": "zh", "traditional_chinese": "zh",
    "japanese": "ja", "korean": "ko", "english": "latin",
}


def target_lang_family(lang: str):
    return _TARGET_LANG_FAMILY.get((lang or "").strip().lower().replace("-", "_"))


def _has_language_info(text: str) -> bool:
    """该行是否值得参与语言判定（纯数字/符号行没有语言信息）。"""
    if has_kana(text) or _HANGUL_RE.search(text) or _CJK_RE.search(text):
        return True
    return len(_LATIN_RE.findall(text)) >= 3


def _is_target_text(text: str, family: str) -> bool:
    """一行译文是否看得出是目标语言（启发式）。"""
    kana = has_kana(text)
    hangul = _HANGUL_RE.search(text) is not None
    cjk = _CJK_RE.search(text) is not None
    latin = len(_LATIN_RE.findall(text))
    if family == "ja":
        # 汉字行在日语里也常见，但纯英文字母行不算；含谚文则不是日语
        return kana or (cjk and not hangul and latin == 0)
    if family == "ko":
        return hangul
    if family == "zh":
        # 夹假名 → 是日文残留，不算达标（与 [显示] 残留日文假名同口径）
        return cjk and not kana
    if family == "latin":
        letters = (latin + len(_HANGUL_RE.findall(text))
                   + len(_CJK_RE.findall(text)) + len(KANA_RE.findall(text)))
        return latin >= 3 and latin >= letters * 0.6
    return True


def lang_ratio_issues(rows, family, threshold, chunk=20, min_block=None):
    """按块统计目标语言占比，低于阈值的块报 [显示] 语言不匹配。

    rows 是 (ctx, 译文) 列表，ctx 形如 "文件.rpy:120"。只做块级判定——
    启发式单行误判（如中文句里夹一个英文单词）在 20 行窗口里会被稀释；
    块内有效样本不足时不判（样本太少，报出来就是噪音）。
    """
    min_block = min_block or max(3, chunk // 4)
    by_file: dict = {}
    for ctx, text in rows:
        label, _, lineno = ctx.rpartition(":")
        by_file.setdefault(label, []).append((lineno, text))

    out = []
    for label, items in by_file.items():
        checkable = [(ln, t) for ln, t in items if _has_language_info(t)]
        for i in range(0, len(checkable), chunk):
            block = checkable[i:i + chunk]
            if len(block) < min_block:
                continue
            bad = [(ln, t) for ln, t in block if not _is_target_text(t, family)]
            ratio = (len(block) - len(bad)) / len(block)
            if ratio >= threshold:
                continue
            sample = "；".join(f"{ln} {t.strip()[:24]}" for ln, t in bad[:3])
            out.append((
                f"{label} 行 {block[0][0]}-{block[-1][0]}", "显示", "语言不匹配",
                f"目标语言占比 {ratio:.0%} < {threshold:.0%}（{len(block)} 行样本，"
                f"其中 {len(bad)} 行不像目标语言）：{sample}"))
    return out


# ---- --fix 用：机械性修复规则（对原始行文本操作） ----

try:
    from tag_repair import repair_line as _repair_line
except ImportError:   # 单独拷贝 tl_check 时结构修复不可用，其余规则照常
    _repair_line = None


def apply_fix_rules(line: str, old_text: str | None, add_tflag=False, settle=False):
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
    # 规则F: --settle 结构层还原（标签 + 插值）。独立于上面的规范化规则：
    # 那些只处理"同一个标签写得难看"，这条处理"句子结构被破坏"，依据始终是
    # 同一 translate 块的原文注释行。详见 checks/tag_repair.py。
    if settle and _repair_line is not None and find_string_literal is not None:
        lit = find_string_literal(line)
        if lit is not None and lit.closed:
            v, notes = _repair_line(lit.value, old_text)
            if v != lit.value:
                line = replace_literal_content(line, lit, v)
                fixes.extend(notes)
    return line, fixes


def check_file(path: Path, issues: list, untranslated: list, do_fix=False,
               do_tflag=False, do_settle=False, kana_check=True, label=None,
               terms=None, lang_rows=None):
    # label：报告里显示的文件标识；递归扫描后子目录可能与顶层同名，
    # 用相对 tl 的路径避免两行 ctx 指向不同文件却无法区分
    label = label or path.name
    in_strings = False
    old, old_line, last_comment, last_comment_line = None, None, None, None

    # 读入用 utf-8-sig：有 BOM 的文件自动剥掉，与后续按行号写回保持一致。
    # 记录原始 BOM/换行风格，写回时原样还原 —— 否则 --fix 会静默改写整个
    # 文件的编码标记与行尾（Ren'Py 能读，但属于用户没要求的改动）。
    raw_bytes = path.read_bytes()
    had_bom = raw_bytes.startswith(b"\xef\xbb\xbf")
    raw_text = raw_bytes.decode("utf-8-sig", errors="replace")
    newline = "\r\n" if "\r\n" in raw_text else "\n"

    lines = raw_text.splitlines()
    edits: dict = {}  # lineno -> new line

    def maybe_fix(lineno, raw_line, old_text, kind):
        if not do_fix:
            return
        fixed, fixes = apply_fix_rules(raw_line, old_text, add_tflag=do_tflag,
                                       settle=do_settle)
        if fixes:
            edits[lineno] = fixed
            issues.append((f"{label}:{lineno}", "修复", "已自动修复(" + kind + ")",
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
                            untranslated.append((f"{label}:{lineno}", old[:60]))
                        else:
                            compare(old, text, f"{label}:{lineno}", issues, kana_check,
                                    terms=terms, lang_rows=lang_rows)
                        maybe_fix(lineno, line, old, "new行")
                    old = None
                continue

        # 对白译文行
        dm = DIALOGUE_RE.match(line)
        if dm and last_comment is not None:
            new_text = unescape('"' + dm.group(1) + '"')
            if last_comment == new_text and (latin_words(last_comment) or (kana_check and has_kana(last_comment))):
                untranslated.append((f"{label}:{lineno}", new_text[:60]))
            else:
                compare(last_comment, new_text, f"{label}:{lineno}", issues, kana_check,
                        terms=terms, lang_rows=lang_rows)
            maybe_fix(lineno, line, last_comment, "对白")
            last_comment = None
        # 译文行没有对应的 # 原文注释（少见），拿不到原文，跳过

    if edits:
        for ln, newline_text in edits.items():
            lines[ln - 1] = newline_text
        out = newline.join(lines) + newline
        if had_bom:
            out = "\ufeff" + out
        # newline="" 原样写入，保住上面检测到的换行风格与 BOM；
        # backup=True 走 fail-closed：备份失败即中止，不覆盖原文件。
        if _atomic_write_text is not None:
            _atomic_write_text(str(path), out, encoding="utf-8",
                               backup=True, newline="")
        else:
            path.write_bytes(out.encode("utf-8"))


class TlCheckChecker(BaseChecker):
    """tl 翻译文件质检（门面子命令 tlcheck，参与 `all`）。

    只读说明：唯一的写操作（path.write_bytes）在 --fix 分支内，默认关闭；
    门面 `all` 从不传 --fix，故参与 all 时是纯只读。与 `git status` 同理——
    工具具备写能力不违反只读契约，只要默认路径不写。
    """

    name = "tlcheck"
    summary = ("tl 翻译文件质检：崩溃级/显示级/提示级三级报告（--fix 才写盘；"
               "--glossary 术语一致性、--lang-ratio 语言分块判定为可选维度）")
    takes = PROJECT
    requires_tl = True


CHECKER = TlCheckChecker()


def main():
    ap = argparse.ArgumentParser(description="Ren'Py 翻译文件静态质检 v3")
    ap.add_argument("path", help="项目根目录或 game 目录")
    ap.add_argument("--lang", default=DEFAULT_LANG)
    ap.add_argument("-l", "--language", dest="lang2", default=None,
                    help="兼容 all 透传（--lang 已覆盖；不参与逻辑）")
    ap.add_argument("--fix", action="store_true",
                    help="自动修复机械性问题：%%(name)丢s、%%(变量名被翻译)、花括号内空格/大写的简单标签")
    ap.add_argument("--add-tflag", action="store_true",
                    help="配合 --fix：给译文中与原文一致的裸插值补 !t 旗标（值先过 strings 表，中文名经 [mc.name] 显示时必需）")
    ap.add_argument("--max-examples", type=int, default=15,
                    help="每类问题最多打印的明细条数（默认 15，其余只计总数）")
    ap.add_argument("--settle", action="store_true",
                    help="配合 --fix：把译文的标签与插值结构还原到原文注释行"
                         "（修 {i>／{i]／孤立 {/i}／{我}，以及 [PN]、[中文变量] 等被改名的插值）。"
                         "只改符号层不动措辞，详见 references/tl_check.md")
    ap.add_argument("--glossary", default=None, metavar="FILE",
                    help="术语表路径（.xlsx 三栏 原文|译文|备注 / .jsonl / .json）："
                         "原文命中词条而译文没出现定稿译名时报 [术语] 术语未落实")
    ap.add_argument("--lang-ratio", type=float, default=None, metavar="THRESHOLD",
                    help="启用语言不匹配分块判定：按 20 行分块，目标语言占比低于该阈值"
                         "（0-1，如 0.75）的块报 [显示] 语言不匹配。默认关闭（启发式，"
                         "只对 schinese/tchinese/japanese/korean/english 生效）")
    args = ap.parse_args()

    if args.add_tflag and not args.fix:
        print("[错误] --add-tflag 需要与 --fix 一起使用", file=sys.stderr)
        sys.exit(2)
    if args.settle and not args.fix:
        print("[错误] --settle 需要与 --fix 一起使用", file=sys.stderr)
        sys.exit(2)
    if args.lang_ratio is not None and not (0.0 < args.lang_ratio <= 1.0):
        print("[错误] --lang-ratio 需在 (0, 1] 区间，如 0.75", file=sys.stderr)
        sys.exit(2)

    terms = load_glossary_terms(args.glossary) if args.glossary else []
    if args.glossary and not terms:
        print(f"[警告] 术语表 {args.glossary} 里没有可用词条（需要非空 src+dst）",
              file=sys.stderr)

    lang_family = target_lang_family(args.lang) if args.lang_ratio is not None else None
    if args.lang_ratio is not None and lang_family is None:
        print(f"[警告] --lang-ratio 暂不支持目标语言 '{args.lang}'，本次跳过语言分块判定",
              file=sys.stderr)

    base = Path(args.path)
    tl = find_tl_dir(base, args.lang)
    if not tl:
        print(f"[错误] 在 {args.path} 下找不到 tl/{args.lang}", file=sys.stderr)
        sys.exit(2)

    game_dir = tl.parent.parent  # tl/<lang> → game
    safe_text = detect_safe_text(game_dir)
    # 项目自定义标签并入已知集合（不接受关闭的进 NO_CLOSE_TAGS）
    custom_tags, custom_self_closing = detect_custom_tags(game_dir)
    KNOWN_TAGS.update(custom_tags)
    NO_CLOSE_TAGS.update(custom_self_closing)

    issues: list = []          # (ctx, 级别, 类型, 明细)
    untranslated: list = []    # (ctx, 文本)
    lang_rows: list = [] if lang_family else None   # (ctx, 译文) 供语言分块判定
    # 递归扫描：发行项目的 tl 常按 game/ 目录镜像分子目录（Girls Scripts/ 等），
    # 只扫顶层会漏掉大多数翻译文件
    files = sorted(list(tl.rglob("*.rpy")) + list(tl.rglob("*.rpym")))
    # 假名检查只对非日语目标语言有意义（--lang ja* 时假名是正文）
    kana_check = not args.lang.lower().startswith("ja")
    for f in files:
        check_file(f, issues, untranslated, do_fix=args.fix,
                   do_tflag=args.add_tflag, do_settle=args.settle,
                   kana_check=kana_check,
                   label=f.relative_to(tl).as_posix(),
                   terms=terms, lang_rows=lang_rows)

    if lang_rows is not None:
        issues.extend(lang_ratio_issues(lang_rows, lang_family, args.lang_ratio))

    # 项目开启 safe_text 时，未知标签显示为字面文字，不崩溃 → 降级
    if safe_text:
        issues = [(c, "显示" if lv == "崩溃" and t == "未知文本标签" else lv, t, d)
                  for c, lv, t, d in issues]

    print(f"扫描 {len(files)} 个文件: {tl}"
          + ("（检测到 config.safe_text=True，未知标签降级为显示级）" if safe_text else ""))
    if terms:
        print(f"术语表: {args.glossary}（{len(terms)} 条，核对译文是否落实定稿译名）")
    if lang_family:
        print(f"语言分块判定: 目标语言族 {lang_family}，块内占比 < {args.lang_ratio:.0%} 报问题")

    if untranslated:
        print(f"\n== [提示] 未翻译 new==old ({len(untranslated)} 处) ==")
        for ctx, txt in untranslated[:args.max_examples]:
            print(f"  {ctx}: {txt}")
        if len(untranslated) > args.max_examples:
            print(f"  ... 其余 {len(untranslated) - args.max_examples} 条省略")

    if not issues:
        print("\nOK 未发现崩溃/显示/术语隐患"
              + (f"（另有 {len(untranslated)} 处未翻译）" if untranslated else ""))
        if args.lang_ratio is not None and lang_family:
            print(f"     语言分块判定（占比 < {args.lang_ratio:.0%} 报问题）：未发现异常")
        sys.exit(0)

    order = {"崩溃": 0, "显示": 1, "修复": 2, "术语": 3}
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
    n_term = sum(1 for _, lv, _, _ in issues if lv == "术语")
    print(f"\n共 {len(issues)} 处问题"
          + (f"（其中崩溃级 {n_crash} 处）" if n_crash else "（无崩溃级）")
          + (f"（术语级 {n_term} 处）" if n_term else ""))

    # 与 checks/ 同类的交叉说明：同一次 `all` 里还有别的检查器会碰同一批句子，
    # 口径不同会让人以为重复报警。说清谁看什么，避免用户二选一选错。
    print("\n注：本工具按「句」比对 old/new（含崩溃级分级）；同批句子在 `all` 里")
    print("    还会被 untranslated（只看 new 是否为空/等于 old）与 integrity")
    print("    （变量/标签结构/转义）各看一遍。三者视角不同、互不取代：")
    print("      · 要修（--fix）→ 用本工具，只有它带自动修复")
    print("      · 只要空译文清单 → untranslated 更快（还支持 --csv）")
    print("      · 要变量/转义层面的结构比对 → integrity")
    print("    另有两条可选维度默认关闭：--glossary 术语一致性、")
    print("    --lang-ratio 语言分块判定（都不参与 `all`，需要时显式打开）。")
    sys.exit(1)


if __name__ == "__main__":
    main()
