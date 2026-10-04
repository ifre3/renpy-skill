#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_missing_tags.py — 修复译文中丢失的 Ren'Py 文本标签

分类修复策略:
  A. HTML 替代 (<i> -> {i})           — 自动修复
  B. {size} 整段包裹丢失               — 自动修复
  C. {w} 句间停顿丢失                  — 半自动（在对应标点处插入）
  D. {i} 单词强调丢失                  — 映射表匹配，命中则自动修复
  E. {s} 删除线丢失                    — S_CONTENT_MAP 匹配
  F. 人工覆盖表                         — 逐条审核的 (search, replace) 对
  Z. 无法自动修复                       — 生成 JSON 待人工处理

用法:
  python fix_missing_tags.py <tl_dir> --dry-run   # 预览
  python fix_missing_tags.py <tl_dir> --apply      # 执行修复
  python fix_missing_tags.py <tl_dir> --report manual_fixes.json
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "公共")
)
from backup import atomic_write_text  # noqa: E402
from rpy_syntax import (  # noqa: E402
    iter_translation_pairs,
    parse_new_line,
    parse_translation_line,
    replace_literal_content,
)

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TAG_RE = re.compile(r"\{(/?)([a-zA-Z]+)(?:=[^}]*)?\}")
HTML_TAG_RE = re.compile(r"<(/?)(i|b|u|s)>")
# 提取 {i}content{/i} 中的 content
ITALIC_CONTENT_RE = re.compile(r"\{i\}(.+?)\{/i\}")
# 匹配引号内内容（正确处理转义引号 \\"）

# -- {i} 单词映射表：英文强调词 -> [中文对应词列表] --
ITALIC_MAP = {
    "really": ["真的", "确实"],
    "probably": ["大概"],
    "technically": ["技术上"],
    "this": ["这", "如此"],
    "too": ["太", "过于"],
    "pretty": ["挺", "很"],
    "not": ["不"],
    "now": ["现在"],
    "again": ["再"],
    "would": ["会", "确实", "理所当然"],
    "could": ["可以"],
    "did": ["确实"],
    "is": ["确实", "真的", "还是"],
    "am": ["确实"],
    "she": ["她"],
    "he": ["他"],
    "i": ["我"],
    "me": ["我"],
    "my": ["我的"],
    "your": ["你的", "自己的"],
    "you": ["你"],
    "that": ["那"],
    "very": ["很"],
    "so": ["所以"],
    "just": ["只是"],
    "only": ["只", "唯一"],
    "even": ["甚至"],
    "still": ["还是"],
    "also": ["也"],
    "actually": ["实际上", "真的"],
    "obviously": ["显然"],
    "clearly": ["清楚"],
    "simply": ["简直"],
    "literally": ["简直"],
    "basically": ["基本上"],
    "definitely": ["肯定"],
    "certainly": ["当然"],
    "maybe": ["也许"],
    "perhaps": ["也许"],
    "instead": ["而是"],
    "though": ["不过"],
    "either": ["要么"],
    "both": ["两个"],
    "all": ["所有"],
    "any": ["任何"],
    "every": ["每"],
    "one": ["一个"],
    "two": ["两个"],
    "first": ["第一"],
    "last": ["最后"],
    "same": ["同样"],
    "different": ["不同"],
    "cute": ["可爱"],
    "ugly": ["丑"],
    "weird": ["奇怪"],
    "normal": ["正常"],
    "simple": ["简单"],
    "hard": ["难"],
    "easy": ["容易"],
    "bad": ["糟糕"],
    "good": ["好"],
    "great": ["很好"],
    "ok": ["还行"],
    "sure": ["当然"],
    "yes": ["是的"],
    "no": ["不"],
    "think": ["觉得"],
    "might": ["可能"],
    "may": ["可能"],
    "before": ["之前"],
    "milk": ["牛奶"],
    "got": ["一定"],
    "why": ["理由"],
    "something": ["一些"],
    "real": ["真正", "真正的"],
    "ad-block": ["广告拦截器"],
}

# -- {s} 删除线内容映射表 --
S_CONTENT_MAP = {
    "god": ["上帝", "老天", "神"],
    "the world": ["全世界"],
    "upstanding": ["守规矩"],
}

