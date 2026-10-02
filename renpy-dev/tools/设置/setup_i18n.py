#!/usr/bin/env python3
"""
Ren'Py 多语言设置脚本
=====================
为 Ren'Py 游戏项目配置多语言支持，包括:
  1. 生成语言选择界面 (screens/language_selector.rpy)
  2. 生成多语言字体配置 (screens/fonts_common.rpy)
  3. 创建翻译目录结构 (tl/<语言>/)
  4. 生成配置说明文档 (I18N_SETUP.md)

使用方法:
  python tools/setup_i18n.py <项目路径> --languages schinese japanese
  python tools/setup_i18n.py tmp/finaltest --languages schinese japanese tchinese
  python tools/setup_i18n.py tmp/finaltest --languages schinese --key s

参数:
  项目路径          包含 game/ 目录的项目根路径
  --languages       要配置的语言代码列表 (如 schinese japanese tchinese korean)
  --default-lang    默认语言代码 (默认 english, 即不翻译)
  --key             打开语言选择菜单的快捷键 (默认 s)
  --force           覆盖已存在的配置文件
"""

import argparse
import os
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
    "italian": "Italiano",
    "portuguese": "Português",
}

# CJK 语言列表 (需要使用 CJK 字体)
CJK_LANGUAGES = {"schinese", "tchinese", "japanese", "korean"}

LANGUAGE_SELECTOR_TEMPLATE = """\
## 语言选择界面
## 由 setup_i18n.py 自动生成

screen language_selector():
    modal True
    frame:
        xalign 0.5
        yalign 0.5
        xpadding 40
        ypadding 30
        vbox:
            spacing 10
            xalign 0.5
            text _("选择语言 / Select Language"):
                size 28
                bold True
                xalign 0.5
            null height 10
{language_buttons}
            null height 10
            textbutton _("关闭"):
                action Hide("language_selector")
                xalign 0.5

## 按键绑定：按 {key} 键打开语言选择
define config.keymap["open_language_selector"] = ["{key}"]

## 注册快捷键处理
init python:
    def _check_lang_key():
        if renpy.get_screen("language_selector") is None:
            renpy.show_screen("language_selector")
    config.underlay.append(
        renpy.Keymap(open_language_selector=_check_lang_key)
    )
"""

FONTS_COMMON_TEMPLATE = """\
## 多语言字体配置 (CJK 优先)
## 由 setup_i18n.py 自动生成
##
## 字体文件需放在 game/fonts/ 目录下。
## 可使用 add_fonts.py 脚本自动添加字体文件。

## --- 中文字体 (CJK) ---
define font_cjk_regular = "fonts/NotoSansSC-Regular.otf"
define font_cjk_bold = "fonts/NotoSansSC-Bold.otf"

## --- 英文/默认字体 ---
define font_default_regular = "DejaVuSans.ttf"
define font_default_bold = "DejaVuSans.ttf"

## 根据当前语言切换字体
init python:
    def get_font_regular():
        lang = _preferences.language
        if lang in ('schinese', 'tchinese', 'japanese', 'korean'):
            return font_cjk_regular
        return font_default_regular

    def get_font_bold():
        lang = _preferences.language
        if lang in ('schinese', 'tchinese', 'japanese', 'korean'):
            return font_cjk_bold
        return font_default_bold

## 应用到 GUI 默认字体
define gui.text_font = get_font_regular()
define gui.name_text_font = get_font_bold()
define gui.interface_text_font = get_font_regular()
define gui.button_text_font = get_font_regular()
define gui.choice_button_text_font = get_font_regular()
"""

SETUP_DOC_TEMPLATE = """\
# 多语言项目配置

## 项目路径
{project_path}

## 已配置语言
{languages}
默认语言: {default_lang}

## 目录结构
```
game/
├── tl/
{tl_tree}├── screens/
│   ├── language_selector.rpy  # 语言选择界面
│   └── fonts_common.rpy       # 字体配置文件
└── options.rpy
```

## 工作流程

### 1. 生成翻译模板
在 Ren'Py 启动器中:
1. 打开项目
2. 点击 "Generate Translations"
3. 选择要生成的语言
4. 启动器会自动在 `tl/<语言>/` 下生成翻译骨架

或使用命令行:
```
renpy.sh <项目路径> translate <语言>
```

### 2. 填写翻译
编辑 `tl/<语言>/script/*.rpy` 中的翻译文本。

### 3. 测试
按 {key} 键调出语言选择菜单，切换语言测试显示效果。

### 4. 字体
需要在 `game/fonts/` 目录下放入对应字体文件。
推荐免费中文字体:
- Noto Sans SC (Google Fonts)
- Source Han Sans (思源黑体)
- Noto Serif SC (思源宋体)

可使用 add_fonts.py 脚本自动添加字体:
```
python tools/add_fonts.py <项目路径> <字体文件路径>
```

## 切换默认语言
使用 switch_default_language.py 脚本:
```
python tools/switch_default_language.py <项目路径> <语言代码>
```

## 注意事项
- 翻译文件必须保持和原文相同的标签和结构
- 切换语言后需要重新加载场景以刷新文本
- CJK 语言 (中日韩) 需要专用字体，否则会显示为方块
"""


def get_language_display(lang_code):
    """获取语言的显示名称"""
    return LANGUAGE_NAMES.get(lang_code, lang_code)


