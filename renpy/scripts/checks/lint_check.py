#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ren'Py 翻译 lint 工具 —— 调用 SDK lint + 翻译专项检查

Phase 1: 调用 renpy SDK 内置 lint（含 --check-unclosed-tags 等选项）
Phase 2: 翻译专项检查（未翻译条目、空翻译）

用法:
  python tools/lint_check.py <游戏目录> --sdk <SDK路径>
  python tools/lint_check.py <游戏目录> --sdk <SDK路径> -l schinese
  python tools/lint_check.py <游戏目录> --skip-sdk-lint  # 只做翻译专项检查

示例:
  python lint_check.py MyGame-1.0-pc --sdk /path/to/renpy-sdk
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile

_TOOLS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _path in (
    os.path.join(_TOOLS_DIR, "shared"),
):
    if _path not in sys.path:
        sys.path.insert(0, _path)

# check_untranslated 已从 translate/ 归位到 checks/（2026-10-06），与本脚本同级
from check_untranslated import has_real_text  # noqa: E402
from rpy_syntax import iter_translation_pairs  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def red(s):
    return f"\033[91m{s}\033[0m" if sys.stdout.isatty() else s


def yellow(s):
    return f"\033[93m{s}\033[0m" if sys.stdout.isatty() else s


def green(s):
    return f"\033[92m{s}\033[0m" if sys.stdout.isatty() else s


def dim(s):
    return f"\033[2m{s}\033[0m" if sys.stdout.isatty() else s


# ─── SDK lint ────────────────────────────────────────────────────

def find_renpy_exe(sdk_path):
    """在 SDK 目录中查找 renpy.exe / renpy.sh"""
    exe = os.path.join(sdk_path, "renpy.exe")
    if os.path.isfile(exe):
        return exe
    sh = os.path.join(sdk_path, "renpy.sh")
    if os.path.isfile(sh):
        return sh
    return None


