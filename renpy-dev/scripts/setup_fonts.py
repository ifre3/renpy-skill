#!/usr/bin/env python3
"""
Ren'Py 字体适配配置工具
自动生成多语言字体配置，检测字体文件，生成字体回退方案
"""

import os
import argparse
from pathlib import Path

CJK_FONTS = {
    "noto_sans_sc": {
        "name": "Noto Sans SC (思源黑体)",
        "desc": "Google 出品的中文无衬线字体，最推荐",
        "regular": "NotoSansSC-Regular.otf",
        "bold": "NotoSansSC-Bold.otf",
        "url": "https://fonts.google.com/specimen/Noto+Sans+SC",
    },
    "noto_serif_sc": {
        "name": "Noto Serif SC (思源宋体)",
        "desc": "Google 出品的中文衬线字体",
        "regular": "NotoSerifSC-Regular.otf",
        "bold": "NotoSerifSC-Bold.otf",
        "url": "https://fonts.google.com/specimen/Noto+Serif+SC",
    },
    "source_han_sans": {
        "name": "Source Han Sans (思源黑体)",
        "desc": "Adobe 出品，Noto Sans SC 的源头",
        "regular": "SourceHanSansSC-Regular.otf",
        "bold": "SourceHanSansSC-Bold.otf",
        "url": "https://github.com/adobe-fonts/source-han-sans",
    },
    "source_han_serif": {
        "name": "Source Han Serif (思源宋体)",
        "desc": "Adobe 出品的中文衬线字体",
        "regular": "SourceHanSerifSC-Regular.otf",
        "bold": "SourceHanSerifSC-Bold.otf",
        "url": "https://github.com/adobe-fonts/source-han-serif",
    },
    "lxgw_wenkai": {
        "name": "霞鹜文楷 (LXGW WenKai)",
        "desc": "开源楷体，适合古风/文艺题材",
        "regular": "LXGWWenKai-Regular.ttf",
        "bold": "LXGWWenKai-Bold.ttf",
        "url": "https://github.com/lxgw/LxgwWenKai",
    },
    "zcool_kuaile": {
        "name": "站酷快乐体",
        "desc": "手写风格，适合轻松幽默题材",
        "regular": "ZCOOL_Kuaile.ttf",
        "bold": "ZCOOL_Kuaile.ttf",
        "url": "https://github.com/googlefonts/zcool-kuaile",
    },
}

EN_FONTS = {
    "source_sans_pro": {
        "name": "Source Sans Pro",
        "desc": "Adobe 出品，清晰易读的无衬线字体",
        "regular": "SourceSansPro-Regular.ttf",
        "bold": "SourceSansPro-Bold.ttf",
        "url": "https://fonts.google.com/specimen/Source+Sans+Pro",
    },
    "source_serif_pro": {
        "name": "Source Serif Pro",
        "desc": "Adobe 出品的衬线字体",
        "regular": "SourceSerifPro-Regular.ttf",
        "bold": "SourceSerifPro-Bold.ttf",
        "url": "https://fonts.google.com/specimen/Source+Serif+Pro",
    },
    "open_sans": {
        "name": "Open Sans",
        "desc": "Google 出品，友好且可读性高",
        "regular": "OpenSans-Regular.ttf",
        "bold": "OpenSans-Bold.ttf",
        "url": "https://fonts.google.com/specimen/Open+Sans",
    },
    "lato": {
        "name": "Lato",
        "desc": "Łukasz Dziedzic 设计，现代感强",
        "regular": "Lato-Regular.ttf",
        "bold": "Lato-Bold.ttf",
        "url": "https://fonts.google.com/specimen/Lato",
    },
}


def detect_fonts(project_path):
    """检测项目 game/fonts 目录下已有的字体文件"""
    fonts_dir = Path(project_path) / "game" / "fonts"
    if not fonts_dir.exists():
        print("ℹ️  未找到 game/fonts/ 目录，正在创建...")
        fonts_dir.mkdir(parents=True, exist_ok=True)
        return []

    found = []
    for f in sorted(fonts_dir.iterdir()):
        if f.suffix.lower() in (".ttf", ".otf", ".ttc"):
            found.append(f.name)
    return found


