"""
Ren'Py 错误诊断 — 解析 Ren'Py 错误/警告日志并推荐修复方案

用法：
    diagnose("D:/projects/my_game/game/log.txt")
    diagnose_from_text('''  # 从文本
I''m sorry, but an uncaught exception occurred.
...
''')

    # 检测项目常见问题
    check_project("D:/projects/my_game")
"""

import os
import re
import sys


# ── 诊断规则 ──────────────────────────────────────────

DIAG_RULES = [
    {
        "pattern": r"NameError: name '(\w+)' is not defined",
        "summary": "变量/函数未定义",
        "severity": "error",
        "fix": lambda m: f"变量「{m.group(1)}」未定义。请检查拼写，或在文件顶部使用 default 或 define 声明。"
    },
    {
        "pattern": r"SyntaxError while compiling '([^']+)'",
        "summary": "语法错误",
        "severity": "error",
        "fix": lambda m: f"文件 {m.group(1)} 存在语法错误。检查括号、缩进、引号是否匹配。"
    },
    {
        "pattern": r"Exception: (.*?)'([^']+)'.*?not found",
        "summary": "资源文件缺失",
        "severity": "error",
        "fix": lambda m: f"资源「{m.group(2)}」未找到。检查文件名和路径是否正确，以及文件是否在 game/ 目录下。"
    },
    {
        "pattern": r"IOError:.*?Couldn't find file '([^']+)'",
        "summary": "文件找不到",
        "severity": "error",
        "fix": lambda m: f"文件「{m.group(1)}」不存在。确认文件已放入 game/ 目录且文件名大小写正确。"
    },
    {
        "pattern": r"IndexError: list index out of range",
        "summary": "列表索引越界",
        "severity": "error",
        "fix": "尝试访问不存在的列表元素。检查列表长度，确保索引 < len(list)。"
    },
    {
        "pattern": r"AttributeError: '(\w+)' object has no attribute '(\w+)'",
        "summary": "对象属性不存在",
        "severity": "error",
        "fix": lambda m: f"对象 {m.group(1)} 没有属性 {m.group(2)}。检查拼写或确认该对象已正确初始化。"
    },
    {
        "pattern": r"TypeError: '(\w+)' object is not callable",
        "summary": "对象不可调用",
        "severity": "error",
        "fix": lambda m: f"{m.group(1)} 不是函数/类，不能像函数一样调用。检查是否漏了 = 或变量名冲突。"
    },
    {
        "pattern": r"KeyError: '([^']+)'",
        "summary": "字典键不存在",
        "severity": "error",
        "fix": lambda m: f"字典中找不到键「{m.group(1)}」。使用 .get() 方法或先用 in 检查。"
    },
    {
        "pattern": r"Style.*?could not be found",
        "summary": "样式未定义",
        "severity": "warning",
        "fix": "screen 引用了未定义的 style。检查 style 名称是否拼写正确。"
    },
    {
        "pattern": r"Screen '([^']+)'.*?not found",
        "summary": "Screen 不存在",
        "severity": "error",
        "fix": lambda m: f"screen {m.group(1)} 未定义。检查 screen 名称拼写或是否在正确的 .rpy 文件中。"
    },
    {
        "pattern": r"could not find label '([^']+)'",
        "summary": "Label 不存在",
        "severity": "error",
        "fix": lambda m: f"label {m.group(1)} 不存在。检查 jump/call 的目标名称是否存在。"
    },
    {
        "pattern": r"Variable '([^']+)'.*?not defined",
        "summary": "变量未定义",
        "severity": "warning",
        "fix": lambda m: f"变量 {m.group(1)} 在使用前未定义。用 default 提前声明，或检查拼写。"
    },
    {
        "pattern": r"Image '([^']+)'.*?not defined",
        "summary": "图片未定义",
        "severity": "warning",
        "fix": lambda m: f"图片 {m.group(1)} 在使用前未通过 image 语句定义。"
    },
    {
        "pattern": r"RuntimeError: maximum recursion depth exceeded",
        "summary": "递归调用过深",
        "severity": "error",
        "fix": "可能是 call 循环调用（A→B→A）。检查 label 间是否有循环跳转。"
    },
    {
        "pattern": r"renpy.display.error:",
        "summary": "界面渲染错误",
        "severity": "error",
        "fix": "Screen 渲染时出错。检查 screen 定义中的语法和引用的变量。"
    },
    {
        "pattern": r"While running game code:",
        "summary": "运行时异常",
        "severity": "info",
        "fix": "请在错误信息中找到「File \"game/...\"」行，定位具体文件和行号。"
    },
    {
        "pattern": r"File \"(game/[^\"]+)\", line (\d+)",
        "summary": "文件/行号定位",
        "severity": "info",
        "fix": lambda m: f"错误位置：{m.group(1)} 第 {m.group(2)} 行。"
    },
    {
        "pattern": r"Lint.*?warning",
        "summary": "Lint 检查警告",
        "severity": "warning",
        "fix": "Lint 发现的警告不会阻止游戏运行，但建议修复以保持代码质量。"
    },
    # 中文字体相关
    {
        "pattern": r"Font.*?not found",
        "summary": "字体文件缺失",
        "severity": "error",
        "fix": "指定的字体文件未找到。检查 fonts/ 目录或 gui.text_font 配置。"
    },
    {
        "pattern": r"Could not find font",
        "summary": "字体加载失败",
        "severity": "error",
        "fix": "字体文件不存在。将字体放入 game/ 目录并在 options.rpy 中配置 gui.font。"
    },
]


