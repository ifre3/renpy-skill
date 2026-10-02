#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查 Ren'Py 项目中缺少翻译的 UI 文本，包括:
  - textbutton/text/label 等屏幕语句中未用 _() 包裹的字符串
  - Character("[variable]") 变量引用缺少 !t 翻译标志（真正 bug）
  - _() 包裹的字符串中 [变量] 插值缺少 !t 翻译标志（真正 bug）
  - renpy.input() / renpy.notify() 提示文本
  - heading/settings_item/tab_button 等自定义屏幕调用文本
  - menu 选择项文本（仅交叉引用翻译状态）
  - show text 语句
  - define/default 中错误使用 _() 的误判提醒

翻译知识（Ren'Py 官方文档）:
  - _()  : 标记字符串可翻译，翻译在【显示时】才生效，init 阶段返回原字符串
  - __() : 立即返回翻译后的字符串（适用于 init 阶段需要翻译值的场景）
  - ___(): 立即翻译并执行插值
  - Character("Hina")      : 直接字符串，字符串翻译系统自动匹配，无需 _()
  - Character("[var]")      : 变量引用不会触发翻译，需改为 [var!t]
  - Character(_("[var]"))   : _() 在 init 时返回原字符串，包裹无效
  - define x = _("Ryou")   : init 时 _() 返回 "Ryou"，翻译不生效
  - _("好感度 [points]")   : [points] 插值替换后不翻译，需改为 [points!t]

检测排除模式:
  - 已用 _()/__()/___() 包裹的字符串不再报"缺少 _()"
  - 支持下划线与括号间有空格的写法: _ ("text")

用法:
  python tools/check-button-missing-translation.py <游戏目录>
  python tools/check-button-missing-translation.py <游戏目录> -l schinese -o report.txt

示例:
  python tools/check-button-missing-translation.py MyGame-1.0-pc
  python check-button-missing-translation.py /path/to/MyGame-1.0-pc
