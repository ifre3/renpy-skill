#!/usr/bin/env python3
"""
Ren'Py 多语言项目基础设施搭建工具
不涉及翻译内容本身，只负责项目结构、配置、字体等工程相关工作
"""
import os
import sys
import argparse
import json
from pathlib import Path

# 常用语言的 Ren'Py locale code 映射
LANG_MAP = {
    "zh": "schinese",
    "zh_tw": "tchinese",
    "en": "english",
    "ja": "japanese",
    "ko": "korean",
    "fr": "french",
    "de": "german",
    "es": "spanish",
    "ru": "russian",
    "th": "thai",
    "vi": "vietnamese",
}

FONT_STACK_CJK = [
    ("Noto Sans SC", "fonts/NotoSansSC-Regular.otf"),
    ("Noto Sans SC Bold", "fonts/NotoSansSC-Bold.otf"),
    ("Source Han Sans", "fonts/SourceHanSansSC-Regular.otf"),
]

FONT_STACK_EN = [
    ("Source Sans Pro", "fonts/SourceSansPro-Regular.ttf"),
    ("Source Sans Pro Bold", "fonts/SourceSansPro-Bold.ttf"),
]


def setup_i18n(project_path, languages, default_lang="english", font_mode="cjk"):
    """为 Ren'Py 项目添加多语言基础设施"""
    project_path = Path(project_path)
    game_dir = project_path / "game"
    if not game_dir.exists():
        print(f"❌ 未找到项目目录: {game_dir}")
        print("   请确认路径指向 Ren'Py 项目根目录（含 game/ 文件夹）")
        return

    # 1. 生成 tl/ 目录结构
    tl_root = game_dir / "tl"
    for lang in languages:
        (tl_root / lang).mkdir(parents=True, exist_ok=True)
        # 每个语言目录下创建 screens 和 script 子目录
        (tl_root / lang / "screens").mkdir(exist_ok=True)
        (tl_root / lang / "script").mkdir(exist_ok=True)

    # 2. 生成或更新 options.rpy 中的多语言配置
    options_file = game_dir / "options.rpy"
    if not options_file.exists():
        # 创建基础 options.rpy
        options_file.write_text(
            f"""## 项目设置
define config.name = _("项目名称")
define config.version = "1.0.0"
define config.save_directory = "_saves"
define config.window_title = _("游戏标题")

## 窗口分辨率
define config.screen_width = 1280
define config.screen_height = 720
"""
        )
        print(f"📄 创建了 options.rpy（基础模板）")

    # 3. 生成语言选择界面 screens
    lang_screen = game_dir / "screens" / "language_selector.rpy"
    screen_content = _gen_language_screen(languages, default_lang)
    lang_screen.parent.mkdir(exist_ok=True)
    lang_screen.write_text(screen_content, encoding="utf-8")
    print(f"📄 生成语言选择界面: language_selector.rpy")

    # 4. 生成字体配置文件
    font_cfg = game_dir / "screens" / "fonts_common.rpy"
    font_content = _gen_font_config(font_mode, languages, default_lang)
    font_cfg.parent.mkdir(exist_ok=True)
    font_cfg.write_text(font_content, encoding="utf-8")
    print(f"📄 生成字体配置文件: fonts_common.rpy")

    # 5. 生成多语言 README
    readme = project_path / "I18N_SETUP.md"
    readme.write_text(
        _gen_i18n_readme(project_path, languages, default_lang), encoding="utf-8"
    )
    print(f"📄 生成多语言说明文档: I18N_SETUP.md")

    # 输出摘要
    print(f"\n✅ 多语言基础设施搭建完成")
    print(f"   项目路径: {project_path}")
    print(f"   语言: {', '.join(languages)}")
    print(f"   默认语言: {default_lang}")
    print(f"\n💡 下一步操作建议:")
    print(f"   1. 运行 Ren'Py 启动器 → Generate Translations → 生成翻译文件骨架")
    print(f"   2. 编辑 tl/<语言>/ 目录下的 rpy 文件，填入翻译内容")
    print(f"   3. 在游戏中按 S 键可调出语言选择菜单")


def _gen_language_screen(languages, default_lang):
    """生成语言选择界面（vbox 缩进正确，Ren'Py lint 通过）"""
    buttons_lines = []
    for lang in languages:
        display_name = {
            "schinese": "简体中文", "tchinese": "繁体中文",
            "english": "English", "japanese": "日本語",
            "korean": "한국어", "french": "Français",
            "german": "Deutsch", "spanish": "Español",
            "russian": "Русский", "thai": "ไทย",
            "vietnamese": "Tiếng Việt",
        }.get(lang, lang)
        buttons_lines.append(
            f'            textbutton "{display_name}":')
        buttons_lines.append(
            f'                action Language("{lang}")')
        buttons_lines.append(
            f'                xalign 0.5')

    buttons_block = "\n".join(buttons_lines)

    return (
        f"""## 语言选择界面
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
"""
        + buttons_block
        + """
            null height 10
            textbutton _("关闭"):
                action Hide("language_selector")
                xalign 0.5

## 按键绑定：按 S 键打开语言选择
define config.keymap["open_language_selector"] = ["s"]

## 注册快捷键处理
init python:
    def _check_lang_key():
        if renpy.get_screen("language_selector") is None:
            renpy.show_screen("language_selector")
    config.underlay.append(
        renpy.Keymap(open_language_selector=_check_lang_key)
    )

## 默认语言
define gui.language = \"""" + default_lang + """\"
"""
    )


