#!/usr/bin/env python3
import argparse
import json
import os
import re
import shutil
import sys
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── 引入共享公共 ──
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "公共")
)
from backup import create_bak

DEFAULT_GLOSSARY = r"glossary.json"
DEFAULT_TL_DIR = r"game/tl/schinese"
DEFAULT_WORK_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ANALYSIS_FILE = "name_analysis_v2.json"
DEFAULT_CORRECTION_FILE = "correction_plan_v2.json"
BACKUP_DIR_NAME = ".fix_name_backup_v2"

SKIP_FILES = {
    "defaultlanguage.rpy",
    "character_name_map.rpy",
    "options_translated.rpy",
    "cheats_translated.rpy",
}

KNOWN_VARIANTS = {
    "Tomori": {
        "朋里": "灯里",
        "朋美": "灯里",
        "朋莉": "灯里",
        "朋多里": "灯里",
        "朋绘": "灯里",
        "托莫里": "灯里",
        "灯理": "灯里",
    },
    "Nami": {
        "南米": "奈美",
        "小波": "奈美",
        "波奇": "奈美",
        "南子": "奈美",
        "南美": "奈美",
    },
    "Saki": {"萨琪": "咲", "咲子": "咲"},
    "Yui": {"由衣": "优衣", "由依": "优衣", "尤伊": "优衣"},
    "Kurumi": {"栗生": "胡桃", "久瑠美": "胡桃", "曲美": "胡桃", "玖瑠美": "胡桃"},
    "Ikari": {
        "碇君": "怒",
        "碇": "怒",
        "伊卡莉": "怒",
        "伊卡丽": "怒",
        "伊卡里": "怒",
        "伊卡利": "怒",
        "伊织": "怒",
        "伊吹": "怒",
        "一歌": "怒",
        "一里": "怒",
        "一丽": "怒",
        "衣织": "怒",
        "伊狩": "怒",
    },
    "Yokubo": {"欲部": "欲望", "优库波": "欲望"},
    "Shuu": {"修": "秀", "シュウ": "秀"},
    "Hina": {"日奈": "雏", "日奈子": "雏"},
    "Kodoku": {"孤獨": "孤独"},
    "Sekai": {"世界树": "世界"},
    "Sensei": {"先生": "老师"},
}

STOPWORDS = {
    # 代词
    "我",
    "你",
    "他",
    "她",
    "它",
    "我们",
    "你们",
    "他们",
    "她们",
    "它们",
    "这个",
    "那个",
    "这样",
    "那样",
    "自己",
    "大家",
    "咱们",
    "咱",
    # 常见对话词（原 v2 误判为变体的词）
    "是的",
    "好吧",
    "那么",
    "哈啊",
    "亲爱的",
    "是啊",
    "不是吗",
    "你知道吗",
    "不行",
    "不要",
    "不能",
    "不会",
    "没有",
    "不是",
    "没什么",
    "没事",
    "好的",
    "好吧",
    "行了",
    "够了",
    "算了",
    "当然",
    "确实",
    "真的",
    "也许",
    "可能",
    "大概",
    "应该",
    "必须",
    "一定",
    "当然",
    "为什么",
    "怎么",
    "怎样",
    "什么样",
    "什么",
    "哪个",
    "哪里",
    "哪儿",
    "因为",
    "所以",
    "但是",
    "然后",
    "如果",
    "虽然",
    "尽管",
    "不过",
    "已经",
    "正在",
    "将要",
    "刚刚",
    "马上",
    "现在",
    "刚才",
    # 时间词
    "今天",
    "明天",
    "昨天",
    "晚上",
    "早上",
    "下午",
    "中午",
    "现在",
    "时候",
    "时间",
    "一会儿",
    "马上",
    "等会",
    "待会",
    # 常见动词/形容词
    "觉得",
    "知道",
    "希望",
    "感觉",
    "认为",
    "以为",
    "发现",
    "明白",
    "理解",
    "看到",
    "听到",
    "想到",
    "认为",
    "相信",
    "担心",
    "害怕",
    "喜欢",
    "讨厌",
    "想要",
    "需要",
    "觉得",
    "认为",
    # 常见名词
    "事情",
    "东西",
    "地方",
    "问题",
    "情况",
    "办法",
    "感觉",
    "名字",
    "故事",
    "身体",
    "学校",
    "房间",
    "酒吧",
    "公寓",
    "食堂",
    "卧室",
    "妈妈",
    "朋友",
    "同学",
    "老师",
    "女孩",
    "男孩",
    "哥哥",
    "姐姐",
    "弟弟",
    "妹妹",
    "爸爸",
    "父亲",
    "母亲",
    # 其他
    "一下",
    "有点",
    "只是",
    "这里",
    "那里",
    "就是",
    "可以",
    "应该",
    "可能",
    "回家",
    "午餐",
    "对话",
    "广告牌",
    "高速公路",
    "葡萄酒",
    "阴茎",
    "精液",
    # 拟声词/感叹词
    "啊",
    "哎",
    "哦",
    "嗯",
    "诶",
    "哇",
    "哈",
    "嘿",
    "哼",
    "唔",
    "啊啊",
    "哈哈",
    "嘿嘿",
    "嗯嗯",
    "哦哦",
}

