#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""renpy-tools 统一 CLI 入口。

用法::

    python renpy-tools-cli.py list
    python renpy-tools-cli.py all <项目目录> -l schinese
    python renpy-tools-cli.py integrity <项目目录> -l schinese

命令后的参数会原样传给子脚本。

退出码约定:
    0  - 所有检查通过 / 命令成功
    1  - 检查发现问题（不是脚本崩溃）
    2  - 脚本崩溃 / 参数错误 / 未找到命令

子脚本返回负值（如被信号终止）时会被归一化为 2。
"""

import argparse
import os
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PYTHON = sys.executable

# 工具注册表在 shared/tool_registry.py：子命令→路径、检查器契约元数据、分组。
# 过去这里是两张 33 项手写表（TOOL_SCRIPTS / TOOL_DESC）+ 两个硬编码集合
# （NEEDS_TL_DIR / TL_DIR_TOOLS）；现检查器的 name/summary/takes/requires_tl 由
# 各脚本自己的 CHECKER 声明，门面不再重复维护。动工具清单只改注册表一处。
_SHARED = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shared")
if _SHARED not in sys.path:
    sys.path.insert(0, _SHARED)

import tool_registry as REG  # noqa: E402

CHECK_DIR = os.path.join(REG.TOOLS_DIR, "checks")
TRANSLATE_DIR = os.path.join(REG.TOOLS_DIR, "translate")

#: 子命令 → 脚本绝对路径（工具清单只在注册表一处维护）
TOOL_SCRIPTS = {n: REG.script_path(n) for n in REG.TOOL_SCRIPTS}

#: 描述文案。检查器走 CHECKER.summary（脚本自报），非检查器走注册表 TOOL_DESC。
#: 门面多处用到 TOOL_DESC[name]，故这里给检查器也填一份快照——
#: 取自注册表，源头唯一，不会与脚本漂移。
TOOL_DESC = {n: REG.summary(n) for n in REG.TOOL_SCRIPTS}

#: 无 game/tl/<lang> 就无法工作的工具。all 跑之前统一检查一次，避免用户对着
#: 5 段一模一样的报错找原因。检查器部分来自各自 CHECKER.requires_tl。
NEEDS_TL_DIR = set(REG.all_requires_tl()) | REG.TL_DIR_WRITERS

# 分组只影响 `list` 的展示与 all 的先后；清单本体在 shared/tool_registry.py。
CHECK_GROUP = REG.CHECK_GROUP
CRASH_GROUP = REG.CRASH_GROUP
I18N_GROUP = REG.I18N_GROUP
STRUCT_GROUP = REG.STRUCT_GROUP
FIX_GROUP = REG.FIX_GROUP
SETUP_GROUP = REG.SETUP_GROUP

ALL_GROUP = REG.ALL_GROUP

# 接受 tl_dir 而非项目目录的子脚本：all 需要替用户把 `<项目>` 换算成
# `<项目>/game/tl/<lang>`，否则把项目路径直接喂给它们必然报「目录不存在」。
# 现在由各脚本的 CHECKER.takes 声明（untranslated 是唯一吃 tl_dir 的）。
TL_DIR_TOOLS = set(REG.all_takes_tl_dir())
DEFAULT_LANG = REG.DEFAULT_LANG


def _split_all_args(child_args):
    """从 all 的透传参数里拆出 (项目目录, 其它参数)。

    只做最小识别：第一个既不以 '-' 开头、也不是某个选项取值的 token 视为项目目录。
    无法可靠判断时返回 None，交由调用方跳过需要 tl_dir 的脚本（而不是传错路径）。
    """
    project = None
    rest = list(child_args)
    i = 0
    value_opts = {"-l", "--language", "--lang", "-o", "--output", "--csv", "--sdk"}
    while i < len(rest):
        tok = rest[i]
        if tok in value_opts:
            i += 2
            continue
        if tok.startswith("-"):
            i += 1
            continue
        if project is None:
            project = tok
        i += 1
    lang = DEFAULT_LANG
    for flag in ("-l", "--language", "--lang"):
        if flag in rest:
            idx = rest.index(flag)
            if idx + 1 < len(rest) and not rest[idx + 1].startswith("-"):
                lang = rest[idx + 1]
    return project, lang


def _tl_dir_for(project, lang):
    """项目目录 → tl 语言目录；不存在则返回 None。"""
    if not project:
        return None
    cand = os.path.join(project, "game", "tl", lang)
    return cand if os.path.isdir(cand) else None


def _replace_project_arg(child_args, project, replacement):
    """把透传参数里的项目路径替换为 tl_dir，其余参数原样保留。"""
    out = []
    for tok in child_args:
        out.append(replacement if tok == project else tok)
    return out


def run_script(name, args):
    script = TOOL_SCRIPTS[name]
    cmd = [PYTHON, script] + list(args)
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        rc = subprocess.call(cmd, env=env)
    except OSError as exc:
        print(f"[ERROR] 无法启动 {name}: {exc}", file=sys.stderr)
        return 2
    # 归一化退出码：负值（被信号终止）→ 2，其他非 0/1 值 → 1
    if rc < 0:
        return 2
    if rc > 1:
        return 1
    return rc


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        description="Ren'Py 翻译工具集",
        usage="python renpy-tools-cli.py <命令> [参数...]",
        add_help=False,
    )
    parser.add_argument("command", nargs="?", help=argparse.SUPPRESS)
    parser.add_argument("args", nargs="*", help=argparse.SUPPRESS)

    if not argv:
        parser.print_help()
        return 0
    if argv[0] in ("-h", "--help"):
        parser.print_help()
        return 0

    # 命令后的所有 token 原样转发。根 argparse 不能“消费” -l/--sdk 等
    # 子脚本参数，否则看似成功执行，实际使用了错误配置。
    cmd = argv[0]
    child_args = argv[1:]

    if cmd == "list":
        if child_args:
            print("[ERROR] list 命令不接受额外参数")
            return 2
        print("Ren'Py 翻译工具集\n")
        print("检查类 (只读，`all` 会跑):")
        for name in ALL_GROUP:
            print(f"  {name:14s} {TOOL_DESC[name]}")
        needs = sorted(NEEDS_TL_DIR & set(ALL_GROUP))
        print(f"\n上面 {len(ALL_GROUP)} 项中，{'/'.join(needs)}")
        print("需要 game/tl/<lang> 存在；没有时 all 会明确跳过并提示先跑 setup_i18n。")
        print("\n修补/写入类 (默认试运行，--apply/--execute 才落盘):")
        for name in FIX_GROUP + SETUP_GROUP:
            print(f"  {name:14s} {TOOL_DESC[name]}")
        print("\n其他 (只读，需显式调用):")
        grouped = set(ALL_GROUP) | set(FIX_GROUP) | set(SETUP_GROUP)
        for name in TOOL_DESC:
            if name not in grouped:
                print(f"  {name:14s} {TOOL_DESC[name]}")
        print("\n批量: python renpy-tools-cli.py all <项目目录> -l <语言>")
        return 0

    if cmd == "all":
        print("=" * 60)
        print("  ALL: " + " + ".join(ALL_GROUP))
        print("=" * 60)
        project, lang = _split_all_args(child_args)
        tl_dir = _tl_dir_for(project, lang)

        if not tl_dir:
            print(f"[WARN] 未找到 {project}/game/tl/{lang}")
            print("       以下翻译侧检查将跳过：")
            print("         " + " ".join(sorted(NEEDS_TL_DIR & set(ALL_GROUP))))
            print("       这是预期行为（项目还没建翻译目录），不是错误。")
            print("       想做翻译体检先跑：python sdk/setup_i18n.py --path <项目> --lang %s\n" % lang)
        else:
            print(f"tl 目录: {tl_dir}\n")

        failed = []
        for name in ALL_GROUP:
            print(f"\n--- {name} {'-' * (50 - len(name))}")
            print(f"  {TOOL_DESC[name]}")

            if name in NEEDS_TL_DIR and not tl_dir:
                print(f"  -- 跳过：无 {lang} 翻译目录")
                continue

            args = child_args
            if name in TL_DIR_TOOLS:
                # 用 tl_dir 替换透传参数里的项目路径位
                args = _replace_project_arg(child_args, project, tl_dir)
                print(f"  （tl_dir: {tl_dir}）")

            print(f"{'-' * 54}")
            rc = run_script(name, args)
            if rc != 0:
                failed.append((name, rc))
                print(f"\n  !! {name} exit code {rc}")
        if failed:
            print("\n有问题的检查项: " + ", ".join(f"{name}({rc})" for name, rc in failed))
            print("（退出码 1 通常表示「查出了问题」，不是脚本崩溃；崩溃看 traceback）")
            return 1
        return 0

    if cmd in TOOL_SCRIPTS:
        return run_script(cmd, child_args)

    print(f"未知命令: {cmd}")
    print(f"可用: {', '.join(TOOL_SCRIPTS.keys())}, all, list")
    return 2


if __name__ == "__main__":
    sys.exit(main() or 0)
