# -*- coding: utf-8 -*-
"""硬性质校筛行：外文残留 / 假名残片 / 半角标点 / 相似度漏翻。

与 ``screen_suspicious.py``（翻译腔风格筛行）互补：本脚本只管「机械可判」的
硬性问题，规则判定经验移植自 LinguaGacha（github.com/neavo/LinguaGacha，
src/shared/text/translation-quality-rules.ts 等文件，2026-10 摘录）：

- 外文残留按「连续拉丁段」聚合成一条证据（而非散字符计数）；孤立单字母与
  2-4 字全大写缩写（HP/RPG/OK）证据不足，豁免——因此夹生词可以给高信号，
  不再依赖翻译腔权重凑分。
- 免翻词豁免（其 rule-prefilter.ts 的 Ren'Py 实测清单：默认字体名、
  {#file_time} 存档时间戳、EV 事件编号）。
- 相似度用包含快判 + 字符集 Jaccard > 0.8（其 is_translation_text_similar
  同口径），抓「原文照抄加点料」的局部漏翻——与 screen_suspicious 的
  new==old 检测互补。
- 假名残片口径与 ``../sdk/tl_check.py`` 一致（[ぁ-ヿ]+，汉字不算）。

用法（输入输出与 screen_suspicious.py 同约定）::

    python screen_quality.py <tl目录或entries.json> -o quality_candidates.json [--lang schinese]

输出:
  quality_candidates.json ---- 硬性质可疑行（file/line/orig/trans 锚点 + hits，可直接进回填管线）
  quality_untranslated.json -- 相似度漏翻（new≈old 但未全抄，screen_suspicious 抓不到的形态）
退出码: 有命中=1，无命中=0（renpy-tools 惯例），用法错误=2
"""
import argparse
import io
import json
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).parent))
from _say_parse import iter_say_entries  # noqa: E402

# 连续拉丁段（外文残留的聚合单位；对齐 LG 的字素聚合思路，标准库近似）
LATIN_RUN_RE = re.compile(r"[A-Za-z]+")
# 日文假名（平假名 U+3041-309F + 片假名 U+30A0-30FF），与 tl_check 的 KANA_RE 同区间
KANA_RE = re.compile(r"[\u3041-\u30FF]+")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
# 半角标点残留：!? 必报；, 除数字千分位（1,000）外必报。句点/冒号合法场景
# 太多（小数、文件名、时间），不查。
HALF_PUNCT_RE = re.compile(r"[!?]")
SIMILARITY_THRESHOLD = 0.8   # LG 同阈值：字符集 Jaccard
SIM_MIN_LEN = 4              # 过短的相似行多为标点/拟声，豁免（对齐 screen_suspicious 思路）

# 免翻短语（大小写不敏感，命中后从文本中剔除再判残留）。来源：LG
# rule-prefilter.ts 的 Ren'Py 清单（默认字体名、引擎名）适配成短语级——
# 按单词拆段后 "DejaVu Sans" 的 "Sans"、"Ren'Py" 的 "Ren"/"Py" 仍会误报，
# 必须在拆段前先剔除。需要时在此增删（如项目专名）。
EXEMPT_PHRASES = ("dejavu sans", "dejavusans", "dejavu", "opendyslexic", "ren'py", "renpy")
EV_RE = re.compile(r"^EV\d+$", re.I)   # 事件编号（LG rule-prefilter）


def strip_markup(s):
    """剥掉 {文本标签} 与 [插值]/[[转义]，只留自然文本，避免把结构当残留。"""
    s = re.sub(r"\{[^}]*\}", "", s)
    s = re.sub(r"\[\[[^\]]*\]\]", "", s)
    return re.sub(r"\[[^\]]*\]", "", s)


def foreign_residue_fragments(text):
    """需要报告的外文残留片段（连续拉丁段聚合，保序去重，已应用豁免）。"""
    for ph in EXEMPT_PHRASES:
        text = re.sub(re.escape(ph), " ", text, flags=re.I)
    frags, seen = [], set()
    for m in LATIN_RUN_RE.finditer(text):
        frag = m.group(0)
        if EV_RE.match(frag):
            continue
        if len(frag) == 1:                      # 单字母证据不足：A 班、X 光
            continue
        if re.fullmatch(r"[A-Z]{2,4}", frag):   # 2-4 字大写缩写：HP/RPG/OK
            continue
        if frag not in seen:
            seen.add(frag)
            frags.append(frag)
    return frags


