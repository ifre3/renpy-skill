"""
Ren'Py 预制模式库 — 开箱即用的游戏功能模块

每个 pattern 是一个函数，返回 RenPyScript 实例，
AI 只需调  pattern = apply("gallery", {...}) 即可。

内置 pattern:
  - gallery:    图片画廊 + 解锁系统
  - cjk_font:   中/日/韩字体全局配置
  - splash:     开场动画 (logo 渐入渐出)
  - nvl_mode:   NVL 模式适配
  - save_load:  存档/读档界面增强
  - preferences: 设置界面扩展（文字速度/音量/全屏）
  - credit_roll: 制作人员名单滚动
  - day_night:  早晚切换系统（背景 + BGM）
"""

import os
import sys
import textwrap

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bridge import RenPyScript

# 版本边界守卫
try:
    from _version_guard import check as _version_check, RENPY_MIN_STR as _RENPY_MIN_STR
except ImportError:
    _version_check = lambda: True
    _RENPY_MIN_STR = "8.0.0"


def apply(name: str, params: dict = None) -> RenPyScript:
    """
    应用一个预制模式，返回 RenPyScript 实例。
    name: pattern 名称
    params: 参数字典

    用法：
        script = apply("gallery", {
            "images": [("bg_beach", "bg beach", "海滩"), ...],
            "rows": 2, "cols": 3
        })
        print(script.render())
    """
    params = params or {}
    registry = {
        "gallery": _pattern_gallery,
        "cjk_font": _pattern_cjk_font,
        "splash": _pattern_splash,
        "nvl_mode": _pattern_nvl_mode,
        "save_load": _pattern_save_load,
        "preferences": _pattern_preferences,
        "credit_roll": _pattern_credit_roll,
        "day_night": _pattern_day_night,
        "affection": _pattern_affection,
        "choice_timer": _pattern_choice_timer,
    }
    if name not in registry:
        raise ValueError(f"未知模式: {name}。可用: {', '.join(registry.keys())}")
    return registry[name](params)


def load(path: str) -> dict:
    """从 JSON 文件加载 pattern 参数。"""
    import json
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    name = data.pop("pattern", None)
    if not name:
        raise ValueError("JSON 中需要 'pattern' 字段指定模式名称")
    return name, data


# ── Pattern 实现 ───────────────────────────────────────

