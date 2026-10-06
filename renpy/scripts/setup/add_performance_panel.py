#!/usr/bin/env python3
"""
Ren'Py 性能面板添加脚本
=======================
为 Ren'Py 游戏项目添加一个可调节的性能面板。

设计要点:
  - 独立浮层屏幕 (overlay)，不修改游戏原有任何屏幕
  - 可拖动，按快捷键显示/隐藏
  - 实时显示 FPS / 帧时间 / 渲染器
  - 可调节: 电源节省、垂直同步帧率、撕裂、转场、全屏、文本速度
  - 适用于高度定制的游戏 UI (零侵入)

使用方法:
  # 添加性能面板 (默认快捷键 p)
  python tools/add_performance_panel.py MyGame-1.0-pc

  # 指定快捷键
  python tools/add_performance_panel.py MyGame-1.0-pc --key F8

  # 覆盖已存在的面板
  python tools/add_performance_panel.py MyGame-1.0-pc --force

  # 移除性能面板
  python tools/add_performance_panel.py MyGame-1.0-pc --remove

参数:
  项目路径          包含 game/ 目录的项目根路径
  --key             打开/关闭性能面板的快捷键 (默认 p)
  --force           覆盖已存在的配置文件
  --remove          移除性能面板
"""

import argparse
import os
import sys