# -- 人工覆盖表：(file, line) -> [(search, replace), ...] --
# search/replace 针对 issue["cn"]（引号内内容）操作。
# 每条均经人工审核，确定英文强调词在中文译文中的对应位置。
MANUAL_OVERRIDES = {
    # ── ch1.rpy ──
    ("chapters\\ch1.rpy", 2797): [
        ("看到", "{i}看到{/i}"),
    ],
    ("chapters\\ch1.rpy", 8287): [
        ("糟糕透了", "糟糕{i}透{/i}了"),
    ],
    ("chapters\\ch1.rpy", 11287): [
        ("在我家的睡衣派对", "在{i}我家{/i}的{i}睡衣派对{/i}"),
    ],
    ("chapters\\ch1.rpy", 11701): [
        ("\u201c\u53eb\u9192\u201d", "{i}\u201c\u53eb\u9192\u201d{/i}"),
    ],
    ("chapters\\ch1.rpy", 18545): [
        ("很难", "{i}很{/i}难"),
    ],
    ("chapters\\ch1.rpy", 19445): [
        ("随时都可以", "{i}随时都可以{/i}"),
        ("没必要", "没{i}必要{/i}"),
    ],
    ("chapters\\ch1.rpy", 21341): [
        ("真的", "{i}真的{/i}"),
    ],
    ("chapters\\ch1.rpy", 21437): [
        ("已经", "{i}已经{/i}"),
    ],
    ("chapters\\ch1.rpy", 24851): [
        ("\u201c我们\u201d", "{i}\u201c我们\u201d{/i}"),
    ],
    # ── ch2.rpy ──
    ("chapters\\ch2.rpy", 3763): [
        ("现在，", "现在，{i}*咳咳*{/i}"),
    ],
    ("chapters\\ch2.rpy", 1843): [
        ("不想", "不{i}想{/i}"),
    ],
    ("chapters\\ch2.rpy", 11749): [
        ("还没", "{i}还没{/i}"),
    ],
    ("chapters\\ch2.rpy", 14353): [
        ("会说出口", "{i}会{/i}说出口"),
    ],
    ("chapters\\ch2.rpy", 14965): [
        ("上帝", "{s}上帝{/s}"),
    ],
    ("chapters\\ch2.rpy", 15061): [
        ("上帝", "{s}上帝{/s}"),
    ],
    ("chapters\\ch2.rpy", 16609): [
        ("理由", "{i}理由{/i}"),
    ],
    ("chapters\\ch2.rpy", 18499): [
        ("唯一", "{i}唯一{/i}"),
        ("某些原因", "{i}某些原因{/i}"),
    ],
    ("chapters\\ch2.rpy", 29185): [
        ("很简单", "{i}很简单{/i}"),
    ],
    # ── ch3.rpy ──
    ("chapters\\ch3.rpy", 2947): [
        ("看起来", "{i}看起来{/i}"),
    ],
    # ── hina.rpy (547 已手动修复，跳过) ──
    ("events\\hina.rpy", 391): [
        ("\u201c那件事\u201d", "{i}\u201c那件事\u201d{/i}"),
    ],
    ("events\\hina.rpy", 2989): [
        ("有人", "{i}有人{/i}"),
    ],
    ("events\\hina.rpy", 3445): [
        ("可能", "{i}可能{/i}"),
    ],
    ("events\\hina.rpy", 4423): [
        ("确实", "{i}确实{/i}"),
    ],
    # ── ikari.rpy ──
    ("events\\ikari.rpy", 2197): [
        ("正是我", "正是{i}我{/i}"),
    ],
    ("events\\ikari.rpy", 4357): [
        ("我自己", "{i}我自己{/i}"),
    ],
    # ── kurumi.rpy ──
    ("events\\kurumi.rpy", 1495): [
        ("到底", "{i}到底{/i}"),
    ],
    ("events\\kurumi.rpy", 3181): [
        ("\u201c意外\u201d", "{i}\u201c意外\u201d{/i}"),
    ],
    ("events\\kurumi.rpy", 3619): [
        ("一定是", "{i}一定{/i}是"),
    ],
    ("events\\kurumi.rpy", 4207): [
        ("如此", "{i}如此{/i}"),
    ],
    ("events\\kurumi.rpy", 5071): [
        ("被电击", "{i}真的{/i}被电击"),
    ],
    ("events\\kurumi.rpy", 5137): [
        ("真的", "{i}真的{/i}"),
    ],
    ("events\\kurumi.rpy", 5383): [
        ("真的在家", "{i}真的{/i}在家"),
    ],
    ("events\\kurumi.rpy", 6031): [
        ("一些", "{i}一些{/i}"),
    ],
    # ── nami.rpy ──
    ("events\\nami.rpy", 727): [
        ("为她提供服务", "{i}为她提供服务{/i}"),
    ],
    ("events\\nami.rpy", 763): [
        ("觉得", "{i}觉得{/i}"),
    ],
    ("events\\nami.rpy", 3625): [
        ("不太适合工作环境", "{i}*咳咳* 不太适合工作环境。{/i}"),
    ],
    ("events\\nami.rpy", 7555): [
        ("真正的", "{i}真正的{/i}"),
    ],
    # ── teacher.rpy ──
    ("events\\teacher.rpy", 421): [
        ("一点", "{i}一点{/i}"),
    ],
    ("events\\teacher.rpy", 847): [
        ("理所当然", "{i}理所当然{/i}"),
    ],
    ("events\\teacher.rpy", 1933): [
        ("让我看到了", "让{s}全世界{/s}我看到了"),
    ],
    ("events\\teacher.rpy", 2287): [
        ("相信我", "相信{i}我{/i}"),
    ],
    ("events\\teacher.rpy", 3535): [
        ("{i}守规矩{/i}", "{s}守规矩{/s}"),
    ],
    # ── tomori.rpy ──
    ("events\\tomori.rpy", 1903): [
        ("之前", "{i}之前{/i}"),
    ],
    ("events\\tomori.rpy", 2719): [
        ("还是", "{i}还是{/i}"),
    ],
    ("events\\tomori.rpy", 3121): [
        ("\u201c牛奶\u201d", "{i}\u201c牛奶\u201d{/i}"),
    ],
    ("events\\tomori.rpy", 3163): [
        ("灯里的", "{i}灯里的{/i}"),
    ],
    ("events\\tomori.rpy", 3223): [
        ("老天", "{s}老天{/s}"),
    ],
    ("events\\tomori.rpy", 3277): [
        ("获得想要的", "获得想要的{i}机会{/i}"),
    ],
    ("events\\tomori.rpy", 3289): [
        ("自己的", "{i}自己的{/i}"),
    ],
    ("events\\tomori.rpy", 3373): [
        ("一直", "{i}一直{/i}"),
    ],
    ("events\\tomori.rpy", 3379): [
        ("广告拦截器", "{i}广告拦截器{/i}"),
    ],
    ("events\\tomori.rpy", 3523): [
        ("些什么", "{i}些什么{/i}"),
    ],
    ("events\\tomori.rpy", 9187): [
        ("是我", "是{i}我{/i}"),
    ],
    ("events\\tomori.rpy", 9253): [
        ("重复", "{i}重复{/i}"),
    ],
    ("events\\tomori.rpy", 9277): [
        ("在我已经给了她额外的30分钟之后", "{i}在我已经给了她额外的30分钟之后{/i}"),
    ],
    ("events\\tomori.rpy", 9307): [
        ("这么晚", "{i}这么晚{/i}"),
    ],
    ("events\\tomori.rpy", 13207): [
        ("实在", "{i}实在{/i}"),
    ],
    # ── yokubo.rpy ──
    ("events\\yokubo.rpy", 4777): [
        ("可能", "{i}可能{/i}"),
    ],
    # ── yui.rpy ──
    ("events\\yui.rpy", 409): [
        ("是你", "是{i}你{/i}"),
    ],
}