VAR_PATTERN = re.compile(r"\[.*?\]")
TAG_PATTERN = re.compile(r"\{.*?\}")
CJK_TOKEN_PATTERN = re.compile(r"[\u4e00-\u9fffぁ-んァ-ヶ]{1,8}")


def load_glossary(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return {item["src"]: item["dst"] for item in data}
    return data


def collect_files(tl_dir):
    files = []
    for root, dirs, filenames in os.walk(tl_dir):
        dirs[:] = [d for d in dirs if not d.startswith(".fix_name_backup")]
        for fn in filenames:
            if fn.endswith(".rpy") and fn not in SKIP_FILES:
                files.append(os.path.join(root, fn))
    return sorted(files)


def normalize_text(text):
    text = VAR_PATTERN.sub("", text)
    text = TAG_PATTERN.sub("", text)
    return text


def contains_en_name(text, en_name):
    return (
        re.search(
            r"(?<![A-Za-z])" + re.escape(en_name) + r"(?![A-Za-z])",
            normalize_text(text),
        )
        is not None
    )


def parse_blocks(lines):
    blocks = []
    i = 0
    while i < len(lines):
        m = re.match(r"^\s*#\s+(.+)$", lines[i])
        if not m:
            i += 1
            continue
        en_line = m.group(1).strip()
        j = i + 1
        while j < len(lines) and lines[j].strip() == "":
            j += 1
        if j < len(lines) and re.match(r"^\s*translate\s+\w+\s+\w+.*:$", lines[j]):
            j += 1
            while j < len(lines) and lines[j].strip() == "":
                j += 1
        if j < len(lines):
            m_cn = re.search(r'"(.*)"', lines[j])
            if m_cn:
                blocks.append(
                    {
                        "comment_line": i + 1,
                        "translation_line": j + 1,
                        "en": en_line,
                        "cn": m_cn.group(1),
                    }
                )
        i += 1
    return blocks


def guess_unknown_candidates(cn_text, standard_names, known_variants_for_name):
    """旧版：纯频率统计（已弃用，保留作为 fallback）"""
    clean = normalize_text(cn_text)
    tokens = []
    for token in CJK_TOKEN_PATTERN.findall(clean):
        if token in STOPWORDS:
            continue
        if token in standard_names:
            continue
        if len(token) <= 1:
            continue
        tokens.append(token)
    counts = Counter(tokens)
    ordered = [token for token, _ in counts.most_common()]
    boosted = []
    for token in ordered:
        if token in known_variants_for_name:
            boosted.append(token)
    for token in ordered:
        if token not in boosted:
            boosted.append(token)
    return boosted[:8]


def compute_chi2(a_freq, a_total, b_freq, b_total):
    """卡方检验：判断 token 是否在 A组（含角色名）比 B组（不含）更显著

    返回卡方值，越大越显著。使用 2x2 列联表：
        A组  B组
    出现  a   b
    未现  c   d
    """
    a = a_freq
    b = b_freq
    c = a_total - a_freq
    d = b_total - b_freq
    n = a + b + c + d
    if n == 0:
        return 0.0
    # 期望值
    ea = (a + b) * (a + c) / n
    eb = (a + b) * (b + d) / n
    ec = (c + d) * (a + c) / n
    ed = (c + d) * (b + d) / n
    # 卡方（避免除零）
    chi2 = 0.0
    for obs, exp in [(a, ea), (b, eb), (c, ec), (d, ed)]:
        if exp > 0:
            chi2 += (obs - exp) ** 2 / exp
    return chi2


def is_valid_candidate(token, standard_names, known_variants_for_name):
    """判断 token 是否为有效的变体候选"""
    if token in STOPWORDS:
        return False
    if token in standard_names:
        return False
    if token in known_variants_for_name:
        return False
    # 人名通常 2-3 字（标准译名均为 1-3 字：雏/奈美/灯里/胡桃/优衣/孤独/欲望/老师/世界/梦/怒/秀/凉）
    if len(token) < 2 or len(token) > 3:
        return False
    # 排除纯数字/标点
    if not re.search(r"[\u4e00-\u9fff]", token):
        return False
    return True


def scan_names(glossary, tl_dir):
    files = collect_files(tl_dir)
    compiled = {
        en_name: re.compile(
            r"(?<![A-Za-z])" + re.escape(en_name) + r"(?![A-Za-z])", re.IGNORECASE
        )
        for en_name in glossary
    }
    standard_names = set(glossary.values())
    result = {}
    for en_name, std in glossary.items():
        result[en_name] = {
            "standard": std,
            "correct_count": 0,
            "untranslated_count": 0,
            "known_variants": defaultdict(int),
            "unknown_candidates": defaultdict(int),
            "occurrences": [],
        }

    # ─── 第一遍：收集所有翻译块 ───────────────────────────────
    all_blocks = []
    for fpath in files:
        rel_path = os.path.relpath(fpath, tl_dir)
        with open(fpath, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for block in parse_blocks(lines):
            block["file"] = rel_path
            all_blocks.append(block)

    # ─── 第二遍：对每个角色名，用概率匹配找变体候选 ─────────────
    # 概率匹配：A组（英文注释含角色名）vs B组（不含），卡方检验找显著相关 token
    probability_candidates = {}  # {en_name: [(token, count, chi2), ...]}
    for en_name, std in glossary.items():
        a_token_freq = Counter()  # A组中各 token 出现的块数
        b_token_freq = Counter()  # B组中各 token 出现的块数
        a_block_count = 0
        b_block_count = 0

        for block in all_blocks:
            en_line = block["en"]
            cn_text = block["cn"]
            clean_cn = normalize_text(cn_text)
            # 用 set 去重（每块只计一次）
            tokens = set(CJK_TOKEN_PATTERN.findall(clean_cn))

            if compiled[en_name].search(en_line):
                a_block_count += 1
                for t in tokens:
                    a_token_freq[t] += 1
            else:
                b_block_count += 1
                for t in tokens:
                    b_token_freq[t] += 1

        # 计算每个 token 的卡方值，找 A 组显著高于 B 组的
        known_variants_for_name = KNOWN_VARIANTS.get(en_name, {})
        candidates = []
        for token, a_freq in a_token_freq.items():
            if not is_valid_candidate(token, standard_names, known_variants_for_name):
                continue
            if a_freq < 3:  # 至少出现 3 次（提高下限）
                continue
            b_freq = b_token_freq.get(token, 0)
            chi2 = compute_chi2(a_freq, a_block_count, b_freq, b_block_count)
            # 严格过滤：卡方 >= 10 (p<0.005) 且 B 组频率极低
            # 真正的变体应该只在含该角色名的对话中出现，B 组接近 0
            ratio = a_freq / max(b_freq, 1)
            if chi2 >= 10 and (b_freq == 0 or ratio >= 10):
                candidates.append((token, a_freq, chi2))

        # 按卡方值降序排序
        candidates.sort(key=lambda x: (-x[2], -x[1]))
        probability_candidates[en_name] = candidates

    # ─── 第三遍：分类每个 occurrence ───────────────────────────
    for block in all_blocks:
        en_line = block["en"]
        cn_text = block["cn"]
        clean_cn = normalize_text(cn_text)
        rel_path = block["file"]

        for en_name, std in glossary.items():
            if not compiled[en_name].search(en_line):
                continue
            occ = {
                "file": rel_path,
                "comment_line": block["comment_line"],
                "translation_line": block["translation_line"],
                "en": en_line,
                "cn": cn_text,
            }
            if std in clean_cn:
                occ["type"] = "correct"
                result[en_name]["correct_count"] += 1
                result[en_name]["occurrences"].append(occ)
                continue
            if contains_en_name(cn_text, en_name):
                occ["type"] = "untranslated"
                result[en_name]["untranslated_count"] += 1
                result[en_name]["occurrences"].append(occ)
                continue
            found_known = []
            for variant in KNOWN_VARIANTS.get(en_name, {}):
                if variant in clean_cn:
                    found_known.append(variant)
            if found_known:
                occ["type"] = "known_variant"
                occ["variants"] = found_known
                for variant in found_known:
                    result[en_name]["known_variants"][variant] += 1
                result[en_name]["occurrences"].append(occ)
                continue

            # unknown：用概率匹配候选 + 句内实际出现的 token
            occ["type"] = "unknown"
            prob_cands = probability_candidates.get(en_name, [])
            # 从概率候选中挑出本句实际出现的
            in_sentence = []
            for token, count, chi2 in prob_cands:
                if token in clean_cn:
                    in_sentence.append(token)
                    result[en_name]["unknown_candidates"][token] += 1
            occ["candidates"] = in_sentence
            result[en_name]["occurrences"].append(occ)

    return result, files


def step1_discover(glossary_path, tl_dir, output_path):
    glossary = load_glossary(glossary_path)
    print("=" * 70)
    print("  Step 1: 发现 — 全面扫描翻译文件")
    print("=" * 70)
    print(f"  术语表: {glossary_path}")
    print(f"  翻译目录: {tl_dir}")
    print(f"  角色数: {len(glossary)}")
    names, files = scan_names(glossary, tl_dir)
    data = {
        "description": "Step 1 全面扫描结果",
        "glossary": glossary,
        "tl_dir": tl_dir,
        "total_files": len(files),
        "names": {},
    }
    total_occurrences = 0
    total_correct = 0
    total_untranslated = 0
    total_known_variants = 0
    total_unknown = 0
    for en_name, info in names.items():
        unknown_count = sum(1 for o in info["occurrences"] if o["type"] == "unknown")
        total = len(info["occurrences"])
        total_occurrences += total
        total_correct += info["correct_count"]
        total_untranslated += info["untranslated_count"]
        total_known_variants += sum(info["known_variants"].values())
        total_unknown += unknown_count
        data["names"][en_name] = {
            "standard": info["standard"],
            "total": total,
            "correct_count": info["correct_count"],
            "untranslated_count": info["untranslated_count"],
            "known_variants": dict(info["known_variants"]),
            "unknown_candidates": dict(info["unknown_candidates"]),
            "occurrences": info["occurrences"],
        }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n  扫描完成: {len(files)} 个文件, {total_occurrences} 处角色名引用")
    print(f"  ✓  正确: {total_correct}")
    print(f"  ⚠  英文未翻译: {total_untranslated}")
    print(f"  ✗  已识别变体: {total_known_variants}")
    print(f"  ?  未识别条目: {total_unknown}")
    print(f"  分析结果: {output_path}")
    return data


def step2_review(analysis_path, correction_path, interactive=False, auto=False):
    with open(analysis_path, "r", encoding="utf-8") as f:
        analysis = json.load(f)
    glossary = analysis["glossary"]
    corrections = []
    pending = []
    print("=" * 70)
    print("  Step 2: 审核 — 生成修正方案")
    print("=" * 70)
    for en_name, info in analysis["names"].items():
        standard = glossary[en_name]
        untranslated = [o for o in info["occurrences"] if o["type"] == "untranslated"]
        if untranslated:
            item = {
                "en_name": en_name,
                "old": en_name,
                "new": standard,
                "type": "untranslated",
                "desc": f"英文名「{en_name}」→「{standard}」",
                "count": len(untranslated),
                "occurrences": untranslated,
            }
            corrections.append(item)
            if auto:
                print(f"  ⚠ {en_name}: {len(untranslated)} 处英文名未翻译 → 自动接受")
        for variant, count in sorted(info["known_variants"].items()):
            occs = [
                o
                for o in info["occurrences"]
                if o["type"] == "known_variant" and variant in o.get("variants", [])
            ]
            item = {
                "en_name": en_name,
                "old": variant,
                "new": standard,
                "type": "variant",
                "desc": f"变体「{variant}」→「{standard}」",
                "count": count,
                "occurrences": occs,
            }
            corrections.append(item)
            if auto:
                print(f"  ✗ {en_name}: 变体「{variant}」×{count} → 自动接受")
        unknown_occs = [o for o in info["occurrences"] if o["type"] == "unknown"]
        if unknown_occs:
            pending.append(
                {
                    "en_name": en_name,
                    "standard": standard,
                    "count": len(unknown_occs),
                    "top_candidates": sorted(
                        info["unknown_candidates"].items(), key=lambda x: (-x[1], x[0])
                    )[:10],
                    "examples": unknown_occs[:5],
                }
            )
    plan = {
        "description": "Step 2 修正方案",
        "analysis_file": analysis_path,
        "corrections": corrections,
        "pending": pending,
        "total_corrections": len(corrections),
        "total_pending": len(pending),
    }
    with open(correction_path, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)
    print(f"\n  可自动修正: {len(corrections)} 项")
    print(f"  待人工确认: {len(pending)} 项")
    print(f"  修正方案: {correction_path}")
    return plan


def backup_files(tl_dir):
    backup_dir = os.path.join(tl_dir, BACKUP_DIR_NAME)
    if os.path.exists(backup_dir):
        return backup_dir
    files = collect_files(tl_dir)
    for fpath in files:
        rel = os.path.relpath(fpath, tl_dir)
        dst = os.path.join(backup_dir, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(fpath, dst)
    return backup_dir


def rollback(tl_dir):
    backup_dir = os.path.join(tl_dir, BACKUP_DIR_NAME)
    if not os.path.exists(backup_dir):
        print(f"错误: 备份目录不存在: {backup_dir}")
        return
    restored = 0
    for root, _, files in os.walk(backup_dir):
        for fn in files:
            src = os.path.join(root, fn)
            rel = os.path.relpath(src, backup_dir)
            dst = os.path.join(tl_dir, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            restored += 1
    print(f"已恢复 {restored} 个文件")


def replace_in_quoted_line(line, old, new, mode):
    m = re.search(r'(")(.+?)(")', line)
    if not m:
        return line, False
    inner = m.group(2)
    original_inner = inner
    if mode == "untranslated":
        inner = re.sub(r"(?<![A-Za-z])" + re.escape(old) + r"(?![A-Za-z])", new, inner)
    else:
        inner = inner.replace(old, new)
    if inner == original_inner:
        return line, False
    return line[: m.start(2)] + inner + line[m.end(2) :], True


def step3_unify(correction_path, tl_dir, dry_run=False, apply=False):
    with open(correction_path, "r", encoding="utf-8") as f:
        plan = json.load(f)
    corrections = plan.get("corrections", [])
    if not corrections:
        print("没有需要执行的修正。")
        return
    print("=" * 70)
    print(
        "  Step 3: 统一 — "
        + ("预览模式" if dry_run else "执行替换" if apply else "未执行")
    )
    print("=" * 70)
    print(f"  共 {len(corrections)} 项修正操作:")
    for c in corrections:
        print(f"    {c['desc']} ({c['count']} 处)")
    if apply:
        backup_dir = backup_files(tl_dir)
        print(f"  备份目录: {backup_dir}")
    file_changes = defaultdict(int)
    modified_cache = {}
    for correction in corrections:
        old = correction["old"]
        new = correction["new"]
        mode = correction["type"]
        for occ in correction["occurrences"]:
            rel = occ["file"]
            fpath = os.path.join(tl_dir, rel)
            if rel not in modified_cache:
                with open(fpath, "r", encoding="utf-8") as f:
                    modified_cache[rel] = f.readlines()
            lines = modified_cache[rel]
            idx = occ["translation_line"] - 1
            if idx < 0 or idx >= len(lines):
                continue
            new_line, changed = replace_in_quoted_line(lines[idx], old, new, mode)
            if changed:
                lines[idx] = new_line
                file_changes[rel] += 1
    for rel, lines in modified_cache.items():
        if file_changes[rel] and apply:
            filepath = os.path.join(tl_dir, rel)
            create_bak(filepath)
            with open(filepath, "w", encoding="utf-8") as f:
                f.writelines(lines)
    total = sum(file_changes.values())
    print(f"\n  将影响/已修改 {len(file_changes)} 个文件, {total} 处替换")
    for rel, count in sorted(file_changes.items()):
        print(f"    {rel}: {count} 处")


def main():
    parser = argparse.ArgumentParser(description="Ren'Py 人名翻译统一脚本 v2")
    parser.add_argument("--glossary", default=DEFAULT_GLOSSARY)
    parser.add_argument("--tl-dir", default=DEFAULT_TL_DIR)
    parser.add_argument("--step", type=int, choices=[1, 2, 3])
    parser.add_argument(
        "--analysis", default=os.path.join(DEFAULT_WORK_DIR, DEFAULT_ANALYSIS_FILE)
    )
    parser.add_argument(
        "--correction", default=os.path.join(DEFAULT_WORK_DIR, DEFAULT_CORRECTION_FILE)
    )
    parser.add_argument("--interactive", "-i", action="store_true")
    parser.add_argument("--auto", action="store_true")
    parser.add_argument("--dry-run", "-n", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--rollback", action="store_true")
    args = parser.parse_args()

    tl_dir = os.path.abspath(args.tl_dir)
    glossary = os.path.abspath(args.glossary)
    analysis = os.path.abspath(args.analysis)
    correction = os.path.abspath(args.correction)

    if args.rollback:
        rollback(tl_dir)
        return
    if not os.path.exists(tl_dir):
        print(f"错误: 翻译目录不存在: {tl_dir}")
        sys.exit(1)
    if args.step in (1, None) and not os.path.exists(glossary):
        print(f"错误: 术语表不存在: {glossary}")
        sys.exit(1)

    if args.step == 1:
        step1_discover(glossary, tl_dir, analysis)
    elif args.step == 2:
        step2_review(analysis, correction, args.interactive, args.auto)
    elif args.step == 3:
        step3_unify(correction, tl_dir, args.dry_run, args.apply)
    else:
        step1_discover(glossary, tl_dir, analysis)
        step2_review(analysis, correction, args.interactive, args.auto)
        step3_unify(correction, tl_dir, dry_run=not args.apply, apply=args.apply)


if __name__ == "__main__":
    main()
