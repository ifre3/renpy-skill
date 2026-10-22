#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
tag_repair.py — 标签/插值结构修复层（供 tl_check --fix --settle 调用）

为什么单独成模块
----------------
翻译管线（尤其 AI 机翻）在句首句尾丢符号是成体系的损伤，产出这几类形态：

    {i>…        {i]…        {/i>      开/闭标签右侧符号写错
    {我}        中文被包进花括号（本该是正文）
    …。{/i}     孤立闭合标签（对应开标签被吞掉）
    [PN]        插值变量被大写化（引擎插值大小写敏感 → KeyError）
    [阿梓子羁绊]  插值变量被当作文本翻译了 → KeyError
    [chyo_bond] 变量名拼错 → KeyError

这些和 tl_check 原有的规范化（去空格、转小写、补 %s）不是一类问题：后者
是「同一个标签写得难看」，前者是「句子结构被破坏」。混在一个文件里会让
apply_fix_rules 承担两种职责，所以拆出来：本模块只做**基于原文真值的结构
还原**，tl_check 负责调用与落盘。

设计原则
--------
1. **原文注释行是唯一真值**。同一 translate 块里的 `# 原文` 行结构完好，
   中文措辞无需改动 —— 修复只重写符号层，一个自然语言字符都不挪位置。
2. **纯函数**。`repair(new, old) -> (str, [说明])`，无 IO 无全局状态，便于单测。
3. **宁可不修也不错修**。修完仍不平衡就原样返回，留给人工；原作自带标签
   错误时不猜（译文不必为上游 bug 背锅）。
4. **保住语义**。孤立闭合标签默认补开标签而不是删闭合 —— 删闭合会静默丢掉
   原文的斜体/加粗强调。

引擎行为依据
------------
renpy/text/text.py 的文本标记解析：标签名大小写敏感、花括号内不 strip 空格、
`config.safe_text=False`（默认）时未知标签直接 raise；只有「接受关闭」的
标签进栈（w / p / space / vspace / fast / nw / done / image 不进栈）。

用法（通常经由 tl_check 调用，也可单独用）:
    python tag_repair.py          # 跑内置自检用例
"""

import os
import re
import sys

# shared/rpy_syntax 提供字符串感知的字面量定位；不可用时退化（仅影响行级 helper）
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shared"))

# ---- 引擎认可的标签注册表（与 tl_check 保持一致，独立模块故自带一份）----
KNOWN_TAGS = {
    "p", "space", "vspace", "w", "fast", "done", "nw", "a", "b", "i", "u",
    "s", "plain", "font", "size", "color", "outlinecolor", "alpha", "k",
    "rt", "art", "rb", "cps", "vert", "horiz", "alt", "noalt", "instance",
    "shader", "image",
}
NO_CLOSE_TAGS = {"done", "image", "p", "w", "fast", "nw", "space", "vspace"}
# 这些 tag 带值参数且必须闭合
TAG_VALUE_PREFIXES = ("a=", "font=", "size=", "color=", "outlinecolor=",
                      "alpha=", "cps=", "k=", "shader=")

_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
# 畸形右符号：{i> / {i] / {/i> / {/i] —— 名字之后本应是 }
_MALFORMED_RE = re.compile(r"\{(/)?([A-Za-z_][A-Za-z0-9_]*)(=[^{}>\]}]*)?[>\]}]")
# [tag 形式的开插值：`[cps=3}...` 是 {cps=3} 的开括号写成了 [
_BRACKETED_TAG_RE = re.compile(r"\[([A-Za-z_][A-Za-z0-9_]*=[^{}>\]}]*)[\}>]")
# 名字后面直接是 \}] 且整个[...]未配对的说话人泄漏,如 `[t>` `[sas"`
_LEAKED_PREFIX_RE = re.compile(r"(?<![{\[])\[([A-Za-z_][A-Za-z0-9_]*)[>\]}\"]")


# ---------------------------------------------------------------- 基础工具

def tokenize_tags(s):
    """模拟 Ren'Py 的 {{ 转义与 {} 切分。返回 [(inner, closed)]，
    closed=False 表示到串尾都没有 '}'。"""
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
            i = j + 1          # {{ → 字面 {，不产生标签
            continue
        tokens.append((inner, True))
        i = j + 1


def tag_problems(s, known=KNOWN_TAGS, no_close=NO_CLOSE_TAGS):
    """按引擎真实行为分析串内标签，返回 [(片段, 类型)]。

    类型：未闭合大括号 / 标签不接受关闭 / 关闭无开放标签 / 未知文本标签。
    """
    problems, stack = [], []
    for inner, closed in tokenize_tags(s):
        if not closed:
            problems.append(("{" + inner[:30], "未闭合大括号"))
            continue
        if inner.startswith("#"):
            continue                                   # {#注释}
        name = inner.split("=", 1)[0]
        if name.startswith("/"):
            open_name = name[1:]
            if open_name in no_close:
                problems.append(("{" + inner + "}", "标签不接受关闭"))
            elif not stack:
                problems.append(("{" + inner + "}", "关闭无开放标签"))
            elif stack[-1] != open_name:
                # 引擎 extras.check_text_tags 比的是**栈顶名字**，不等就报错。
                # 早先这里只做压栈计数不看名字，于是 {i}…{/s} 这类错配会被
                # 当成正常关闭而漏掉 —— 它恰恰是机翻「吞掉中间开标签」之后
                # 留下的形态，必须报出来才修得到。
                problems.append(("{" + inner + "}", "关闭标签名不匹配"))
                stack.pop()
            else:
                stack.pop()
        elif name.startswith(TAG_VALUE_PREFIXES):
            stack.append(name)
        elif name.split("=", 1)[0] in known:
            if name.split("=", 1)[0] not in no_close:
                stack.append(name.split("=", 1)[0])
        else:
            problems.append(("{" + inner + "}", "未知文本标签"))
    return problems


def _rows(s):
    """把串切成 [(kind, text)]，kind ∈ lit / esc / tag / bad。

    lit=普通文本  esc={{ 转义（字面 {）  tag=合法 {-标签  bad=未闭合 { 残片
    """
    rows, i, n = [], 0, len(s)
    while i < n:
        c = s.find("{", i)
        if c < 0:
            rows.append(("lit", s[i:]))
            break
        if c > i:
            rows.append(("lit", s[i:c]))
        if s.startswith("{{", c):
            rows.append(("esc", "{{"))
            i = c + 2
            continue
        j = s.find("}", c)
        if j < 0:
            rows.append(("bad", s[c:]))
            break
        rows.append(("tag", s[c:j + 1]))
        i = j + 1
    return rows


def _is_tag(text):
    """花括号片段是否是 {name} / {/name} / {name=val} 形态（text 含花括号）。"""
    inner = text[1:-1]
    if not inner or inner.startswith("#"):
        return inner.startswith("#") and _NAME_RE.match(inner[1:].split("=", 1)[0]) is not None
    core = inner[1:] if inner.startswith("/") else inner
    return _NAME_RE.match(core.split("=", 1)[0]) is not None


def interp_base(expr):
    """插值表达式的「核心」部分：剥掉 ! 旗标与 :格式规格。"""
    return expr.split("!")[0].split(":")[0].strip()


def interp_keys(s):
    """提取插值核心表达式列表（跳过 [[ 转义）。"""
    out, i, n = [], 0, len(s)
    while i < n:
        if s[i] == "[":
            if s.startswith("[[", i):
                i += 2
                continue
            j = s.find("]", i)
            if j < 0:
                break
            out.append(s[i + 1:j])
            i = j + 1
        else:
            i += 1
    return out


# ---------------------------------------------------------------- 标签修复

def _fix_bracket_layer(s):
    """修三种把 [ 和 { 写混 / 说话人前缀泄漏进文本的情况。

      [cps=3}...{/cps}   → {cps=3}...{/cps}    标签的开括号写成了 [
      [t>那就...          → 那就...             说话人前缀泄漏，删掉
      i]主要是             → i]]主要是           多余裸 ] 转成字面

    只在串本身方括号不平衡时才改写，避免动到 [pn] 这类正常插值。
    """
    # 0) 先不要动 {i] 这类——那是标签的右符号写错，统一由符号层处理。
    #    这里只对「方括号整体不平衡」出手，且仅限于真·泄漏/混淆。
    if s.count("[") == s.count("]"):
        return s
    out = s
    # 1) [Name=val} / [Name=val] —— 是 {Name=val} 的开括号写错
    cand = _BRACKETED_TAG_RE.sub(lambda m: "{" + m.group(1) + "}", out)
    if cand != out:
        if cand.count("[") == cand.count("]"):
            return cand
        out = cand
    # 2) 孤立 [t> / [t" —— 说话人前缀泄漏，连同右侧错符号一起删
    if out.count("[") != out.count("]"):
        cand = _LEAKED_PREFIX_RE.sub("", out)
        if cand != out:
            if cand.count("[") == cand.count("]"):
                return cand
            out = cand
    # 3) 多余的裸 ]：若是某个 {tag] 的残留 (紧跟在标签名之后) 留给符号层，
    #    其余孤立 ] 当脏字符删掉。
    diff = out.count("]") - out.count("[")
    if diff > 0:
        for _ in range(diff):
            pos = out.rfind("]")
            if pos < 0:
                break
            # ] 紧跟在一个未收口的 {tag 之后 → 那是 {i] 的尾巴，符号层会处理
            head = out[:pos]
            anch = max(head.rfind("{"), head.rfind("}"))
            if anch >= 0 and head[anch] == "{" and _NAME_RE.match(
                    head[anch + 1:].split("=")[0].rstrip("]>")):
                break
            out = out[:pos] + out[pos + 1:]
    return out


def _unwrap_sentence(s):
    """剥掉包住整句的多余花括号：{中文…{/i}} → 中文…{/i}。

    判据：串的首个 token 是 'tag' 但内容不像标签（多为中文），且整串以 }} 收尾
    —— 说明机翻给整句加了壳，真实标签被埋在里面。剥壳后交给后续规则处理。
    """
    if len(s) < 2 or not s.startswith("{") or not s.endswith("}"):
        return s
    rows = _rows(s)
    if not rows or rows[0][0] != "tag":
        return s
    if _is_tag(rows[0][1]):
        return s
    # 末尾必须是连续两个 }（外壳闭合 + 内层标签闭合），这才是"整句被包壳"的形态。
    # 也兼容已被前序规则补成形如 {X}正文{/i}} 的情况。
    if not s.rstrip().endswith("}}") or s == "{{}}":
        return s
    inner = s[1:s.rfind("}")]
    if "{/" not in inner and not s.rstrip().endswith("}}"):
        return s
    # 剥掉最外层那对：去掉首个 { 与最后那个多余的 }
    return inner


def _strip_broken(s):
    """修掉「写得不对但语义明确」的两类:畸形右符号、非法内容花括号。

    `{}{size}` 这类空/乱码花括号不在此处删:它们的正确归属要等栈式修补判定
    （可能是漏写的闭合），过早删掉会把 `{size=..}` 的闭合吞掉。
    """
    # 1) 给"忘了写右花括号"的开标签补回 }：{i…{/i} → {i}…{/i}
    #    前提是这串确实处于"开标签没收口"的状态（_right_symbol_is_typo 判定），
    #    否则会误伤 {size=-10} 这类本来就有 } 的正常标签。
    # 顺序：先剥外层壳（整句被包的情况），再逐 token 修符号。
    out = _unwrap_sentence(s)

    # ① 先给"忘了写右花括号 / 右符号写成 ] 或 >"的开标签补回 }（{i] / {i> / {i）。
    #    必须在剥 키非法花括号之前做，否则整个标签会被当成 "{中文}" 剥掉。
    out = _reclose_forgotten(out)

    rebuilt = []
    for kind, text in _rows(out):
        if kind != "tag":
            rebuilt.append((kind, text))
            continue
        inner = text[1:-1]
        if inner.startswith("#"):
            rebuilt.append((kind, text))          # {#注释} 保留原样
            continue
        core = inner[1:] if inner.startswith("/") else inner
        name = core.split("=", 1)[0]
        if not _NAME_RE.match(name):
            # 不是合法标签名：有内容就当正文（{我} → 我），空壳不动
            rebuilt.append(("lit", inner) if inner.strip() else (kind, text))
            continue
        rebuilt.append((kind, text))

    out = "".join(t for _, t in rebuilt)
    out = _MALFORMED_RE.sub(
        lambda m: "{" + (m.group(1) or "") + m.group(2) + (m.group(3) or "") + "}",
        out)
    return out


def _token_close_state(s):
    """返回一个 dict：{起始位置: 该 { 标签的状态}。

    status ∈ {'ok', 'typo_symbol', 'unclosed'}
      ok           —— 在下一个 `{` 之前就正常遇到 }
      typo_symbol  —— 中间先遇到了 ] 或 >，那才是真正的闭合（写错了符号）
      unclosed     —— 一路扫到下一个 `{` 或串尾都没闭合
    用 token 边界而不是自由正则，避免把 {size=-10} 这类正常参数标签误判。
    """
    states = {}
    i, n = 0, len(s)
    while i < n:
        if s[i] != "{":
            i += 1
            continue
        if s.startswith("{{", i):
            i += 2
            continue
        start = i
        j = i + 1
        m = re.match(r"/?[A-Za-z_][A-Za-z0-9_]*", s[j:])
        if not m:
            i += 1
            continue
        j += m.end()
        # 跳过 = 参数（参数值里允许 ] > 但不含 { }）
        if j < n and s[j] == "=":
            j += 1
            while j < n and s[j] not in "{}[]>":
                j += 1
        # 从这个位置起找真正的收口点
        k = j
        saw_typo = False
        while k < n:
            c = s[k]
            if c == "}":
                states[start] = ("typo_symbol", k) if saw_typo else ("ok", k)
                break
            if c == "{":
                states[start] = ("unclosed", k)
                break
            if c in "]>":
                saw_typo = True
            k += 1
        else:
            states[start] = ("unclosed", n)
        i = start + 1
    return states


def _reclose_forgotten(s):
    """给忘写 } 或把 } 写成 ] / > 的开标签补回 }。幂等，已正常的 {i} 不动。"""
    states = _token_close_state(s)
    edits = []          # (位置, 要插入/替换的内容) 由后往前应用
    for start, (status, close_at) in states.items():
        if status == "ok":
            continue
        # 标签主体结束的位置
        j = start + 1
        m = re.match(r"/?[A-Za-z_][A-Za-z0-9_]*", s[j:])
        j += m.end()
        if j < len(s) and s[j] == "=":
            j += 1
            while j < len(s) and s[j] not in "{}[]>":
                j += 1
        if status == "typo_symbol":
            # {i]…}：写错的是紧跟的 ] / > ，把它换回 } 即可（标签名已在[start:j)）
            tail = s[j:close_at].replace("]", "").replace(">", "")
            edits.append((start, start, close_at + 1, s[start:j] + tail + "}"))
        else:  # unclosed —— 漏写 }：紧跟的 ] / > 一并吞掉再补 }
            k = j
            while k < close_at and s[k] in "]>":
                k += 1
            edits.append((start, start, close_at, s[start:j] + "}" + s[k:close_at]))
    out = s
    for start, a, b, repl in sorted(edits, reverse=True):
        out = out[:a] + repl + out[b:]
    return out


def _open_tags_of(s):
    """串里的开标签序列（不去重，按出现顺序）。"""
    out = []
    for inner, closed in tokenize_tags(s):
        if not closed or inner.startswith("#"):
            continue
        if inner.startswith("/"):
            continue
        name = inner.split("=", 1)[0]
        if name not in NO_CLOSE_TAGS:
            out.append(name)
    return out


def repair_tags(new_value, old_value):
    """把译文的标签结构还原到与原文一致。返回 (新串, [说明])。纯函数。

    只在**原文本身标签平衡**时才动手 —— 原作有 bug 时保持译文原样，交人工。
    """
    notes = []
    if old_value is None or tag_problems(old_value):
        return new_value, notes

    s = new_value

    # 0) 方括号层（repair_line 也会跑，这里保留以免单独调用本函数时漏掉）
    cand = _fix_bracket_layer(s)
    if cand != s:
        notes.append("方括号补正")
        s = cand

    # 1) 符号层：畸形右符号 + 非法内容花括号
    if tag_problems(s):
        cand = _strip_broken(s)
        if cand != s:
            notes.append("标签符号补正")
            s = cand

    # 1b) 符号层修完可能暴露新的方括号失衡（{i] → {i} 会剩一个孤立 ]），再收一次
    cand = _fix_bracket_layer(s)
    if cand != s:
        notes.append("方括号补正")
        s = cand

    # 2) 配对层：孤立闭合补开标签；未闭合的在原处收口
    for _ in range(80):
        probs = tag_problems(s)
        if not probs:
            return s, notes
        kind = probs[0][1]
        if kind == "关闭标签名不匹配":
            # 先试「尾部补闭合」：译文丢的是闭合标签时（没有孤立闭合），
            # 把缺失的闭合按栈序补到句尾即可，中文排版一字不动。这优先于
            # 重排 —— 重排会按原文标签的相对位置把闭合插进句子中间
            # （"时间{/b}会说明一切"），把本来就通顺的译文改坏。
            cand = _close_missing_at_tail(s, old_value)
            if cand is not None and cand != s and not tag_problems(cand):
                s = cand
                notes.append("补句尾闭合")
                continue
            # 错位一格：单个标签看都没错，是序列整体缺了一层。按原文重排，
            # 这是唯一能同时摆平后续所有标签的办法。
            cand = _realign_sequence(s, old_value)
            if cand is None or tag_problems(cand):
                return s, notes
            if cand == s:
                return s, notes
            s = cand
            notes.append("标签序列重排")
        elif kind == "关闭无开放标签":
            cand = _restore_orphan(s, old_value)
            if cand is None:
                s, fb = _fallback_close(s, notes)
                notes = fb
                continue
            s = cand
            notes.append("补开标签")
        elif kind == "未闭合大括号":
            # 残片在串尾：按原文同名标签收口，否则原样返回让上层知道没修好
            cand = _close_tail(s, old_value)
            if cand is None:
                return s, notes
            s = cand
            notes.append("闭合未收口标签")
        else:
            return s, notes
    return s, notes


def _plain_and_tags(s):
    """把串拆成「纯文本」与「标签清单」。

    返回 (plain, marks)：plain 是所有 {-标签切除后剩下的文本（{{ 转义原样
    保留），marks 是 [(inner, 该标签之前的纯文本长度)]。用于按原文标签的
    相对位置，把标签重新落到译文的对应位置。
    """
    parts, marks, total = [], [], 0
    i, n = 0, len(s)
    while i < n:
        c = s.find("{", i)
        if c < 0:
            parts.append(s[i:])
            break
        j = s.find("}", c)
        if j < 0:
            parts.append(s[i:])
            break
        inner = s[c + 1:j]
        if inner.startswith("{") or inner == "":
            parts.append(s[i:j + 1])          # {{ → 字面 {，保留
            total += j + 1 - i
            i = j + 1
            continue
        parts.append(s[i:c])
        total += c - i
        marks.append((inner, total))
        i = j + 1
    return "".join(parts), marks


def _close_missing_at_tail(s, old_value):
    """串尾缺失闭合时，按栈序补上闭合标签。中文一字不动。

    例：原文 {i}{b}That{/b} is time.{/i}、译文 {i}{b}时间会说明一切。{/i}
    —— 译文的 {/i} 去关 {b}，栈顶不匹配。正确修法是在 {/i} 之前补 {/b}，
    得到 {i}{b}时间会说明一切。{/b}{/i}，而不是把 {/b} 插到句中。

    只在「该串没有孤立闭合」时适用（缺的是闭合而非开标签），与
    _realign_sequence 分工互补。
    """
    if _has_orphan_close(s):
        return None
    # 逐标签走栈。遇到闭合 {/X} 时，若栈顶不是 X，说明 X 之上有若干层
    # 没被关掉 —— 这些就是缺失的闭合（例：{i}{b}…{/i} 里 {/i} 出现时栈顶
    # 是 b，缺的是 {/b}）。把它们记下来后继续。
    stack: list = []
    missing: list = []
    for inner, closed in tokenize_tags(s):
        if not closed:
            break
        if inner.startswith("#"):
            continue
        name = inner.split("=", 1)[0]
        if name.startswith("/"):
            want = name[1:]
            if not stack:
                return None                  # 孤立闭合：不是本函数的场景
            if stack[-1] == want:
                stack.pop()
            elif want in stack:
                # 关的是外层：把压在它上面的层按顺序补闭合
                while stack and stack[-1] != want:
                    missing.append(stack.pop())
                stack.pop()
            else:
                return None
        elif (name.startswith(TAG_VALUE_PREFIXES)
              or name.split("=", 1)[0] in KNOWN_TAGS):
            if name.split("=", 1)[0] not in NO_CLOSE_TAGS:
                stack.append(name.split("=", 1)[0])
    missing.extend(reversed(stack))
    if not missing:
        return None

    # 末尾已有的闭合序列（从串尾剥出来），补的闭合要放在它们之前
    trailing = ""
    body = s
    while True:
        m = re.search(r"\{/[A-Za-z_][A-Za-z0-9_]*\}\s*$", body)
        if not m:
            break
        trailing = m.group(0) + trailing
        body = body[:m.start()]

    # 按栈的逆序（内层先关）补齐，放在已有尾部闭合之前
    add = "".join("{/" + n + "}" for n in reversed(missing))
    return body.rstrip() + add + trailing


def _has_orphan_close(s: str) -> bool:
    """串里是否存在孤立闭合标签（栈空时遇到闭合）。

    这是"丢了开标签却留下闭合"损伤的确证，也是 _realign_sequence 的适用
    前提。缺的是**闭合**标签时不成立 —— 那种情况不该重排整句。
    """
    stack = []
    for inner, closed in tokenize_tags(s):
        if not closed:
            break
        if inner.startswith("#"):
            continue
        name = inner.split("=", 1)[0]
        if name.startswith("/"):
            if not stack:
                return True
            stack.pop()
        elif (name.startswith(TAG_VALUE_PREFIXES)
              or name.split("=", 1)[0] in KNOWN_TAGS):
            if name.split("=", 1)[0] not in NO_CLOSE_TAGS:
                stack.append(name.split("=", 1)[0])
    return False


def _realign_sequence(s, old_value):
    """按原文标签序列整体重排译文的标签。解决「错位一格」型损伤。

    机翻有一种成体系的损伤：吞掉序列中间的某个**开标签**，却保留了它对应
    的闭合（例：原文 {i}A {s}said{/s} B{/i} → 译文 {i}话虽如此{/s}，…{/i}，
    丢了 {s}）。后果不是"孤立闭合"，而是后面每个标签的层级都错一格 ——
    逐个标签修补无从下手（每个标签名字单独看都不算错），必须以原文序列
    为模板整体对齐。

    做法是保留译文的**全部纯文本一字不动**，只把标签按原文中各自的相对
    位置重新落回去。位置用"标签之前的纯文本长度占比"映射，天然适配中英
    文长度差异。

    触发条件刻意收紧，避免误伤健康的句：
      · 原文的标签名集合 ⊇ 译文的标签名集合（译文没引入新标签）
      · 译文标签数 < 原文标签数（确实是丢了标签，而非多余标签）
      · **译文里存在孤立闭合**，即本函数真正对治的"丢了开标签却留下闭合"
        这一损伤形态。
        反例（曾经误伤）：原文 {i}{b}That{/b} is time.{/i}、译文
        {i}{b}时间会说明一切。{/i} —— 译文丢的是**闭合** {/b} 而不是开
        标签，没有孤立闭合。此时按位置重排会把 {/b} 插到句中（"时间{/b}
        会说明一切"），把一个只是尾部未收口的句子改得面目全非。缺闭合
        应当交给尾部补闭合的路径处理，不动中文的排版。
    返回 None 表示不适用，交由上层走别的路径。
    """
    old_plain, old_marks = _plain_and_tags(old_value)
    new_plain, new_marks = _plain_and_tags(s)
    if not old_marks:
        return None
    old_names = {m[0].split("=", 1)[0] for m in old_marks}
    new_names = {m[0].split("=", 1)[0] for m in new_marks}
    if not new_names.issubset(old_names):
        return None
    if len(new_marks) >= len(old_marks):
        return None
    if not _has_orphan_close(s):
        return None

    # 把原文每个标签的相对位置映射到译文的纯文本上
    total = len(old_plain) or 1
    nlen = len(new_plain)
    out, prev = [], 0
    for inner, off in old_marks:
        pos = int(round(off * nlen / float(total)))
        pos = max(prev, min(pos, nlen))       # 位置单调，防止标签倒挂
        out.append(new_plain[prev:pos])
        out.append("{" + inner + "}")
        prev = pos
    out.append(new_plain[prev:])
    return "".join(out)


def _restore_orphan(s, old_value):
    """给第一个孤立闭合标签补上对应的开标签。

    插入点不是「闭合前」而是**按原文语义推断的位置**：原文里这个标签包裹
    的是哪个词，译文就尽力裹住对应的词。做不到精确定位时（信息不足），
    返回 None 让上层改用「删除闭合」的保守路径 —— 宁可丢一次强调，也不
    在句尾塞一个空的 {i}{/i}。
    """
    stack = []
    target = None
    for inner, closed in tokenize_tags(s):
        if not closed:
            break
        if inner.startswith("#"):
            continue
        name = inner.split("=", 1)[0]
        if name.startswith("/"):
            if not stack:
                target = name[1:]
                break
            stack.pop()
        elif name.startswith(TAG_VALUE_PREFIXES) or name.split("=", 1)[0] in KNOWN_TAGS:
            if name.split("=", 1)[0] not in NO_CLOSE_TAGS:
                stack.append(name.split("=", 1)[0])
    if target is None:
        return None

    close_tag = "{/" + target + "}"
    pos = s.find(close_tag)
    if pos < 0:
        return None

    head = s[:pos]
    # 该标签在原文里裹住的文本（用于判断合理的包裹范围）
    src_text = _wrapped_text(old_value, target)
    opener = _opener_for(old_value, target)

    # 关键：译文里可能已经有同名的开标签存在（只是被引擎判为失配）。
    # 这时不能再补一个 —— 重复叠加会产生 {i}{i} 这类新的不匹配。
    existing = [t for t, c in tokenize_tags(s)
                if c and not t.startswith("/") and not t.startswith("#")
                and t.split("=", 1)[0] == target]
    if existing:
        # 已有同名开标签：丢的不是开标签而是"闭合"本身。
        # 一次性按原文的开标签序列重建句尾闭合；必须是幂等的，
        # 否则会被上层的循环反复追加而发散。
        opens = [t.split("=", 1)[0] for t, c in tokenize_tags(old_value)
                 if c and not t.startswith("/") and not t.startswith("#")
                 and t.split("=", 1)[0] not in NO_CLOSE_TAGS]
        # 只补足"句尾缺失的那一层"，保留译文里已有的正确闭合。目标是让
        # 栈净空：数一下当前串里每个标签的开闭差额，缺多少补多少。
        net = {}
        for t, c in tokenize_tags(s):
            if not c or t.startswith("#"):
                continue
            name = t.split("=", 1)[0]
            if name.startswith("/"):
                net[name[1:]] = net.get(name[1:], 0) + 1
            elif name not in NO_CLOSE_TAGS:
                net[name] = net.get(name, 0) - 1
        body = s.rstrip()
        # 按原文逆序补齐仍未闭合的开标签
        for n in reversed(opens):
            while net.get(n, 0) < 0:
                body += "{/" + n + "}"
                net[n] = net.get(n, 0) + 1
        return body if body != s.rstrip() else None

    # ① 原文裹住的是少数几个词（最常见的 {i}word{/i}）→ 在译文里找对应长度
    #    的词段靠近闭合标签的那一段，把开标签插到它前面。
    if src_text and 0 < len(src_text) <= 24:
        tail = _tail_chunk(head, len(src_text))
        if tail is not None:
            cut = len(head) - len(tail)
            return head[:cut] + opener + tail + s[pos:]

    # ② 原文整句都在标签内（{i}整句{/i}）→ 开标签放句首
    if src_text and head.strip() and len(src_text) >= len(old_value.strip()) - 8:
        lead_ws = len(head) - len(head.lstrip())
        return head[:lead_ws] + opener + head[lead_ws:] + s[pos:]

    # ③ 定位依据不足 → 交给调用方走保守路径
    return None


def _opener_for(old_value, target):
    """原文里同名开标签的完整片段（保留 = 参数），没有就用裸名字。"""
    for inner, closed in tokenize_tags(old_value):
        if closed and not inner.startswith("/") and inner.split("=", 1)[0] == target:
            return "{" + inner + "}"
    return "{" + target + "}"


def _wrapped_text(old_value, name):
    """原文中 {name}…{/name} 裹住的内容；找不到返回 None。"""
    pattern = re.compile(r"\{" + re.escape(name) + r"(?:=[^{}]*)?\}(.*?)\{/"
                         + re.escape(name) + r"\}", re.S)
    m = pattern.search(old_value or "")
    return m.group(1) if m else None


def _tail_chunk(head, want_len):
    """取 head 末尾的一个自然词段：长度在 [want_len/3, want_len*2] 之间，
    且从词边界开始。用于把开标签插到正确的词前面。"""
    units = [u for u in re.findall(r"\s+|[^\s]+", head)]
    if not units:
        return None
    acc, take = "", []
    for u in reversed(units):
        take.append(u)
        acc = u + acc
        core = "".join(x for x in take if not x.isspace())
        if len(core) >= max(1, want_len // 3):
            break
    core = "".join(x for x in take if not x.isspace())
    if not core or len(core) > want_len * 3:
        return None
    return acc.lstrip()


def _close_tail(s, old_value):
    """串尾残片 {i>abc → 按原文同名标签收口成 {i}abc{/i}。"""
    fragments = [t for kind, t in _rows(s) if kind == "bad"]
    if not fragments:
        return None
    frag = fragments[-1]
    pos = s.rfind(frag)
    if pos < 0:
        return None
    m = re.match(r"^\{/?([A-Za-z_][A-Za-z0-9_]*)", frag)
    if not m:
        return None
    name = m.group(1)
    src = None
    for inner, closed in tokenize_tags(old_value):
        if closed and not inner.startswith("/") and inner.split("=", 1)[0] == name:
            src = inner
            break
    opener = "{" + (src or name) + "}"
    rest = frag[len(m.group(0)):]
    return s[:pos] + opener + rest + "{/" + name + "}"


def _fallback_close(s, notes):
    """最小收口：只删孤立闭合，不动其他。用于没有可靠配对依据时。"""
    for kind, text in _rows(s):
        pass
    stack = []
    for inner, closed in tokenize_tags(s):
        if not closed:
            break
        if inner.startswith("#"):
            continue
        name = inner.split("=", 1)[0]
        if name.startswith("/"):
            if not stack:
                tag = "{" + inner + "}"
                pos = s.find(tag)
                if pos < 0:
                    return s, notes
                # 删掉这个闭合标签后若整句什么都不剩，就不删 —— 把一句有
                # 内容的台词清成空串，比留着一个多余闭合标签糟糕得多
                # （见模块头原则 3「宁可不修也不错修」）。实测里
                # 译文只剩 "{/i}" 时会走到这里。
                if not (s[:pos] + s[pos + len(tag):]).strip():
                    return s, notes
                notes.append("删除无对应闭合")
                return s[:pos] + s[pos + len(tag):], notes
            stack.pop()
        elif name.startswith(TAG_VALUE_PREFIXES) or name.split("=", 1)[0] in KNOWN_TAGS:
            if name.split("=", 1)[0] not in NO_CLOSE_TAGS:
                stack.append(name.split("=", 1)[0])
    return s, notes


# -------------------------------------------------------------- 插值修复

def _core_map(new_value, old_value):
    """把译文里多出来的插值配回原文变量。返回 [(译名, 原名)]。

    判定顺序：
      1. 同名不同大小写（[PN]↔[pn]）—— 引擎插值大小写敏感
      2. 编辑距离 ≤ 2 且首字母相同的近似拼写（[chyo_bond]↔[chiyo_bond]）
      3. 剩余的一对一按出现顺序回填（覆盖 [中文名] 这类完全被翻译的）
    """
    old_keys = [interp_base(k) for k in interp_keys(old_value)]
    new_keys = [interp_base(k) for k in interp_keys(new_value)]
    missing = [k for k in old_keys if k not in new_keys]
    extra = [k for k in new_keys if k not in old_keys]
    if not missing or not extra:
        return []

    pairs, used_target = [], set()

    # 1) 大小写
    for e in list(extra):
        for m in missing:
            if m in used_target:
                continue
            if e.lower() == m.lower():
                pairs.append((e, m))
                used_target.add(m)
                extra.remove(e)
                break

    # 2) 近似拼写
    for e in list(extra):
        best = None
        for m in missing:
            if m in used_target:
                continue
            if abs(len(e) - len(m)) <= 2 and _levenshtein(e, m) <= 2:
                if best is None or _levenshtein(e, m) < _levenshtein(e, best):
                    best = m
        if best:
            pairs.append((e, best))
            used_target.add(best)
            extra.remove(e)

    # 3) 剩余按序回填
    rest = [m for m in missing if m not in used_target]
    for e, m in zip(extra, rest):
        pairs.append((e, m))
        used_target.add(m)

    return pairs


def _levenshtein(a, b):
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1,
                           prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def repair_interps(new_value, old_value):
    """把译文里被改名/大写化的插值还原成原文变量。返回 (新串, [说明])。"""
    notes = []
    if not old_value:
        return new_value, notes
    pairs = _core_map(new_value, old_value)
    if not pairs:
        return new_value, notes
    s = new_value
    for src, dst in pairs:
        token = "[" + src + "]"
        if token in s:
            s = s.replace(token, "[" + dst + "]")
            notes.append("插值还原 [%s] → [%s]" % (src, dst))
    return s, notes


# ---------------------------------------------------------------- 组合入口

def repair_line(new_value, old_value):
    """先修方括号层，再修标签，最后修插值。返回 (新串, [说明])。对外主入口。

    顺序有讲究：方括号畸形（[cps=3}、说话人前缀泄漏）会让后面的标签/插值
    扫描把整句判歪，必须先摆平方括号。
    """
    notes = []

    s = new_value
    if old_value is not None and s.count("[") != s.count("]"):
        cand = _fix_bracket_layer(s)
        if cand != s:
            notes.append("方括号补正")
            s = cand

    s, n1 = repair_tags(s, old_value)
    notes.extend(n1)
    s, n2 = repair_interps(s, old_value)
    notes.extend(n2)
    return s, notes


# ---------------------------------------------------------------- 自检

_CASES = [
    ("孤儿闭标签应补开标签", 'Right… {i}ripped{/i}.', '嗯……撕裂了{/i}。', '{i}'),
    ("畸形右符号 {i>", '... {i}Sensei{/i}.', '老师的{i>教{/i}。', '{i}'),
    ("畸形右符号 {i]", '{i}How far back?!{/i}', '{i]多久以前啊？{/i}', '{i}'),
    ("中文入花括号", '{i}Haahhh…{/i}', '{我}哈啊啊啊……{/i}', None),
    ("孤立闭合+多余", '{i}Haahhh…{/i}', '哈啊啊啊……{/i}{/i}', None),
    ("插值大写还原", '…is that you, [pn]?', '……是你吗？[PN]', '[pn]'),
    ("插值被翻译还原", "Atsuko's bond [atsuko_bond]!",
     '阿梓子的羁绊[阿梓子羁绊]！', '[atsuko_bond]'),
    ("插值拼错还原", "Chiyo's bond [chiyo_bond]!", '千与[chyo_bond]！', '[chiyo_bond]'),
    ("正常句不动", 'Hello [pn], ok?', '你好[pn]，好吗？', None),
    ("标签一致不动", '{i}Hi{/i} [pn].', '{i}你好{/i}[pn]。', None),
    ("未闭合大括号", 'take things {i}too{/i} far', '把事情{i}搞{/i>太远了', None),
    ("嵌套错配", '{i}That {s}said{/s} now.{/i}', '{i}话虽如此{/s}现在.{/i}', None),
    ("size 参数完好", '{size=-10}[[Edited]{/size}', '{size=-10}[[编辑]{/size}', None),
    ("cps 完好", '{cps=3}...{/cps}', '{cps=3}……{/cps}', None),
]


def _selfcheck():
    bad = 0
    for name, old, new, must in _CASES:
        got, notes = repair_line(new, old)
        probs = tag_problems(got)
        status = "OK  " if not probs else "FAIL"
        if probs:
            bad += 1
        if must and must not in got:
            status = "FAIL"
            bad += 1
        print("%s %-22s %s" % (status, name, "+".join(notes) or "无"))
        print("       原 %s" % old)
        print("       译 %s" % new)
        if got != new:
            print("     → %s" % got)
        if probs:
            print("       残留 %s" % probs)
    print()
    print("自检：%d 例，%d 例未达标" % (len(_CASES), bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(_selfcheck())
