#!/usr/bin/env python3
"""
Ren'Py 默认语言切换脚本
=======================
切换 Ren'Py 游戏项目的默认语言。

工作原理:
  在 game/screens/language_selector.rpy 中写入一个 init python 块，
  使用 persistent 标志确保默认语言只在首次启动时生效，
  不会覆盖用户后续手动选择的语言。

使用方法:
  # 设置默认语言为简体中文
  python tools/switch_default_language.py MyGame-1.0-pc schinese

  # 设置默认语言为英文 (即不翻译)
  python tools/switch_default_language.py MyGame-1.0-pc english

  # 查看当前配置
  python tools/switch_default_language.py MyGame-1.0-pc --show

  # 列出可用语言
  python tools/switch_default_language.py MyGame-1.0-pc --list

参数:
  项目路径          包含 game/ 目录的项目根路径
  语言代码          要设为默认的语言代码 (如 schinese / english / japanese)
"""

import argparse
import os
import re
import sys

# ── 引入共享公共 ──
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "公共")
)
from backup import create_bak

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── 语言代码到显示名称的映射 ──
LANGUAGE_NAMES = {
    "english": "English",
    "schinese": "简体中文",
    "tchinese": "繁體中文",
    "japanese": "日本語",
    "korean": "한국어",
    "russian": "Русский",
    "spanish": "Español",
    "french": "Français",
    "german": "Deutsch",
}

# 默认语言 init 块的标记 (用于定位和替换)
DEFAULT_LANG_MARKER = "## 默认语言设置 (由 switch_default_language.py 管理)"

DEFAULT_LANG_BLOCK_TEMPLATE = """\
{marker}
default persistent._i18n_lang_initialized = False

init python:
    if not persistent._i18n_lang_initialized:
        _preferences.language = "{language}"
        persistent._i18n_lang_initialized = True
"""


def get_language_display(lang_code):
    """获取语言的显示名称"""
    return LANGUAGE_NAMES.get(lang_code, lang_code)


def find_language_selector(project_path):
    """查找 language_selector.rpy 文件位置"""
    game_dir = os.path.join(project_path, "game")

    # 优先查找 screens/language_selector.rpy
    candidates = [
        os.path.join(game_dir, "screens", "language_selector.rpy"),
        os.path.join(game_dir, "language_selector.rpy"),
    ]

    for path in candidates:
        if os.path.exists(path):
            return path

    # 搜索其他位置
    for root, _, files in os.walk(game_dir):
        for fn in files:
            if fn == "language_selector.rpy":
                return os.path.join(root, fn)

    return None


def list_available_languages(project_path):
    """列出项目中所有可用的语言 (基于 tl/ 目录)"""
    tl_dir = os.path.join(project_path, "game", "tl")
    if not os.path.isdir(tl_dir):
        return []

    languages = []
    for entry in sorted(os.listdir(tl_dir)):
        full_path = os.path.join(tl_dir, entry)
        if os.path.isdir(full_path) and not entry.startswith("."):
            languages.append(entry)
    return languages


