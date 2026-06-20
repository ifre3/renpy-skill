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


def apply(name: str, params: dict = None, validate: bool = True) -> RenPyScript:
    """
    应用一个预制模式，返回 RenPyScript 实例。

    Args:
        name: pattern 名称
        params: 参数字典
        validate: 是否验证参数（默认 True）

    Returns:
        RenPyScript 实例

    Raises:
        ValueError: 如果模式名称未知或参数无效
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
        "after_load_migration": _pattern_after_load_migration,
       "layeredimage": _pattern_layeredimage,
        "fault_tolerance": _pattern_fault_tolerance,
   }
    if name not in registry:
        available = ', '.join(registry.keys())
        raise ValueError(f"未知模式: {name}。可用模式: {available}")

    # 参数验证
    if validate:
        _validate_params(name, params)

    return registry[name](params)


def _validate_params(name: str, params: dict):
    """
    验证模式参数。

    Args:
        name: 模式名称
        params: 参数字典

    Raises:
        ValueError: 如果参数无效
    """
    if name == "gallery":
        if "images" not in params:
            print("⚠️  警告: gallery 模式缺少 'images' 参数，将生成空画廊")
        elif not isinstance(params["images"], list):
            raise ValueError("'images' 参数必须是列表")

    elif name == "cjk_font":
        if "font" in params and not isinstance(params["font"], str):
            raise ValueError("'font' 参数必须是字符串")

    elif name == "splash":
        if "logo" in params and not isinstance(params["logo"], str):
            raise ValueError("'logo' 参数必须是字符串")

    # 其他模式的验证可以在这里添加
    pass


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
    script.python(f"""
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
    script.python(f"{screen_name}_unlocked = [{', '.join(f'\"{img[0]}\"' for img in images)}]")
    script.return_()
    script._raw('# end label')

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
    中/日/韩字体配置（改进版：更灵活，不强制要求标准GUI结构）。
    params:
      font: 字体文件名 (默认 "SourceHanSansSC-Regular.otf")
      bold: 粗体文件名 (可选)
      size: 字号调整 (默认 22)
      fallback: 后备字体
      flexible: 是否灵活模式（默认 True，不检查GUI结构）
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
    flexible = params.get("flexible", True)  # 新增：灵活模式

    script = RenPyScript()
    script.comment("CJK Font Configuration (Improved: flexible mode)")

    # 警告：字体文件需要手动放置
    script.comment("注意: 请将字体文件放置到 game/ 目录或指定路径")
    script.comment(f"字体文件: {font}")

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

    # 灵活模式：不检查GUI结构，只生成配置
    if flexible:
        script.comment("Flexible mode: 不检查GUI结构")
        script.comment("如果使用的是自定义GUI，请手动调整样式")
    else:
        script.comment("Strict mode: 建议在标准GUI结构中使用")

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
    script._raw('scene')
    script.python(f"renpy.music.set_volume(0.0)")
    script._raw('scene')
    script._raw(f'show solid Solid({bg})')
    script.with_("None")
    script.pause(0.5)
    script._raw(f"show {logo} at True alpha 0.0")
    script.with_("None")
    script._raw(f"show {logo} at True alpha 1.0")
    script.with_(f"Dissolve({fi})")
    script.pause(hold)
    script._raw(f"show {logo} at True alpha 0.0")
    script.with_(f"Dissolve({fo})")
    script.label("splash_done")
    script.return_()
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
    script._raw('scene')
    script._raw(f'show solid Solid({bg})')
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
    script.python(f"""
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
    script.return_()
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

    script.python(f"""
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
    script.python(f"""
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

    script.python(f"""
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


def _pattern_after_load_migration(params: dict) -> RenPyScript:
    """
    存档兼容性：版本升级后的数据迁移。
    基于 Ren'Py 8.5.3 官方：
      - config.after_load_callbacks (renpy/common/00start.rpy)
      - config.before_load_callbacks
      - config.after_load_transition
    params:
      version: 当前游戏版本 (默认 "1.0")
      migrations: [(旧版本, 迁移代码), ...]
    """
    version = params.get("version", "1.0")
    migrations = params.get("migrations", [])
    script = RenPyScript()
    script.comment("Save Migration System")
    script.comment("基于 Ren'Py 8.5.3 config.after_load_callbacks")
    script.default("save_version", '"0.0"')
    script.blank()
    script.python(f"""
def after_load_migration():
    current = config.version
    saved = save_version
    if saved == current:
        return
    migrations = {repr(migrations)}
    for old_ver, code in migrations:
        if saved <= old_ver and current > old_ver:
            exec(code)
    renpy.set_variable("save_version", current)
""")
    script.blank()
    script.python("config.after_load_callbacks.append(after_load_migration)")
    script.blank()
    script.python("config.after_load_transition = dissolve")
    script.blank()
    return script


def _pattern_layeredimage(params: dict) -> RenPyScript:
    """
    LayeredImage 立绘系统。
    基于 Ren'Py 8.5.3 官方:
      - doc/layeredimage.html
      - renpy/common/00layeredimage.rpy
    params:
      name: 立绘变量名 (默认 "sprite")
      layers: [{"attribute": str, "dir": str, "default": str}, ...]
      path: 图片基础路径 (默认 "images/sprites")
    """
    name = params.get("name", "sprite")
    path = params.get("path", "images/sprites")
    layers = params.get("layers", [])
    script = RenPyScript()
    script.comment(f"LayeredImage: {name}")
    script.comment("基于 Ren'Py 8.5.3 layeredimage 系统")
    script.blank()
    script.line(f"layeredimage {name}:")
    script._indent_level += 1
    script.blank()
    for layer in layers:
        attr = layer.get("attribute", "base")
        dir_name = layer.get("dir", attr)
        default_attr = layer.get("default", "")
        script.comment(f"图层: {attr}")
        script.line(f"group {attr}:")
        script._indent_level += 1
        script.line(f"attribute {default_attr} default:")
        script._indent_level += 1
        script.line(f'"{path}/{dir_name}/{default_attr}.png"')
        script._indent_level -= 2
        script.blank()
    script._indent_level -= 1
    script.blank()
    return script


def _pattern_fault_tolerance(params: dict) -> RenPyScript:
    script = RenPyScript()
    script.comment("Fault Tolerance")
    script.define("config.developer", "True")
    script.blank()
    script.python("""
def _ft_handler(exception, traceback):
    for p in ["NameError","TypeError","KeyError","IndexError"]:
        if p in str(exception):
            renpy.notify("遇到小问题，已跳过。")
            return True
    return False
config.exception_handler = _ft_handler
config.load_failed_label = "load_failed"
def _ft_label(n):
    return "missing_label"
config.missing_label_callback = _ft_label
def _ft_img(n):
    return "bg placeholder"
config.missing_image_callback = _ft_img
config.save_dump = True
def _ft_load():
    pass
config.after_load_callbacks.append(_ft_load)
""")
    script.blank()
    script.comment("存档加载失败兜底")
    script.label("load_failed")
    script.say(None, "存档版本过旧，已重置。")
    script.jump("start")
    script.blank()
    script.comment("缺失 label 兜底")
    script.label("missing_label")
    script.say(None, "剧情跳转到了一个未完成的部分。")
    script.jump("start")
    script.blank()
    script.comment("Warp 跳转测试")
    script.label("after_warp")
    script.say(None, "Warp 模式 -- 测试用。")
    script.return_()
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
            "after_load_migration": "存档兼容性(版本升级数据迁移)",
            "layeredimage": "LayeredImage 立绘系统(多图层/多属性)",
            "fault_tolerance": "容错性配置(异常处理/存档兜底/缺失兜底)",
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






