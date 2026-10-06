#!/usr/bin/env python3
"""
Ren'Py 人名翻译统一脚本 v6 — 三步流程：收集 → 分类 → 统一
============================================================

设计原则：变体来源严格限制，不做滑动窗口猜测。
变体只有两种来源：
  1. 译文含英文原名 → 英文变体（概率筛选：英文出现在中文译文里大概率是漏翻）
  2. 译文含标准译名 → ok
两者都没有 → omitted（未翻译/遗漏），不猜测，留给人工或 LLM 处理。

三步流程:
  Step 1 (收集):  扫描翻译文件，解析翻译块，记录角色名引用（必须有注释行作为英文原文）
  Step 2 (分类):  读 Step 1 原始数据，分类 ok/variant/omitted
  Step 3 (统一):  安全替换（CJK 边界保护 + 首次匹配），支持回滚

用法示例:
  python unify_name_translations.py -g glossary.json -t game/tl/schinese
  python unify_name_translations.py -g glossary.json -t game/tl/schinese --step collect
  python unify_name_translations.py --step classify
  python unify_name_translations.py --step unify --dry-run
  python unify_name_translations.py --step unify --apply
  python unify_name_translations.py --rollback -t game/tl/schinese

--step 接受编号或名称（1/collect=收集，2/classify=分类，3/unify=统一），
编号保留兼容旧命令行，与仓库其他多入口脚本的 add_parser 命名风格对齐。
"""

import argparse
import json
import os
import re
import shutil
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore

# ── 引入 shared/ 公共模块 ──
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shared")
)
from backup import atomic_write_text  # type: ignore  # noqa: E402
from rpy_syntax import (  # type: ignore  # noqa: E402
    iter_translation_pairs,
    parse_new_line,
    parse_translation_line,
    replace_literal_content,
)

# ─── 默认路径 ───────────────────────────────────────────────
DEFAULT_GLOSSARY = r"glossary.json"
DEFAULT_TL_DIR = r"game/tl/schinese"
DEFAULT_WORK_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_COLLECT_FILE = "name_collection.json"
DEFAULT_CLASSIFICATION_FILE = "name_classification.json"

# 跳过这些文件（内容不是可翻译的人名对话）
#
# 这四个名字是本工具历史处理过的项目产物文件名，不是 Ren'Py 标准文件：
# Ren'Py 标准里 defaultlanguage.rpy 由 define config.language 相关逻辑使用，
# 其余三个完全取决于游戏自己的脚本命名。留在代码里会导致「换游戏时这游戏
# 恰好有同名文件 → 被静默跳过」这种难以察觉的漏处理。
#
# 改为外置：需要时放项目根的 renpy_skip_files.json（列表或 {"add": [...]}）。
_SKIP_FILES_JSON = "renpy_skip_files.json"
_DEFAULT_SKIP_FILES = ("defaultlanguage.rpy",)


def _load_skip_files():
    """返回本次要跳过的文件名集合。

    项目根目录放 renpy_skip_files.json 即可增删，不必改代码：
      ["a.rpy", "b.rpy"]     → 追加
      {"replace": [...]}     → 完全替换
    """
    import json

    path = os.environ.get("RENPY_SKIP_FILES") or os.path.join(
        os.getcwd(), _SKIP_FILES_JSON
    )
    if not os.path.isfile(path):
        return set(_DEFAULT_SKIP_FILES)
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        print(f"[WARN] {_SKIP_FILES_JSON} 读取失败，改用默认清单：{exc}", file=sys.stderr)
        return set(_DEFAULT_SKIP_FILES)
    if isinstance(data, list):
        return set(_DEFAULT_SKIP_FILES) | {str(x) for x in data}
    if isinstance(data, dict) and "replace" in data:
        return {str(x) for x in data["replace"]}
    return set(_DEFAULT_SKIP_FILES)


# ═══════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════


