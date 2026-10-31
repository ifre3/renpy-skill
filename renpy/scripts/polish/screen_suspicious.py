# -*- coding: utf-8 -*-
"""翻译腔可疑行筛选（局部润色档的"可疑行"定义）。

用法::

    python screen_suspicious.py <tl目录或entries.json> -o candidates.json [--min-score 2]

规则组（在 RULES 里增删即可）：
  翻译腔高频词、英文残留、长度比异常、new==old 长句疑似漏翻。
输出:
  candidates.json —— 可疑行（含 score/hits，锚点齐全可直接回填）
  untranslated.json —— new==old 且像真句子的疑似漏翻
"""
import argparse
import io
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _say_parse import iter_say_entries, strip_tags

# (正则, 名称, 权重)；命中一次即计分
RULES = [
    (r"的.{0,8}的.{0,8}的.{0,8}的", "的连用≥4", 3),
    (r"作为一个", "作为一个", 2),
    (r"对于.{0,12}来说", "对于…来说", 2),
    (r"是否", "是否", 1),
    (r"的话[，。！？…]", "…的话", 1),
    (r"将会", "将会", 1),
    (r"这(真的|确实)是", "这是强调句", 2),
    (r"哦，?我的天", "哦我的天", 3),
    (r"我(真|是)(的)?不敢相信", "不敢相信直译", 2),
    (r"在这里", "在这里直译", 1),
    (r"发生在.{0,6}身上", "happen to 直译", 2),
    (r"被(?=[\u4e00-\u9fff])", "被动句", 1),
    (r"你(知道|看)，", "you know 直译", 1),
    (r"，不是吗[？?]", "不是吗反问", 2),
    (r"(?<!，)不是吗[？?]", "不是吗反问", 2),
    (r"假设[一它这那你我]|假设我|假设你", "假设句式", 1),
    (r"对此[，。]", "对此直译", 1),
    (r"总而言之", "总而言之", 1),
    (r"[A-Za-z]{4,}", "英文词≥4", 1),
    # 2026-10-27 增补（实测 fixes_003：Dissonance 汉化的典型机翻残留）
    (r"^[A-Za-z]{2,}$", "纯单英文词未译", 4),
    (r"〔[^〕]{1,12}〕", "〔…〕角色标记残留", 3),
    (r"[hH]{2,}", "拟声 hhh 残留", 2),
]
MIN_LEN_ENG_RESIDUE = 4
# 英→中译文天然比原文短（实测全库中位数 0.42，19.5% 低于 0.35），把 0.35 当
# 异常会误报掉五分之一的通顺句子——那些被送进 AI 批次后模型判「不用改」，
# 整批空转。下限收到 0.22 才指向真漏翻/截断；权重也从 2 降到 1，避免把
# 1 分级的常见表达（…的话 / 被动句 / 英文词）抬过阈值。
RATIO_LOW, RATIO_HIGH, RATIO_WEIGHT = 0.22, 2.8, 1
# new==old 视为疑似漏翻的最短长度（过短的多为拟声词，应保留）
UNTRANS_MIN_LEN = 8


def entry_score(e):
    """返回 (score, hits, is_untranslated)。"""
    hits, score = [], 0
    t, o = e["trans"], e["orig"]
    for pat, name, w in RULES:
        if re.search(pat, t):
            hits.append(name)
            score += w
    oz = len(re.sub(r"\{[^}]*\}|\s", "", o))
    tz = len(re.sub(r"\{[^}]*\}|\s", "", t))
    ratio = tz / oz if oz else 1.0
    if oz > 0 and (ratio < RATIO_LOW or ratio > RATIO_HIGH):
        hits.append(f"长度比{ratio:.2f}")
        score += RATIO_WEIGHT
    unt = strip_tags(t) == strip_tags(o) and len(strip_tags(t)) > UNTRANS_MIN_LEN \
        and re.search(r"\w\w\s+\w\w", strip_tags(t))
    return score, hits, bool(unt)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    else:  # pragma: no cover
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="翻译腔可疑行筛选")
    ap.add_argument("source", help="tl 目录或 extract_say 输出的 JSON")
    ap.add_argument("-o", "--out", default="candidates.json")
    ap.add_argument("--min-score", type=int, default=2,
                    help="最低可疑分，默认 2（旧版为 3，会漏掉只命中一条低权重规则的行）")
    args = ap.parse_args()

    src = Path(args.source)
    if src.suffix == ".json":
        entries = json.loads(src.read_text(encoding="utf-8"))
    else:
        entries = list(iter_say_entries(src))

    suspicious, untranslated = [], []
    for e in entries:
        if e["trans"] == "":
            continue
        score, hits, unt = entry_score(e)
        if unt:
            untranslated.append(e)
        if score >= args.min_score:
            e2 = dict(e)
            e2["score"], e2["hits"] = score, hits
            suspicious.append(e2)

    suspicious.sort(key=lambda x: (-x["score"], x["file"], x["line"]))
    Path(args.out).write_text(
        json.dumps(suspicious, ensure_ascii=False, indent=1), encoding="utf-8")
    unt_path = Path(args.out).with_name("untranslated.json")
    Path(unt_path).write_text(
        json.dumps(untranslated, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"可疑行 {len(suspicious)} -> {args.out}")
    print(f"疑似漏翻 {len(untranslated)} -> {unt_path}")


if __name__ == "__main__":
    main()