def _pattern_gallery(params: dict) -> RenPyScript:
    """
    图片画廊系统。
    params:
      images: [(unlock_var, image_name, display_name), ...]
      cols: 列数 (默认 3)
      rows: 行数 (默认 2)
      screen_name: 屏幕名称 (默认 "gallery")
    """
    script = RenPyScript()
    images = params.get("images", [])
    cols = params.get("cols", 3)
    rows = params.get("rows", 2)
    screen_name = params.get("screen_name", "gallery")
    per_page = cols * rows
    pages = max(1, -(-len(images) // per_page))  # ceil division

    script.comment(f"Gallery: {screen_name}")
    script.default(f"{screen_name}_unlocked", "[]")
    script.default(f"{screen_name}_page", "0")

    # unlock 函数
    script.python_block(f"""
def {screen_name}_unlock(var_name):
    unlocked = globals().get("{screen_name}_unlocked", [])
    if var_name not in unlocked:
        unlocked.append(var_name)
        globals()["{screen_name}_unlocked"] = unlocked
        renpy.notify("解锁了新图片！")

def {screen_name}_is_unlocked(var_name):
    return var_name in globals().get("{screen_name}_unlocked", [])
""")

    # unlock all (for debug)
    script.label(f"{screen_name}_unlock_all")
    script.py(f"{screen_name}_unlocked = [{', '.join(f'\"{img[0]}\"' for img in images)}]")
    script.ret()
    script.end_label()

    # screen
    script.comment(f"{screen_name} screen 定义")
    asm = f"""
screen {screen_name}():
    tag menu
    use game_menu(_("{screen_name}"), scroll="viewport"):
        vbox:
            spacing 10
            grid {cols} {rows}:
                spacing 5
                xalign 0.5
                for i in range({per_page}):
                    $ idx = {screen_name}_page * {per_page} + i
                    if idx < len({screen_name}_unlocked):
                        $ img_name = {screen_name}_unlocked[idx]
                        imagebutton:
                            idle img_name
                            action NullAction()
                            xsize 200 ysize 160
                    else:
                        frame:
                            xsize 200 ysize 160
                            text "?" xalign 0.5 yalign 0.5
            hbox:
                xalign 0.5
                spacing 20
                if {screen_name}_page > 0:
                    textbutton "◀ 上一页" action SetVariable("{screen_name}_page", {screen_name}_page - 1)
                if {screen_name}_page < {pages - 1}:
                    textbutton "下一页 ▶" action SetVariable("{screen_name}_page", {screen_name}_page + 1)
"""
    script.screen(screen_name, textwrap.dedent(asm).strip())

    return script


def _pattern_cjk_font(params: dict) -> RenPyScript:
    """
    中/日/韩字体配置。
    params:
      font: 字体文件名 (默认 "SourceHanSansSC-Regular.otf")
      bold: 粗体文件名 (可选)
      size: 字号调整 (默认 22)
      fallback: 后备字体
    """
    font = params.get("font", "SourceHanSansSC-Regular.otf")
    # 推断粗体文件名：将权重替换为 Bold
    if "Bold" in font:
        bold_default = None
    else:
        import re
        base, ext = font.rsplit(".", 1)
        # 替换常见权重标记：-Regular / -Medium / -Light → -Bold
        base_bold = re.sub(r"-(Regular|Medium|Light|Thin|ExtraLight|SemiBold)$", "-Bold", base)
        if base_bold == base and "-" in base:
            # 无匹配时在最后一段前插入 -Bold
            base_bold = f"{base}-Bold"
        elif base_bold == base:
            base_bold = f"{base}Bold"
        bold_default = f"{base_bold}.{ext}"
    bold = params.get("bold", bold_default)
    size = params.get("size", 22)

    script = RenPyScript()
    script.comment("CJK Font Configuration")

    defines = [
        f'gui.text_font = "{font}"',
        f'gui.name_text_font = "{font}"',
        f'gui.interface_text_font = "{font}"',
        f'gui.button_text_font = "{font}"',
        f'gui.choice_button_text_font = "{font}"',
        f'gui.text_size = {size}',
        f'gui.name_text_size = {size + 4}',
    ]

    if bold:
        defines.insert(1, f'gui.bold_font = "{bold}"')

    for line in defines:
        script._raw(line)

    script.blank()
    return script


def _pattern_splash(params: dict) -> RenPyScript:
    """
    开场动画。
    params:
      logo: logo 图片名 (默认 "logo")
      bg_color: 背景色 (默认 "#000")
      fade_in: 淡入时间 (默认 1.0)
      hold: 停留时间 (默认 2.0)
      fade_out: 淡出时间 (默认 1.0)
      skip_key: 跳过键 (默认 "space")
    """
    logo = params.get("logo", "logo")
    bg = params.get("bg_color", "#000")
    fi = params.get("fade_in", 1.0)
    hold = params.get("hold", 2.0)
    fo = params.get("fade_out", 1.0)
    skip = params.get("skip_key", "space")

    script = RenPyScript()
    script.comment("Splashscreen")
    script.define("config.splashscreen_skip_label", '"splash_done"', )
    script.blank()
    script.label("splashscreen")
    script.scene()
    script.py(f"renpy.music.set_volume(0.0)")
    script.scene()
    script.show("solid", what=f"Solid({bg})")
    script.with_("None")
    script.pause(0.5)
    script.show(logo, atl=f"True alpha 0.0")
    script.with_("None")
    script.show(logo, atl=f"True alpha 1.0")
    script.with_(f"Dissolve({fi})")
    script.pause(hold)
    script.show(logo, atl="True alpha 0.0")
    script.with_(f"Dissolve({fo})")
    script.label("splash_done")
    script.ret()
    return script


def _pattern_nvl_mode(params: dict) -> RenPyScript:
    """NVL 模式适配
    params: {} (无参数)
    """
    script = RenPyScript()
    script.comment("NVL Mode Configuration")
    script._raw("define gui.nvl_height = 115")
    script._raw("define gui.nvl_spacing = 15")
    script._raw("define gui.nvl_thought_height = 115")
    script._raw("define gui.nvl_thought_spacing = 15")
    script._raw("")
    script._raw("define config.nvl_list_length = 6")
    script._raw("define config.nvl_choice_layer = \"overlay\"")
    script._raw("define config.nvl_layer = \"master\"")
    script.blank()
    return script


def _pattern_save_load(params: dict) -> RenPyScript:
    """存档/读档界面增强
    params:
      slots: 存档栏位数 (默认 12)
      auto_slots: 自动存档数 (默认 6)
    """
    slots = params.get("slots", 12)
    auto = params.get("auto_slots", 6)
    script = RenPyScript()
    script.comment("Save/Load Configuration")
    script._raw(f"define config.save_slots = {slots + auto}")
    script._raw(f"define config.has_autosave = True")
    script._raw(f"define config.autosave_slots = {auto}")
    script._raw(f"define config.auto_save_delay = {params.get('auto_delay', 300)}")
    script._raw(f"define config.auto_save_on_choice = True")
    script._raw(f"define config.auto_save_on_quit = True")
    script.blank()
    return script


def _pattern_preferences(params: dict) -> RenPyScript:
    """设置界面扩展
    params:
      text_speed: 是否包含文字速度滑块 (默认 True)
      afm: 是否包含自动前进 (默认 True)
      volume: 是否包含音量 (默认 True)
      fullscreen: 是否包含全屏开关 (默认 True)
    """
    ts = params.get("text_speed", True)
    afm = params.get("afm", True)
    vol = params.get("volume", True)
    fs = params.get("fullscreen", True)

    script = RenPyScript()
    script.comment("Preferences Extensions")
    script.define("config.has_quicksave", "False")

    body_lines = ["vbox:", '    style_prefix "pref"']
    if ts:
        body_lines.append('    label _("文字速度")')
        body_lines.append('    bar value Preference("text speed")')
    if afm:
        body_lines.append('    label _("自动前进")')
        body_lines.append('    bar value Preference("auto-forward time")')
    if vol:
        body_lines.append('    label _("音量")')
        body_lines.append('    bar value Preference("music volume")')
        body_lines.append('    bar value Preference("sound volume")')
        body_lines.append('    bar value Preference("voice volume")')
    if fs:
        body_lines.append('    null height 15')
        body_lines.append('    textbutton _("窗口/全屏") action Preference("display", "toggle")')

    script.screen("preference_extras", "\n".join(body_lines))
    script.blank()
    return script


def _pattern_credit_roll(params: dict) -> RenPyScript:
    """
    制作人员名单滚动。
    params:
      title: 游戏标题
      credits: [("角色", "名字"), ...] 或 ["纯文本行", ...]
      speed: 滚动速度 (默认 30.0)
      bg: 背景色 (默认 "#000")
    """
    title = params.get("title", "Staff Roll")
    credits = params.get("credits", [])
    speed = params.get("speed", 30.0)
    bg = params.get("bg_color", "#000")

    script = RenPyScript()
    script.comment("Credits Roll")
    script.label("credits")
    script.scene()
    script.show("solid", what=f"Solid({bg})")
    script.with_("None")

    # 构建滚动内容（JSON 序列化防注入）
    import json as _json
    c_lines = []
    for item in credits:
        if isinstance(item, str):
            c_lines.append(item)
        elif isinstance(item, (list, tuple)):
            c_lines.append(f"{item[0]}: {item[1]}")
        elif isinstance(item, dict):
            c_lines.append(f"{item.get('role', '')}: {item.get('name', '')}")

    content = "\\n\\n".join(c_lines)
    safe_title = _json.dumps(f"{title}\\n\\n{content}\\n\\n\\n\\n\\n\\n\\n\\n\\n\\n\\n\\n")
    script.python_block(f"""
text = {safe_title}
ui.add(
    renpy.text.text.Text(
        text,
        text_align=0.5,
        size=24,
        color="#fff",
    ),
    xalign=0.5,
    yalign=0.5,
)
renpy.pause({speed}, hard=True)
""")
    script.with_("fade")
    script.ret()
    return script


def _pattern_day_night(params: dict) -> RenPyScript:
    """
    早/晚切换系统。
    params:
      transition: 切换转场 (默认 "dissolve")
      bgm_day: 白天 BGM 文件名 (可选)
      bgm_evening: 傍晚 BGM 文件名 (可选)
      bgm_night: 夜晚 BGM 文件名 (可选)
    """
    trans = params.get("transition", "dissolve")
    bgm_day = params.get("bgm_day", None)
    bgm_evening = params.get("bgm_evening", None)
    bgm_night = params.get("bgm_night", None)
    script = RenPyScript()
    script.comment("Day/Night System")
    script.default("game_time", '"day"')
    script.blank()

    # 构建 BGM 切换代码（如果有指定 BGM）
    bgm_switch_code = ""
    if bgm_day or bgm_evening or bgm_night:
        bgm_map_lines = []
        for label, bgm in [("day", bgm_day), ("evening", bgm_evening), ("night", bgm_night)]:
            if bgm:
                bgm_map_lines.append(f'        "{label}": "{bgm}"')
        bgm_switch_code = "\n    bgm_map = {\n"
        bgm_switch_code += ",\n".join(bgm_map_lines)
        bgm_switch_code += "\n    }\n    if time_str in bgm_map:\n        renpy.music.play(bgm_map[time_str], fadeout=0.5, fadein=0.5)\n"

    script.python_block(f"""
def set_time(time_str, transition="{trans}"):
    \"\"\"切换早晚。
    time_str: "day", "evening", "night"
    \"\"\"
    globals()["game_time"] = time_str
    renpy.with_statement(eval(transition))
{bgm_switch_code}

def is_day():
    return globals().get("game_time") == "day"

def is_night():
    return globals().get("game_time") == "night"

def is_evening():
    return globals().get("game_time") == "evening"

def bg_with_time(bg_name):
    \"\"\"返回带时间后缀的背景名。如 "bg_street_night" \"\"\"
    time = globals().get("game_time", "day")
    return f"{{bg_name}}_{{time}}"
""")
    script.blank()

    # show_time screen — 在左上角显示当前时间
    script._raw("screen show_time():")
    script._raw("    if game_time == \"day\":")
    script._raw("        text \"☀️ 白天\" xalign 0.0 yalign 0.0 color \"#FFD700\" size 20")
    script._raw("    elif game_time == \"evening\":")
    script._raw("        text \"🌅 傍晚\" xalign 0.0 yalign 0.0 color \"#FF8C00\" size 20")
    script._raw("    else:")
    script._raw("        text \"🌙 夜晚\" xalign 0.0 yalign 0.0 color \"#87CEEB\" size 20")
    script.blank()
    return script


def _pattern_affection(params: dict) -> RenPyScript:
    """
    好感度系统。
    params:
      characters: [{"var": "e", "name": "艾琳"}, ...]
      tiers: 好感度等级 (默认 5)
      max_points: 每级需要点数 (默认 20)
      screen: 是否生成好感度界面 (默认 True)
    """
    chars = params.get("characters", [])
    tiers = params.get("tiers", 5)
    pts = params.get("max_points", 20)
    show_screen = params.get("screen", True)

    max_total = pts * tiers

    script = RenPyScript()
    script.comment("Affection System")
    for ch in chars:
        v = ch["var"]
        script.default(f"{v}_affection", "0")
        script.default(f"{v}_affection_tier", "1")
        script.default(f"{v}_affection_flag", "False")
        script.default(f"{v}_affection_max", str(max_total))

    script.blank()
    script.python_block(f"""
def change_affection(char, delta):
    \"\"\"
    char: 角色变量名 (如 \"e\")
    delta: 变化值 (正/负)
    \"\"\"
    max_val = globals()[f"{{char}}_affection_max"]
    cur = globals()[f"{{char}}_affection"]
    cur = max(0, min(max_val, cur + delta))
    globals()[f"{{char}}_affection"] = cur

    new_tier = min(int(cur / {pts}) + 1, {tiers})
    old_tier = globals()[f"{{char}}_affection_tier"]
    if new_tier > old_tier:
        globals()[f"{{char}}_affection_tier"] = new_tier
        globals()[f"{{char}}_affection_flag"] = True
        renpy.notify(f"{{char}} 好感度升级！")

def get_tier_name(tier):
    names = ["陌生", "熟悉", "友好", "亲密", "挚爱"]
    return names[min(tier - 1, len(names) - 1)]
""")

    if show_screen and chars:
        script.blank()
        script.comment("Affection Status Screen")
        script._raw("screen affection_status():")
        script._raw("    vbox:")
        script._raw("        style_prefix \"pref\"")
        script._raw("        xalign 0.5 yalign 0.5")
        for ch in chars:
            v = ch["var"]
            display = ch.get("name", v)
            script._raw(f"        label \"{display}: [get_tier_name({v}_affection_tier)]\"")
            script._raw(f"        bar value AnimatedValue(value={v}_affection, range={v}_affection_max) xmaximum 400")
            script._raw(f"        null height 10")

    script.blank()
    return script


def _pattern_choice_timer(params: dict) -> RenPyScript:
    """
    菜单计时器：选项超时自动触发。
    params:
      timeout: 超时秒数 (默认 10.0)
      default_choice: 默认选项索引 (默认 0)
    """
    timeout = params.get("timeout", 10.0)
    default_idx = params.get("default_choice", 0)

    script = RenPyScript()
    script.comment("Choice Timer System")
    script.default("choice_timeout", "False")
    script.blank()

    script.python_block(f"""
def timed_menu(items, timeout={timeout}, default={default_idx}):
    \"\"\"
    带计时器的菜单。
    items: 和 menu() 相同格式的列表
    timeout: 超时秒数
    default: 超时后默认选择的索引
    返回: selected_value
    \"\"\"
    import renpy.exports
    renpy.exports.set_variable("choice_timeout", False)

    # 启动计时器
    ui.timer(timeout, SetVariable("choice_timeout", True))

    # 显示菜单
    result = renpy.exports.display_menu(items)

    # 如果超时且用户没选
    if result is None:
        if default < len(items):
            result = items[default][1] if items[default][1] is not None else None

    return result
""")
    script.blank()
    return script


# ── CLI 测试 ───────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Ren'Py 预制模式库")
    parser.add_argument("pattern", nargs="?", help="模式名称")
    parser.add_argument("--params", help="参数 JSON 字符串或文件路径(.json)")
    parser.add_argument("--list", action="store_true", help="列出所有可用模式")
    parser.add_argument("--output", "-o", help="输出到 .rpy 文件")

    args = parser.parse_args()

    if args.list:
        registry = {
            "gallery": "图片画廊 + 解锁系统",
            "cjk_font": "中/日/韩字体配置",
            "splash": "开场动画(logo淡入/停留/淡出)",
            "nvl_mode": "NVL模式适配",
            "save_load": "存档/读档配置增强",
            "preferences": "设置界面扩展(文字速度/音量)",
            "credit_roll": "制作人员名单滚动",
            "day_night": "早/晚切换系统",
            "affection": "好感度系统(多角色/多等级)",
            "choice_timer": "菜单计时器(超时自动选择)",
        }
        print("📦 Ren'Py 预制模式:")
        for name, desc in registry.items():
            print(f"   {name:15s}  {desc}")
        return

    if not args.pattern:
        parser.print_help()
        return

    params = {}
    if args.params:
        if args.params.endswith(".json"):
            import json
            with open(args.params, "r", encoding="utf-8") as f:
                params = json.load(f)
        else:
            import json
            params = json.loads(args.params)

    script = apply(args.pattern, params)

    if args.output:
        script.write(args.output)
        print(f"✅ 已写入: {args.output}")
    else:
        print(script.render())


if __name__ == "__main__":
    main()