def kana_fragments(text):
    """文本中的假名连续片段（保序去重）。汉字不算——先輩 不报。"""
    frags, seen = [], set()
    for m in KANA_RE.finditer(text):
        frag = m.group(0)
        if frag not in seen:
            seen.add(frag)
            frags.append(frag)
    return frags


def half_punct_hits(text):
    """中文译文里的半角标点集合（, 数字间豁免）；无中文正文的行不判。"""
    if not CJK_RE.search(text):
        return set()
    hits = set(HALF_PUNCT_RE.findall(text))
    for m in re.finditer(r",", text):
        pre = text[m.start() - 1 : m.start()]
        post = text[m.end() : m.end() + 1]
        if pre.isdigit() and post.isdigit():    # 1,000 千分位
            continue
        hits.add(",")
    return hits


def _char_set(s):
    return set(strip_markup(s)) - set(" \t\r\n")


def is_similar(orig, trans):
    """包含快判 + 字符集 Jaccard（LG 同口径），判「原文照抄加点料」。

    整句完全照抄（strip 后 new==old）不在此报——那是 screen_suspicious /
    check_untranslated 的未翻译通道，这里只抓局部漏翻。
    """
    o, t = strip_markup(orig).strip(), strip_markup(trans).strip()
    if not o or not t or o == t:
        return False
    if o in t or t in o:
        return True
    a, b = _char_set(o), _char_set(t)
    if not a or not b:
        return False
    return len(a & b) / len(a | b) > SIMILARITY_THRESHOLD


def entry_issues(e, lang="schinese"):
    """返回 (hits, is_untranslated)。

    hits 为空表示无硬性质命中；is_untranslated 走 quality_untranslated 通道。
    """
    t, o = e["trans"], e["orig"]
    if t.strip() == "":
        return [], False        # 空译文归 untranslated 专项工具（check_untranslated / tl_check）
    lang = lang.lower()
    do_residue = lang.startswith(("zh", "sc", "tc", "ja", "ko"))  # CJK 目标才查拉丁残留
    do_kana = not lang.startswith("ja")                           # ja 目标假名合法（同 tl_check）
    do_punct = lang.startswith(("zh", "sc", "tc"))

    hits = []
    natural = strip_markup(t)
    if do_residue:
        residue = foreign_residue_fragments(natural)
        if residue:
            hits.append("外文残留:" + "、".join(residue[:5]))
    if do_kana:
        kana = kana_fragments(natural)
        if kana:
            hits.append("假名残片:" + "、".join(kana[:5]))
    if do_punct:
        punct = half_punct_hits(natural)
        if punct:
            hits.append("半角标点:" + "".join(sorted(punct)))
    unt = do_residue and len(natural.strip()) >= SIM_MIN_LEN and is_similar(o, t)
    return hits, unt


def _load(source):
    src = Path(source)
    if src.suffix == ".json":
        return json.loads(src.read_text(encoding="utf-8"))
    return list(iter_say_entries(src))


def main():
    ap = argparse.ArgumentParser(description="硬性质校筛行（外文残留/假名/半角标点/相似度漏翻）")
    ap.add_argument("source", help="tl 目录或 extract_say 输出的 JSON")
    ap.add_argument("-o", "--out", default="quality_candidates.json")
    ap.add_argument("--lang", default="schinese", help="目标语言（schinese/tchinese/japanese/english…）")
    args = ap.parse_args()

    try:
        entries = _load(args.source)
    except (OSError, json.JSONDecodeError) as exc:
        ap.error(f"无法读取输入 {args.source}: {exc}")

    candidates, untranslated = [], []
    for e in entries:
        hits, unt = entry_issues(e, args.lang)
        if unt:
            e2 = dict(e)
            e2["hits"] = ["疑似漏翻:相似度>0.8（原文照抄加点料）"]
            untranslated.append(e2)
        if hits:
            e2 = dict(e)
            e2["hits"] = hits
            candidates.append(e2)

    candidates.sort(key=lambda x: (x["file"], x["line"]))
    Path(args.out).write_text(
        json.dumps(candidates, ensure_ascii=False, indent=1), encoding="utf-8")
    unt_path = Path(args.out).with_name("quality_untranslated.json")
    Path(unt_path).write_text(
        json.dumps(untranslated, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"硬性质可疑行 {len(candidates)} -> {args.out}")
    print(f"相似度疑似漏翻 {len(untranslated)} -> {unt_path}")
    sys.exit(1 if (candidates or untranslated) else 0)


if __name__ == "__main__":
    main()
