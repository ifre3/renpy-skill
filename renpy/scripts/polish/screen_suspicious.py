# -*- coding: utf-8 -*-
"""翻译腔可疑行筛选（局部润色档的"可疑行"定义）。

用法::

    python screen_suspicious.py <tl目录或entries.json> -o candidates.json [--min-score 3]

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

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
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
    (r"[A-Za-z]{4,}", "英文词≥4", 1),
]
MIN_LEN_ENG_RESIDUE = 4
RATIO_LOW, RATIO_HIGH, RATIO_WEIGHT = 0.35, 2.8, 2
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
    ap = argparse.ArgumentParser(description="翻译腔可疑行筛选")
    ap.add_argument("source", help="tl 目录或 extract_say 输出的 JSON")
    ap.add_argument("-o", "--out", default="candidates.json")
    ap.add_argument("--min-score", type=int, default=3)
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
