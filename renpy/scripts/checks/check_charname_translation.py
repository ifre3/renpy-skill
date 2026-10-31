#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""角色名字框（namebox）翻译完整性检查

原理
----
Ren'Py 把裸字符串说话人现场包成 Character（``renpy/defaultstore.py:420-422``），
名字最终经 ``substitute(..., translate=True)`` 查字符串翻译
（``renpy/character.py:1348-1349`` → ``renpy/substitutions.py:344-345``）。
所以 namebox 是否显示中文，取决于 ``tl/<lang>`` 里是否存在与
**完整串精确相等**的条目——含 ``{color=}`` 标签时 ``old`` 也必须带标签。

这和名字出现在哪里无关：Character 定义、裸 define 变量、菜单选项、
正文同名串共用同一个 key。

本工具做的事
------------
1. 扫全项目 .rpy，识别三类名字来源（识别逻辑见 ``shared/namebox.py``）::

       define e  = Character("Eri", ...)             # kind=character
       define nih = "{color=#0f37f2}Niwa{/color}"    # kind=define（无 Character 的项目）
       "Ailing Man" "Uggghhhhhh..."                  # kind=inline

   只认 Character 的话，Dissonance_0.14 这类项目会扫出 0 个名字并误报全绿；
2. 统计每个说话人的实际台词条数，用于排优先级；
3. 读 ``tl/<lang>`` 的 old/new，判断条目是否存在、译文是否为空；
4. ``--stub`` 生成待填的 ``translate strings`` 骨架（新串保留原颜色标签）。

与既有工具的分工
----------------
``check_auto_trans.py``      —— 交叉引用 menu 选项等字符串
``sync_namebox_translation.py`` —— 按术语表批量补条目（需 xlsx/json 术语表）

用法
----
    python check_charname_translation.py <项目目录>
    python check_charname_translation.py <项目目录> -l schinese
    python check_charname_translation.py <项目目录> --stub game/tl/schinese/zz_namebox.rpy
    python check_charname_translation.py <项目目录> --json report.json

