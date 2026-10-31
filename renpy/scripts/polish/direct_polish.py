#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""无需 API 的直接润色：基于规则清洗中文翻译腔，不调大模型。

用法::

    python direct_polish.py <tl目录或entries.json> -o direct_fixes.json [--dry-run]
    python direct_polish.py <tl目录或entries.json> --apply
    python direct_polish.py entries.json -o direct_fixes.json --report direct_report.json

设计目标：
  - 零 token、零 API 密钥；只做高置信度的机械改写
  - 绝不动 {标签}、[插值]、%%、\\n 转义；只改译文，不动行号/原文/角色/场景
  - 产出 direct_fixes.json（file:line -> 新译文，锚点齐全），可直接进
    merge_polish.py → autotranslate.py apply --overwrite，也可 --apply 直接回填 tl
  - 默认 --dry-run：只产出 JSON + 报告，不碰 tl 文件

规则（按置信度分组，写在 SAFE_RULES / REVIEW_RULES，增删即可）：
  SAFE（误伤低，自动应用）：
    - 同种中文标点重复→一个：！！！！→！ ？？？→？ ，，→， 。。。→。
    - 重复半角标点→全角单个：!!!→！ ???→？
    - 半角标点→全角：! ? ; :（避开 1,000 千分位逗号）
    - 多空格→一个空格
    - 将会→会
    - 如果…的话→如果…（去冗余“的话”）
    - 连续的的→的（的{2,}→的）
    - 哦我的天→天哪
  REVIEW（应用但标记，建议人工过目）：
    - 被+1~4 个汉字→去掉“被”（如“被击中”→“击中”，被动直译常见）
    - 作为一个→去掉（如“作为一个玩家”→“玩家”）

输出：
  direct_fixes.json   —— {"file:line": "新译文", ...}，可直接进 autotranslate apply --input
  direct_report.json  —— 每条改了哪条规则、前后对比，供人工复核

安全：
  - 回填前结构守恒：与润色前译文比对标签/插值/%%/换行数，丢结构的条目不入 fixes
  - --apply 前自动 .bak + 原子写入（shared/backup.atomic_write_text）
  - 空译文或结构破损的条目直接跳过，不入报告