def collect_files(tl_dir):
    """收集所有翻译文件。

    跳过清单在调用时才求值（每次读 JSON）：同一进程里若用户中途改了配置，
    重跑 collect 能立刻生效，不必重启。
    """
    files = []
    skip = _load_skip_files()
    backup_marker = ".fix_name_backup"
    for root, dirs, filenames in os.walk(tl_dir):
        if backup_marker in root:
            continue
        for fn in filenames:
            if fn in skip:
                continue
            if fn.endswith(".rpy"):
                files.append(os.path.join(root, fn))
    return sorted(files)


def load_glossary(path):
    """加载术语表: {英文名: 中文标准名}"""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return {e["src"]: e["dst"] for e in data}
    return data


def _is_source_path_comment(text):
    """判断注释内容是否为 Ren'Py 源文件路径引用（如 game/events/tomori.rpy:23）。"""
    return bool(re.match(r"^game/[\w/]+\.(rpy|rpym):\d+", text))


def is_name_reference(english_line, en_name):
    """检查英文行是否引用了角色名（作为独立单词）。

    特殊处理：
    - 排除源文件路径中的文件名（如 game/events/tomori.rpy:23 中的 tomori）
    - 'Ren' 不应匹配 'Ren'Py'（引擎名），需排除撇号+Py 的情况
    但 'Ren's（所有格）仍应匹配。
    """
    if not english_line:
        return False
    # 排除源文件路径注释行（parse_blocks 已跳过，此处作为双重保险）
    if _is_source_path_comment(english_line):
        return False
    # 对短名（<=4字符），排除后面紧跟 'Py 的情况（如 Ren'Py）
    if len(en_name) <= 4:
        pattern = r"\b" + re.escape(en_name) + r"(?!['\u2019]Py)\b"
    else:
        pattern = r"\b" + re.escape(en_name) + r"\b"
    return bool(re.search(pattern, english_line, re.IGNORECASE))


# ═══════════════════════════════════════════════════════════════
# parse_blocks — 通用翻译块解析器
# ═══════════════════════════════════════════════════════════════


def parse_blocks(lines):
    """解析 Ren'Py 翻译对，支持旁白、任意角色及 old/new。

    共享解析器会正确处理转义引号，并禁止跨到下一条原文误配译文。
    """
    blocks = []
    for pair in iter_translation_pairs(lines):
        if pair.translated is None or pair.translated_line is None:
            continue
        if pair.kind == "on":
            en = pair.original
        else:
            source_line = lines[pair.original_line - 1].strip()
            en = source_line[1:].strip() if source_line.startswith("#") else pair.original
        blocks.append(
            {
                "comment_line": pair.original_line,
                "translation_line": pair.translated_line,
                "en": en,
                "cn": pair.translated,
            }
        )
    return blocks


# ═══════════════════════════════════════════════════════════════
# Step 1: 收集 — 扫描翻译文件，记录角色名引用（不做分类）
# ═══════════════════════════════════════════════════════════════


