#!/usr/bin/env python3
"""
Ren'Py 对话中人名统一修复脚本 v2 (deprecated)
=====================================
基于原始英文台词判断角色名引用，精准替换对话中的中文名变体。

使用方法:
    python fix_name_inconsistencies.py --glossary 术语表.json --tl-dir game/tl/schinese          # 审计模式 (只扫描)
    python fix_name_inconsistencies.py --glossary 术语表.json --tl-dir game/tl/schinese --apply  # 执行替换
    python fix_name_inconsistencies.py --rollback --tl-dir game/tl/schinese  # 从备份恢复
"""

import json
import os
import re
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── 引入共享公共 ──
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "公共")
)
from backup import create_bak

BACKUP_DIR = None  # 初始化时设置


def parse_args():
    import argparse
    ap = argparse.ArgumentParser(description="Ren'Py 人名翻译一致性修复 (deprecated)")
    ap.add_argument("--glossary", "-g", required=False, help="术语表 JSON 文件路径")
    ap.add_argument("--tl-dir", "-t", required=False, help="翻译文件目录 (如 game/tl/schinese)")
    return ap.parse_args()

SKIP_FILES = [
    "defaultlanguage.rpy",
    "character_name_map.rpy",
    "options_translated.rpy",
    "cheats_translated.rpy",
]


def load_glossary():
    """加载术语表: {英文名: 中文标准名}"""
    with open(GLOSSARY_PATH, "r", encoding="utf-8") as f:
        return {e["src"]: e["dst"] for e in json.load(f)}


def collect_all_files():
    """收集所有需要扫描的翻译文件"""
    files = []
    for root, dirs, filenames in os.walk(TL_DIR):
        if ".fix_name_backup" in root:
            continue
        for fn in filenames:
            if fn in SKIP_FILES:
                continue
            if fn.endswith(".rpy"):
                files.append(os.path.join(root, fn))
    return sorted(files)


# 已知的中文名变体映射: {英文原名: {中文变体: 标准译名}}
# 这些变体是通过人工验证确认的对话中真实角色名引用
KNOWN_VARIANTS = {
    "Tomori": {
        "朋里": "灯里",
        "朋美": "灯里",
        "朋莉": "灯里",
        "朋多里": "灯里",
        "朋绘": "灯里",
        "托莫里": "灯里",
    },
    "Nami": {
        "南米": "奈美",
        "小波": "奈美",
        "波奇": "奈美",
        "南子": "奈美",
    },
    "Saki": {
        "萨琪": "咲",
        "咲子": "咲",
    },
    "Yui": {
        "由衣": "优衣",
        "由依": "优衣",
        "尤伊": "优衣",
    },
    "Kurumi": {
        "栗生": "胡桃",
        "久瑠美": "胡桃",
        "曲美": "胡桃",
    },
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
    },
    "Yokubo": {
        "欲部": "欲望",
        "优库波": "欲望",
    },
    "Shuu": {
        "修": "秀",
    },
    "Hina": {
        "日奈": "雏",
    },
    "Kodoku": {
        "孤獨": "孤独",
    },
}


def is_character_reference(english_line, en_name, zh_name):
    """
    判断某英文台词行是否引用了指定角色。
    策略: 检查英文原文中是否包含角色英文名 (作为独立单词)
    """
    if not english_line:
        return False

    # 角色名作为独立单词出现 (不区分大小写)
    pattern = r"\b" + re.escape(en_name) + r"\b"
    return bool(re.search(pattern, english_line, re.IGNORECASE))


