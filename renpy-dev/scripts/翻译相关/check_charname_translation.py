#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""角色名字框（namebox）翻译完整性检查

原理：
  Ren'Py 显示说话人名字时会经 substitute(..., translate=True) 查字符串翻译，
  所以 namebox 是否显示中文，取决于 tl/<lang> 里是否存在 ``old "名字"`` 完全匹配的条目。
  这和名字出现在哪里无关——Character 定义、菜单选项、正文里的同名串共用同一个 key。

本工具做的事（既有工具都不覆盖的组合）：
  1. 扫全项目 .rpy（自动跳过 tl/、备份目录、.bak）提取 ``Character("Name")`` 定义，
     以及 ``"Name" "台词"`` 这种内联说话人写法；
  2. 统计每个角色变量的实际台词条数，用于排优先级；
  3. 读 tl/<lang> 的全部 old/new 字符串翻译，判断名字是否有条目、译文是否为空；
  4. 报告缺失清单，可用 --stub 生成待填的 translate strings 骨架。

与既有工具的分工：
  check_auto_trans.py  —— 交叉引用 menu 选项等字符串（不含只出现在 Character 定义里的名字）
  sync_namebox_translation.py —— 按术语表批量补条目（需先有 xlsx/json 术语表）

用法：
  python check_charname_translation.py <项目目录>               # 项目根或 game 目录均可
  python check_charname_translation.py <项目目录> -l schinese
  python check_charname_translation.py <项目目录> --stub out.rpy
  python check_charname_translation.py <项目目录> --json report.json