def gen_font_fallback(project_path, output_file=None):
    """生成字体回退链配置（解决 CJK 字符缺字问题）"""
    project_path = Path(project_path)
    fonts_dir = project_path / "game" / "fonts"
    available = detect_fonts(project_path)

    if not available:
        print("⚠️  game/fonts/ 目录为空，生成的配置会引用不存在的字体。")
        print("   建议先下载字体放入 game/fonts/ 中。")

    fallback_config = """## 字体回退链配置（防止缺字导致方块）
## 由 setup_fonts.py 自动生成

init python:
    ## 自定义字体回退注册
    ## Ren'Py 默认不支持 CSS 式 font-family 回退，
    ## 这里通过语言切换 + 硬编码方式实现

    def register_fallback_fonts():
        \"\"\"
        注册字体回退信息。
        当主字体缺少某个字符时，Ren'Py 会依次检查回退字体。
        \"\"\"
        # 这里仅为文档标注，具体切换通过 gui.font 赋值完成
        pass

    register_fallback_fonts()

## ---- 按语言配置字体 ----
"""
    # 为每个已检测到的 CJK 字体生成 lang-specific 配置
    cjk_entries = [f for f in available if any(kw in f.lower() for kw in ["cjk", "sc", "tc", "han", "wenkai", "kuaile", "noto"])]
    en_entries = [f for f in available if f not in cjk_entries]

    fallback_config += f"\n## 当前可用字体: {len(available)} 个\n"
    fallback_config += f"## CJK 字体: {len(cjk_entries)} 个\n"
    fallback_config += f"## 其他字体: {len(en_entries)} 个\n\n"

    if cjk_entries:
        fallback_config += "## CJK 语言字体配置\n"
        for f in cjk_entries:
            name = Path(f).stem
            fallback_config += f"define font_cjk_regular = \"fonts/{f}\"\n"
            break  # 只用第一个作为 regular
        # 如果有第二个，当 bold
        if len(cjk_entries) > 1:
            fallback_config += f"define font_cjk_bold = \"fonts/{cjk_entries[1]}\"\n"
        else:
            fallback_config += "define font_cjk_bold = font_cjk_regular\n"

    fallback_config += """
## 语言切换时自动切换字体
init python:
    def _switch_font_for_lang():
        lang = _preferences.language if _preferences.language else "english"
        if lang in ("schinese", "tchinese", "japanese", "korean"):
            gui.text_font = font_cjk_regular
            gui.name_text_font = font_cjk_bold
        else:
            gui.text_font = font_en_regular
            gui.name_text_font = font_en_bold
        gui.interface_text_font = gui.text_font
        gui.button_text_font = gui.text_font
        gui.choice_button_text_font = gui.text_font

    config.start_interact_callbacks.append(_switch_font_for_lang)
"""

    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(exist_ok=True)
        output_path.write_text(fallback_config, encoding="utf-8")
        print(f"✅ 字体回退配置已生成: {output_path}")
    else:
        print(fallback_config)


