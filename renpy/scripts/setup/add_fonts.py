#!/usr/bin/env python3
"""
Ren'Py 字体添加脚本
===================
为 Ren'Py 游戏项目添加字体文件并配置到正确位置。

功能:
  1. 将字体文件复制到 game/fonts/ 目录
  2. 验证字体格式 (支持 .ttf / .otf / .ttc)
  3. 自动更新 screens/fonts_common.rpy 中的字体引用
  4. 支持批量添加字体目录

使用方法:
  # 添加单个字体文件 (自动识别 regular/bold)
  python tools/add_fonts.py MyGame-1.0-pc NotoSansSC-Regular.otf

  # 添加多个字体文件
  python tools/add_fonts.py MyGame-1.0-pc NotoSansSC-Regular.otf NotoSansSC-Bold.otf

  # 添加整个字体目录
  python tools/add_fonts.py MyGame-1.0-pc --dir path/to/fonts/

  # 指定字体角色 (cjk-regular / cjk-bold / default-regular / default-bold)
  python tools/add_fonts.py MyGame-1.0-pc myfont.ttf --role cjk-regular

  # 仅复制不更新配置
  python tools/add_fonts.py MyGame-1.0-pc myfont.ttf --no-update

参数:
  项目路径          包含 game/ 目录的项目根路径
  字体文件          一个或多个字体文件路径 (.ttf/.otf/.ttc)
  --dir             字体目录路径 (添加目录下所有字体文件)
  --role            强制指定字体角色
  --no-update       仅复制字体文件，不更新 fonts_common.rpy
"""

import argparse
import os
import re
import shutil
import sys

# ── 引入 shared/ 公共模块 ──
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shared")
)
from backup import create_bak

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── 支持的字体格式 ──
FONT_EXTENSIONS = {".ttf", ".otf", ".ttc"}

# ── 字体角色 ──
FONT_ROLES = {
    "cjk-regular": ("font_cjk_regular", "CJK 常规字体"),
    "cjk-bold": ("font_cjk_bold", "CJK 粗体字体"),
    "default-regular": ("font_default_regular", "默认常规字体"),
    "default-bold": ("font_default_bold", "默认粗体字体"),
}

# ── 用于从文件名猜测字重的关键词 ──
REGULAR_KEYWORDS = {"regular", "normal", "book", "light", "medium", "thin"}
BOLD_KEYWORDS = {"bold", "black", "heavy", "semibold", "demibold"}


def is_font_file(path):
    """判断是否为支持的字体文件"""
    ext = os.path.splitext(path)[1].lower()
    return ext in FONT_EXTENSIONS


def guess_font_role(filename):
    """根据文件名猜测字体角色

    返回 (role_key, role_desc) 或 None
    """
    name_lower = os.path.splitext(filename)[0].lower()

    # 检测是否为 CJK 字体 (通过文件名关键词)
    is_cjk = any(
        kw in name_lower
        for kw in {
            "noto",
            "sanssc",
            "serifsc",
            "sourcehan",
            "han",
            "sc",
            "tc",
            "jp",
            "kr",
            "cjk",
            "chinese",
            "japanese",
            "korean",
            "sanscn",
            "serifcn",
            "cn",
        }
    )

    # 检测字重
    is_bold = any(kw in name_lower for kw in BOLD_KEYWORDS)
    is_regular = any(kw in name_lower for kw in REGULAR_KEYWORDS)

    if is_cjk:
        if is_bold:
            return "cjk-bold"
        return "cjk-regular"
    else:
        if is_bold:
            return "default-bold"
        if is_regular:
            return "default-regular"
    return None


def collect_fonts_from_dir(dir_path):
    """从目录收集所有字体文件"""
    fonts = []
    for root, _, files in os.walk(dir_path):
        for fn in files:
            if is_font_file(fn):
                fonts.append(os.path.join(root, fn))
    return sorted(fonts)


def copy_font_to_project(font_path, project_path):
    """复制字体文件到项目的 game/fonts/ 目录

    返回 (目标相对路径, 目标绝对路径)
    """
    fonts_dir = os.path.join(project_path, "game", "fonts")
    os.makedirs(fonts_dir, exist_ok=True)

    filename = os.path.basename(font_path)
    dst_path = os.path.join(fonts_dir, filename)

    # 如果同名文件已存在，添加序号
    if os.path.exists(dst_path) and os.path.abspath(font_path) != os.path.abspath(
        dst_path
    ):
        name, ext = os.path.splitext(filename)
        i = 1
        while os.path.exists(dst_path):
            dst_path = os.path.join(fonts_dir, f"{name}_{i}{ext}")
            i += 1

    if os.path.abspath(font_path) != os.path.abspath(dst_path):
        shutil.copy2(font_path, dst_path)

    rel_path = os.path.relpath(dst_path, os.path.join(project_path, "game"))
    # 统一使用正斜杠 (Ren'Py 路径规范)
    rel_path = rel_path.replace("\\", "/")
    return rel_path, dst_path