"""
import argparse
import io
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
else:  # pragma: no cover
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent))
from _say_parse import iter_say_entries  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))
from backup import atomic_write_text  # noqa: E402
from rpy_syntax import find_string_literal, replace_literal_content  # noqa: E402

#: 结构 token 正则（与 merge_polish.py 同口径，用于保护不被规则碰触）
_STRUCT_TOKEN_RE = re.compile(
    r"\{\{|\}\}|\[\[|\]\]"                          # 转义 {{ }} [[ ]]
    r"|(?<!\{)\{(?!\{)[^{}]*\}(?!\})"                # 标签 {i} {/i} {size=+10}
    r"|(?<!\[)\[(?!\[)[^\[\]]*\](?!\])"              # 插值 [pn] [name!t]
    r"|%\([^)]*\)[a-zA-Z%]?|%%"                      # %% %(who)s
    r"|\\n"                                            # 字面换行
)

#: (正则, 替换, 规则名)；替换若是字符串则直接替换，若是函数则传入 match 对象
SAFE_RULES = [
    (r"([，。！？])\1+", r"\1", "同种中文标点重复→一个"),
    (r"([!])\1+", "！", "重复半角!→全角！"),
    (r"([?])\1+", "？", "重复半角?→全角？"),
    (r"(?<!\d)!(?!\d)", "！", "半角!→全角！"),
    (r"(?<!\d)\?(?!\d)", "？", "半角?→全角？"),
    (r"(?<!\d);(?!\d)", "；", "半角;→全角；"),
    (r"(?<!\d):(?!\d)", "：", "半角:→全角："),
    (r"[ \t]{2,}", " ", "多空格→一个空格"),
    (r"将会", "会", "将会→会"),
    (r"如果(.{0,40}?)的话", r"如果\1", "如果…的话→如果…"),
    (r"的{2,}", "的", "连续的的→的"),
    (r"哦，?我的天", "天哪", "哦我的天→天哪"),
    # 2026-10-27 增补（实测 fixes_003）：〔chy〕 一类角色标记垃圾前缀，可安全整删
    (r"〔[^〕]*〕", "", "删〔…〕角色标记"),
]

#: 保守规则：应用但会在报告里标记，建议人工过目
REVIEW_RULES = [
    (r"被([\u4e00-\u9fff]{1,4})", r"\1", "被+短动词→去掉被（被动直译）"),
    (r"作为一个(.{0,12}?)", r"\1", "作为一个→去掉"),
]


def _split_segments(text):
    """把文本切成 ("text", 段) / ("struct", 标记) 交替序列，只改 text 段。"""
    parts, last = [], 0
    for m in _STRUCT_TOKEN_RE.finditer(text):
        if m.start() > last:
            parts.append(("text", text[last:m.start()]))
        parts.append(("struct", m.group(0)))
        last = m.end()
    if last < len(text):
        parts.append(("text", text[last:]))
    return parts


def _apply_rules(segment, rules):
    """对纯文本段应用规则，返回 (新段, 命中规则名列表)。"""
    hits, cur = [], segment
    for pat, repl, name in rules:
        new_cur, n = re.subn(pat, repl, cur)
        if n:
            hits.append(name)
            cur = new_cur
    return cur, hits


def polish_entry(e, include_review=False):
    """对单条目应用直接润色规则。

    返回 (新条目或 None, 报告条目或 None)。若译文未变或结构被破坏，返回 None。
    """
    trans = e.get("trans") or ""
    if not trans.strip():
        return None, None

    rules = list(SAFE_RULES)
    if include_review:
        rules.extend(REVIEW_RULES)

    parts = _split_segments(trans)
    changed, all_hits = False, []
    new_parts = []
    for kind, seg in parts:
        if kind == "struct":
            new_parts.append(seg)
            continue
        new_seg, hits = _apply_rules(seg, rules)
        if new_seg != seg:
            changed = True
            all_hits.extend(hits)
        new_parts.append(new_seg)

    if not changed:
        return None, None

    new_trans = "".join(new_parts)

    # 结构守恒：与润色前译文比对标签/插值/%%/换行数
    from merge_polish import structure_diff  # noqa: WPS433
    problems = structure_diff(trans, new_trans)
    if problems:
        return None, {
            "file": e.get("file"), "line": e.get("line"),
            "orig": e.get("orig", ""),
            "trans_before": trans, "trans_after": new_trans,
            "reason": "结构守恒失败：" + "；".join(problems),
            "rules": all_hits,
        }

    new_e = dict(e)
    new_e["trans"] = new_trans
    report = {
        "file": e.get("file"), "line": e.get("line"),
        "orig": e.get("orig", ""),
        "trans_before": trans, "trans_after": new_trans,
        "rules": all_hits,
    }
    return new_e, report


def _load_entries(source):
    src = Path(source)
    if src.suffix == ".json":
        return json.loads(src.read_text(encoding="utf-8-sig"))
    return list(iter_say_entries(src))


def main(argv=None):
    ap = argparse.ArgumentParser(description="无 API 直接润色：基于规则清洗中文翻译腔")
    ap.add_argument("source", help="tl 目录或 extract_say 输出的条目 JSON")
    ap.add_argument("-o", "--out", default="direct_fixes.json",
                    help="输出 fixes JSON（file:line -> 新译文，可进 merge_polish/apply）")
    ap.add_argument("--report", default="direct_report.json",
                    help="输出报告 JSON（前后对比+命中规则）")
    ap.add_argument("--include-review", action="store_true",
                    help="同时应用保守规则（被+动词/作为一个），建议人工过目报告")
    ap.add_argument("--apply", action="store_true",
                    help="直接回填到 tl 文件（自带 .bak + 原子写入，默认试运行）")
    ap.add_argument("--dry-run", action="store_true", default=True,
                    help="只产出 JSON，不写入 tl 文件（默认开启，--apply 才落盘）")
    args = ap.parse_args(argv)

    entries = _load_entries(args.source)
    fixes, reports = {}, []
    applied_files = set()

    for e in entries:
        new_e, report = polish_entry(e, include_review=args.include_review)
        if report:
            reports.append(report)
        if new_e:
            # fixes 的锚点用 line（原文注释行号），与 autotranslate / merge_polish 约定一致
            fixes[f'{new_e["file"]}:{new_e["line"]}'] = new_e["trans"]
            if args.apply:
                # 回填时必须用 src_line（译文实际行号），否则会把 # 原文注释行误覆盖成译文
                applied_files.add((new_e["file"], new_e.get("src_line") or new_e["line"], new_e["trans"]))

    Path(args.out).write_text(
        json.dumps(fixes, ensure_ascii=False, indent=1), encoding="utf-8")
    Path(args.report).write_text(
        json.dumps(reports, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"直接润色完成：{len(reports)} 条译文被规则改写 -> {args.out}")
    print(f"报告 -> {args.report}")

    if args.apply:
        # 按文件聚合，按 src_line 替换译文行
        by_file = {}
        for fname, line, new_trans in applied_files:
            by_file.setdefault(fname, []).append((line, new_trans))
        # 需要 tl 目录来定位文件：source 若是目录直接用，否则无法 apply
        src = Path(args.source)
        tl_dir = src if src.is_dir() else None
        if tl_dir is None:
            print("[ERROR] --apply 需要 source 为 tl 目录（而非 entries.json）")
            return 2
        total = 0
        for fname, items in sorted(by_file.items()):
            abs_path = tl_dir / fname
            if not abs_path.is_file():
                print(f"  [SKIP] 文件不存在: {fname}")
                continue
            raw = abs_path.read_bytes()
            has_bom = raw.startswith(b"\xef\xbb\xbf")
            # utf-8-sig 会自动剥 BOM，写回时按原文件是否带 BOM 决定编码，避免无端改动文件头
            lines = raw.decode("utf-8-sig").splitlines()
            for line_no, new_trans in sorted(items):
                idx = line_no - 1
                if idx < 0 or idx >= len(lines):
                    print(f"  [SKIP] {fname}:{line_no} 行号越界")
                    continue
                literal = find_string_literal(lines[idx])
                if literal is None or not literal.closed:
                    print(f"  [SKIP] {fname}:{line_no} 无法解析译文字面量")
                    continue
                lines[idx] = replace_literal_content(lines[idx], literal, new_trans)
            enc = "utf-8-sig" if has_bom else "utf-8"
            atomic_write_text(abs_path, "\n".join(lines), encoding=enc,
                              backup=True)
            total += len(items)
            print(f"  {fname}: 写入 {len(items)} 条 (BOM={'有' if has_bom else '无'})")
        print(f"完成：回填 {total} 条（已自动 .bak 备份）")

    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