def extract_tag_issues(lines, filepath, relpath):
    """使用共享解析器提取所有标签丢失问题。

    支持 old/new、旁白和任意角色变量，并正确处理转义引号；不会因行间距
    变化把译文和下一条原文误配。
    """
    issues = []
    for pair in iter_translation_pairs(lines):
        if pair.translated is None or pair.translated_line is None:
            continue
        en = pair.original
        cn = pair.translated
        en_tags = set(TAG_RE.findall(en))
        cn_tags = set(TAG_RE.findall(cn))
        en_tag_names = {tag[1] for tag in en_tags}
        cn_tag_names = {tag[1] for tag in cn_tags}
        missing = en_tag_names - cn_tag_names
        if not missing:
            continue

        target_index = pair.translated_line - 1
        issues.append(
            {
                "file": relpath,
                "filepath": filepath,
                "line": pair.translated_line,
                "en": en,
                "cn": cn,
                "missing_tags": sorted(missing),
                "has_html": bool(HTML_TAG_RE.search(cn)),
                "italic_contents": ITALIC_CONTENT_RE.findall(en),
                "w_positions": [
                    match.start()
                    for match in re.finditer(r"\{w(?:=[^}]*)?\}", en)
                ],
                "s_contents": re.findall(r"\{s\}(.+?)\{/s\}", en),
                "is_old_new": pair.kind == "on",
                "raw_line": lines[target_index],
            }
        )
    return issues


