#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
make_glossary.py — 术语表草稿生成 v3（确定性取证端）

分工（学自 LinguaGacha 内置 glossary 技能的架构，app.asar
/builtin/skills/glossary/{SKILL.md,references/rule.md}）：

  * 本脚本只做确定性取证：Character 定义人名、tl strings 配对、
    字面碰撞、出现次数——全部可复现，零猜测
  * 术语资格判断（该不该收、info 怎么写、旧词新用识别）交给 AI
    略读全文——普通词在这部作品里可能是专有概念（"星核"式旧词新用），
    不读原文不可能判断，脚本不做此判定
  * 收录判据（rule.md）：资格 = 身份可建立且需要保持一致；频率只是
    证据之一，不单独构成资格

数据来源（全部离线、确定性）：
  1. game 源码 Character("...") 定义——人名主来源，身份最明确；
     变量插值/动态构造跳过；只有 .rpyc 无源码时提示先反编译
  2. tl strings 块 old→new 配对（逐行匹配，不假定相邻）
  3. tl 对白原文注释的字面出现次数（证据字段，不是门槛）
  4. 字面碰撞（May/may、セラ/セラミック 式包含关系）→ 消歧提示

输出：
  - glossary 草稿 JSON：{"src": "dst"} 扁平格式，只收 Character 定义
    人名（身份由源码确立），直接喂 unify_name_translations.py /
    unify_names.py。普通术语不自动进草稿——等 AI 略读定资格
  - 证据 JSONL：全部候选 {src, dst, info, case_sensitive, count,
    kind, where}，AI 略读时以此为准逐条判定，补语义描述（如
    "A（lo 的姐姐）"）后合并进正式术语表
  - 控制台报告：漂移 / 未翻译 / 碰撞 / AI 略读待判清单

后续 AI 略读工作流见 references/translation_workflow.md「术语表精读」。

用法:
  python make_glossary.py <项目根或game或tl目录> [--lang schinese]
                          [-o glossary_draft.json] [--max-examples N]