"""

import argparse
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 共享常量/函数统一定义在 common.py（SCREEN_CALL_KW 按游戏补充时只改那一处）
from common import (
    TRANS_FUNC_PAT,
    RENPY_FUNC_KW,
    SCREEN_CALL_KW,
    SKIP_PREFIX,
    SKIP_SUFFIX,
    SKIP_WORDS,
    TEXT_KW,
    green,
    load_trans,
    print_items,
    red,
    scan_files,
    should_skip,
    yellow,
)


# ── 检测函数 ──────────────────────────────────────────────────────────


def check_ui(lines, rel):
    """检测 screen 语言中 textbutton/text/label/button 后未用 _() 包裹的字符串"""
    results = []
    in_say = False
    kw_pat = "|".join(TEXT_KW)
    # 匹配关键字 + 空格 + (非 _()/__()/___() 包裹)的字符串
    pat = re.compile(
        r"\b(" + kw_pat + r")\s+(?!" + TRANS_FUNC_PAT + r")(\"[^\"]+\"|'[^']+')"
    )
    # text_属性名列表（这些是属性不是显示文本）
    text_prop_re = re.compile(
        r"\btext_(font|size|color|align|xalign|yalign|outlines|"
        r"idle_color|hover_color|selected_color|insensitive_color|"
        r"idle|hover|selected|insensitive|bold|italic|underline|strikethrough|"
        r"kerning|line_spacing|line_leading|justify|"
        r"hover_bold|selected_bold|hover_italic|selected_italic)\b"
    )

    for no, line in enumerate(lines, 1):
        s = line.strip()
        if s.startswith("#"):
            continue
        # 跳过 say 屏幕
        if s.startswith("screen say("):
            in_say = True
        elif in_say and re.match(r"^screen\s", s):
            in_say = False
        if in_say:
            continue
        # 跳过 style 声明
        if s.startswith("style "):
            continue
        # 跳过 text_属性行
        if text_prop_re.search(s):
            if re.match(r"\s*text_", s):
                continue

        for m in pat.finditer(s):
            raw = m.group(2)
            text = raw[1:-1]
            if not should_skip(text):
                results.append({"line": no, "text": text, "file": rel})
    return results


def check_showtext(lines, rel):
    """检测 show text "..." 未用 _() 包裹"""
    results = []
    pat = re.compile(
        r"show\s+text\s+(?!" + TRANS_FUNC_PAT + r')("([^"]+)"|\'([^\']+)\')'
    )
    for no, line in enumerate(lines, 1):
        s = line.strip()
        if s.startswith("#"):
            continue
        m = pat.search(s)
        if m:
            text = m.group(2) or m.group(3)
            if not should_skip(text):
                results.append({"line": no, "text": text, "file": rel})
    return results


def check_char(lines, rel):
    """检测 Character("名字") 中缺少翻译的名字
    注意: Character("Hina") 不需要 _() 包裹，字符串翻译系统自动匹配。
    此检测仅用于交叉引用翻译状态。"""
    results = []
    for no, line in enumerate(lines, 1):
        # 位置参数: Character("名字"
        for m in re.finditer(r'Character\(\s*"([^"]+)"', line):
            n = m.group(1)
            if not n.startswith("["):
                results.append({"line": no, "text": n, "file": rel})
        # 关键字参数: Character(name="名字"
        for m in re.finditer(r'Character\(\s*.*?name\s*=\s*"([^"]+)"', line):
            n = m.group(1)
            if not n.startswith("["):
                results.append({"line": no, "text": n, "file": rel})
        # 单引号版本
        for m in re.finditer(r"Character\(\s*'([^']+)'", line):
            n = m.group(1)
            if not n.startswith("["):
                results.append({"line": no, "text": n, "file": rel})
    return results


def check_char_var_no_t(lines, rel):
    """检测 Character("[variable]") 中变量引用缺少 !t 翻译标志
    这是真正的翻译 bug: 变量引用不会触发字符串翻译，必须用 [var!t] 才能翻译。
    修复: Character("[var]") → Character("[var!t]")
    """
    results = []
    # 匹配 Character("[variable]") 但不匹配 Character("[variable!t]")
    # 也匹配 Character(_("[variable]")) / Character(__("[variable]")) — _()/__() 在 init 时无效
    for no, line in enumerate(lines, 1):
        s = line.strip()
        if s.startswith("#"):
            continue
        # Character("[var]") 或 Character(_("[var]")) / Character(__("[var]"))
        for m in re.finditer(r"Character\((?:_{1,3}\s*\()?\"\[([^\]!]+)\]\"", line):
            var_name = m.group(1)
            # 排除已有 !t 的情况
            if f"[{var_name}!t]" not in line:
                results.append(
                    {
                        "line": no,
                        "text": f"[{var_name}]",
                        "file": rel,
                        "note": "缺 !t — 改为 [{0}!t]".format(var_name),
                    }
                )
        # 单引号版本
        for m in re.finditer(r"Character\((?:_{1,3}\s*\()?\'\[([^\]!]+)\]\'", line):
            var_name = m.group(1)
            if f"[{var_name}!t]" not in line:
                results.append(
                    {
                        "line": no,
                        "text": f"[{var_name}]",
                        "file": rel,
                        "note": "缺 !t — 改为 [{0}!t]".format(var_name),
                    }
                )
    return results


def check_interpolation_no_t(lines, rel):
    """检测 UI 文本中 [变量] 插值缺少 !t 翻译标志
    Ren'Py 中 _() 标记整个字符串可翻译，但 [变量] 插值替换后不会被翻译。
    如果变量值本身也是可翻译文本，必须使用 [var!t] 才能在显示时翻译。
    例如: _("好感度已增加到 [points]") → 若 points 对应的值需要翻译，应改为 [points!t]

    检测范围: textbutton/text/label/show text/renpy.notify/renpy.input/自定义屏幕调用
    """
    results = []
    # 匹配 _()/__()/___() 包裹的字符串内容
    trans_func_str = re.compile(r'_{1,3}\s*\(\s*("([^"]+)"|\'([^\']+)\')\s*\)')
    # 匹配字符串中的 [变量] 插值（不含 !t / !ti 等翻译标志）
    # [var] 匹配, [var!t] / [var!ti] / [var!q] 不匹配
    interp_no_t = re.compile(r"\[([^\]!]+)\]")
    # 需要跳过的纯数值变量名（如 [0] [1] 等 Python 格式化占位符，不需要翻译）
    numeric_var = re.compile(r"^\d+$")

    for no, line in enumerate(lines, 1):
        s = line.strip()
        if s.startswith("#"):
            continue
        # 只检测 _()/__()/___() 包裹的字符串中的插值
        for tm in trans_func_str.finditer(s):
            content = tm.group(2) or tm.group(3)
            if not content:
                continue
            # 检查字符串中是否包含 [变量] 但不含 [变量!t] 等
            for im in interp_no_t.finditer(content):
                var_name = im.group(1).strip()
                # 跳过纯数值变量
                if numeric_var.match(var_name):
                    continue
                # 跳过纯属性访问但无文字的变量（如 store.xxx）
                # 只跳过看起来像纯属性/数值的不需翻译的变量
                # 常见不需翻译的变量: 纯数字、带 . 的属性路径
                if "." in var_name:
                    continue
                # 检查同一行中是否已有 [var!t] 版本
                if f"[{var_name}!t]" in content or f"[{var_name}!ti]" in content:
                    continue
                results.append(
                    {
                        "line": no,
                        "text": f"[{var_name}]",
                        "file": rel,
                        "note": f"在翻译字符串 _() 内 [{{var_name}}] 缺 !t — 若值需翻译改为 [{{var_name}}!t]".format(
                            var_name=var_name
                        ),
                        "context": content,
                    }
                )
    return results


def check_define_default_misuse(lines, rel):
    """检测 define/default 中错误使用 _() 的情况
    _() 在 init 阶段返回原字符串，翻译不生效。
    如需 init 阶段就获取翻译值，应使用 __()（双下划线）。
    """
    results = []
    pat = re.compile(r'^(?:define|default)\s+\w+\s*=\s*_\(("([^"]+)"|\'([^\']+)\')\)')
    for no, line in enumerate(lines, 1):
        s = line.strip()
        if s.startswith("#"):
            continue
        m = pat.match(s)
        if m:
            text = m.group(2) or m.group(3)
            results.append(
                {
                    "line": no,
                    "text": text,
                    "file": rel,
                    "note": "_() 在 init 时返回原值，改用 __() 或 [var!t]",
                }
            )
    return results


def check_renpy_func(lines, rel):
    """检测 renpy.input("提示") / renpy.notify("文本") 中未用 _() 包裹的字符串"""
    results = []
    kw_pat = "|".join(re.escape(k) for k in RENPY_FUNC_KW)
    pat = re.compile(
        r"\b(" + kw_pat + r")\s*\(\s*(?!" + TRANS_FUNC_PAT + r")(\"[^\"]+\"|'[^']+')"
    )
    for no, line in enumerate(lines, 1):
        s = line.strip()
        if s.startswith("#"):
            continue
        for m in pat.finditer(s):
            raw = m.group(2)
            text = raw[1:-1]
            if not should_skip(text):
                results.append(
                    {"line": no, "text": text, "file": rel, "func": m.group(1)}
                )
    return results


def check_screen_calls(lines, rel):
    """检测 use heading("...") / use settings_item("...") 等自定义屏幕调用中的文本"""
    results = []
    kw_pat = "|".join(re.escape(k) for k in SCREEN_CALL_KW)
    pat = re.compile(
        r"(?:use\s+)?\b("
        + kw_pat
        + r")\s*\(\s*(?!"
        + TRANS_FUNC_PAT
        + r")(\"[^\"]+\"|'[^']+')"
    )
    for no, line in enumerate(lines, 1):
        s = line.strip()
        if s.startswith("#"):
            continue
        for m in pat.finditer(s):
            raw = m.group(2)
            text = raw[1:-1]
            if not should_skip(text):
                results.append(
                    {"line": no, "text": text, "file": rel, "screen": m.group(1)}
                )
    return results


def check_menu_choices(lines, rel):
    """检测 menu 选项中的纯文本选项
    Ren'Py 对话翻译系统会自动提取 menu 选项，不需要 _() 包裹，
    此检测仅用于交叉引用翻译状态。"""
    results = []
    in_menu = False
    for no, line in enumerate(lines, 1):
        s = line.strip()
        if s.startswith("#"):
            continue
        if re.match(r"menu\s*(\([^)]*\))?\s*:", s):
            in_menu = True
            continue
        if in_menu:
            if line and not line[0].isspace() and s:
                in_menu = False
                continue
            m = re.match(
                r"(?!"
                + TRANS_FUNC_PAT
                + r')("([^"]+)"|\'([^\']+)\')\s*(if\s+.+?)?\s*:',
                s,
            )
            if m:
                text = m.group(2) or m.group(3)
                if not should_skip(text):
                    results.append({"line": no, "text": text, "file": rel})
    return results


def check_fstring_text(lines, rel):
    """检测 text f"..." 模式 — f-string 中混合了可翻译文本"""
    results = []
    pat = re.compile(r'\btext\s+f("([^"]+)"|\'([^\']+)\')')
    for no, line in enumerate(lines, 1):
        s = line.strip()
        if s.startswith("#"):
            continue
        if s.startswith("style "):
            continue
        for m in pat.finditer(s):
            raw = m.group(1)
            text = raw[1:-1]
            results.append(
                {"line": no, "text": "f" + raw, "file": rel, "note": "f-string"}
            )
    return results


# ── 输出 ──────────────────────────────────────────────────────────────
# print_items 也来自 common.py（带 BUG/WARN/INFO 严重级着色）


def main():
    ap = argparse.ArgumentParser(description="检测 Ren'Py 缺少翻译的 UI 文本")
    ap.add_argument("project", help="游戏目录（含 game/）")
    ap.add_argument("-l", "--language", default="schinese")
    ap.add_argument("-o", "--output", help="输出报告文件")
    args = ap.parse_args()

    project = os.path.abspath(args.project)
    if not os.path.isdir(project):
        print(f"目录不存在: {project}")
        sys.exit(1)

    game = os.path.join(project, "game")
    tl_path = (
        os.path.join(game, "tl") if os.path.isdir(game) else os.path.join(project, "tl")
    )

    trans = load_trans(tl_path, args.language)
    print(f"翻译条目: {len(trans)}")

    rpy_files = scan_files(project)
    print(f"扫描文件: {len(rpy_files)} 个\n")

    # ── BUG 级别：必须修复 ──
    var_not_results = []  # Character("[var]") 缺 !t
    misuse_results = []  # define/default 中 _() 无效
    interp_no_t_results = []  # _() 内 [变量] 缺 !t

    # ── WARN 级别：需要 _() 包裹 ──
    ui_results = []
    st_results = []
    func_results = []
    screen_results = []
    fstr_results = []

    # ── INFO 级别：仅参考，自动翻译 ──
    char_results = []
    menu_results = []

    for fpath in rpy_files:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                lines = f.read().splitlines(keepends=False)
        except Exception as e:
            print(f"  跳过 {fpath}: {e}", file=sys.stderr)
            continue
        rel = os.path.relpath(fpath, os.path.dirname(game))

        # BUG 级别
        var_not_results.extend(check_char_var_no_t(lines, rel))
        misuse_results.extend(check_define_default_misuse(lines, rel))
        interp_no_t_results.extend(check_interpolation_no_t(lines, rel))

        # WARN 级别
        ui_results.extend(check_ui(lines, rel))
        st_results.extend(check_showtext(lines, rel))
        func_results.extend(check_renpy_func(lines, rel))
        screen_results.extend(check_screen_calls(lines, rel))
        fstr_results.extend(check_fstring_text(lines, rel))

        # INFO 级别
        char_results.extend(check_char(lines, rel))
        menu_results.extend(check_menu_choices(lines, rel))

    # ── 输出：按严重程度排序 ──
    print("\n" + "=" * 60)
    print(red("  [ BUG ] 必须修复 — 翻译不会生效"))
    print("=" * 60)
    print_items(
        var_not_results, trans, "Character('[var]') 缺 !t 翻译标志", severity="bug"
    )
    print_items(
        misuse_results,
        trans,
        "define/default 中 _() 无效（init时不翻译）",
        severity="bug",
    )
    print_items(
        interp_no_t_results,
        trans,
        "_() 内 [变量] 缺 !t（插值替换后不翻译）",
        severity="bug",
    )

    print("\n" + "=" * 60)
    print(yellow("  [ WARN ] 需要加 _() 包裹"))
    print("=" * 60)
    print_items(
        ui_results, trans, "UI 显示文本 (textbutton/text/label)", severity="warn"
    )
    print_items(st_results, trans, "show text", severity="warn")
    print_items(func_results, trans, "renpy.input/notify 提示文本", severity="warn")
    print_items(
        screen_results,
        trans,
        "自定义屏幕调用文本 (heading/settings_item 等)",
        severity="warn",
    )
    print_items(fstr_results, trans, "text f-string (混合插值与文本)", severity="warn")

    print("\n" + "=" * 60)
    print("  [ INFO ] 仅参考 — 字符串翻译系统自动处理")
    print("=" * 60)
    print_items(
        char_results,
        trans,
        "Character 名字框（无需 _()，字符串翻译自动匹配）",
        severity="info",
    )
    print_items(
        menu_results, trans, "menu 选择项（Ren'Py 自动提取翻译）", severity="info"
    )

    all_results = (
        var_not_results
        + misuse_results
        + interp_no_t_results
        + ui_results
        + st_results
        + func_results
        + screen_results
        + fstr_results
        + char_results
        + menu_results
    )
    total_uncov = sum(1 for i in all_results if i["text"] not in trans)
    total_all = len(all_results)
    bug_count = len(var_not_results) + len(misuse_results) + len(interp_no_t_results)
    warn_count = (
        len(ui_results)
        + len(st_results)
        + len(func_results)
        + len(screen_results)
        + len(fstr_results)
    )
    info_count = len(char_results) + len(menu_results)

    print(f"\n{'=' * 60}")
    print(
        f"总计: {total_all} 条  |  {red(f'BUG {bug_count}')}  |  {yellow(f'WARN {warn_count}')}  |  INFO {info_count}"
    )
    print(f"未翻译: {red(str(total_uncov))} 条")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as fo:
            fo.write(f"Ren'Py 翻译检测报告\n")
            fo.write(f"游戏: {project}\n语言: {args.language}\n\n")

            severity_map = {
                "BUG": [
                    (var_not_results, "Character('[var]') 缺 !t"),
                    (misuse_results, "define/default 中 _() 无效"),
                    (interp_no_t_results, "_() 内 [变量] 缺 !t"),
                ],
                "WARN": [
                    (ui_results, "UI 显示文本"),
                    (st_results, "show text"),
                    (func_results, "renpy.input/notify"),
                    (screen_results, "自定义屏幕调用"),
                    (fstr_results, "text f-string"),
                ],
                "INFO": [
                    (char_results, "Character 名字框"),
                    (menu_results, "menu 选择项"),
                ],
            }
            for sev, sections in severity_map.items():
                fo.write(f"\n{'=' * 40}\n")
                fo.write(f"[ {sev} ]\n")
                fo.write(f"{'=' * 40}\n")
                for items, title in sections:
                    fo.write(f"\n--- {title} ---\n")
                    for i in items:
                        status = "已翻" if i["text"] in trans else "未翻"
                        extra = ""
                        if "func" in i:
                            extra = f" [{i['func']}]"
                        elif "screen" in i:
                            extra = f" [{i['screen']}]"
                        elif "note" in i:
                            extra = f" ({i['note']})"
                        fo.write(
                            f'  {sev}\t{status}\t{i["file"]}:{i["line"]}\t"{i["text"]}"{extra}'
                        )
                        if i["text"] in trans:
                            fo.write(f' -> "{trans[i["text"]]}"')
                        fo.write("\n")
        print(f"\n报告已保存: {args.output}")

    return 1 if bug_count or total_uncov else 0


if __name__ == "__main__":
    sys.exit(main() or 0)