def scan_file(filepath, name_map):
    """
    扫描单个文件，基于原始英文台词判断角色名引用。
    返回: [(行号, 英文原句, 中文对话, 英文角色名, 变体字符串, 标准译名)]
    """
    results = []

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
        lines = content.split("\n")

    is_strings_file = "translate schinese strings:" in content
    if is_strings_file:
        return results  # 跳过 strings 文件

    in_dialogue_block = False
    prev_comment = ""  # 上一条 # 注释行 (原始英文台词)

    for i, line in enumerate(lines):
        stripped = line.strip()

        # 追踪 translate 块类型
        if stripped.startswith("translate schinese"):
            if "strings:" in stripped:
                in_dialogue_block = False
            else:
                in_dialogue_block = True
            prev_comment = ""
            continue

        if not in_dialogue_block:
            prev_comment = ""
            continue

        # 记录注释行 (原始英文)
        if stripped.startswith("#"):
            # 去掉 # 前缀和可能的 c_xxx 前缀
            comment_text = stripped.lstrip("# ")
            prev_comment = comment_text
            continue

        # 空行重置
        if not stripped:
            prev_comment = ""
            continue

        # 只处理 c_xxx "对话内容" 格式
        dialog_match = re.match(r'^(c_\w+)\s+"(.*)"\s*$', stripped)
        if not dialog_match:
            continue

        character_var = dialog_match.group(1)
        dialog_text = dialog_match.group(2)

        # 对术语表中每个角色，检查是否有引用
        for en_name, zh_name in name_map.items():
            if not is_character_reference(prev_comment, en_name, zh_name):
                continue

            # 英文原文引用了这个角色
            # 检查中文翻译是否使用了标准译名
            if zh_name in dialog_text:
                continue  # 已使用标准名

            # 检查是否有已知中文变体
            en_variants = KNOWN_VARIANTS.get(en_name, {})
            matched = False
            for variant, standard in en_variants.items():
                if variant in dialog_text:
                    results.append(
                        {
                            "file": filepath,
                            "line_num": i + 1,
                            "character_var": character_var,
                            "en_line": prev_comment,
                            "cn_line": dialog_text,
                            "en_name": en_name,
                            "old_text": variant,
                            "new_text": standard,
                        }
                    )
                    matched = True
                    break

            if matched:
                continue

            # 检查英文名是否照原样保留在中文中 (未翻译)
            en_pattern = r"\b" + re.escape(en_name) + r"\b"
            if re.search(en_pattern, dialog_text):
                results.append(
                    {
                        "file": filepath,
                        "line_num": i + 1,
                        "character_var": character_var,
                        "en_line": prev_comment,
                        "cn_line": dialog_text,
                        "en_name": en_name,
                        "old_text": en_name,
                        "new_text": zh_name,
                    }
                )
                continue
                # 英文提到了角色，但中文既没用标准名也没用已知变体
                # 可能是完全不同的翻译，需要人工检查
                results.append(
                    {
                        "file": filepath,
                        "line_num": i + 1,
                        "character_var": character_var,
                        "en_line": prev_comment,
                        "cn_line": dialog_text,
                        "en_name": en_name,
                        "old_text": "(未知变体)",
                        "new_text": zh_name,
                        "unknown": True,
                    }
                )

    return results


def scan_all(name_map):
    """扫描所有文件"""
    files = collect_all_files()
    print(f"待扫描文件: {len(files)} 个\n")

    all_results = []
    for filepath in files:
        results = scan_file(filepath, name_map)
        all_results.extend(results)

    return all_results


