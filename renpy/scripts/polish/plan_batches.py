#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""润色批次规划：切批 + 场景边界 + 提示词装上下文 + 批次账本。

用法::

    python plan_batches.py --pool entries.json --tl <tl目录> \\
        [--candidates cand.json qcand.json] [--batch-size 200] \\
        -o <项目根>/.cache/polish/

为什么需要这个脚本（2026-10-11，Dissonance 0.14 实测 44,387 条 say 条目）:
``references/translation_polish.md`` 的策略一写了「~200 句/批」「在
polish_state.json 维护批次状态」，但没有任何脚本产出它们——切批、场景分组、
提示词装上下文、账本全靠人手工做。本脚本把这几件事合成一次遍历。

## 三条硬约束（写进工具本身，不靠人自觉）

1. **场景段不被劈开**：以 `translate <lang> <label>_<hash>:` 的 label 为边界，
   按 ~200 条上限合并**相邻**场景。实测：连续同场景段共 3,637 个，最长 223 条、
   中位数仅 1 条——所以「每场景一批」会切出数千批，比不切还糟。只有单场景超过
   上限才按条切，并标 ``split: true`` 让下一批从同一场景续。
2. **已 consumed 的批次不再产出**：落实「润色只做一轮，越润越差」的实测结论。
   重跑同一命令，已完成的批次不会被重新生成。
3. **不碰写入通道**：本脚本只产出批次 JSON / 提示词 / 账本；回填仍走
   ``merge_polish.py`` + ``autotranslate.py apply --overwrite``。

## 刻意保持简单（2026-10-18）

曾经提供 ``--auto-screen``（内置跑两个筛行器）与 ``--direct-fixes``（预载规则层
改写结果）。两者都删了，因为各自都有一条更简单的等价路径：

- 要筛行：``screen_suspicious.py`` / ``screen_quality.py`` 各自产出 JSON，再
  ``--candidates a.json b.json`` 传入——筛行规则因此只有一个维护处。
- 要先过规则层：``direct_polish.py --apply`` 写回 tl，重新 ``extract_say.py``
  抽条目，再跑本脚本。多一次抽取，换来不必在切批器里维护第二份改写状态。

留下的选项各司其职，没有第二条路做同一件事。

产出（都在 ``-o`` 目录）：