# ── 引入 shared/ 公共模块 ──
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shared")
)
from backup import create_bak

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PERFORMANCE_PANEL_TEMPLATE = """\
## 性能调节面板 (可拖动浮层)
## 由 add_performance_panel.py 自动生成
## 按快捷键 {key} 显示/隐藏，不修改游戏原有 UI

init python:
    def _perf_get_fps():
        frame_times = renpy.display.interface.frame_times
        if len(frame_times) < 11:
            return 0.0, 0.0, 0.0
        ift = [(j - i) for i, j in zip(frame_times, frame_times[1:])]
        fps = 1.0 / (sum(ift[-10:]) / 10.0)
        cur = ift[-1] * 1000
        mx = max(ift) * 1000
        return fps, cur, mx

    def _perf_get_renderer():
        try:
            return renpy.get_renderer_info()["renderer"]
        except Exception:
            return "unknown"

    def _perf_reset_stats():
        renpy.display.interface.frame_times[:] = []

    def _perf_toggle_panel():
        if renpy.get_screen("performance_panel") is not None:
            renpy.hide_screen("performance_panel")
        else:
            renpy.show_screen("performance_panel")

    # 加入每帧刷新列表，使 FPS 实时更新
    if "performance_panel" not in config.per_frame_screens:
        config.per_frame_screens.append("performance_panel")

screen performance_panel():
    layer config.interface_layer
    zorder 1000
    modal False

    # 每帧读取实时数据
    python:
        fps, cur_ms, max_ms = _perf_get_fps()
        renderer = _perf_get_renderer()
        _fr = _preferences.gl_framerate
        _cps = _preferences.text_cps
        _ps = _preferences.gl_powersave
        _te = _preferences.gl_tearing
        _tr = _preferences.transitions
        _fs = _preferences.fullscreen

    drag:
        draggable True
        focus_mask None
        xpos 10
        ypos 10

        frame:
            style "empty"
            background "#0008"
            xpadding 12
            ypadding 10
            xminimum 260

            vbox:
                spacing 6

                ## ── 标题栏 ──
                hbox:
                    xfill True
                    text _("性能面板 Performance"):
                        size 16
                        bold True
                        color "#ffd"
                    null width 10
                    textbutton "×":
                        action Hide("performance_panel")
                        text_size 18
                        text_color "#f88"
                        text_hover_color "#fff"
                        xalign 1.0

                ## ── 实时 FPS ──
                text _("[fps:.1f] FPS  |  [cur_ms:.2f] ms  |  [max_ms:.2f] ms max  |  [renderer]"):
                    size 13
                    color "#9f9"

                null height 2

                ## ── 渲染设置 ──
                text _("渲染 Rendering"):
                    size 14
                    bold True
                    color "#ddf"

                ## 电源节省模式
                hbox:
                    spacing 8
                    text _("电源节省 Powersave"):
                        size 13
                        color "#ccc"
                    null width 5
                    textbutton ("[ON]" if _ps else "[OFF]"):
                        action Preference("gl powersave", "toggle")
                        text_size 13
                        text_color ("#8f8" if _ps else "#f88")
                        text_hover_color "#fff"

                ## 撕裂 (跳帧 vs 撕裂)
                hbox:
                    spacing 8
                    text _("允许撕裂 Tearing"):
                        size 13
                        color "#ccc"
                    null width 5
                    textbutton ("[ON]" if _te else "[OFF]"):
                        action Preference("gl tearing", "toggle")
                        text_size 13
                        text_color ("#8f8" if _te else "#f88")
                        text_hover_color "#fff"

                ## 转场效果
                hbox:
                    spacing 8
                    text _("转场 Transitions"):
                        size 13
                        color "#ccc"
                    null width 5
                    textbutton ("全部" if _tr == 2 else "部分" if _tr == 1 else "关闭"):
                        action Preference("transitions", "toggle")
                        text_size 13
                        text_color "#8cf"
                        text_hover_color "#fff"

                ## 全屏
                hbox:
                    spacing 8
                    text _("全屏 Fullscreen"):
                        size 13
                        color "#ccc"
                    null width 5
                    textbutton ("[ON]" if _fs else "[OFF]"):
                        action Preference("display", "toggle")
                        text_size 13
                        text_color ("#8f8" if _fs else "#f88")
                        text_hover_color "#fff"

                null height 2

                ## ── 帧率限制 ──
                text _("垂直同步帧率 GL Framerate"):
                    size 14
                    bold True
                    color "#ddf"

                hbox:
                    spacing 4
                    textbutton _("自适应"):
                        action Preference("gl framerate", None)
                        text_size 12
                        text_color ("#8f8" if _fr is None else "#888")
                        text_hover_color "#fff"
                    null width 4
                    textbutton "30":
                        action Preference("gl framerate", 30)
                        text_size 12
                        text_color ("#8f8" if _fr == 30 else "#888")
                        text_hover_color "#fff"
                    null width 4
                    textbutton "60":
                        action Preference("gl framerate", 60)
                        text_size 12
                        text_color ("#8f8" if _fr == 60 else "#888")
                        text_hover_color "#fff"
                    null width 4
                    textbutton "90":
                        action Preference("gl framerate", 90)
                        text_size 12
                        text_color ("#8f8" if _fr == 90 else "#888")
                        text_hover_color "#fff"
                    null width 4
                    textbutton "120":
                        action Preference("gl framerate", 120)
                        text_size 12
                        text_color ("#8f8" if _fr == 120 else "#888")
                        text_hover_color "#fff"

                null height 2

                ## ── 文本速度 ──
                text _("文本速度 Text Speed (CPS)"):
                    size 14
                    bold True
                    color "#ddf"

                hbox:
                    spacing 6
                    text _("CPS:"):
                        size 13
                        color "#ccc"
                    text ("瞬间" if _cps == 0 else "[_cps]"):
                        size 13
                        color "#9cf"

                bar:
                    value FieldValue(_preferences, "text_cps", range=200, step=1)
                    xsize 220
                    ysize 14

                null height 4

                ## ── 操作按钮 ──
                hbox:
                    spacing 6
                    textbutton _("重置统计"):
                        action Function(_perf_reset_stats)
                        text_size 12
                        text_color "#ccc"
                        text_hover_color "#fff"
                    null width 6
                    textbutton _("关闭面板"):
                        action Hide("performance_panel")
                        text_size 12
                        text_color "#f88"
                        text_hover_color "#fff"

## 按键绑定：按 {key} 键切换性能面板
define config.keymap["toggle_performance_panel"] = ["{key}"]

init python:
    config.underlay.append(
        renpy.Keymap(toggle_performance_panel=_perf_toggle_panel)
    )
"""


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