def create_backup():
    """创建所有文件的备份"""
    if os.path.exists(BACKUP_DIR):
        shutil.rmtree(BACKUP_DIR)
    os.makedirs(BACKUP_DIR)

    files = collect_all_files()
    for filepath in files:
        rel = os.path.relpath(filepath, TL_DIR)
        dest = os.path.join(BACKUP_DIR, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(filepath, dest)
    print(f"备份完成: {len(files)} 文件 -> {BACKUP_DIR}")


def rollback():
    """从备份恢复"""
    if not os.path.exists(BACKUP_DIR):
        print("错误: 没有找到备份目录")
        return

    restored = 0
    for root, dirs, files in os.walk(BACKUP_DIR):
        for fn in files:
            src = os.path.join(root, fn)
            rel = os.path.relpath(src, BACKUP_DIR)
            dest = os.path.join(TL_DIR, rel)
            shutil.copy2(src, dest)
            restored += 1
    print(f"已恢复 {restored} 个文件")


def main():
    args = parse_args()

    global GLOSSARY_PATH, TL_DIR, BACKUP_DIR
    if args.glossary:
        GLOSSARY_PATH = args.glossary
    if args.tl_dir:
        TL_DIR = args.tl_dir
    BACKUP_DIR = os.path.join(TL_DIR, ".fix_name_backup")

    if "--rollback" in sys.argv or hasattr(args, 'rollback'):
        rollback()
        return

    if not os.path.exists(GLOSSARY_PATH):
        print(f"错误: 术语表不存在: {GLOSSARY_PATH}")
        print("用法: python fix_name_inconsistencies.py --glossary 术语表.json --tl-dir game/tl/schinese")
        sys.exit(1)
    if not os.path.isdir(TL_DIR):
        print(f"错误: 翻译目录不存在: {TL_DIR}")
        print("用法: python fix_name_inconsistencies.py --glossary 术语表.json --tl-dir game/tl/schinese")
        sys.exit(1)

    print("=" * 60)
    print("Ren'Py 人名翻译一致性审计 v2")
    print("=" * 60)
    print()

    name_map = load_glossary()
    print(f"术语表角色: {len(name_map)} 个")
    for en, zh in sorted(name_map.items()):
        variants = KNOWN_VARIANTS.get(en, {})
        if variants:
            print(f"  {en} -> {zh}  (变体: {', '.join(variants.keys())})")
        else:
            print(f"  {en} -> {zh}")
    print()

    all_results = scan_all(name_map)

    # 分离已知变体和未知变体
    known = [r for r in all_results if not r.get("unknown")]
    unknown = [r for r in all_results if r.get("unknown")]

    print("=" * 60)

    if not known and not unknown:
        print("\n[OK] 未发现不一致！")
        return

    if known:
        print(f"\n[可自动修复] {len(known)} 处:")
        by_file = {}
        for r in known:
            rel = os.path.relpath(r["file"], TL_DIR)
            by_file.setdefault(rel, []).append(r)

        for rel, items in sorted(by_file.items()):
            print(f"\n  {rel} ({len(items)} 处)")
            for r in items:
                print(
                    f'    L{r["line_num"]:>5} | {r["en_name"]}: "{r["old_text"]}" -> "{r["new_text"]}"'
                )
                print(f"          原: {r['en_line'][:70]}")
                print(f"          译: {r['cn_line'][:70]}")

    if unknown:
        print(
            f"\n[需人工审核] {len(unknown)} 处 (英文引用了角色名但中文翻译使用了非标准名称):"
        )
        by_file = {}
        for r in unknown:
            rel = os.path.relpath(r["file"], TL_DIR)
            by_file.setdefault(rel, []).append(r)

        for rel, items in sorted(by_file.items()):
            print(f"\n  {rel} ({len(items)} 处)")
            for r in items[:10]:
                print(
                    f'    L{r["line_num"]:>5} | {r["en_name"]} 应译为 "{r["new_text"]}"'
                )
                print(f"          原: {r['en_line'][:70]}")
                print(f"          译: {r['cn_line'][:70]}")
            if len(items) > 10:
                print(f"    ... 还有 {len(items) - 10} 处")

    # 执行替换
    if "--apply" in sys.argv and known:
        print("\n" + "=" * 60)
        print("开始执行替换...")
        create_backup()

        by_file = {}
        for r in known:
            rel = os.path.relpath(r["file"], TL_DIR)
            by_file.setdefault(rel, []).append(r)

        replaced = 0
        files_modified = set()

        for rel, items in sorted(by_file.items()):
            filepath = os.path.join(TL_DIR, rel)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            lines = content.split("\n")

            file_changed = False
            for r in items:
                line_idx = r["line_num"] - 1
                if line_idx >= len(lines):
                    continue
                old_line = lines[line_idx]
                new_line = old_line.replace(r["old_text"], r["new_text"])
                if new_line != old_line:
                    lines[line_idx] = new_line
                    file_changed = True
                    replaced += 1
                    print(
                        f'  [OK] {rel}:L{r["line_num"]} "{r["old_text"]}" -> "{r["new_text"]}"'
                    )

            if file_changed:
                create_bak(filepath)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines))
                files_modified.add(rel)

        print(f"\n[完成] 替换完成!")
        print(f"  修改文件: {len(files_modified)} 个")
        print(f"  替换条目: {replaced} 处")
        print(f"  备份目录: {BACKUP_DIR}")
        print(f"  回滚命令: python fix_name_inconsistencies.py --rollback")

    elif "--apply" in sys.argv and not known:
        print("\n没有需要自动修复的条目。")
    else:
        print("\n" + "=" * 60)
        print("当前为审计模式 (只扫描不修改)")
        print("如需执行替换:")
        print("  python fix_name_inconsistencies.py --apply")


if __name__ == "__main__":
    main()