退出码：0 = 全部有译文；1 = 存在缺失/空译文；2 = 参数或路径错误。
"""

import argparse
import io
import json
import os
import sys
# 契约层在 shared/（跨组共享，故按相对路径加入 sys.path）
_SHARED_CONTRACT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "../shared")
if _SHARED_CONTRACT_DIR not in sys.path:
    sys.path.insert(0, _SHARED_CONTRACT_DIR)

from lang_names import DEFAULT_LANG  # noqa: E402
from base_checker import PROJECT, BaseChecker  # noqa: E402

try:
    from namebox import (
        NameDef,
        load_tl_strings,
        lookup_translation,
        render_entry,
        render_strings_block,
        scan_namebox_names,
        splice_tags,
        strip_text_tags,
    )
except ImportError:  # 独立运行时退化：只支持 Character 写法
    NameDef = None


class CharnameTranslationChecker(BaseChecker):
    """角色名漏译检测。"""

    name = "charname"
    summary = "检查角色名字框翻译完整性（Character 定义名是否有字符串翻译）"
    takes = PROJECT
    requires_tl = True


#: 门面发现用的实例（契约见 shared/base_checker.py）
CHECKER = CharnameTranslationChecker()


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def write_stub(path, missing, language):
    """生成待填的 translate strings 骨架（new 留空，AI/人工填）。"""
    header = "\n".join([
        "角色名字框翻译补漏（由 check_charname_translation.py --stub 生成）",
        "经字符串翻译生效：Ren'Py 按 old 原文**全串精确匹配**。",
        "含 {color=} 标签的旧串，new 里必须保留同样的标签，否则角色配色会丢。",
        "请把每条 old 对应的中文名填到 new 里，然后删掉本注释块。",
    ])
    entries = [render_entry(nd.value, "", comment=nd.source) for nd in missing]
    io.open(path, "w", encoding="utf-8", newline="\n").write(
        render_strings_block(language, entries, header=header)
    )
    return path


def main():
    ap = argparse.ArgumentParser(
        description="检查角色名字框翻译完整性（说话人名字 vs tl 字符串翻译）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  python check_charname_translation.py "MyGame-1.0-pc"
  python check_charname_translation.py "MyGame-1.0-pc" -l schinese
  python check_charname_translation.py "MyGame-1.0-pc" --stub game/tl/schinese/zz_namebox.rpy
""",
    )
    ap.add_argument("project", help="项目根目录或 game 目录")
    ap.add_argument("-l", "--language", default=DEFAULT_LANG, help="目标语言目录名")
    ap.add_argument(
        "--glossary",
        help="术语表路径（.xlsx/.json）。给了才能识别「可保留英文」的名字——"
             "那类名字原样显示即正确，不算缺失",
    )
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

    keep_english = set()
    if args.glossary:
        sys.path.insert(
            0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "..", "translate"))
        try:
            from sync_namebox_translation import (
                KEEP_ENGLISH_MARKERS, load_glossary_with_notes)
            _g, _notes = load_glossary_with_notes(args.glossary)
            keep_english = {
                src for src, note in _notes.items()
                if any(m in note for m in KEEP_ENGLISH_MARKERS)
            }
        except ImportError:
            print("[WARN] 读不到 sync_namebox_translation，跳过「保留英文」判定")

    names = scan_namebox_names(game_dir)
    strings = load_tl_strings(tl_dir)

    if not names:
        print("[?] 一个说话人定义都没扫到。")
        print("    纯 .rpyc 发行版（无 .rpy 源码）请先反编译；"
              "若源码在但仍为 0，可能是识别规则需要更新。")
        return 0

    translated, empty, missing, kept = [], [], [], []
    for nd in sorted(names, key=lambda n: (-n.say_lines, n.plain.lower())):
        hit = lookup_translation(nd.value, strings)
        if hit is None:
            if args.glossary and nd.plain in keep_english:
                kept.append(nd)
            else:
                missing.append(nd)
        elif not hit.strip():
            empty.append(nd)
        else:
            translated.append((nd, hit))

    print(f"扫描 {len(names)} 个说话人（character {sum(1 for n in names if n.kind=='character')} / "
          f"define {sum(1 for n in names if n.kind=='define')} / "
          f"inline {sum(1 for n in names if n.kind=='inline')}）")
    print(f"翻译目录: {tl_dir}")
    print(f"已有译文 {len(translated)} | 空译文 {len(empty)} | 无条目 {len(missing)}"
          + (f" | 保留英文 {len(kept)}" if args.glossary else "") + "\n")

    if missing:
        print("[!!] 缺少翻译条目（namebox 会显示英文）：")
        rows = []
        for nd in missing:
            tag = "带标签" if nd.tagged else "裸名  "
            src = os.path.basename(nd.source.split(":")[0])
            print(f'   {nd.plain:<22} {nd.say_lines:>5} 句  {tag}  [{nd.kind}] <- {src}')
            rows.append({
                "name": nd.plain, "value": nd.value, "lines": nd.say_lines,
                "kind": nd.kind, "tagged": nd.tagged, "source": nd.source,
            })
    else:
        print("[OK] 所有说话人名字都有翻译条目。")
        rows = []

    if empty:
        print("\n[!!] 有条目但译文为空：")
        for nd in empty:
            print(f'   {nd.plain!r}  (old "{nd.value}")')

    if kept:
        print("\n[-] 术语表标注「保留英文」（原样显示即正确，不算缺失）：")
        for nd in sorted(kept, key=lambda n: -n.say_lines):
            print(f"   {nd.plain}（{nd.say_lines} 句）")

    if args.stub:
        if not missing:
            print("\n--stub: 无缺失，未生成文件。")
        else:
            path = write_stub(args.stub, missing, args.language)
            print(f"\n已生成待填骨架: {path}（{len(missing)} 条，new 均为空）")

    if args.json_path:
        io.open(args.json_path, "w", encoding="utf-8").write(json.dumps({
            "total": len(names),
            "translated": {nd.plain: hit for nd, hit in translated},
            "empty": [nd.value for nd in empty],
            "missing": rows,
            "kept_english": [nd.plain for nd in kept],
        }, ensure_ascii=False, indent=2))
        print(f"结果已导出: {args.json_path}")

    return 1 if (missing or empty) else 0


if __name__ == "__main__":
    sys.exit(main())