- ``batch_NNN.json``      —— 锚点齐全，可直接进 merge_polish / apply
- ``batch_NNN.prompt.md`` —— 每批自带角色表、禁改清单、术语表指向 + 连续剧本
- ``polish_state.json``   —— 批次号 / file 范围 / 行数 / consumed，跨会话续跑
"""

import argparse
import io
import json
import os
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
else:  # pragma: no cover
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

#: `translate schinese foo_1234abcd:` —— 去掉末尾 8 位哈希得到场景名。
LABEL_RE = re.compile(r"^translate\s+\w+\s+([A-Za-z_][\w]*?)(?:_([0-9a-f]{8}))?\s*:\s*$")

DEFAULT_BATCH_SIZE = 200

#: 提示词里必须写死的禁改清单。来源：translation_polish.md 策略一步骤 3 +
#: polish/README.md 实测注意（裸 % 在 safe_text=False 下直接崩溃）。
DO_NOT_TOUCH = [
    "`{tag}` 文本标签（`{i}` `{b}` `{w}` `{cps=…}` 等）—— 一个字符都不许动",
    "`[var]` / `[var!t]` 插值及其转换标志 —— 不许改写、不许增删",
    "`%%`（百分号必须成对）—— 裸 `%` 在 `config.safe_text=False` 下显示到该行直接崩溃",
    "`\\n` `\\\"` `[[` 等转义符 —— 不许擅自展开或删除",
    "行号、`# game/...` 路径注释、`translate` 块结构 —— 只改译文内容",
]


def load_scene_map(tl_dir):
    """回扫 tl 目录，建立 ``(文件名, 行号) -> 场景名``。

    ``extract_say.py`` 的条目没有场景字段，这是当前数据结构唯一的硬缺口。
    返回 dict；tl 目录不可读时返回空 dict（调用方降级为按文件顺序切批）。
    """
    out = {}
    tl = Path(tl_dir)
    if not tl.is_dir():
        return out
    for f in sorted(tl.glob("*.rpy")):
        try:
            lines = f.read_text(encoding="utf-8-sig", errors="replace").splitlines()
        except OSError:
            continue
        for i, line in enumerate(lines, 1):
            m = LABEL_RE.match(line)
            if m:
                out[(f.name, i)] = m.group(1)
    return out


def attach_scenes(entries, scene_map):
    """给条目补 ``scene`` 字段。

    条目的 ``line`` 是原文注释行号，而场景 label 在它上面 1~2 行
    （`translate` 行 → 空行 → 原文注释）。从 line 往上找最近的 label。
    """
    if not scene_map:
        for e in entries:
            e["scene"] = ""
        return entries
    for e in entries:
        fname, line = e.get("file"), e.get("line")
        scene = ""
        for back in range(0, 6):  # label 行到原文注释行最多隔几行空行/注释
            hit = scene_map.get((fname, line - back))
            if hit:
                scene = hit
                break
        e["scene"] = scene or Path(fname).stem
    return entries


def build_scene_segments(entries):
    """按 (file, scene) 的**连续**出现切成段，保持原有顺序。

    同一场景在文件里出现多次（如 menu 复用）会成为多个段，这是对的——
    它们本来就不连续，硬合并会把无关文本塞进同一批。
    """
    segments = []
    cur_key, cur = None, []
    for e in entries:
        key = (e.get("file"), e.get("scene", ""))
        if key != cur_key:
            if cur:
                segments.append((cur_key, cur))
            cur_key, cur = key, []
        cur.append(e)
    if cur:
        segments.append((cur_key, cur))
    return segments


def plan(segments, batch_size):
    """把场景段装进批次：不劈开段，除非单段超过 batch_size。

    超过上限的段按条切，且每个被切开的子批都标 ``split: true``
    （提示：本批与相邻批属于同一场景，术语与语气要一致）。
    """
    batches = []
    cur, cur_scenes, cur_size = [], [], 0
    for (_fname, scene), items in segments:
        if cur and cur_size + len(items) > batch_size:
            batches.append((cur, cur_scenes, False))
            cur, cur_scenes, cur_size = [], [], 0
        if len(items) > batch_size:
            # 单场景本身超限：先收尾当前批，再按条切这个大段
            if cur:
                batches.append((cur, cur_scenes, False))
                cur, cur_scenes, cur_size = [], [], 0
            n_chunks = (len(items) + batch_size - 1) // batch_size
            for i in range(0, len(items), batch_size):
                chunk = items[i:i + batch_size]
                # n_chunks > 1 表示本场景被切开，标记提示 AI 保持术语/语气一致
                batches.append((chunk, [scene], n_chunks > 1))
        else:
            cur.extend(items)
            if scene not in cur_scenes:
                cur_scenes.append(scene)
            cur_size += len(items)
    if cur:
        batches.append((cur, cur_scenes, False))
    return batches


def _entry_for_apply(e, new_trans=None):
    """条目 → apply 批次条目（锚点齐全）。"""
    out = {
        "file": e["file"],
        "line": e["line"],
        "type": e.get("type", "tb"),
        "orig": e.get("orig", ""),
        "trans": e.get("trans", "") if new_trans is None else new_trans,
    }
    if e.get("char"):
        out["char"] = e["char"]
    return out


def load_state(out_dir):
    p = Path(out_dir) / "polish_state.json"
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            pass
    return {"batches": [], "version": 1}


#: 剧本块里单行原文/译文超过此长度才截断。审稿要读完整句子才谈得上"通不通顺"，
#: 旧版一律截到 90 字，实测 39.4% 的行原文被砍断（44,387 条里 17,485 条），
#: 模型看到半句既判断不了语病，也判断不了前后衔接。
SCRIPT_MAX_CHARS = 400

#: Tier B —— 这些行**只看译文改不动**，必须对照原文，否则只能瞎猜。
#: 实测（Dissonance 0.14，44,387 条）命中约 350 条 ≈ 0.8%；其余 99% 只给译文即可，
#: 省一半 prompt 体积。取向是「宁可漏标不可误标」：误标只是多看一眼原文，
#: 漏标则会让审稿者在没有依据的情况下改写语义（实测教训：把 `私室` 猜成「包厢」）。
TIER_B_RULES = [
    (re.compile(r"[A-Za-z]{3,}"), "外文残留：可能漏翻，也可能是刻意的原文保留"),
    (re.compile(r"[\u3041-\u30ff]"), "假名残片：日文残留"),
    (re.compile(r"[（(]\s*[?？]+\s*[)）]"), "译者留下的疑虑标记"),
]

#: 长度比下界：英文词数 → 中文字数的期望倍率约 1.2；低于 0.8 视为疑似漏译。
_LEN_RATIO_MIN = 0.8
_EN_WORD_MIN = 6


def _strip_markup(text):
    """剥掉 {标签} 与 [插值]，避免把结构当外文残留、或把标签算进长度比。"""
    text = re.sub(r"\{[^}]*\}", "", text)
    return re.sub(r"\[[^\]]*\]", "", text)


def classify_entry(e):
    """判定该行是 Tier A（只看译文）还是 Tier B（须对照原文）。

    返回 ``("A", [])`` 或 ``("B", [信号, ...])``。

    分层依据：语病、语序、冗余、语气一律 Tier A——中文母语审稿人读译文就能判断；
    只有**语义、术语、完整性**存疑时才升级到 B，因为那正是「看译文硬改」会出事
    的地方。纯占位行（``...``）归 A 但无可审内容。
    """
    orig = e.get("orig") or ""
    trans = e.get("trans") or ""
    if not trans.strip() or set(trans.strip()) <= set(".… 　"):
        return "A", []

    natural = _strip_markup(trans)
    reasons = [msg for pat, msg in TIER_B_RULES if pat.search(natural)]

    words = len(re.findall(r"[A-Za-z']+", orig))
    if words >= _EN_WORD_MIN:
        ratio = len(_strip_markup(trans)) / words
        if ratio < _LEN_RATIO_MIN:
            reasons.append(f"长度比 {ratio:.2f}（疑似漏译或过度压缩）")

    return ("B", reasons) if reasons else ("A", [])


def _one_line(text):
    """把可能含换行/竖线的文本压成单行可读形式（剧本块不是 markdown 表格了）。"""
    return (text or "").replace("\\", "\\\\").replace("\n", "\\n")


def _script_block(items):
    """把条目渲染成连续剧本块，按 Tier 分层给料。

    Tier A（语病/语序/冗余/语气）—— 只给译文。这类问题中文母语读译文就能判断，
    原文是多余的，占一半 prompt 体积。实测占全库 99%。
    Tier B（外文残留/假名/长度比异常）—— 给原文+译文。这类是语义与完整性问题，
    只看译文改就是瞎猜（实测教训：把 `私室` 猜成「包厢」）。

    为什么不是表格：表格把每行变成独立四元组，审稿者看不到"这句接上一句"，
    也看不到同一个人在连续对白里的语气变化——那恰恰是"上下文流畅"的全部。
    剧本块按原始出现顺序排列，保留 `file:line` 锚点以便回填。
    """
    out = []
    cur_scene = object()   # 哨兵：保证第一个场景一定打印标题
    for e in items:
        scene = e.get("scene", "")
        if scene != cur_scene:
            cur_scene = scene
            title = scene or "(无场景名)"
            out.append(f"### 场景：`{title}`")
        anchor = f"`{e['file']}:{e['line']}`"
        tier, reasons = classify_entry(e)
        orig = _one_line(e.get("orig"))
        trans = _one_line(e.get("trans"))
        if len(orig) > SCRIPT_MAX_CHARS:
            orig = orig[:SCRIPT_MAX_CHARS] + "…"
        if len(trans) > SCRIPT_MAX_CHARS:
            trans = trans[:SCRIPT_MAX_CHARS] + "…"
        char = e.get("char") or ""
        who = char if char else "旁白"
        if tier == "B":
            out.append(f"{anchor} {who}：  ⚠ {reasons[0]}")
            out.append(f"  原：{orig}")
            out.append(f"  译：{trans}")
        else:
            out.append(f"{anchor} {who}：")
            out.append(f"  {trans}")
    return out


def find_glossary(project_root):
    """探测术语表：术语表.xlsx（make_glossary.py 产物）优先于 翻译结果.md。

    实测教训：拿 .cache 里的 glossary_draft 核对覆盖会漏掉 2/3 条目（16 vs 47），
    因为 draft 只是取证中间产物，定稿在 xlsx。润色必须看定稿。
    """
    for name in ("术语表.xlsx", "翻译结果.md"):
        p = Path(project_root) / name
        if p.is_file():
            return str(p)
    return None


def render_prompt(batch_no, items, scenes, split, chars, prev_terms,
                  glossary_hint):
    """生成一批的提示词：AI 拿到就能直接开工，不用再去翻流程文档。

    2026-10-18 从"机翻矫正表"改为"连续剧本审稿"。旧版把每行渲染成
    `| file:line | 角色 | 原文 | 译文 |` 表格且一律截断到 90 字，并要求
    "去翻译腔/改口语/修正语法"三件事——等于鼓励逐行找茬，违背本项目自己的
    实测结论"润色只做一轮、越润越差"。新版按场景连成剧本块、不截断长句、
    并明确允许"不改"。
    """
    lines = []
    lines.append(f"# 审稿批次 {batch_no:03d}（{len(items)} 条）\n")
    if scenes:
        lines.append(f"涉及场景：{', '.join(scenes[:8])}"
                     + (f" 等 {len(scenes)} 个" if len(scenes) > 8 else ""))
    if split:
        lines.append("⚠️ 本批是某场景被切开的一部分：与相邻批属同一场景，"
                     "术语与角色语气必须保持一致。")
    lines.append("")
    lines.append("## 你的角色")
    lines.append("你是这段剧本的**中文审稿人**。下面按场景给出连续对白，请像读稿一样通读，"
                 "判断译文是否**读起来顺**。")
    lines.append("")
    lines.append("**核心原则：大部分句子是好的，保持原样。**")
    lines.append("只有当某句确实读着别扭（语序生硬、词不达意、语气与角色不符、"
                 "和前后句衔接不上）时才改；拿不准就不改。")
    lines.append("逐句找茬式改写会让通顺的句子变差——这是润色的头号副作用。")
    lines.append("禁止增删剧情信息（不要加原文没有的细节，也不要丢原文有的）。\n")
    lines.append("## 怎么读这批")
    lines.append("每条只给**译文**——语病、语序、冗余、语气这类问题，读中文就能判断。")
    lines.append("标了 `⚠` 的那几条额外给了**原文**：它们有外文残留或长度异常，"
                 "属于语义与完整性问题，**必须对照原文改，不要猜**。")
    lines.append("没标 `⚠` 的行若你觉得信息不足以判断，就跳过它，不要硬改。\n")
    lines.append("## 可以做的")
    lines.append("- 让别扭的句子自然、符合中文口语")
    lines.append("- 让语气贴合说话人（角色性格、身份、亲疏远近）")
    lines.append("- 让相邻两句**连贯**：承接、递进、语气呼应，读下来一气呵成")
    lines.append("- 修正语法与用词错误")
    lines.append("")
    lines.append("## 禁止改动（改了就会崩或显示错）")
    for d in DO_NOT_TOUCH:
        lines.append(f"- {d}")
    lines.append("")
    if chars:
        lines.append("## 本批出现的角色")
        for c, n in chars[:20]:
            lines.append(f"- `{c}`（{n} 条）")
        lines.append("")
    if prev_terms:
        lines.append("## 前批已定术语（本批必须沿用）")
        for term in prev_terms:
            lines.append(f"- {term}")
        lines.append("")
    if glossary_hint:
        lines.append("## 术语一致性")
        lines.append(f"润色前先读 {glossary_hint} 的「专有名词」章；")
        lines.append("本批改了人名/专名时，把新术语记下来回写进去。\n")
    lines.append("## 输出格式")
    lines.append("只给 `fixes.json` 的内容——一个 JSON 对象，键是 `file:line`，"
                 "值是**改动后**的整行译文。")
    lines.append("")
    lines.append("**只列出真正改动过的行；判断为「不用改」的句子不要出现。**"
                 "（`merge_polish.py` 用条目池补齐锚点，漏掉的行默认保持原样。）")
    lines.append("")
    lines.append("```json")
    lines.append("{")
    for e in items[:3]:
        lines.append(f'  "{e["file"]}:{e["line"]}": "...",')
    lines.append("  ...")
    lines.append("}")
    lines.append("```")
    lines.append("")
    lines.append(f"共 {len(items)} 条待读。回填走 `merge_polish.py` → "
                 "`autotranslate.py apply --overwrite`（先 --dry-run）。")
    lines.append("")
    lines.append("## 剧本")
    lines.append("")
    lines.extend(_script_block(items))
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(
        description="润色批次规划：场景感知切批 + 提示词 + 账本")
    ap.add_argument("--pool", required=True,
                    help="extract_say.py 输出的条目池 JSON")
    ap.add_argument("--tl", help="tl 目录（用于回扫场景 label；不给则按文件顺序切批）")
    ap.add_argument("--candidates", nargs="*", default=[],
                    help="筛行器输出的 JSON（只润这些行）；不给则润整个池")
    ap.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    ap.add_argument("--skip-placeholders", action="store_true",
                    help="跳过译文为 '...' 之类纯占位的行（实测占 5.5%%，无可审内容）")
    ap.add_argument("--tier-report", metavar="PATH",
                    help="把 Tier A/B 分层结果写成 JSON：哪些行必须对照原文")
    ap.add_argument("-o", "--out", required=True, help="输出目录（建议 <项目根>/.cache/polish/）")
    ap.add_argument("--glossary",
                    help="术语表路径，写进提示词（默认按 术语表.xlsx > 翻译结果.md 探测项目根）")
    ap.add_argument("--reset", action="store_true", help="忽略账本重排（会覆盖已产出批次）")
    args = ap.parse_args()

    entries = json.loads(Path(args.pool).read_text(encoding="utf-8-sig"))
    if not isinstance(entries, list):
        print("[ERROR] 条目池顶层必须是数组")
        return 2

    # ── 候选行筛选（唯一入口：--candidates 传筛行器产物；不传则润整个池）──
    if args.candidates:
        wanted = set()
        for c in args.candidates:
            p = Path(c)
            if not p.is_file():
                print(f"[WARN] 筛行结果不存在，跳过: {c}")
                continue
            for item in json.loads(p.read_text(encoding="utf-8-sig")):
                wanted.add((item.get("file"), item.get("line")))
        before = len(entries)
        entries = [e for e in entries if (e.get("file"), e.get("line")) in wanted]
        print(f"筛行后 {len(entries)} 条（池里共 {before} 条）")

    if not entries:
        print("[ERROR] 没有待润色条目")
        return 1

    # Tier A/B 分层：Tier B 才有原文，Tier A 只给译文。分层统计先打出来，
    # 让调用方知道这批里有多少行是"必须对照原文"的。
    tier_b = [e for e in entries if classify_entry(e)[0] == "B"]
    if tier_b:
        print(f"分层：Tier B（须对照原文）{len(tier_b)} / {len(entries)} 条 "
              f"({len(tier_b)/len(entries)*100:.1f}%)")
    if args.tier_report:
        Path(args.tier_report).write_text(json.dumps(
            [{"file": e["file"], "line": e["line"], "reasons": classify_entry(e)[1],
              "orig": e.get("orig", ""), "trans": e.get("trans", "")}
             for e in tier_b], ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"Tier B 清单 -> {args.tier_report}")

    scene_map = load_scene_map(args.tl) if args.tl else {}
    if args.tl and not scene_map:
        print(f"[WARN] {args.tl} 里没解析到 translate 块，降级为按文件顺序切批")
    entries = attach_scenes(entries, scene_map)
    # 保序：先按文件、再按行号，保证同场景连续
    entries.sort(key=lambda e: (e.get("file", ""), e.get("line", 0)))

    segments = build_scene_segments(entries)
    if args.skip_placeholders:
        segments = [(k, [e for e in items
                         if not set((e.get("trans") or "").strip()) <= set(".… 　")])
                    for k, items in segments]
        segments = [(k, items) for k, items in segments if items]
    batches = plan(segments, args.batch_size)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    state = {"batches": [], "version": 1} if args.reset else load_state(out)
    # 账本只保留「已 consumed」的批：重跑时未消费的批会被重排（条目集合可能
    # 因为筛行结果变化而变了），已消费的按首条目锚点去重，不再产出。
    # 编号在保留下来的批之后顺延，保证批次号与 JSON 文件名一一对应。
    kept = [b for b in state.get("batches", []) if b.get("consumed")]
    state["batches"] = kept
    done_keys = {(b.get("first_file"), b.get("first_line")) for b in kept}
    if done_keys:
        print(f"账本保留 {len(done_keys)} 个已完成批次，不会重复产出")

    # ── 术语表：显式 --glossary 优先，否则探测项目根 ──
    glossary_hint = args.glossary
    if not glossary_hint:
        root = Path(args.out).parent.parent if args.out else Path(".")
        glossary_hint = find_glossary(root)
        if glossary_hint is None:
            print("[提示] 项目根未找到 术语表.xlsx / 翻译结果.md；"
                  "润色前应先定术语，否则 AI 只能凭上下文猜译名：\n"
                  f"    python names/make_glossary.py {root} "
                  "--lang schinese -o glossary.json")
        else:
            print(f"术语表: {glossary_hint}")

    # 跨批术语：前批回写进账本 new_terms 的术语要带进后续提示词，否则术语会漂。
    prev_terms = []
    for b in state.get("batches", []):
        for term in b.get("new_terms", []):
            if term not in prev_terms:
                prev_terms.append(term)

    written = 0
    idx = len(kept)
    for items, scenes, split in batches:
        first = items[0]
        key = (first.get("file"), first.get("line"))
        if key in done_keys:
            continue
        idx += 1
        no = idx
        stem = f"batch_{no:03d}"
        (out / f"{stem}.json").write_text(
            json.dumps([_entry_for_apply(e) for e in items],
                       ensure_ascii=False, indent=1),
            encoding="utf-8")

        counts = {}
        for e in items:
            if e.get("char"):
                counts[e["char"]] = counts.get(e["char"], 0) + 1
        chars = sorted(counts.items(), key=lambda kv: -kv[1])

        files = sorted({e["file"] for e in items})
        (out / f"{stem}.prompt.md").write_text(
            render_prompt(no, items, scenes, split, chars, prev_terms,
                          glossary_hint),
            encoding="utf-8")

        state.setdefault("batches", []).append({
            "no": no,
            "json": f"{stem}.json",
            "prompt": f"{stem}.prompt.md",
            "count": len(items),
            "files": files,
            "scenes": scenes,
            "split": bool(split),
            "first_file": first.get("file"),
            "first_line": first.get("line"),
            "consumed": False,
            "new_terms": [],
        })
        written += 1

    (out / "polish_state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"产出 {written} 批 -> {out}")
    print(f"账本: {out / 'polish_state.json'}"
          f"（共 {len(state.get('batches', []))} 批记录）")
    print("\n下一步：")
    print("  1. 读 batch_NNN.prompt.md，AI 产出 fixes.json")
    print("  2. python merge_polish.py --pool entries.json --fixes fixes.json "
          "-o polish_batch.json")
    print("  3. python ../translate/autotranslate.py apply <tl目录> "
          "--input polish_batch.json --overwrite --dry-run")
    print("  4. 核对 SKIP 数后去掉 --dry-run 实写（自动 .bak）")
    print("  5. 把该批在 polish_state.json 里标 consumed=true，再跑下一批")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