def classify_and_fix(issue):
    """对单个问题分类并尝试修复，返回 (category, new_cn, confidence)"""
    cn = issue["cn"]
    en = issue["en"]
    missing = issue["missing_tags"]

    # F: 人工覆盖表（优先检查，处理标签类型错误等特殊情况）
    key = (issue["file"], issue["line"])
    if key in MANUAL_OVERRIDES:
        new_cn = cn
        ok = True
        for search, replace in MANUAL_OVERRIDES[key]:
            if search in new_cn:
                new_cn = new_cn.replace(search, replace, 1)
            else:
                ok = False
                break
        if ok and new_cn != cn:
            return "F_override", new_cn, "high"

    # A: HTML 替代
    if issue["has_html"] and "i" in missing:
        new_cn = cn.replace("<i>", "{i}").replace("</i>", "{/i}")
        new_cn = new_cn.replace("<b>", "{b}").replace("</b>", "{/b}")
        new_cn = new_cn.replace("<u>", "{u}").replace("</u>", "{/u}")
        new_cn = new_cn.replace("<s>", "{s}").replace("</s>", "{/s}")
        if new_cn != cn:
            return "A_html", new_cn, "high"

    # B: {size} 整段包裹
    if "size" in missing:
        size_match = re.search(r"\{(size=[^}]+)\}", en)
        if size_match:
            size_open = size_match.group(0)
            new_cn = f"{size_open}{cn}{{/size}}"
            return "B_size", new_cn, "high"

    # C: {w} 句间停顿
    if "w" in missing:
        w_match = re.search(r"(.*?)\{w(?:=[^}]*)?\}", en)
        if w_match:
            before_w = w_match.group(1).strip()
            sentence_end = re.search(r"([.!?...]+)\s*$", before_w)
            if sentence_end:
                cn_puncts = list(re.finditer(r"[\u3002\uff01\uff1f\u2026]+", cn))
                if cn_puncts:
                    pos = cn_puncts[0].end()
                    new_cn = cn[:pos] + "{w}" + cn[pos:]
                    return "C_w_pause", new_cn, "medium"

    # D: {i} 单词强调 — 映射表匹配
    if "i" in missing and issue["italic_contents"]:
        for content in issue["italic_contents"]:
            clean = content.replace('\\"', '"').replace("\\\\", "\\")
            cn_words = ITALIC_MAP.get(clean.lower().strip(), [])
            for cn_word in cn_words:
                if cn_word in cn:
                    pos = cn.find(cn_word)
                    new_cn = (
                        cn[:pos] + "{i}" + cn_word + "{/i}" + cn[pos + len(cn_word) :]
                    )
                    return "D_i_mapped", new_cn, "medium"

    # E: {s} 删除线 — S_CONTENT_MAP 匹配
    if "s" in missing and issue.get("s_contents"):
        for sc in issue["s_contents"]:
            for cn_word in S_CONTENT_MAP.get(sc.lower().strip(), []):
                # 检查译文中是否已有错误的 {i} 标签
                wrong_tag = "{i}" + cn_word + "{/i}"
                if wrong_tag in cn:
                    new_cn = cn.replace(wrong_tag, "{s}" + cn_word + "{/s}")
                    return "E_s_tag", new_cn, "high"
                if cn_word in cn:
                    new_cn = cn.replace(cn_word, "{s}" + cn_word + "{/s}", 1)
                    return "E_s_tag", new_cn, "medium"

    # Z: 无法自动修复
    return "Z_manual", cn, "low"