退出码：0 = 全部有译文；1 = 存在缺失/空译文；2 = 参数或路径错误。
"""

import argparse
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "公共"))
try:
    from rpy_syntax import encode_rpy_string_content, iter_translation_pairs
except ImportError:  # 独立运行时退化为内置实现
    encode_rpy_string_content = None
    iter_translation_pairs = None

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# define c_x = Character("Name"  /  define c_x = Character(_("Name"
CHAR_DEF = re.compile(
    r'^\s*define\s+(\w+)\s*=\s*Character\(\s*_?\(\s*"((?:[^"\\]|\\.)*)"'
)
CHAR_DEF_PLAIN = re.compile(
    r'^\s*define\s+(\w+)\s*=\s*Character\(\s*"((?:[^"\\]|\\.)*)"'
)
# 内联说话人: "Name" "台词"
INLINE_SAY = re.compile(r'^\s{2,}"((?:[^"\\]|\\.)*)"\s+"')
# 角色台词: c_name "..." / c_name '...'
CHAR_SAY = re.compile(r'^\s{2,}(\w+)\s+[\'"]')

SKIP_DIR_HINTS = ("backup", ".git", "__pycache__", "saves", "cache")


def iter_rpy_files(game_dir):
    """游戏脚本 .rpy（排除 tl/ 翻译目录、备份与缓存目录、.bak 文件）。"""
    for dirpath, dirnames, filenames in os.walk(game_dir):
        rel = os.path.relpath(dirpath, game_dir).replace("\\", "/")
        parts = rel.split("/")
        if "tl" in parts or any(
            any(h in p.lower() for h in SKIP_DIR_HINTS) for p in parts
        ):
            dirnames[:] = []
            continue
        for fn in filenames:
            if fn.endswith(".rpy") and not fn.endswith(".rpy.bak"):
                yield os.path.join(dirpath, fn)


def collect_characters(game_dir):
    """返回 names: {显示名: [(文件, 变量或<inline who>), ...]}"""
    names = {}
    files = sorted(iter_rpy_files(game_dir))
    for path in files:
        try:
            lines = io.open(path, encoding="utf-8").read().splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for line in lines:
            m = CHAR_DEF.match(line) or CHAR_DEF_PLAIN.match(line)
            if m:
                names.setdefault(m.group(2), []).append((os.path.basename(path), m.group(1)))
                continue
            m = INLINE_SAY.match(line)
            if m and m.group(1) and not m.group(1).startswith("["):
                names.setdefault(m.group(1), []).append((os.path.basename(path), "<inline who>"))
    return names, files


def count_lines(var, game_dir):
    """统计该角色变量的台词条数（用于排优先级）。"""
    if var == "<inline who>":
        return 0
    pat = re.compile(r'^\s{2,}' + re.escape(var) + r'\s+[\'"]')
    total = 0
    for path in iter_rpy_files(game_dir):
        try:
            text = io.open(path, encoding="utf-8").read()
        except (OSError, UnicodeDecodeError):
            continue
        total += sum(1 for line in text.splitlines() if pat.match(line))
    return total


def collect_string_translations(tl_dir):
    """tl 目录下的 old -> new 映射（跳过备份与 bilingual_auto）。"""
    result = {}
    for dirpath, dirnames, filenames in os.walk(tl_dir):
        rel = os.path.relpath(dirpath, tl_dir).replace("\\", "/")
        if any(h in rel.lower() for h in SKIP_DIR_HINTS) or "bilingual_auto" in rel:
            dirnames[:] = []
            continue
        for fn in filenames:
            if not (fn.endswith(".rpy") and not fn.endswith(".rpy.bak")):
                continue
            path = os.path.join(dirpath, fn)
            try:
                lines = io.open(path, encoding="utf-8").read().splitlines()
            except (OSError, UnicodeDecodeError):
                continue
            if iter_translation_pairs is not None:
                for pair in iter_translation_pairs(lines):
                    if pair.kind == "on":
                        result[pair.original] = pair.translated or ""
            else:  # 退化解析
                for i, line in enumerate(lines):
                    om = re.match(r'^\s{4}old\s+"((?:[^"\\]|\\.)*)"\s*$', line)
                    if om:
                        nm = re.match(r'^\s{4}new\s+"((?:[^"\\]|\\.)*)"', lines[i + 1] if i + 1 < len(lines) else "")
                        result[om.group(1)] = nm.group(1) if nm else ""
    return result


def encode(text):
    if encode_rpy_string_content is not None:
        return encode_rpy_string_content(text)
    return text.replace("\\", "\\\\").replace('"', '\\"')


def write_stub(path, missing, language):
    """生成待填的 translate strings 骨架（new 留空，AI/人工填）。"""
    body = [
        "## 角色名字框翻译补漏（由 check_charname_translation.py --stub 生成）",
        "## 经字符串翻译生效：Ren'Py 显示名字时按 old 原文全局匹配。",
        "## 请把每条 old 对应的中文名填到 new 里，然后删掉本注释块。",
        "",
        f"translate {language} strings:",
        "",
    ]
    for name in missing:
        body.append(f'    old "{encode(name)}"')
        body.append('    new ""')
        body.append("")
    io.open(path, "w", encoding="utf-8", newline="\n").write("\n".join(body))
    return path


def main():
    ap = argparse.ArgumentParser(
        description="检查角色名字框翻译完整性（Character 定义名 vs tl 字符串翻译）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  python check_charname_translation.py "MyGame-1.0-pc"
  python check_charname_translation.py "MyGame-1.0-pc" -l schinese
  python check_charname_translation.py "MyGame-1.0-pc" --stub game/tl/schinese/zz_charnames.rpy
""",
    )
    ap.add_argument("project", help="项目根目录或 game 目录")
    ap.add_argument("-l", "--language", default="schinese", help="目标语言目录名（默认 schinese）")
    ap.add_argument("--stub", dest="stub", help="把缺失名单写成 translate strings 骨架到该路径")
    ap.add_argument("--json", dest="json_path", help="把结果导出为 JSON")
    args = ap.parse_args()

    project = args.project
    game_dir = project if os.path.basename(project) == "game" else os.path.join(project, "game")
    if not os.path.isdir(game_dir):
        print(f"[ERROR] 未找到 game 目录: {game_dir}")
        return 2
    tl_dir = os.path.join(game_dir, "tl", args.language)
    if not os.path.isdir(tl_dir):
        print(f"[ERROR] 未找到翻译目录: {tl_dir}")
        return 2

    names, files = collect_characters(game_dir)
    strings = collect_string_translations(tl_dir)

    translated, empty, missing = [], [], []
    for name in sorted(names, key=lambda s: s.lower()):
        if name not in strings:
            missing.append(name)
        elif not strings[name].strip():
            empty.append(name)
        else:
            translated.append((name, strings[name]))

    print(f"扫描 {len(files)} 个脚本，提取 {len(names)} 个名字")
    print(f"翻译目录: {tl_dir}")
    print(f"已有译文 {len(translated)} | 空译文 {len(empty)} | 无条目 {len(missing)}\n")

    if missing:
        print("[!!] 缺少翻译条目（namebox 会显示英文）：")
        rows = []
        for name in missing:
            where = names[name]
            src = ", ".join(sorted({f for f, _ in where}))
            cnt = sum(count_lines(v, game_dir) for _, v in where) if len(where) <= 3 else 0
            print(f'   {name!r:40} {cnt:>4} 句   <- {src}')
            rows.append({"name": name, "lines": cnt, "files": sorted({f for f, _ in where})})
    else:
        print("[OK] 所有名字都有翻译条目。")
        rows = []

    if empty:
        print("\n[!!] 有条目但译文为空：")
        for name in empty:
            print(f"   {name!r}")

    if args.stub:
        if not missing:
            print("\n--stub: 无缺失，未生成文件。")
        else:
            path = write_stub(args.stub, missing, args.language)
            print(f"\n已生成待填骨架: {path}（{len(missing)} 条，new 均为空）")

    if args.json_path:
        io.open(args.json_path, "w", encoding="utf-8").write(json.dumps({
            "total": len(names),
            "translated": {k: v for k, v in translated},
            "empty": empty,
            "missing": rows,
        }, ensure_ascii=False, indent=2))
        print(f"结果已导出: {args.json_path}")

    return 1 if (missing or empty) else 0


if __name__ == "__main__":
    sys.exit(main())