def generate_language_buttons(languages):
    """生成语言选择按钮代码"""
    buttons = []
    for lang in languages:
        display = get_language_display(lang)
        buttons.append(
            f'            textbutton "{display}":\n'
            f'                action Language("{lang}")\n'
            f"                xalign 0.5"
        )
    return "\n".join(buttons)


def ensure_dir(path):
    """确保目录存在"""
    os.makedirs(path, exist_ok=True)


def write_file(path, content, force=False):
    """写入文件，已存在时根据 force 决定是否覆盖"""
    if os.path.exists(path) and not force:
        print(f"  跳过 (已存在): {path}")
        return False
    if os.path.exists(path):
        create_bak(path)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  已创建: {path}")
    return True


def setup_i18n(project_path, languages, default_lang="english", key="s", force=False):
    """为主项目配置多语言支持"""
    project_path = os.path.abspath(project_path)
    game_dir = os.path.join(project_path, "game")

    if not os.path.isdir(game_dir):
        print(f"错误: 找不到 game 目录: {game_dir}")
        sys.exit(1)

    print("=" * 70)
    print("  Ren'Py 多语言设置")
    print("=" * 70)
    print(f"  项目路径: {project_path}")
    print(f"  配置语言: {', '.join(languages)}")
    print(f"  默认语言: {default_lang}")
    print(f"  快捷键:   {key}")
    print()

    # ── 1. 创建翻译目录结构 ──
    print("[1/4] 创建翻译目录结构...")
    tl_dir = os.path.join(game_dir, "tl")
    ensure_dir(tl_dir)
    for lang in languages:
        lang_dir = os.path.join(tl_dir, lang)
        ensure_dir(lang_dir)
        # 创建常见的子目录
        ensure_dir(os.path.join(lang_dir, "script"))
        ensure_dir(os.path.join(lang_dir, "screens"))
        print(f"  已创建: tl/{lang}/")

    # ── 2. 生成语言选择界面 ──
    print("\n[2/4] 生成语言选择界面...")
    screens_dir = os.path.join(game_dir, "screens")
    ensure_dir(screens_dir)

    buttons = generate_language_buttons(languages)
    selector_content = LANGUAGE_SELECTOR_TEMPLATE.format(
        language_buttons=buttons,
        key=key,
    )
    write_file(
        os.path.join(screens_dir, "language_selector.rpy"), selector_content, force
    )

    # ── 3. 生成字体配置 ──
    print("\n[3/4] 生成字体配置...")
    write_file(
        os.path.join(screens_dir, "fonts_common.rpy"), FONTS_COMMON_TEMPLATE, force
    )

    # 创建 fonts 目录
    fonts_dir = os.path.join(game_dir, "fonts")
    ensure_dir(fonts_dir)
    print(f"  已创建: game/fonts/")

    # ── 4. 生成配置文档 ──
    print("\n[4/4] 生成配置文档...")
    tl_tree = ""
    for lang in languages:
        tl_tree += f"│   ├── {lang}/       # {get_language_display(lang)} 翻译文件\n"
        tl_tree += f"│   │   ├── script/\n"
        tl_tree += f"│   │   └── screens/\n"

    doc_content = SETUP_DOC_TEMPLATE.format(
        project_path=project_path,
        languages=", ".join(languages),
        default_lang=default_lang,
        tl_tree=tl_tree,
        key=key,
    )
    write_file(os.path.join(project_path, "I18N_SETUP.md"), doc_content, force)

    # ── 完成 ──
    print("\n" + "=" * 70)
    print("  多语言设置完成!")
    print("=" * 70)
    print(f"\n下一步:")
    print(f"  1. 在 Ren'Py 启动器中生成翻译模板 (Generate Translations)")
    print(f"  2. 使用 add_fonts.py 添加 CJK 字体到 game/fonts/")
    print(f"  3. 按 {key} 键测试语言切换")
    if default_lang != "english":
        print(
            f"  4. 默认语言已设为 {default_lang} (使用 switch_default_language.py 修改)"
        )


def main():
    parser = argparse.ArgumentParser(
        description="为 Ren'Py 游戏配置多语言支持",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例:\n"
        "  python tools/setup_i18n.py tmp/finaltest --languages schinese japanese\n"
        "  python tools/setup_i18n.py tmp/finaltest --languages schinese --key p --force",
    )
    parser.add_argument("project", help="项目根路径 (包含 game/ 目录)")
    parser.add_argument(
        "--languages",
        "-l",
        nargs="+",
        required=True,
        help="要配置的语言代码列表 (如 schinese japanese)",
    )
    parser.add_argument(
        "--default-lang", default="english", help="默认语言代码 (默认: english)"
    )
    parser.add_argument("--key", default="s", help="打开语言选择菜单的快捷键 (默认: s)")
    parser.add_argument(
        "--force", "-f", action="store_true", help="覆盖已存在的配置文件"
    )
    args = parser.parse_args()

    if not os.path.isdir(args.project):
        print(f"错误: 项目路径不存在: {args.project}")
        sys.exit(1)

    if args.default_lang not in args.languages and args.default_lang != "english":
        print(f"警告: 默认语言 {args.default_lang} 不在配置语言列表中")

    setup_i18n(args.project, args.languages, args.default_lang, args.key, args.force)


if __name__ == "__main__":
    main()