def apply_fixes(issues, tl_dir, dry_run=False):
    """应用修复"""
    fixes_applied = []
    manual_needed = []

    for issue in issues:
        category, new_cn, confidence = classify_and_fix(issue)

        if category == "Z_manual":
            manual_needed.append(issue)
            continue

        if new_cn != issue["cn"]:
            old_raw = issue["raw_line"]

            if issue["is_old_new"]:
                literal = parse_new_line(old_raw)
            else:
                parsed = parse_translation_line(old_raw)
                literal = parsed[0] if parsed is not None else None
            if literal is None:
                # 理论上前置解析已验证目标；保守地转为人工处理。
                manual_needed.append(issue)
                continue
            new_raw = replace_literal_content(old_raw, literal, new_cn)

            fixes_applied.append(
                {
                    "category": category,
                    "confidence": confidence,
                    "file": issue["file"],
                    "line": issue["line"],
                    "old_cn": issue["cn"][:80],
                    "new_cn": new_cn[:80],
                    "en": issue["en"][:80],
                }
            )

            if not dry_run:
                filepath = issue["filepath"]
                with open(filepath, "r", encoding="utf-8", newline="") as f:
                    content = f.read()
                newline = "\r\n" if "\r\n" in content else "\n"
                lines = content.replace("\r\n", "\n").replace("\r", "\n").splitlines(
                    keepends=True
                )
                lines[issue["line"] - 1] = new_raw
                atomic_write_text(
                    filepath,
                    "".join(lines),
                    encoding="utf-8",
                    backup=True,
                    newline=newline,
                )

    return fixes_applied, manual_needed


def main():
    parser = argparse.ArgumentParser(description="修复译文中丢失的 Ren'Py 文本标签")
    parser.add_argument("tl_dir", help="翻译目录")
    parser.add_argument("--dry-run", "-n", action="store_true", help="预览模式")
    parser.add_argument("--apply", action="store_true", help="执行修复")
    parser.add_argument(
        "--report", default="manual_fixes.json", help="人工修复清单输出路径"
    )
    args = parser.parse_args()

    tl_dir = os.path.abspath(args.tl_dir)
    dry_run = args.dry_run or not args.apply

    print(f"扫描目录: {tl_dir}")
    if dry_run:
        print("模式: 预览 (不修改文件)")
    else:
        print("模式: 执行修复")

    # 收集文件
    rpy_files = []
    for root, dirs, files in os.walk(tl_dir):
        dirs[:] = [name for name in dirs if not name.startswith((".", "_"))]
        for fn in files:
            if fn.endswith(".rpy"):
                rpy_files.append(os.path.join(root, fn))

    # 扫描所有问题
    all_issues = []
    for filepath in sorted(rpy_files):
        relpath = os.path.relpath(filepath, tl_dir)
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
        all_issues.extend(extract_tag_issues(lines, filepath, relpath))

    print(f"发现标签问题: {len(all_issues)} 条")

    # 分类修复
    fixes_applied, manual_needed = apply_fixes(all_issues, tl_dir, dry_run)

    # 输出统计
    by_cat = {}
    for f in fixes_applied:
        by_cat.setdefault(f["category"], []).append(f)

    print(f"\n{'=' * 60}")
    print(f"  自动修复: {len(fixes_applied)} 条")
    for cat, items in sorted(by_cat.items()):
        print(f"    {cat}: {len(items)} 条")
    print(f"  待人工修复: {len(manual_needed)} 条")

    if fixes_applied:
        print(f"\n  修复示例:")
        for f in fixes_applied[:5]:
            print(f"    [{f['category']}] {f['file']}:L{f['line']}")
            print(f"      原文: {f['en'][:60]}")
            print(f"      旧译: {f['old_cn'][:60]}")
            print(f"      新译: {f['new_cn'][:60]}")

    # 输出人工修复清单
    if manual_needed:
        manual_data = []
        for issue in manual_needed:
            manual_data.append(
                {
                    "file": issue["file"],
                    "line": issue["line"],
                    "missing_tags": issue["missing_tags"],
                    "en": issue["en"],
                    "cn": issue["cn"],
                    "italic_contents": issue["italic_contents"],
                    "s_contents": issue["s_contents"],
                    "w_positions": issue["w_positions"],
                }
            )
        report_path = os.path.join(os.path.dirname(tl_dir), args.report)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(manual_data, f, ensure_ascii=False, indent=2)
        print(f"\n  人工修复清单: {report_path}")

    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