def add_performance_panel(project_path, key="p", force=False):
    """为项目添加性能面板"""
    project_path = os.path.abspath(project_path)
    game_dir = os.path.join(project_path, "game")

    if not os.path.isdir(game_dir):
        print(f"错误: 找不到 game 目录: {game_dir}")
        sys.exit(1)

    print("=" * 70)
    print("  Ren'Py 性能面板添加")
    print("=" * 70)
    print(f"  项目路径: {project_path}")
    print(f"  快捷键:   {key}")
    print()

    screens_dir = os.path.join(game_dir, "screens")
    os.makedirs(screens_dir, exist_ok=True)

    panel_path = os.path.join(screens_dir, "performance_panel.rpy")
    content = PERFORMANCE_PANEL_TEMPLATE.format(key=key)
    write_file(panel_path, content, force)

    print("\n" + "=" * 70)
    print("  性能面板添加完成!")
    print("=" * 70)
    print(f"\n功能说明:")
    print(f"  - 按 {key} 键显示/隐藏性能面板")
    print(f"  - 面板可拖动到任意位置")
    print(f"  - 实时显示 FPS / 帧时间 / 渲染器")
    print(f"  - 可调节: 电源节省 / 撕裂 / 转场 / 全屏 / 帧率 / 文本速度")
    print(f"\n设计特点:")
    print(f"  - 独立浮层屏幕，不修改游戏原有 UI")
    print(f"  - 适用于高度定制的游戏界面 (零侵入)")
    print(f"  - 所有设置通过 Ren'Py 标准 Preference API，自动持久化")


def remove_performance_panel(project_path):
    """移除性能面板"""
    project_path = os.path.abspath(project_path)
    panel_path = os.path.join(project_path, "game", "screens", "performance_panel.rpy")

    print("=" * 70)
    print("  移除性能面板")
    print("=" * 70)

    if os.path.exists(panel_path):
        try:
            create_bak(panel_path)
        except OSError as exc:
            print(f"  [ERROR] 备份失败，已阻止删除: {exc}")
            sys.exit(1)
        os.remove(panel_path)
        print(f"  已删除: {os.path.relpath(panel_path, project_path)}  (原文件备份为 performance_panel.rpy.bak)")
        print("\n  性能面板已移除")
    else:
        print(f"  未找到性能面板文件: {os.path.relpath(panel_path, project_path)}")
        print("  可能未安装或已被删除")


def main():
    parser = argparse.ArgumentParser(
        description="为 Ren'Py 游戏添加可调节的性能面板",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例:\n"
        "  python tools/add_performance_panel.py MyGame-1.0-pc\n"
        "  python tools/add_performance_panel.py MyGame-1.0-pc --key F8\n"
        "  python tools/add_performance_panel.py MyGame-1.0-pc --force\n"
        "  python tools/add_performance_panel.py MyGame-1.0-pc --remove",
    )
    parser.add_argument("project", help="项目根路径 (包含 game/ 目录)")
    parser.add_argument(
        "--key", default="p", help="打开/关闭性能面板的快捷键 (默认: p)"
    )
    parser.add_argument(
        "--force", "-f", action="store_true", help="覆盖已存在的性能面板文件"
    )
    parser.add_argument("--remove", action="store_true", help="移除性能面板")
    args = parser.parse_args()

    if not os.path.isdir(args.project):
        print(f"错误: 项目路径不存在: {args.project}")
        sys.exit(1)

    if args.remove:
        remove_performance_panel(args.project)
    else:
        add_performance_panel(args.project, args.key, args.force)


if __name__ == "__main__":
    main()