def diagnose(text: str) -> list:
    """
    解析错误文本，返回诊断结果列表。
    每条结果: {line, type, summary, severity, fix}
    """
    results = []
    lines = text.split("\n")

    # 匹配每一行
    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped:
            continue

        for rule in DIAG_RULES:
            m = re.search(rule["pattern"], stripped, re.IGNORECASE)
            if m:
                fix = rule["fix"](m) if callable(rule["fix"]) else rule["fix"]
                results.append({
                    "line": lineno,
                    "type": rule["summary"],
                    "summary": stripped[:120],
                    "severity": rule["severity"],
                    "fix": fix,
                })
                break  # 一行只匹配一条规则

    return results


def diagnose_from_file(path: str) -> list:
    """从文件读取并诊断。"""
    if not os.path.isfile(path):
        return [{
            "line": 0,
            "type": "文件不存在",
            "summary": f"无法读取: {path}",
            "severity": "error",
            "fix": "确认文件路径正确。"
        }]

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    return diagnose(text)


def format_report(results: list, verbose: bool = False) -> str:
    """格式化诊断报告。"""
    if not results:
        return "✅ 未检测到已知错误模式。"

    severity_icons = {
        "error": "❌",
        "warning": "⚠️",
        "info": "ℹ️",
    }

    errors = [r for r in results if r["severity"] == "error"]
    warnings = [r for r in results if r["severity"] == "warning"]
    infos = [r for r in results if r["severity"] == "info"]

    lines = []
    if errors:
        lines.append(f"❌ 错误 ({len(errors)} 处):")
        for r in errors:
            lines.append(f"  [{r['line']}] {r['type']}")
            lines.append(f"       {r['summary'][:80]}")
            lines.append(f"       💡 {r['fix']}")
        lines.append("")

    if warnings:
        lines.append(f"⚠️ 警告 ({len(warnings)} 处):")
        for r in warnings:
            lines.append(f"  [{r['line']}] {r['type']}")
            if verbose:
                lines.append(f"       {r['summary'][:80]}")
                lines.append(f"       💡 {r['fix']}")
        lines.append("")

    if infos:
        lines.append(f"ℹ️ 信息 ({len(infos)} 处):")
        for r in infos:
            lines.append(f"  [{r['line']}] {r['type']}")

    return "\n".join(lines)


# ── 项目级诊断 ────────────────────────────────────────

def check_project(project_dir: str) -> list:
    """检测项目常见问题。"""
    game_dir = os.path.join(project_dir, "game")
    issues = []

    if not os.path.isdir(game_dir):
        issues.append({
            "type": "game 目录缺失",
            "severity": "error",
            "fix": "在项目根目录下创建 game/ 文件夹。"
        })
        return issues

    # 必要文件检查
    required = ["options.rpy", "screens.rpy", "gui.rpy", "script.rpy"]
    for f in required:
        path = os.path.join(game_dir, f)
        if not os.path.isfile(path):
            issues.append({
                "type": f"缺少 {f}",
                "severity": "warning",
                "fix": f"创建 game/{f}。可用 scaffold.py 生成。"
            })

    # 检查是否有角色定义
    has_character = False
    for root, _, names in os.walk(game_dir):
        for name in names:
            if name.endswith(".rpy"):
                with open(os.path.join(root, name), "r", encoding="utf-8",
                          errors="replace") as f:
                    content = f.read()
                    if "Character(" in content:
                        has_character = True
                        break
        if has_character:
            break

    if not has_character:
        issues.append({
            "type": "未定义角色",
            "severity": "info",
            "fix": "使用 define e = Character(\"艾琳\") 在 game/characters.rpy 中定义角色。"
        })

    # options.rpy 检查
    options_path = os.path.join(game_dir, "options.rpy")
    if os.path.isfile(options_path):
        with open(options_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
            if "config.name" not in content:
                issues.append({
                    "type": "options.rpy 缺少 config.name",
                    "severity": "warning",
                    "fix": "添加 define config.name = \"游戏名称\""
                })

    return issues


# ── CLI ─────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Ren'Py 错误诊断")
    parser.add_argument("input", nargs="?", help="错误日志文件或项目目录")
    parser.add_argument("--mode", choices=["log", "project"], default=None,
                        help="诊断模式 (自动检测)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="详细输出")

    args = parser.parse_args()

    if not args.input:
        parser.print_help()
        return

    if args.mode == "project" or (args.mode is None and os.path.isdir(args.input)):
        # 项目诊断
        issues = check_project(args.input)
        errors = [i for i in issues if i["severity"] == "error"]
        warnings = [i for i in issues if i["severity"] == "warning"]
        infos = [i for i in issues if i["severity"] == "info"]

        if not issues:
            print("✅ 项目结构检查通过。")
        else:
            print(f"📋 项目诊断报告 ({os.path.basename(args.input)})")
            for r in errors:
                print(f"  ❌ {r['type']} → {r['fix']}")
            for r in warnings:
                print(f"  ⚠️ {r['type']} → {r['fix']}")
            for r in infos:
                print(f"  ℹ️ {r['type']} → {r['fix']}")
    else:
        # 日志诊断
        results = diagnose_from_file(args.input)
        print(format_report(results, verbose=args.verbose))


if __name__ == "__main__":
    main()