def parse_current_default(selector_path):
    """从 language_selector.rpy 解析当前设置的默认语言"""
    if not selector_path or not os.path.exists(selector_path):
        return None

    with open(selector_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 匹配 _preferences.language = "xxx"
    match = re.search(
        r'_preferences\.language\s*=\s*"([^"]*)"',
        content,
    )
    if match:
        return match.group(1)

    # 兼容旧版 define gui.language = "xxx" (不推荐)
    match = re.search(r'define\s+gui\.language\s*=\s*"([^"]*)"', content)
    if match:
        return match.group(1)

    return None


def remove_old_default_blocks(content):
    """移除旧的默认语言设置块

    兼容:
      - 新版 (带 marker 的 init python 块)
      - 旧版 define gui.language = "xxx"
    """
    # 移除新版默认语言块 (从 marker 到下一个空行后的 init 块结束)
    # 匹配: ## 默认语言设置... \n default persistent._i18n_lang_initialized... \n\n init python: ... \n
    pattern = re.compile(
        r"## 默认语言设置.*?\n"
        r"default persistent\._i18n_lang_initialized[^\n]*\n"
        r"\s*\n"
        r"init python:\n"
        r"\s*if not persistent\._i18n_lang_initialized[^\n]*\n"
        r'\s*_preferences\.language\s*=\s*"[^"]*"\n'
        r"\s*persistent\._i18n_lang_initialized\s*=\s*True\n",
        re.DOTALL,
    )
    content = pattern.sub("", content)

    # 移除旧版 define gui.language = "xxx"
    content = re.sub(
        r'##\s*默认语言[^\n]*\ndefine\s+gui\.language\s*=\s*"[^"]*"\n',
        "",
        content,
    )

    # 移除可能残留的 marker 行
    content = re.sub(
        r"^" + re.escape(DEFAULT_LANG_MARKER) + r"\s*\n",
        "",
        content,
        flags=re.MULTILINE,
    )

    return content


def switch_default_language(project_path, language):
    """切换项目的默认语言"""
    project_path = os.path.abspath(project_path)
    game_dir = os.path.join(project_path, "game")

    if not os.path.isdir(game_dir):
        print(f"错误: 找不到 game 目录: {game_dir}")
        sys.exit(1)

    print("=" * 70)
    print("  Ren'Py 默认语言切换")
    print("=" * 70)
    print(f"  项目路径: {project_path}")
    print(f"  目标语言: {language} ({get_language_display(language)})")
    print()

    # ── 查找语言选择文件 ──
    selector_path = find_language_selector(project_path)
    if selector_path:
        print(f"  语言配置文件: {os.path.relpath(selector_path, project_path)}")
    else:
        print("  警告: 未找到 language_selector.rpy")
        print("  提示: 请先运行 setup_i18n.py 创建多语言配置")
        # 直接在 screens/ 下创建
        screens_dir = os.path.join(game_dir, "screens")
        os.makedirs(screens_dir, exist_ok=True)
        selector_path = os.path.join(screens_dir, "language_selector.rpy")
        with open(selector_path, "w", encoding="utf-8") as f:
            f.write(DEFAULT_LANG_MARKER + "\n")
        print(f"  已创建: {os.path.relpath(selector_path, project_path)}")

    # ── 验证语言是否可用 ──
    available = list_available_languages(project_path)
    if available:
        print(f"  可用语言: {', '.join(available)}")
        if language != "english" and language not in available:
            print(f"\n  警告: 语言 {language} 不在 tl/ 目录中")
            print(f"  该语言可能尚未生成翻译文件")
    else:
        print("  提示: 未找到 tl/ 目录，无法验证语言可用性")

    # ── 读取当前配置 ──
    current = parse_current_default(selector_path)
    if current:
        print(f"  当前默认语言: {current} ({get_language_display(current)})")
    else:
        print(f"  当前默认语言: 未设置 (使用引擎默认)")

    if current == language:
        print(f"\n  默认语言已经是 {language}，无需修改")
        return

    # ── 更新配置文件 ──
    print(f"\n[更新] 设置默认语言为 {language}...")

    with open(selector_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 移除旧的默认语言块
    content = remove_old_default_blocks(content)

    # 添加新的默认语言块
    new_block = DEFAULT_LANG_BLOCK_TEMPLATE.format(
        marker=DEFAULT_LANG_MARKER,
        language=language,
    )

    # 确保文件以换行结尾
    if content and not content.endswith("\n"):
        content += "\n"

    content = content.rstrip() + "\n\n" + new_block

    create_bak(selector_path)
    with open(selector_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"  已更新: {os.path.relpath(selector_path, project_path)}")

    # ── 完成 ──
    print("\n" + "=" * 70)
    print("  默认语言切换完成!")
    print("=" * 70)
    print(f"\n  默认语言: {language} ({get_language_display(language)})")
    print(f"\n说明:")
    print(f"  - 默认语言仅在玩家首次启动游戏时生效")
    print(f"  - 玩家手动选择语言后，其选择会被记住")
    print(f"  - english 表示不应用翻译 (使用游戏脚本原文)")


def show_current(project_path):
    """显示当前默认语言配置"""
    project_path = os.path.abspath(project_path)

    print("=" * 70)
    print("  当前多语言配置")
    print("=" * 70)
    print(f"  项目路径: {project_path}")
    print()

    selector_path = find_language_selector(project_path)
    if selector_path:
        print(f"  配置文件: {os.path.relpath(selector_path, project_path)}")
        current = parse_current_default(selector_path)
        if current:
            print(f"  当前默认语言: {current} ({get_language_display(current)})")
        else:
            print(f"  当前默认语言: 未设置 (使用引擎默认)")
    else:
        print("  未找到 language_selector.rpy")

    print()
    available = list_available_languages(project_path)
    if available:
        print(f"  可用语言 ({len(available)}):")
        for lang in available:
            display = get_language_display(lang)
            marker = " (默认)" if parse_current_default(selector_path) == lang else ""
            print(f"    - {lang}: {display}{marker}")
    else:
        print("  未找到翻译目录 (game/tl/)")


def main():
    parser = argparse.ArgumentParser(
        description="切换 Ren'Py 游戏的默认语言",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例:\n"
        "  python tools/switch_default_language.py MyGame-1.0-pc schinese\n"
        "  python tools/switch_default_language.py MyGame-1.0-pc english\n"
        "  python tools/switch_default_language.py MyGame-1.0-pc --show\n"
        "  python tools/switch_default_language.py MyGame-1.0-pc --list",
    )
    parser.add_argument("project", help="项目根路径 (包含 game/ 目录)")
    parser.add_argument("language", nargs="?", help="要设为默认的语言代码")
    parser.add_argument("--show", action="store_true", help="显示当前默认语言配置")
    parser.add_argument("--list", action="store_true", help="列出项目中所有可用的语言")
    args = parser.parse_args()

    if not os.path.isdir(args.project):
        print(f"错误: 项目路径不存在: {args.project}")
        sys.exit(1)

    if args.show or args.list:
        show_current(args.project)
        return

    if not args.language:
        print("错误: 请指定语言代码，或使用 --show/--list 查看信息")
        parser.print_help()
        sys.exit(1)

    switch_default_language(args.project, args.language)


if __name__ == "__main__":
    main()