def step1_collect(glossary, tl_dir, output_path):
    """
    扫描翻译文件，解析所有翻译块，记录哪些块引用了角色名。

    本步只做收集，不做任何分类判断（ok/untranslated/omitted）。
    分类逻辑在 Step 2 中独立完成，便于后续扩展新分类规则。

    输出 JSON 结构:
    {
      "tl_dir": "...",
      "glossary_file": "...",
      "total_files": N,
      "total_blocks": N,
      "total_name_refs": N,
      "glossary": {英文名: 标准译名},
      "refs": [
        {
          "en_name": "Tomori",
          "standard": "灯里",
          "file": "events/tomori.rpy",
          "line": 42,
          "en_context": "Tomori is here.",
          "cn_text": "灯里在这里。"
        },
        ...
      ]
    }
    """
    name_map = load_glossary(glossary) if isinstance(glossary, str) else glossary
    files = collect_files(tl_dir)

    refs = []
    total_blocks = 0

    for filepath in files:
        relpath = os.path.relpath(filepath, tl_dir)
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.read().split("\n")

        for block in parse_blocks(lines):
            total_blocks += 1
            en_line = block["en"]
            cn_text = block["cn"]

            for en_name, zh_standard in name_map.items():
                if not is_name_reference(en_line, en_name):
                    continue

                refs.append(
                    {
                        "en_name": en_name,
                        "standard": zh_standard,
                        "file": relpath,
                        "line": block["translation_line"],
                        "en_context": en_line[:100],
                        "cn_text": cn_text[:100],
                    }
                )

    output = {
        "description": "Step 1 收集结果 — 原始角色名引用数据（未分类）",
        "tl_dir": tl_dir,
        "glossary_file": glossary if isinstance(glossary, str) else "",
        "total_files": len(files),
        "total_blocks": total_blocks,
        "total_name_refs": len(refs),
        "glossary": name_map,
        "refs": refs,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    return output


# ═══════════════════════════════════════════════════════════════
# Step 2: 分类 — 发现变体、按角色名归组
# ═══════════════════════════════════════════════════════════════


def step2_classify(collection_path, output_path, interactive=False, auto=False):
    """读 Step 1 收集的原始数据，发现译文中的变体写法，按角色名归组。

    对每条角色名引用，检查译文中的实际写法：
      - 含标准译名        → ok（不需要处理）
      - 含英文原名        → 变体 = 英文名本身（概率筛选：英文出现在中文译文里大概率是漏翻）
      - 两者都没有        → omitted（未翻译/遗漏），不猜测

    变体只有两种来源，不做滑动窗口猜测：
    1. 概率筛选：英文原名出现在中文译文里 → 英文变体
    2. 精确匹配：译文含标准译名 → ok

    按变体归组输出，方便批量判断和修复：
    {
      "Ikari": {
        "standard": "怒",
        "variants": {
          "Ikari":  {"count": 5, "occurrences": [...]}
        },
        "ok_count": 195,
        "omitted_count": 0
      }
    }
    """
    with open(collection_path, "r", encoding="utf-8") as f:
        collection = json.load(f)

    glossary = collection["glossary"]
    refs = collection["refs"]
    all_standards = set(glossary.values())

    # 按角色名初始化
    names = {}
    for en_name, zh_standard in glossary.items():
        names[en_name] = {
            "standard": zh_standard,
            "ok_count": 0,
            "omitted_count": 0,
            "variants": {},  # {variant_text: {"count": N, "occurrences": [...]}}
        }

    # 遍历所有引用，分类到 ok / variant / omitted
    for ref in refs:
        en_name = ref["en_name"]
        cn_text = ref["cn_text"]
        zh_standard = ref["standard"]
        info = names[en_name]

        # 1) 译文含标准译名 → ok
        if zh_standard in cn_text:
            info["ok_count"] += 1
            continue

        # 2) 译文含英文原名 → 变体 = 英文名（概率筛选：英文出现在中文译文里大概率是漏翻）
        en_pattern = r"(?<![A-Za-z])" + re.escape(en_name) + r"(?![A-Za-z])"
        if re.search(en_pattern, cn_text):
            variant = en_name
            _add_variant(info, variant, ref)
            continue

        # 3) 两者都没有 → omitted（未翻译/遗漏），不猜测
        info["omitted_count"] += 1
        if "omitted_refs" not in info:
            info["omitted_refs"] = []
        info["omitted_refs"].append({
            "file": ref["file"],
            "line": ref["line"],
            "en_context": ref["en_context"],
            "cn_text": ref["cn_text"],
        })

    # 汇总打印
    print("\n" + "=" * 70)
    print("  Step 2: 分类 — 变体识别与归组")
    print("=" * 70)

    total_ok = 0
    total_variants = 0
    total_omitted = 0
    total_variant_occurrences = 0

    for en_name in sorted(names):
        info = names[en_name]
        standard = info["standard"]
        ok = info["ok_count"]
        omitted = info["omitted_count"]
        variant_items = sorted(
            info["variants"].items(), key=lambda x: -x[1]["count"]
        )
        variant_count = len(variant_items)
        variant_occ = sum(v["count"] for v in info["variants"].values())

        total_ok += ok
        total_variants += variant_count
        total_omitted += omitted
        total_variant_occurrences += variant_occ

        if not variant_items and omitted == 0:
            continue

        print(f"\n{'─' * 70}")
        print(f"  {en_name} → [{standard}]  ✓{ok}", end="")
        if variant_items:
            print(f"  变体{variant_count}种/{variant_occ}处", end="")
        if omitted:
            print(f"  未识别{omitted}处", end="")
        print()

        for variant_text, vinfo in variant_items:
            print(f"    「{variant_text}」 × {vinfo['count']}")

        if omitted:
            for ref in info.get("omitted_refs", []):
                print(f"    ? L{ref['line']} {ref['file']}")
                print(f"      EN: {ref['en_context'][:60]}")
                print(f"      CN: {ref['cn_text'][:60]}")

    print(f"\n{'=' * 70}")
    print(f"  分类完成")
    print(f"  ✓  正确:          {total_ok}")
    print(f"  ✗  变体种类:      {total_variants}")
    print(f"  ✗  变体出现:      {total_variant_occurrences}")
    print(f"  ?  未识别:        {total_omitted}")
    print(f"{'=' * 70}")

    # 保存
    output = {
        "description": "Step 2 分类结果 — 变体归组（严格模式：只保留英文原名变体，不猜测）",
        "collection_file": collection_path,
        "glossary": glossary,
        "names": names,
        "totals": {
            "ok": total_ok,
            "variant_kinds": total_variants,
            "variant_occurrences": total_variant_occurrences,
            "omitted": total_omitted,
        },
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n分类结果已保存: {output_path}")
    if total_variant_occurrences > 0:
        print(f"  下一步: 编辑 {output_path} 确认变体替换方案，或用 --step unify 处理")

    return output


def _add_variant(info, variant, ref):
    """把一条引用归入指定变体组。"""
    if variant not in info["variants"]:
        info["variants"][variant] = {"count": 0, "occurrences": []}
    info["variants"][variant]["count"] += 1
    info["variants"][variant]["occurrences"].append({
        "file": ref["file"],
        "line": ref["line"],
        "en_context": ref["en_context"],
        "cn_text": ref["cn_text"],
    })


def show_occurrences(occurrences, max_show=3):
    """显示问题出现位置"""
    for occ in occurrences[:max_show]:
        print(f"         {occ['file']}:L{occ['line']}")
        print(f"         原文: {occ.get('en_context', '')[:60]}")
        print(f"         译文: {occ.get('cn_text', '')[:60]}")
    if len(occurrences) > max_show:
        print(f"         ... 还有 {len(occurrences) - max_show} 处")


# ═══════════════════════════════════════════════════════════════
# Step 3: 统一 — 安全替换
# ═══════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════
# 安全替换 — 避免短名误伤正文
# ═══════════════════════════════════════════════════════════════


def _replace_name_in_dialogue(line, old_name, new_name):
    """
    安全替换行内的人名变体，避免误伤正文。

    支持 Ren'Py 翻译文件中的所有对话行格式：
    1. c_xxx "dialogue"       — 角色对话行 (translate block)
    2. e "dialogue"           — speaker 简写对话行
    3. "dialogue"             — 纯叙述行（裸引号）
    4. new "dialogue"         — strings 块译文行

    策略：只替换引号内对话文本部分，采用首次匹配 + CJK 边界保护：
    - 替换引号内首次出现的 old_name（人名通常出现在句首或称呼位置）
    - 对短变体（<=2字）额外检查：不替换前后紧邻 CJK 字符的位置
      （如 "修" 前后是 CJK 字符说明它是正文用字而非人名）

    Returns:
        (new_line, replaced_count)
    """
    literal = parse_new_line(line)
    if literal is None:
        parsed = parse_translation_line(line)
        literal = parsed[0] if parsed is not None else None
    if literal is None:
        return line, 0

    dialog_text = literal.value
    pos = dialog_text.find(old_name)
    if pos == -1:
        return line, 0

    # CJK 边界检查：对短变体（<=2字），检查前后是否紧邻 CJK。
    if len(old_name) <= 2:
        after_pos = pos + len(old_name)
        prev_is_cjk = pos > 0 and "\u4e00" <= dialog_text[pos - 1] <= "\u9fff"
        next_is_cjk = (
            after_pos < len(dialog_text)
            and "\u4e00" <= dialog_text[after_pos] <= "\u9fff"
        )
        if prev_is_cjk or next_is_cjk:
            return line, 0

    new_dialog = dialog_text[:pos] + new_name + dialog_text[pos + len(old_name) :]
    return replace_literal_content(line, literal, new_dialog), 1


def step3_unify(classification_path, tl_dir, dry_run=False, apply=False, rollback=False):
    """根据分类结果执行变体替换。

    读取 Step 2 的分类结果（variants 归组），对每个变体执行替换。
    默认所有变体都替换为标准译名。如需跳过某些变体，
    可在 classification JSON 的 variants 中删除对应条目。
    """
    backup_dir = os.path.join(tl_dir, ".fix_name_backup")

    if rollback:
        _do_rollback(tl_dir, backup_dir)
        return

    with open(classification_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    names = data.get("names", {})
    if not names:
        print("没有分类数据。")
        return

    # 从 variants 构建替换任务列表
    replacements = []  # [{en_name, old, new, line, file}, ...]
    for en_name, info in names.items():
        standard = info["standard"]
        for variant_text, vinfo in info.get("variants", {}).items():
            for occ in vinfo["occurrences"]:
                replacements.append({
                    "en_name": en_name,
                    "old": variant_text,
                    "new": standard,
                    "line": occ["line"],
                    "file": occ["file"],
                })

    if not replacements:
        print("没有需要替换的变体。")
        return

    print("\n" + "=" * 70)
    print(f"  Step 3: 统一替换 — {len(replacements)} 处变体")
    print("=" * 70)

    # 按文件分组
    by_file = defaultdict(list)
    for r in replacements:
        by_file[r["file"]].append(r)

    # 汇总显示
    for relpath, items in sorted(by_file.items()):
        print(f"\n  {relpath} ({len(items)} 处)")
        for item in items:
            print(
                f"    L{item['line']:>5} | {item['en_name']}: 「{item['old']}」→ 「{item['new']}」"
            )

    if dry_run:
        print("\n" + "=" * 70)
        print("  [预览模式] 未实际修改文件。")
        print("  执行替换: python unify_name_translations.py --step unify --apply")
        print("=" * 70)
        return

    if not apply:
        print("\n" + "=" * 70)
        print("  预览完毕。如需执行替换:")
        print("    python unify_name_translations.py --step unify --apply")
        print("  或预览替换内容:")
        print("    python unify_name_translations.py --step unify --dry-run")
        print("=" * 70)
        return

    # ── 执行替换 ──
    _create_backup(tl_dir, backup_dir)

    replaced = 0
    skipped = 0
    files_modified = set()

    for relpath, items in sorted(by_file.items()):
        filepath = os.path.join(tl_dir, relpath)
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.read().split("\n")

        file_changed = False
        for item in items:
            line_idx = item["line"] - 1
            if line_idx >= len(lines):
                continue
            old_line = lines[line_idx]
            new_line, count = _replace_name_in_dialogue(
                old_line, item["old"], item["new"]
            )
            if count > 0:
                lines[line_idx] = new_line
                file_changed = True
                replaced += count
                print(
                    f"  [OK] {relpath}:L{item['line']} 「{item['old']}」→ 「{item['new']}」"
                )
            else:
                skipped += 1
                print(
                    f"  [SKIP] {relpath}:L{item['line']} 「{item['old']}」"
                    f" — 变体未在对话文本中找到或被 CJK 边界保护跳过"
                )

        if file_changed:
            atomic_write_text(
                filepath,
                "\n".join(lines),
                encoding="utf-8",
                backup=True,
                newline="\n",
            )
            files_modified.add(relpath)

    print(f"\n{'=' * 70}")
    print(f"  替换完成!")
    print(f"  修改文件: {len(files_modified)} 个")
    print(f"  替换条目: {replaced} 处")
    if skipped:
        print(f"  跳过条目: {skipped} 处（变体未在对话文本中找到或被边界保护）")
    print(f"  备份目录: {backup_dir}")
    print(f"  回滚命令: python unify_name_translations.py --rollback --tl-dir {tl_dir}")
    print(f"{'=' * 70}")


def _create_backup(tl_dir, backup_dir):
    """创建备份。

    安全策略：如果备份目录已存在，说明上次 step3 的替换可能尚未回滚，
    拒绝覆盖以保护原始数据。用户必须先回滚或手动删除备份目录。
    """
    if os.path.exists(backup_dir):
        print(f"  [警告] 备份目录已存在: {backup_dir}")
        print(f"  这可能意味着上次的替换尚未回滚。")
        print(f"  为保护原始数据，拒绝覆盖现有备份。")
        print(
            f"  如需继续，请先回滚: python unify_name_translations.py --rollback --tl-dir {tl_dir}"
        )
        print(f"  回滚后会自动清除备份目录，然后可以重新执行 step3。")
        sys.exit(1)

    os.makedirs(backup_dir)
    files = collect_files(tl_dir)
    for filepath in files:
        rel = os.path.relpath(filepath, tl_dir)
        dest = os.path.join(backup_dir, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(filepath, dest)
    print(f"备份完成: {len(files)} 文件 -> {backup_dir}")


def _do_rollback(tl_dir, backup_dir):
    """从备份恢复，成功后清除备份目录。

    回滚流程：
    1. 检查备份目录是否存在
    2. 将备份文件覆盖回翻译目录
    3. 清除备份目录（表示回滚已完成，可以重新执行 step3）
    """
    if not os.path.exists(backup_dir):
        print("错误: 没有找到备份目录")
        print("可能的原因: 尚未执行过 step3 --apply，或已回滚过。")
        return

    restored = 0
    for root, dirs, files in os.walk(backup_dir):
        for fn in files:
            src = os.path.join(root, fn)
            rel = os.path.relpath(src, backup_dir)
            dest = os.path.join(tl_dir, rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(src, dest)
            restored += 1

    shutil.rmtree(backup_dir)
    print(f"回滚完成: 恢复 {restored} 个文件")
    print(f"备份目录已清除: {backup_dir}")


# ═══════════════════════════════════════════════════════════════
# CLI 入口
# ═══════════════════════════════════════════════════════════════


# ── --step 取值：编号与名称等价，编号保留兼容旧命令行 ──
STEP_ALIASES = {"1": 1, "2": 2, "3": 3, "collect": 1, "classify": 2, "unify": 3}


def normalize_step(value):
    """--step 取值（编号或名称）归一成 1/2/3；None 表示跑全部三步。

    非法取值由 argparse 的 choices 拦截，这里不重复报错。
    """
    if value is None:
        return None
    return STEP_ALIASES[str(value).strip().lower()]


def main():
    parser = argparse.ArgumentParser(
        description="""\
Ren'Py 人名翻译统一脚本 — 三步流程: 收集 → 分类 → 统一

用法示例:
  # 只运行收集步
  python unify_name_translations.py -g glossary.json -t game/tl/schinese --step collect

  # 分类步
  python unify_name_translations.py --step classify

  # 统一步，预览模式
  python unify_name_translations.py --step unify --dry-run

  # 统一步，执行替换
  python unify_name_translations.py --step unify --apply

  # 回滚
  python unify_name_translations.py --rollback -t game/tl/schinese
        """,
    )

    parser.add_argument(
        "--step",
        "-s",
        type=str,
        choices=sorted(STEP_ALIASES),
        help="指定运行步骤：1/collect=收集, 2/classify=分类, 3/unify=统一"
             "（编号与名称等价）。不指定则运行全部三步。",
    )
    parser.add_argument(
        "--glossary",
        "-g",
        default=os.path.join(DEFAULT_WORK_DIR, DEFAULT_GLOSSARY),
        help="术语表 JSON 文件路径",
    )
    parser.add_argument(
        "--tl-dir",
        "-t",
        default=os.path.join(DEFAULT_WORK_DIR, "..", DEFAULT_TL_DIR),
        help="翻译文件目录 (tl/schinese)",
    )
    parser.add_argument(
        "--collection",
        "-a",
        default=os.path.join(DEFAULT_WORK_DIR, DEFAULT_COLLECT_FILE),
        help="Step 1 收集结果文件路径",
    )
    parser.add_argument(
        "--classification",
        "-c",
        default=os.path.join(DEFAULT_WORK_DIR, DEFAULT_CLASSIFICATION_FILE),
        help="Step 2 分类结果文件路径",
    )
    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Step 3: 预览模式，不实际修改",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Step 3: 执行替换",
    )
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="从备份恢复所有文件",
    )

    args = parser.parse_args()
    args.step = normalize_step(args.step)

    # 规范化路径
    tl_dir = os.path.abspath(args.tl_dir)
    glossary_path = os.path.abspath(args.glossary)
    collection_path = os.path.abspath(args.collection)
    classification_path = os.path.abspath(args.classification)

    # ── 回滚 ──
    if args.rollback:
        backup_dir = os.path.join(tl_dir, ".fix_name_backup")
        _do_rollback(tl_dir, backup_dir)
        return

    # ── 验证路径 ──
    if args.step in (1, None) and not os.path.exists(glossary_path):
        print(f"错误: 术语表文件不存在: {glossary_path}")
        sys.exit(1)
    if not os.path.exists(tl_dir):
        print(f"错误: 翻译目录不存在: {tl_dir}")
        sys.exit(1)

    # ── 执行 ──
    if args.step == 1:
        _run_step1(glossary_path, tl_dir, collection_path)
    elif args.step == 2:
        _run_step2(collection_path, classification_path)
    elif args.step == 3:
        _run_step3(classification_path, tl_dir, args.dry_run, args.apply)
    else:
        # 全流程
        print("=" * 70)
        print("  Step 1/3: 收集 — 扫描翻译文件")
        print("=" * 70)
        result = step1_collect(glossary_path, tl_dir, collection_path)

        print(f"\n  收集完成: {result['total_files']} 个文件, "
              f"{result['total_blocks']} 个翻译块, "
              f"{result['total_name_refs']} 处角色名引用")
        print(f"  收集结果: {collection_path}")

        print("\n" + "=" * 70)
        print("  Step 2/3: 分类 — 变体识别与归组")
        print("=" * 70)
        classification = step2_classify(collection_path, classification_path)

        totals = classification["totals"]
        if totals["variant_occurrences"] == 0:
            print("\n  没有发现变体，流程结束。")
            return

        print("\n" + "=" * 70)
        print("  Step 3/3: 统一 — 执行替换")
        print("=" * 70)
        if args.dry_run:
            step3_unify(classification_path, tl_dir, dry_run=True)
        elif args.apply:
            step3_unify(classification_path, tl_dir, apply=True)
        else:
            print("  预览模式（不修改文件）。")
            step3_unify(classification_path, tl_dir, dry_run=True)
            print(f"\n  确认无误后执行:")
            print(
                f"    python unify_name_translations.py --step unify --apply "
                f"--classification {classification_path} --tl-dir {tl_dir}"
            )


def _run_step1(glossary_path, tl_dir, collection_path):
    print("=" * 70)
    print("  Step 1: 收集 — 扫描翻译文件，记录角色名引用")
    print("=" * 70)
    print(f"  术语表: {glossary_path}")
    print(f"  翻译目录: {tl_dir}")

    result = step1_collect(glossary_path, tl_dir, collection_path)

    print(f"\n  扫描完成: {result['total_files']} 个文件, "
          f"{result['total_blocks']} 个翻译块, "
          f"{result['total_name_refs']} 处角色名引用")
    print(f"  收集结果: {collection_path}")
    print(f"\n  下一步: python unify_name_translations.py --step classify")


def _run_step2(collection_path, classification_path):
    if not os.path.exists(collection_path):
        print(f"错误: 收集结果文件不存在: {collection_path}")
        print("请先运行 Step 1")
        sys.exit(1)

    classification = step2_classify(collection_path, classification_path)
    totals = classification["totals"]

    if totals["variant_occurrences"] > 0:
        print(f"\n  下一步: python unify_name_translations.py --step unify --dry-run")


def _run_step3(classification_path, tl_dir, dry_run, apply):
    if not os.path.exists(classification_path):
        print(f"错误: 分类结果文件不存在: {classification_path}")
        print("请先运行 Step 2")
        sys.exit(1)

    step3_unify(classification_path, tl_dir, dry_run=dry_run, apply=apply)


if __name__ == "__main__":
    main()