def check_sdk_version(sdk_path):
    """检查 SDK 主版本，返回 (major_version, version_str)。

    仅支持 Ren'Py 8.x。7.x 及以下会给出明确拒绝提示。
    """
    renpy_exe = find_renpy_exe(sdk_path)
    if not renpy_exe:
        return None, None
    try:
        result = subprocess.run(
            [renpy_exe, "--version"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = (result.stdout + result.stderr).strip()
        # Ren'Py --version 输出首行形如 "Ren'Py 8.1.0" 或 "Ren'Py 7.6.3"
        first_line = output.splitlines()[0] if output else ""
        match = re.search(r"Ren'Py\s+(\d+)\.(\d+)", first_line)
        if match:
            major = int(match.group(1))
            return major, first_line
        # 尝试其他格式
        match = re.search(r"(\d+)\.(\d+)", first_line)
        if match:
            major = int(match.group(1))
            return major, first_line
        return None, first_line
    except Exception:
        return None, None


def run_sdk_lint(project, sdk_path, extra_opts):
    """调用 renpy SDK 内置 lint 命令"""
    renpy_exe = find_renpy_exe(sdk_path)
    if not renpy_exe:
        print(red(f"  ✗ 未找到 renpy 可执行文件: {sdk_path}"))
        return None

    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
    tmp_path = tmp.name
    tmp.close()

    cmd = [renpy_exe, project, "lint", tmp_path, "--check-unclosed-tags"]
    if extra_opts:
        cmd.extend(extra_opts)

    print(dim(f"  运行: {renpy_exe} {project} lint {tmp_path} --check-unclosed-tags"))
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if os.path.isfile(tmp_path):
            with open(tmp_path, "r", encoding="utf-8") as f:
                report = f.read()
            os.unlink(tmp_path)
            return report
        else:
            return result.stdout or ""
    except subprocess.TimeoutExpired:
        if os.path.isfile(tmp_path):
            os.unlink(tmp_path)
        print(red("  ✗ SDK lint 超时 (>300s)"))
        return None
    except Exception as e:
        if os.path.isfile(tmp_path):
            os.unlink(tmp_path)
        print(red(f"  ✗ SDK lint 执行失败: {e}"))
        return None


def parse_sdk_lint_errors(report):
    """从 SDK lint 报告中提取错误行"""
    errors = []
    skip_prefixes = ("Ren'Py", "Statistics", "Lint is not", "The game", "The schinese")
    for line in report.splitlines():
        # 必须匹配 game/路径:数字 格式才算真正的错误行
        m = re.match(r'^(game/[^:]+:\d+)\s+(.+)$', line)
        if m:
            errors.append({"location": m.group(1), "message": m.group(2)})
    return errors


# ─── 翻译专项检查（不用正则做标签检查，标签问题交给SDK lint）──

def game_dir(project):
    """返回项目的 game 目录；也兼容直接传入 game 目录。"""
    candidate = os.path.join(project, "game")
    return candidate if os.path.isdir(candidate) else project


def scan_tl_files(project, lang):
    """扫描 tl/<lang>/ 目录下所有翻译文件"""
    game = game_dir(project)
    tl_dir = os.path.join(game, "tl", lang)
    if not os.path.isdir(tl_dir):
        print(red(f"  ✗ 翻译目录不存在: {tl_dir}"))
        return []

    files = []
    for root, dirs, fnames in os.walk(tl_dir):
        dirs[:] = [d for d in dirs if not d.startswith(".") and not d.startswith("_")]
        for f in fnames:
            if f.endswith(".rpy"):
                files.append(os.path.join(root, f))
    return sorted(files)


def check_untranslated(filepath, lang):
    """检查翻译条目中是否残留大量英文（可能未翻译）"""
    issues = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return []

    for pair in iter_translation_pairs(lines):
        text = pair.translated
        if not text or not text.strip():
            continue
        # 计算中文字符 vs 英文字母比例
        cjk_count = len(re.findall(r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]', text))
        alpha_count = len(re.findall(r'[a-zA-Z]', text))
        total = cjk_count + alpha_count
        if total == 0:
            continue
        # 英文占比>70%且英文字母>10个 → 疑似未翻译
        if alpha_count > 10 and alpha_count / total > 0.7:
            issues.append({
                "type": "untranslated",
                "file": filepath,
                "line": pair.translated_line or pair.original_line,
                "text": text[:80],
                "desc": "疑似未翻译（英文占比 " + str(alpha_count) + "/" + str(total) + "=" + "{:.0%}".format(alpha_count/total) + ")"
            })

    return issues


def check_empty_translations(filepath):
    """检查空的翻译条目"""
    issues = []

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return []

    for pair in iter_translation_pairs(lines):
        if pair.translated != "" or not has_real_text(pair.original):
            continue
        issues.append({
            "type": "empty_translation",
            "file": filepath,
            "line": pair.translated_line or pair.original_line,
            "text": pair.original[:80],
            "desc": "空翻译条目"
        })

    return issues


def run_translation_checks(project, lang):
    """运行翻译专项检查（只做未翻译和空翻译，标签问题由SDK lint负责）"""
    all_issues = []
    game_root = game_dir(project)
    tl_files = scan_tl_files(project, lang)
    print(f"\n扫描翻译文件: {len(tl_files)} 个\n")

    for fpath in tl_files:
        rel = os.path.relpath(fpath, game_root)
        file_issues = []

        # 1. 未翻译检查
        untranslated = check_untranslated(fpath, lang)
        file_issues.extend(untranslated)

        # 2. 空翻译检查
        empty = check_empty_translations(fpath)
        file_issues.extend(empty)

        all_issues.extend(file_issues)

        if file_issues:
            types = {}
            for iss in file_issues:
                t = iss["type"]
                types[t] = types.get(t, 0) + 1
            summary = ", ".join("{}: {}".format(t, c) for t, c in types.items())
            print(yellow("  {}: {} 个问题 ({})".format(rel, len(file_issues), summary)))

    return all_issues


# ─── 主入口 ──────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="Ren'Py 翻译 lint 工具 —— SDK lint + 翻译专项检查",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python lint_check.py MyGame-1.0-pc --sdk /path/to/renpy-sdk
  python lint_check.py MyGame-1.0-pc -l schinese --skip-sdk-lint
        """
    )
    ap.add_argument("project", help="游戏目录（含 game/ 子目录）")
    ap.add_argument("--sdk", default="", help="Ren'Py SDK 路径")
    ap.add_argument("-l", "--language", default="schinese", help="翻译语言代码")
    ap.add_argument("--skip-sdk-lint", action="store_true", help="跳过 SDK lint")
    ap.add_argument("--sdk-lint-opts", nargs="*", default=["--no-orphan-tl", "--reserved-parameters"],
                    help="SDK lint 额外选项")
    ap.add_argument("-o", "--output", help="输出报告文件路径")
    ap.add_argument("--max-untranslated", type=int, default=30,
                    help="未翻译条目最大显示数量（默认30）")
    args = ap.parse_args()

    project = os.path.abspath(args.project)
    game_root = game_dir(project)
    if not os.path.isdir(project):
        print(red("目录不存在: {}".format(project)))
        sys.exit(1)

    # 自动推断 SDK 路径
    sdk_path = args.sdk
    if not sdk_path:
        parent = os.path.dirname(project)
        # 项目可能直接嵌在 SDK 根目录下（父目录本身就是 SDK）
        if os.path.isfile(os.path.join(parent, "renpy.exe")) or \
           os.path.isfile(os.path.join(parent, "renpy.sh")):
            sdk_path = parent
        else:
            for d in os.listdir(parent):
                if d.startswith("renpy-") and "sdk" in d:
                    candidate = os.path.join(parent, d)
                    if os.path.isfile(os.path.join(candidate, "renpy.exe")) or \
                       os.path.isfile(os.path.join(candidate, "renpy.sh")):
                        sdk_path = candidate
                        break

    print("=" * 60)
    print("Ren'Py 翻译 lint 工具")
    print("项目: {}".format(project))
    print("语言: {}".format(args.language))
    if sdk_path:
        print("SDK:  {}".format(sdk_path))
    print("=" * 60)

    # ── Phase 1: SDK lint ──
    sdk_errors = []
    if not args.skip_sdk_lint:
        if sdk_path:
            # 版本边界检查：仅支持 Ren'Py 8.x
            major_ver, ver_str = check_sdk_version(sdk_path)
            if major_ver is not None and major_ver < 8:
                print(red("\n  ✗ 不支持的 Ren'Py 版本: {}".format(ver_str or sdk_path)))
                print(red("  本工具仅支持 Ren'Py 8.x，不支持 7.x 及更早版本。"))
                print(yellow("  请升级到 Ren'Py 8.x 后再使用 SDK lint。"))
                print(yellow("  或使用 --skip-sdk-lint 跳过 SDK lint，只做翻译专项检查。\n"))
            else:
                print("\n── Phase 1: SDK lint ──")
                if ver_str:
                    print(dim("  SDK 版本: {}".format(ver_str)))
                report = run_sdk_lint(project, sdk_path, args.sdk_lint_opts)
                if report:
                    sdk_errors = parse_sdk_lint_errors(report)
                    if sdk_errors:
                        print(red("\n  SDK lint 发现 {} 个错误:\n".format(len(sdk_errors))))
                        for err in sdk_errors:
                            print(red("    {}: {}".format(err["location"], err["message"])))
                    else:
                        print(green("  ✓ SDK lint 通过，无错误"))
                else:
                    print(yellow("  ⚠ SDK lint 无法运行，跳过"))
        else:
            print(yellow("\n  ⚠ 未指定 SDK 路径且无法自动推断，跳过 SDK lint"))
            print("    提示: 使用 --sdk 参数指定 SDK 路径")

    # ── Phase 2: 翻译专项检查 ──
    print("\n── Phase 2: 翻译专项检查 ──")
    all_issues = run_translation_checks(project, args.language)

    # 按类型分组汇总
    by_type = {}
    for iss in all_issues:
        t = iss["type"]
        by_type.setdefault(t, []).append(iss)

    # 输出详细报告
    if all_issues:
        print("\n" + "─" * 60)
        print(red("翻译专项检查发现 {} 个问题:\n".format(len(all_issues))))

        for typ, issues in by_type.items():
            label = {
                "untranslated": "疑似未翻译条目",
                "empty_translation": "空翻译条目",
            }.get(typ, typ)

            print(yellow("  [{}] {} 个".format(label, len(issues))))

            show_count = len(issues) if typ != "untranslated" else min(len(issues), args.max_untranslated)

            for iss in issues[:show_count]:
                rel = os.path.relpath(iss["file"], game_root)
                print("    {}:{} — {}".format(rel, iss["line"], iss["desc"]))
                if iss.get("text") and typ != "untranslated":
                    text_preview = iss["text"][:100]
                    print('      "{}"'.format(text_preview))

            if typ == "untranslated" and len(issues) > args.max_untranslated:
                remaining = len(issues) - args.max_untranslated
                print(dim("    ... 还有 {} 条未显示".format(remaining)))

        print()

    # ── 汇总 ──
    print("=" * 60)
    total = len(sdk_errors) + len(all_issues)
    if total == 0:
        print(green("✓ 所有检查通过，零问题！"))
    else:
        print(yellow("总计: {} 个问题".format(total)))
        if sdk_errors:
            print("  SDK lint: {} 个".format(len(sdk_errors)))
        for typ, issues in by_type.items():
            label = {
                "untranslated": "未翻译",
                "empty_translation": "空翻译",
            }.get(typ, typ)
            print("  {}: {} 个".format(label, len(issues)))

    # 保存报告
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fo:
            fo.write("Ren'Py 翻译 lint 报告\n")
            fo.write("项目: {}\n语言: {}\n\n".format(project, args.language))

            if sdk_errors:
                fo.write("── SDK lint 错误 ──\n")
                for err in sdk_errors:
                    fo.write("{}: {}\n".format(err["location"], err["message"]))
                fo.write("\n")

            if all_issues:
                fo.write("── 翻译专项检查 ──\n")
                for iss in all_issues:
                    rel = os.path.relpath(iss["file"], game_root)
                    fo.write("{}:{} [{}] {}\n".format(rel, iss["line"], iss["type"], iss["desc"]))
                fo.write("\n")

            if total == 0:
                fo.write("✓ 所有检查通过\n")
            else:
                fo.write("总计: {} 个问题\n".format(total))

        print("报告已保存: {}".format(args.output))

    sys.exit(1 if total > 0 else 0)


if __name__ == "__main__":
    main()