def _gen_font_config(font_mode, languages, default_lang):
    """生成字体配置文件"""
    if font_mode == "cjk":
        lines = [
            "## 多语言字体配置（CJK 优先）",
            "## 由 setup_i18n.py 自动生成",
            "",
            "## --- 中文字体 ---",
            f"define font_chinese_regular = \"{FONT_STACK_CJK[0][1]}\"",
            f"define font_chinese_bold = \"{FONT_STACK_CJK[1][1]}\"",
            "",
            "## --- 英文/默认字体 ---",
            f"define font_english_regular = \"{FONT_STACK_EN[0][1]}\"",
            f"define font_english_bold = \"{FONT_STACK_EN[1][1]}\"",
            "",
            "## 根据当前语言切换字体",
            "init python:",
            "    def get_font_regular():",
            "        lang = _preferences.language",
            "        if lang in ('schinese', 'tchinese', 'japanese', 'korean'):",
            "            return font_chinese_regular",
            "        return font_english_regular",
            "",
            "    def get_font_bold():",
            "        lang = _preferences.language",
            "        if lang in ('schinese', 'tchinese', 'japanese', 'korean'):",
            "            return font_chinese_bold",
            "        return font_english_bold",
            "",
            "## 应用到 GUI 默认字体",
            "define gui.text_font = get_font_regular()",
            "define gui.name_text_font = get_font_bold()",
            "define gui.interface_text_font = get_font_regular()",
            "define gui.button_text_font = get_font_regular()",
            "define gui.choice_button_text_font = get_font_regular()",
        ]
    else:
        lines = [
            "## 字体配置（单语言模式）",
            f"define font_regular = \"{FONT_STACK_EN[0][1]}\"",
            f"define font_bold = \"{FONT_STACK_EN[1][1]}\"",
            "",
            "define gui.text_font = font_regular",
            "define gui.name_text_font = font_bold",
            "define gui.interface_text_font = font_regular",
            "define gui.button_text_font = font_regular",
            "define gui.choice_button_text_font = font_regular",
        ]

    return "\n".join(lines)


def _gen_i18n_readme(project_path, languages, default_lang):
    return f"""# 多语言项目配置

## 项目路径
{project_path}

## 已配置语言
{', '.join(languages)}
默认语言: {default_lang}

## 目录结构
```
game/
├── tl/
│   ├── {languages[0]}/       # {languages[0]} 翻译文件
│   │   ├── script/
│   │   └── screens/
│   ├── {languages[1] if len(languages) > 1 else '...'}/
│   └── ...
├── screens/
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

### 2. 填写翻译
编辑 `tl/<语言>/script/*.rpy` 中的翻译文本。

### 3. 测试
按 S 键调出语言选择菜单，切换语言测试显示效果。

### 4. 字体
需要在 `game/fonts/` 目录下放入对应字体文件。
推荐免费中文字体:
- Noto Sans SC (Google Fonts)
- Source Han Sans (思源黑体)
- Noto Serif SC (思源宋体)

## 注意事项
- 翻译文件必须保持和原文相同的标签和结构
- 切换语言后需要重新加载场景以刷新文本
"""


def list_languages():
    """列出可用的语言代号"""
    print("可用的语言代号:")
    for code, name in sorted(LANG_MAP.items(), key=lambda x: x[1]):
        print(f"  {code:10s} → {name}")
    print("\n英语为 Ren'Py 默认语言（无需翻译目录）")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Ren'Py 多语言项目基础设施搭建"
    )
    parser.add_argument(
        "--path", help="Ren'Py 项目根目录（含 game/ 文件夹的路径）"
    )
    parser.add_argument(
        "--lang", nargs="+",
        help=(
            "目标语言代号，支持多个。"
            "常用值: zh(schinese) zh_tw(tchinese) en ja ko fr de es ru"
        )
    )
    parser.add_argument(
        "--default", default="english",
        help="默认语言（english / schinese 等），默认 english"
    )
    parser.add_argument(
        "--font-mode", choices=["cjk", "simple"], default="cjk",
        help="字体配置模式: cjk(中日韩多字体回退), simple(单一字体)"
    )
    parser.add_argument(
        "--list-lang", action="store_true",
        help="列出所有可用的语言代号"
    )

    args = parser.parse_args()

    if args.list_lang:
        list_languages()
        sys.exit(0)

    if not args.path:
        print("❌ 必须指定 --path")
        parser.print_help()
        sys.exit(1)
    if not args.lang:
        print("❌ 必须指定 --lang")
        parser.print_help()
        sys.exit(1)

    # 将简写转换为 Ren'Py locale 名称
    resolved = []
    for lang in args.lang:
        resolved.append(LANG_MAP.get(lang, lang))
    setup_i18n(args.path, resolved, args.default, args.font_mode)