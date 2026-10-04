#!/usr/bin/env python3
"""
安卓平板模式打包工具
====================
修改 Ren'Py SDK 的安卓变体选择逻辑，强制所有安卓设备使用 "tablet/medium" 变体，
绕过 "phone/small" 变体的字幕截断等兼容性问题。

用法：
    python patch_android_tablet.py apply      # 应用补丁（强制平板模式）
    python patch_android_tablet.py restore    # 恢复原始逻辑
    python patch_android_tablet.py status     # 查看当前状态

原理：
    Ren'Py 在安卓上根据屏幕对角线（6英寸阈值）决定变体：
      - < 6英寸 → phone / small 变体（手机端字幕易截断）
      - ≥ 6英寸 → tablet / medium 变体（平板端显示正常）
    本脚本将逻辑改为始终使用 tablet / medium 变体。

前提：
    脚本按 <SDK>/renpy/main.py 的相对布局定位 SDK_DIR（取本文件上两级目录），
    因此必须先拷贝到 Ren'Py SDK 根目录（或其下一级子目录）内运行，
    直接在本 skill 的 scripts/设置/ 下运行无法定位 SDK。
"""

import os
import sys
import shutil

# ── 路径 ──────────────────────────────────────────────────────────
SDK_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(SDK_DIR, "renpy", "main.py")
BACKUP_SUFFIX = ".tablet_patch.bak"

# ── 匹配文本 ──────────────────────────────────────────────────────
# 要替换的原始代码块（缩进敏感，须与文件完全一致）
OLD_BLOCK = """        if diag >= 6:
            renpy.config.variants.insert(0, "tablet")  # type: ignore
            renpy.config.variants.insert(0, "medium")  # type: ignore
        else:
            renpy.config.variants.insert(0, "phone")  # type: ignore
            renpy.config.variants.insert(0, "small")  # type: ignore"""

# 补丁后的代码块
NEW_BLOCK = """        # [PATCHED] Always use tablet variant to bypass phone/small layout issues.
        # Run 'python tools/patch_android_tablet.py restore' to revert.
        renpy.config.variants.insert(0, "tablet")  # type: ignore
        renpy.config.variants.insert(0, "medium")  # type: ignore"""

# 用于检测补丁是否已应用的标记
PATCH_MARKER = "# [PATCHED] Always use tablet variant"


# ── 核心函数 ──────────────────────────────────────────────────────
def read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_file(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def backup(path):
    """创建备份（不覆盖已有备份）。"""
    bak = path + BACKUP_SUFFIX
    if not os.path.exists(bak):
        shutil.copy2(path, bak)
        print(f"  ✔ 备份已创建: {bak}")
    else:
        print(f"  · 备份已存在: {bak}（跳过）")


def restore_from_backup(path):
    """从备份恢复。"""
    bak = path + BACKUP_SUFFIX
    if not os.path.exists(bak):
        return False
    shutil.copy2(bak, path)
    os.remove(bak)
    return True


def is_patched(content):
    return PATCH_MARKER in content


def apply():
    if not os.path.exists(MAIN_PY):
        print(f"  ✘ 未找到 {MAIN_PY}")
        sys.exit(1)

    content = read_file(MAIN_PY)

    if is_patched(content):
        print("  · 补丁已应用，无需重复操作。")
        return

    if OLD_BLOCK not in content:
        print("  ✘ 无法在 main.py 中找到目标代码块，")
        print("    可能是 SDK 版本不匹配或已被手动修改。")
        print("    请检查文件内容后重试。")
        sys.exit(1)

    backup(MAIN_PY)
    content = content.replace(OLD_BLOCK, NEW_BLOCK, 1)
    write_file(MAIN_PY, content)
    print("  ✔ 补丁已应用！所有安卓设备将使用 tablet/medium 变体。")
    print("  ⚠ 重新打包 APK 后生效。")


def restore():
    if not os.path.exists(MAIN_PY):
        print(f"  ✘ 未找到 {MAIN_PY}")
        sys.exit(1)

    content = read_file(MAIN_PY)

    if not is_patched(content):
        print("  · 补丁尚未应用，无需恢复。")
        return

    # 优先从备份恢复（最安全）
    if restore_from_backup(MAIN_PY):
        print("  ✔ 已从备份文件恢复原始代码。")
        return

    # 无备份时尝试反向替换
    if NEW_BLOCK in content:
        content = content.replace(NEW_BLOCK, OLD_BLOCK, 1)
        write_file(MAIN_PY, content)
        print("  ✔ 已通过反向替换恢复原始代码。")
    else:
        print("  ✘ 无法恢复：找不到补丁代码块且无备份文件。")
        sys.exit(1)


def status():
    if not os.path.exists(MAIN_PY):
        print(f"  ✘ 未找到 {MAIN_PY}")
        sys.exit(1)

    content = read_file(MAIN_PY)
    bak = MAIN_PY + BACKUP_SUFFIX

    if is_patched(content):
        print("  状态: ✅ 已补丁（平板模式）")
        print(f"  备份: {'存在' if os.path.exists(bak) else '不存在'}")
    else:
        print("  状态: ❌ 未补丁（原始逻辑）")


# ── 入口 ──────────────────────────────────────────────────────────
def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    action = sys.argv[1]

    if action == "apply":
        print("━━━ 应用安卓平板模式补丁 ━━━")
        apply()
    elif action == "restore":
        print("━━━ 恢复安卓变体原始逻辑 ━━━")
        restore()
    elif action == "status":
        print("━━━ 安卓平板模式状态 ━━━")
        status()
    else:
        print(f"未知操作: {action}")
        print("可用操作: apply, restore, status")
        sys.exit(1)


if __name__ == "__main__":
    main()