def update_fonts_config(project_path, font_assignments):
    """更新 screens/fonts_common.rpy 中的字体引用

    font_assignments: {role_key: relative_font_path}
    """
    config_path = os.path.join(project_path, "game", "screens", "fonts_common.rpy")

    if not os.path.exists(config_path):
        print(f"  警告: 字体配置文件不存在: {config_path}")
        print(f"  提示: 请先运行 setup_i18n.py 创建多语言配置")
        return False

    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()

    updated = False
    for role_key, font_path in font_assignments.items():
        # 匹配 define font_xxx = "..."
        pattern = re.compile(r"(define\s+" + re.escape(role_key) + r'\s*=\s*")[^"]*(")')
        new_content, count = pattern.subn(r"\g<1>" + font_path + r"\g<2>", content)
        if count > 0:
            content = new_content
            updated = True
            print(f"  更新 {role_key} -> {font_path}")
        else:
            print(f"  警告: 未找到 {role_key} 的定义，跳过")

    if updated:
        create_bak(config_path)
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(content)

    return updated


def add_fonts(project_path, font_paths, role=None, no_update=False):
    """添加字体到项目"""
    project_path = os.path.abspath(project_path)
    game_dir = os.path.join(project_path, "game")

    if not os.path.isdir(game_dir):
        print(f"错误: 找不到 game 目录: {game_dir}")
        sys.exit(1)

    print("=" * 70)
    print("  Ren'Py 字体添加")
    print("=" * 70)
    print(f"  项目路径: {project_path}")
    print(f"  字体数量: {len(font_paths)}")
    print()

    # ── 验证字体文件 ──
    valid_fonts = []
    for fp in font_paths:
        if not os.path.exists(fp):
            print(f"  跳过 (文件不存在): {fp}")
            continue
        if not is_font_file(fp):
            print(f"  跳过 (非字体文件): {fp}")
            continue
        valid_fonts.append(fp)

    if not valid_fonts:
        print("\n错误: 没有有效的字体文件")
        sys.exit(1)

    # ── 复制字体文件 ──
    print("[1/2] 复制字体文件...")
    font_assignments = {}  # {role_key: relative_path}
    for fp in valid_fonts:
        filename = os.path.basename(fp)
        rel_path, dst_path = copy_font_to_project(fp, project_path)
        print(f"  {filename} -> game/{rel_path}")

        # 确定字体角色
        if role:
            assigned_role = role
        else:
            assigned_role = guess_font_role(filename)

        if assigned_role and assigned_role in FONT_ROLES:
            role_key, _ = FONT_ROLES[assigned_role]
            font_assignments[role_key] = rel_path
            print(f"    角色: {assigned_role}")

    # ── 更新字体配置 ──
    print("\n[2/2] 更新字体配置...")
    if no_update:
        print("  跳过 (--no-update)")
    elif font_assignments:
        update_fonts_config(project_path, font_assignments)
    else:
        print("  未自动分配字体角色 (可使用 --role 手动指定)")

    # ── 完成 ──
    print("\n" + "=" * 70)
    print("  字体添加完成!")
    print("=" * 70)
    print(f"\n已添加 {len(valid_fonts)} 个字体文件到 game/fonts/")
    if font_assignments and not no_update:
        print("已更新 screens/fonts_common.rpy 中的字体引用")
    print("\n提示:")
    print("  - CJK 语言 (中日韩) 需要专用字体，否则显示为方块")
    print("  - 可使用 --role 强制指定字体角色")
    print("  - 角色说明: cjk-regular / cjk-bold / default-regular / default-bold")


def main():
    parser = argparse.ArgumentParser(
        description="为 Ren'Py 游戏添加字体文件",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例:\n"
        "  python tools/add_fonts.py MyGame-1.0-pc NotoSansSC-Regular.otf\n"
        "  python tools/add_fonts.py MyGame-1.0-pc --dir path/to/fonts/\n"
        "  python tools/add_fonts.py MyGame-1.0-pc myfont.ttf --role cjk-regular",
    )
    parser.add_argument("project", help="项目根路径 (包含 game/ 目录)")
    parser.add_argument("fonts", nargs="*", help="字体文件路径 (.ttf/.otf/.ttc)")
    parser.add_argument("--dir", "-d", help="字体目录路径 (添加目录下所有字体)")
    parser.add_argument(
        "--role", choices=list(FONT_ROLES.keys()), help="强制指定字体角色"
    )
    parser.add_argument(
        "--no-update",
        action="store_true",
        help="仅复制字体文件，不更新 fonts_common.rpy",
    )
    args = parser.parse_args()

    if not os.path.isdir(args.project):
        print(f"错误: 项目路径不存在: {args.project}")
        sys.exit(1)

    # 收集字体文件
    font_paths = list(args.fonts)
    if args.dir:
        if not os.path.isdir(args.dir):
            print(f"错误: 字体目录不存在: {args.dir}")
            sys.exit(1)
        font_paths.extend(collect_fonts_from_dir(args.dir))

    if not font_paths:
        print("错误: 未指定字体文件。请提供字体文件路径或使用 --dir 指定目录")
        parser.print_help()
        sys.exit(1)

    add_fonts(args.project, font_paths, args.role, args.no_update)


if __name__ == "__main__":
    main()