def gen_font_config(project_path, cjk_font, en_font, output_file=None):
    """生成完整的字体配置"""
    project_path = Path(project_path)
    available = detect_fonts(project_path)

    config_lines = [
        "## 字体配置文件",
        "## 由 setup_fonts.py 自动生成",
        "",
        "## --- 中文字体 ---",
    ]

    # 检查字体是否存在于 fonts 目录
    fonts_dir = project_path / "game" / "fonts"
    cjk_ok = (fonts_dir / cjk_font).exists() if cjk_font else False
    en_ok = (fonts_dir / en_font).exists() if en_font else False

    if not cjk_ok and cjk_font:
        config_lines.append(f"## ⚠️  字体未找到: {cjk_font}")
    config_lines.append(f"define font_cjk_regular = \"fonts/{cjk_font}\"" if cjk_font else "## define font_cjk_regular = \"fonts/你的字体.otf\"")

    if not en_ok and en_font:
        config_lines.append(f"## ⚠️  字体未找到: {en_font}")
    config_lines.append(f"define font_en_regular = \"fonts/{en_font}\"" if en_font else "## define font_en_regular = \"fonts/你的字体.ttf\"")

    bold_cjk_font = cjk_font.replace("-Regular", "-Bold").replace("Regular", "Bold") if cjk_font else None
    bold_en_font = en_font.replace("-Regular", "-Bold").replace("Regular", "Bold") if en_font else None

    config_lines.extend([
        "",
        "## --- 加粗变体 ---",
        f"define font_cjk_bold = \"fonts/{bold_cjk_font}\"" if bold_cjk_font else "## define font_cjk_bold = \"fonts/你的粗体.otf\"",
        f"define font_en_bold = \"fonts/{bold_en_font}\"" if bold_en_font else "## define font_en_bold = \"fonts/你的粗体.ttf\"",
        "",
        "## --- 默认字体映射 ---",
        "define gui.text_font = font_en_regular",
        "define gui.name_text_font = font_en_bold",
        "define gui.interface_text_font = font_en_regular",
        "define gui.button_text_font = font_en_regular",
        "define gui.choice_button_text_font = font_en_regular",
    ])

    result = "\n".join(config_lines)
    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(exist_ok=True)
        output_path.write_text(result, encoding="utf-8")
        print(f"✅ 字体配置已生成: {output_path}")
        if not cjk_ok and cjk_font:
            print(f"⚠️  中文字体 {cjk_font} 未在 game/fonts/ 中找到")
        if not en_ok and en_font:
            print(f"⚠️  英文字体 {en_font} 未在 game/fonts/ 中找到")
    else:
        print(result)

    print(f"\n📦 当前 game/fonts/ 包含 {len(available)} 个字体:")
    for f in available:
        print(f"   · {f}")


def list_fonts():
    """列出推荐字体"""
    print("=" * 60)
    print("推荐中文字体（CJK）")
    print("=" * 60)
    for key, info in CJK_FONTS.items():
        print(f"\n  {info['name']}")
        print(f"    {info['desc']}")
        print(f"    文件: {info['regular']}, {info['bold']}")
        print(f"    下载: {info['url']}")

    print("\n" + "=" * 60)
    print("推荐英文字体")
    print("=" * 60)
    for key, info in EN_FONTS.items():
        print(f"\n  {info['name']}")
        print(f"    {info['desc']}")
        print(f"    文件: {info['regular']}, {info['bold']}")
        print(f"    下载: {info['url']}")

    print("\n" + "=" * 60)
    print("字体存放位置: <项目目录>/game/fonts/")
    print("支持格式: .ttf / .otf / .ttc")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Ren'Py 字体适配配置工具"
    )
    sub = parser.add_subparsers(dest="command")

    # detect
    p_detect = sub.add_parser("detect", help="检测项目已有字体")
    p_detect.add_argument("--path", required=True, help="Ren'Py 项目根目录")

    # config
    p_config = sub.add_parser("config", help="生成字体配置文件")
    p_config.add_argument("--path", required=True, help="Ren'Py 项目根目录")
    p_config.add_argument("--cjk", default="NotoSansSC-Regular.otf", help="中文字体文件名")
    p_config.add_argument("--en", default="SourceSansPro-Regular.ttf", help="英文字体文件名")
    p_config.add_argument("--output", default="game/screens/fonts_config.rpy", help="输出路径（相对于项目根目录）")

    # fallback
    p_fallback = sub.add_parser("fallback", help="生成字体回退链配置")
    p_fallback.add_argument("--path", required=True, help="Ren'Py 项目根目录")
    p_fallback.add_argument("--output", default="game/screens/fonts_fallback.rpy", help="输出路径（相对于项目根目录）")

    # list
    p_list = sub.add_parser("list", help="列出推荐字体和下载地址")

    args = parser.parse_args()

    if args.command == "detect":
        found = detect_fonts(args.path)
        if found:
            print(f"✅ 发现 {len(found)} 个字体文件:")
            for f in found:
                size = os.path.getsize(Path(args.path) / "game" / "fonts" / f) / 1024
                print(f"   · {f} ({size:.0f} KB)")
        else:
            print("ℹ️  game/fonts/ 目录为空")

    elif args.command == "config":
        output = str(Path(args.path) / args.output)
        gen_font_config(args.path, args.cjk, args.en, output)

    elif args.command == "fallback":
        output = str(Path(args.path) / args.output)
        gen_font_fallback(args.path, output)

    elif args.command == "list":
        list_fonts()

    else:
        parser.print_help()