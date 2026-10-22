# -*- coding: utf-8 -*-
"""把 AI 润色稿（file:line -> 新译文）合并为 apply 格式批次 JSON。

用法::

    python merge_polish.py --pool entries.json --fixes fixes.json -o polish_batch.json

fixes.json 格式::

    {"HazelEvents.rpy:954": "润色后的译文", ...}

    **只列改动过的行**：提示词已明确要求模型对「判断为不用改」的句子不要输出，
    缺省即保持原样。模型仍可能把未改动的行也塞进来（值等于条目池里的旧译文），
    这类条目在这里被剔除并计入 ``unchanged``——它们回填与否结果相同，留着只会
    污染 diff 视图、让「本批改了几行」的统计失真。

合并时从 pool 中取该行的锚点（file/line/type/orig/char），AI 只需要提供新译文，
不需要碰行号和原文——锚点错误由 merge 阶段直接报缺，不会污染回填。

结构守恒门（2026-10-18）
------------------------

润色只该改措辞，不该动结构。所以每条润色稿都要与**润色前译文**比对三层：标签
``{}`` / 插值 ``[]`` / ``%`` 格式符的**多重集**，以及换行数；对不上的条目
**不入批次**，单独列出原因。

为什么基线取「润色前译文」而不是英文原文：润色这一步的职责是措辞，结构修复是
``checks/tl_check.py --fix --settle`` 的活。用原文当基线的话，一个历史遗留了结构
损伤的项目（如 tl_check 报出的破损句）会被整批卡死；用润色前译文当基线，判据就
收窄成「**这次润色有没有引入新损伤**」，正是这一步该负责的范围。AiNiee 的
``PolisherTask`` 也是拿润色前译文做参照（``translation_text_dict``）。

为什么必须有这道门：管线里下游两步都不看结构——``merge_polish`` 原本只核
锚点存在性，``autotranslate.py apply`` 也只核锚点（原文/角色/目标为空），
于是「润色把 ``{i}`` 润丢了」要等回填完再跑 ``checks/tl_check.py`` 才发现，
那时错误已经在 tl 文件里了。

判据与 ``checks/tl_check.py`` 同口径：
- 只拦「丢/多结构 token」与「换行数增加」；
- 润色前译文有换行而润色后合并断行**不拦**（中英排版允许不同断行）；
- 空译文直接剔除（回填空串比不回填更糟）。

这套规则取自 AiNiee 润色阶段的 ``ResponseChecker.check_polish_response_content``
（行数 / 序号 / 空值 / 换行 / 占位符保留；对照之下它比翻译阶段更松——刻意不做
「返回原文」「残留原文」「回复格式」检查，因为润色后译文贴近原文是正常的）。

退出码: 0=全部条目可用（可有缺锚点警告）, 1=有条目被结构守恒门剔除, 2=输入错误
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

# UTF-8 输出（Windows 终端中文不乱码）。用 reconfigure 而不是换掉 sys.stdout：
# 后者会新建一个共享同一 buffer 的 TextIOWrapper，旧 wrapper 一旦被回收就会
# 顺手关掉 buffer，把整个进程的 stdout 弄坏（被 import 时尤其致命）。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# shared/rpy_syntax 提供嵌套+字符串感知的插值扫描（与 tl_check/autotranslate 同层）
sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))
try:
    from rpy_syntax import iter_bracket_groups as _iter_bracket_groups
except ImportError:  # 独立拷贝运行时退回单层正则
    _iter_bracket_groups = None


# 花括号标签（含 {{ }} 转义本身）；[[ 与 ]] 的转义单独计数
_TAG_RE = re.compile(r"(?<!\{)\{(?!\{)[^{}]*\}(?!\})")
_BRACKET_FALLBACK_RE = re.compile(r"(?<!\[)\[(?!\[)[^\[\]]*\](?!\])")
_ESCAPE_RE = re.compile(r"\{\{|\}\}|\[\[|\]\]")
_PCT_RE = re.compile(r"%\([^)]*\)[a-zA-Z%]?|%%")


def structure_tokens(text: str) -> Counter:
    """文本的结构 token 多重集：标签 / 插值 / 转义 / % 格式符。

    用多重集而不是集合：``{i}{/i}`` 少一个闭合标签时集合看不出差别，
    但引擎会抛「关闭无开放标签」。
    """
    tokens = Counter()
    for m in _ESCAPE_RE.finditer(text):
        tokens[m.group(0)] += 1
    for m in _TAG_RE.finditer(text):
        tokens[m.group(0)] += 1
    if _iter_bracket_groups is not None:
        for _inner, full in _iter_bracket_groups(text):
            tokens[full] += 1
    else:
        for m in _BRACKET_FALLBACK_RE.finditer(text):
            tokens[m.group(0)] += 1
    for m in _PCT_RE.finditer(text):
        tokens[m.group(0)] += 1
    return tokens


def _newline_count(text: str) -> int:
    """真实换行 + 字面 ``\\n`` 转义都算（两边口径一致即可）。"""
    return text.count("\n") + text.count("\\n")


def _fmt_tokens(counter: Counter) -> str:
    return "、".join(f"{tok}×{n}" if n > 1 else tok
                     for tok, n in sorted(counter.items()))


def structure_diff(orig: str, trans) -> list:
    """润色稿相对基线（润色前译文）的结构差异，空列表 = 结构守恒。"""
    if not isinstance(trans, str) or not trans.strip():
        return ["译文为空"]

    problems = []
    o_tok, t_tok = structure_tokens(orig), structure_tokens(trans)
    if o_tok != t_tok:
        parts = []
        if o_tok - t_tok:
            parts.append("丢 " + _fmt_tokens(o_tok - t_tok))
        if t_tok - o_tok:
            parts.append("多 " + _fmt_tokens(t_tok - o_tok))
        problems.append("标签/插值不一致（" + "；".join(parts) + ")")

    o_nl, t_nl = _newline_count(orig), _newline_count(trans)
    if t_nl > o_nl:
        problems.append(f"换行数增加（原文 {o_nl} → 润色 {t_nl}）")
    return problems


def _baseline(anchor: dict) -> str:
    """结构比对基线 = 润色前译文；没有译文（未翻译行）时退回原文锚点。"""
    prev = anchor.get("trans")
    return prev if isinstance(prev, str) and prev.strip() else (anchor.get("orig") or "")


def main(argv=None):
    ap = argparse.ArgumentParser(description="润色稿合并为 apply 批次")
    ap.add_argument("--pool", required=True, help="extract_say 输出的条目池 JSON")
    ap.add_argument("--fixes", required=True, help="file:line -> 新译文 的 JSON")
    ap.add_argument("-o", "--out", default="polish_batch.json")
    args = ap.parse_args(argv)

    pool = {}
    for e in json.loads(Path(args.pool).read_text(encoding="utf-8")):
        pool[(e["file"], e["line"])] = e

    fixes = json.loads(Path(args.fixes).read_text(encoding="utf-8"))
    entries, missing, rejected, unchanged = [], [], [], []
    for key, new_trans in fixes.items():
        fname, _, line = key.rpartition(":")
        try:
            anchor = pool.get((fname, int(line)))
        except ValueError:
            anchor = None
        if anchor is None:
            missing.append(key)
            continue
        # 模型把没改的行也输出了：值与条目池旧译文一致 → 无需回填，剔除。
        if new_trans == anchor.get("trans"):
            unchanged.append(key)
            continue
        problems = structure_diff(_baseline(anchor), new_trans)
        if problems:
            rejected.append((key, problems))
            continue
        entry = {"file": fname, "line": int(line), "type": anchor["type"],
                 "orig": anchor["orig"], "trans": new_trans}
        if anchor.get("char"):
            entry["char"] = anchor["char"]
        entries.append(entry)

    Path(args.out).write_text(
        json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")

    if unchanged:
        print(f"[跳过] {len(unchanged)} 条与原文译文相同（模型判为不用改），"
              f"无需回填：")
        for k in unchanged[:5]:
            print("  ", k)
        if len(unchanged) > 5:
            print(f"   ... 其余 {len(unchanged) - 5} 条省略")
    if missing:
        print(f"[警告] {len(missing)} 条无锚点，未纳入批次:")
        for m in missing[:10]:
            print("  ", m)
    if rejected:
        print(f"[警告] {len(rejected)} 条未通过结构守恒门，已剔除（需修好润色稿再合并）:")
        for key, problems in rejected[:10]:
            print(f"   {key}: " + "；".join(problems))
        if len(rejected) > 10:
            print(f"   ... 其余 {len(rejected) - 10} 条省略")
        print("   提示：润色只改措辞，{标签}/[插值]/% 格式符必须原样保留（基线是润色前译文）；"
              "确认要靠引擎裁决时，可回填后跑 checks/tl_check.py 复核。")

    # 整批零产出：实测出现过 198 条 fixes 全部等于旧译文的情况——模型读了整批
    # 剧本却一条没改，token 全花在空转上。静默跳过会让人以为这批润色完成了。
    if not entries and fixes:
        print(f"[警告] 本批 {len(fixes)} 条 fixes 全部未产出改动"
              f"（unchanged {len(unchanged)} / 剔除 {len(rejected)} / 无锚点 {len(missing)}）。"
              f"这批润色实际没动任何一行：")
        print("   - 若本就无需改动：正常，但要确认筛行阈值没把通顺句子送进来")
        print("   - 若本该有改动：检查提示词是否让 AI 误以为要逐行复述原文")
        print("   - 空转的批次仍消耗了整批 prompt 的 token，建议收紧筛行（--min-score）")
    print(f"生成 {len(entries)} 条 -> {args.out}")
    return 1 if rejected else 0


if __name__ == "__main__":
    sys.exit(main())