退出码: 0=无漂移/未翻译/碰撞问题, 1=有, 2=路径错误
"""

import argparse
import ast
import json
import re
import sys
from collections import Counter
from pathlib import Path

STR_LINE_RE = re.compile(r'^\s*(old|new)\s+("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')\s*$')
STRINGS_HDR_RE = re.compile(r'^translate\s+\w+\s+strings\s*:')
# 对白原文注释：# h "..." / # "..."（与 tl_check 同风格，宽松取整段引号串）
COMMENT_TEXT_RE = re.compile(r'^\s*#\s*(?:.*?\s)?"((?:[^"\\]|\\.)+)"')

# Character 定义首参为纯字面量（_() 包装可选，单双引号均可；变量插值/动态构造不匹配）
CHAR_RE = re.compile(r"""Character\(\s*(?:_?\(\s*)?["']([^"'\[\]{}%\\]+)["']""")

# 专名形状（候选过滤用，不是资格判断）：每词首字母大写、≤4 词、无句读
PROPER_NOUN_RE = re.compile(r"^(?:[A-Z0-9][A-Za-z0-9''\-]*)(?:\s+[A-Z0-9][A-Za-z0-9''\-]*){0,3}$")
CONTAMINATED_RE = re.compile(r"[{}%\[\].,!?…:;\"()（）“”]")

LATIN3 = re.compile(r"[A-Za-z]{3,}")


def unescape(raw: str) -> str:
    try:
        return ast.literal_eval(raw)
    except Exception:
        return raw


def find_dirs(base: Path, lang: str):
    """返回 (tl 目录, game 源码目录或 None)。"""
    tl = None
    for cand in (base, base / "game", base / ".." / "game"):
        t = cand / "tl" / lang
        if t.is_dir():
            tl = t
            break
    if tl is None:
        return None, None
    game = tl.parent.parent  # tl/<lang> → game
    return tl, game if game.name == "game" else None


def scan_strings(tl_dir: Path):
    """逐行扫描全部 strings 块，返回 (old → [(file, line, new)])。"""
    pairs: dict = {}
    for f in sorted(list(tl_dir.glob("*.rpy")) + list(tl_dir.glob("*.rpym"))):
        in_strings = False
        pending_old, pending_line = None, None
        try:
            lines = f.read_text(encoding="utf-8-sig", errors="replace").splitlines()
        except OSError as e:
            print(f"[警告] 读不了 {f.name}: {e}", file=sys.stderr)
            continue
        for lineno, line in enumerate(lines, 1):
            stripped = line.strip()
            if STRINGS_HDR_RE.match(stripped):
                in_strings = True
                pending_old = None
                continue
            if in_strings and stripped.startswith("translate ") and stripped.endswith(":"):
                in_strings = False
                pending_old = None
                continue
            if not in_strings:
                continue
            sm = STR_LINE_RE.match(line)
            if not sm:
                continue
            kind, text = sm.group(1), unescape(sm.group(2))
            if kind == "old":
                pending_old, pending_line = text, lineno
            else:
                if pending_old is not None:
                    pairs.setdefault(pending_old, []).append((f.name, pending_line, text))
                pending_old = None
    return pairs


def scan_characters(game_dir: Path):
    """扫 game/**/*.rpy 的 Character("Name") 定义，返回 {name: "file:line"}。

    只认首参是纯字面量的（变量插值/动态构造跳过——那是运行时才知道的名字）；
    无 .rpy 源码（纯 .rpyc 发行版）时返回 None 并提示反编译。"""
    files = [p for p in game_dir.rglob("*.rpy") if "tl" not in p.parts]
    if not files:
        return None
    found: dict = {}
    for f in sorted(files):
        try:
            lines = f.read_text(encoding="utf-8-sig", errors="replace").splitlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, 1):
            for m in CHAR_RE.finditer(line):
                found.setdefault(m.group(1), f"{f.relative_to(game_dir)}:{lineno}")
    return found


def count_in_dialogue(tl_dir: Path, terms: list):
    """统计每个候选在 tl 对白原文注释里的字面出现次数（证据字段）。

    一次性读入拼接，对每个候选取 count——候选几百个 × 几万行也在秒级。"""
    chunks = []
    for f in sorted(list(tl_dir.glob("*.rpy")) + list(tl_dir.glob("*.rpym"))):
        try:
            for line in f.read_text(encoding="utf-8-sig", errors="replace").splitlines():
                cm = COMMENT_TEXT_RE.match(line)
                if cm:
                    chunks.append(unescape('"' + cm.group(1) + '"'))
        except OSError:
            continue
    text = "\n".join(chunks)
    return {t: text.count(t) for t in terms}


def is_proper_noun(s: str) -> bool:
    if not (2 <= len(s) <= 40) or CONTAMINATED_RE.search(s):
        return False
    return PROPER_NOUN_RE.fullmatch(s) is not None


def find_collisions(terms: list):
    """字面包含关系 → 碰撞对（May/may、セラ/セラミック 的离线近似）。

    返回 {term: [对方词条...]}；命中方建议 case_sensitive 并按语境消歧。"""
    coll: dict = {}
    tset = list(terms)
    for i, a in enumerate(tset):
        for b in tset[i + 1:]:
            if a == b:
                continue
            lo, hi = (a, b) if len(a) <= len(b) else (b, a)
            if lo.lower() in hi.lower():
                coll.setdefault(a, []).append(b)
                coll.setdefault(b, []).append(a)
    return coll


def main():
    ap = argparse.ArgumentParser(description="术语表草稿生成 v3（确定性取证端）")
    ap.add_argument("path", help="项目根目录 / game 目录 / tl 目录")
    ap.add_argument("--lang", default="schinese")
    ap.add_argument("-o", "--output", default="glossary_draft.json",
                    help="草稿 JSON 路径（默认 ./glossary_draft.json；"
                         "证据另存为 <output>.evidence.jsonl）")
    ap.add_argument("--max-examples", type=int, default=20,
                    help="每类报告最多打印条数（默认 20）")
    args = ap.parse_args()

    tl, game = find_dirs(Path(args.path), args.lang)
    if tl is None:
        print(f"[错误] 在 {args.path} 下找不到 tl/{args.lang}", file=sys.stderr)
        sys.exit(2)

    # ── 来源 1：Character 定义（人名主来源，身份最明确）──
    chars = scan_characters(game) if game and game.is_dir() else None
    if chars is None:
        print("[提示] 未找到 .rpy 源码（纯 .rpyc 发行版），人名只能依赖 tl strings 块；"
              "需要更全的人名清单可先用 renpy-script-decompile 反编译")
    char_names = set(chars or {})

    # ── 来源 2：tl strings 块 ──
    pairs = scan_strings(tl)

    candidates: dict = {}  # src -> {"kind", "news", "where"}
    for old, occ in pairs.items():
        if not is_proper_noun(old):
            continue
        candidates[old] = {"kind": "character" if old in char_names else "term",
                           "news": Counter(n for _, _, n in occ), "where": occ[0]}
    # strings 块没抓到、但源码里定义了的 Character 人名（初翻前 strings 还是空的）
    for name in char_names - set(candidates):
        if is_proper_noun(name):
            candidates[name] = {"kind": "character", "news": Counter(), "where": chars[name]}

    # ── 频率：证据字段，不是收录门槛 ──
    freq = count_in_dialogue(tl, list(candidates)) if candidates else {}

    draft: dict = {}
    evidence: list = []
    drift, untranslated, term_pool = [], [], []
    for old, c in sorted(candidates.items()):
        news = c["news"]
        count = freq.get(old, 0)
        where = (f"{c['where'][0]}:{c['where'][1]}" if isinstance(c["where"], tuple)
                 else str(c["where"]))

        if len(news) > 1:
            best, n_best = news.most_common(1)[0]
            variants = "、".join(f'"{n}"×{k}' for n, k in news.most_common())
            drift.append((old, news))
            if c["kind"] == "character" and n_best > 1:
                draft[old] = best  # 身份明确 + 多数派 → 可自动定稿
        elif news and old == next(iter(news)) and LATIN3.search(old):
            untranslated.append((old, where))
        elif news:
            if c["kind"] == "character":
                draft[old] = next(iter(news))  # 身份由源码确立，译名唯一 → 必收
            else:
                term_pool.append((old, next(iter(news)), count))
        else:
            untranslated.append((old, where))  # 只有源码定义、尚无译文（初翻前）

        if c["kind"] == "character":
            info = f"Character 定义于 {chars.get(old, '?')}"
        else:
            info = "普通术语候选，资格由 AI 略读判定"
        evidence.append({"src": old, "dst": draft.get(old, next(iter(news)) if news else ""),
                         "info": info, "case_sensitive": True,
                         "count": count, "kind": c["kind"], "where": where})

    # ── 碰撞检查（字面包含 → 消歧提示）──
    coll = find_collisions(list(candidates))
    for term, others in coll.items():
        for e in evidence:
            if e["src"] == term:
                e["info"] += f"；⚠ 与 {'、'.join(others)} 存在字面包含，按语境消歧"
                e["collisions"] = others
                break

    # ── 报告 ──
    print(f"扫描 {tl}"
          + (f"（Character 定义 {len(char_names)} 个）" if chars is not None else "（无源码）")
          + f"：候选 {len(candidates)}，人名草稿 {len(draft)}，AI 待判术语 {len(term_pool)}")

    if drift:
        print(f"\n== [漂移] 同一原文多种译名 ({len(drift)} 条) ==")
        for old, news in drift[:args.max_examples]:
            variants = "、".join(f'"{n}"×{k}' for n, k in news.most_common())
            print(f'  "{old}" → {variants}')
        if len(drift) > args.max_examples:
            print(f"  ... 其余 {len(drift) - args.max_examples} 条省略")

    if untranslated:
        print(f"\n== [未翻译] 译文与原文相同或尚无译文 ({len(untranslated)} 条) ==")
        for old, where in untranslated[:args.max_examples]:
            print(f'  "{old}"  ({where})')
        if len(untranslated) > args.max_examples:
            print(f"  ... 其余 {len(untranslated) - args.max_examples} 条省略")

    if term_pool:
        print(f"\n== [AI 待判] 术语资格由略读判定 ({len(term_pool)} 条，详情见证据 JSONL) ==")
        for old, dst, count in term_pool[:args.max_examples]:
            print(f'  "{old}" → "{dst}"（出现 {count} 次）')
        if len(term_pool) > args.max_examples:
            print(f"  ... 其余 {len(term_pool) - args.max_examples} 条省略")

    if coll:
        print(f"\n== [碰撞] 字面包含关系，翻译需按语境消歧 ({len(coll)} 条) ==")
        for term in list(coll)[:args.max_examples]:
            print(f'  "{term}" ↔ {coll[term]}')

    out = Path(args.output)
    out.write_text(json.dumps(draft, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ev = out.with_suffix(out.suffix + ".evidence.jsonl")
    ev.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in evidence),
                  encoding="utf-8")
    print(f"\n草稿: {out.resolve()}（Character 人名 {len(draft)} 条，直接喂 unify_name_translations.py / unify_names.py）")
    print(f"证据: {ev.resolve()}（全部候选含 info/count/collisions，AI 略读判定资格后合并进正式术语表）")
    sys.exit(1 if (drift or untranslated or coll) else 0)


if __name__ == "__main__":
    main()
