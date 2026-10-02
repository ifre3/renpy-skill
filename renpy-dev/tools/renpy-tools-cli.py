#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""renpy-tools 统一 CLI 入口。

用法::

    python renpy-tools-cli.py list
    python renpy-tools-cli.py all <项目目录> -l schinese
    python renpy-tools-cli.py integrity <项目目录> -l schinese

命令后的参数会原样传给子脚本，本入口自身的退出码就是子脚本失败状态的汇总。
"""

import argparse
import os
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
CHECK_DIR = os.path.join(TOOLS_DIR, "错误检测")
TRANSLATE_DIR = os.path.join(TOOLS_DIR, "翻译相关")
LINEAR_DIR = os.path.join(TOOLS_DIR, "线性模式")
PYTHON = sys.executable

TOOL_SCRIPTS = {
    "ui": os.path.join(CHECK_DIR, "check_ui_text.py"),
    "misuse": os.path.join(CHECK_DIR, "check_translation_misuse.py"),
    "func": os.path.join(CHECK_DIR, "check_func_text.py"),
    "auto": os.path.join(CHECK_DIR, "check_auto_trans.py"),
    "duplicate": os.path.join(CHECK_DIR, "check_duplicate_translations.py"),
    "button": os.path.join(CHECK_DIR, "check_button_missing_translation.py"),
    "label": os.path.join(CHECK_DIR, "check_label_issues.py"),
    "type": os.path.join(CHECK_DIR, "check_type_safety.py"),
    "lint": os.path.join(CHECK_DIR, "lint_check.py"),
    "integrity": os.path.join(TRANSLATE_DIR, "check_translation_integrity.py"),
    "untranslated": os.path.join(TRANSLATE_DIR, "check_untranslated.py"),
    "charname": os.path.join(TRANSLATE_DIR, "check_charname_translation.py"),
    "namebox": os.path.join(TRANSLATE_DIR, "sync_namebox_translation.py"),
    "crash": os.path.join(CHECK_DIR, "check_crash_risks.py"),
    "linear": os.path.join(LINEAR_DIR, "linear_mode.py"),
}

TOOL_DESC = {
    "ui": "检测 screen UI 文本 (textbutton/label/show text) 缺少 _()",
    "misuse": "检测 Character[var] 缺 !t、翻译函数误用和插值标志问题",
    "func": "检测 renpy.input/notify/自定义屏幕调用缺少 _()",
    "auto": "交叉引用 Character 名字框和 menu 选项翻译覆盖",
    "duplicate": "检测翻译文件中重复的 old 字符串",
    "button": "检测按钮文本未被 translate strings 捕获",
    "label": "检测 Ren'Py 标签问题（未定义/重复/不可达）",
    "type": "检测 Python 类型安全问题",
    "lint": "调用 SDK lint 和翻译专项检查",
    "integrity": "检查变量、角色、标签结构、参数和转义完整性",
    "untranslated": "检查未翻译或空译文条目（支持 CSV）",
    "charname": "检查角色名字框翻译完整性（Character 定义名是否有字符串翻译）",
    "namebox": "同步角色名字框翻译（按术语表）",
    "crash": "检测运行时崩溃风险",
    "linear": "线性模式: analyze 分析 / add 生成补丁 / modify 校验事件表",
}

CHECK_GROUP = ["ui", "misuse", "func", "auto", "charname"]
CRASH_GROUP = ["crash"]


def run_script(name, args):
    script = TOOL_SCRIPTS[name]
    cmd = [PYTHON, script] + list(args)
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        return subprocess.call(cmd, env=env)
    except OSError as exc:
        print(f"[ERROR] 无法启动 {name}: {exc}", file=sys.stderr)
        return 2


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
        print("检查类:")
        for name, desc in TOOL_DESC.items():
            if name in CHECK_GROUP or name in CRASH_GROUP:
                print(f"  {name:14s} {desc}")
        print("\n其他:")
        for name, desc in TOOL_DESC.items():
            if name not in CHECK_GROUP and name not in CRASH_GROUP:
                print(f"  {name:14s} {desc}")
        print("\n批量: python renpy-tools-cli.py all <项目目录> [子脚本参数...]")
        return 0

    if cmd == "all":
        print("=" * 60)
        print("  ALL: ui + misuse + func + auto + charname + crash")
        print("=" * 60)
        failed = []
        for name in CHECK_GROUP + CRASH_GROUP:
            print(f"\n--- {name} {'-' * (50 - len(name))}")
            print(f"  {TOOL_DESC[name]}")
            print(f"{'-' * 54}")
            rc = run_script(name, child_args)
            if rc != 0:
                failed.append((name, rc))
                print(f"\n  !! {name} exit code {rc}")
        if failed:
            print("\n失败项: " + ", ".join(f"{name}({rc})" for name, rc in failed))
            return 1
        return 0

    if cmd in TOOL_SCRIPTS:
        return run_script(cmd, child_args)

    print(f"未知命令: {cmd}")
    print(f"可用: {', '.join(TOOL_SCRIPTS.keys())}, all, list")
    return 2


if __name__ == "__main__":
    sys.exit(main() or 0)
