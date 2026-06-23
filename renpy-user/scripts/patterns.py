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
  - phone:      手机短信系统（收发消息/通知）
  - inventory:  背包道具系统（物品/使用/组合）
  - music_room: 音乐室（解锁 BGM 播放）
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
        "phone": _pattern_phone,
        "inventory": _pattern_inventory,
        "music_room": _pattern_music_room,
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
    图片画廊系统（基于官方 Gallery 类）。
    params:
      images: [(image_name, display_name), ...]
      cols: 列数 (默认 3)
      screen_name: 屏幕名称 (默认 "gallery")
    """
    script = RenPyScript()
    images = params.get("images", [])
    cols = params.get("cols", 3)
    screen_name = params.get("screen_name", "gallery")

    script.comment(f"Gallery: {screen_name}")
    script.comment("基于 Ren'Py 8.5.3 00gallery.rpy Gallery 类")
    script.raw(f"define {screen_name}_g = Gallery()")
    script.raw(f"{screen_name}_g.transition = dissolve")
    script.blank()

    for img_name, display_name in images:
        script.raw(f'{screen_name}_g.button("{img_name}")')
        script.raw(f'{screen_name}_g.image("{img_name}")')
        script.raw(f'{screen_name}_g.unlock("{img_name}")')
        script.blank()

    script.raw(f"screen {screen_name}():")
    script.raw("    tag menu")
    script.raw(f'    use game_menu(_("{screen_name}"), scroll="viewport"):')
    script.raw("        grid {} 1:".format(cols))
    script.raw("            spacing 5")
    for img_name, display_name in images:
        script.raw(f'            {screen_name}_g.make_button("{img_name}", "{img_name}", locked="locked.png")')
    script.blank()
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
        script.raw(line)

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
    """
    logo = params.get("logo", "logo")
    bg = params.get("bg_color", "#000")
    fi = params.get("fade_in", 1.0)
    hold = params.get("hold", 2.0)
    fo = params.get("fade_out", 1.0)

    script = RenPyScript()
    script.comment("Splashscreen")
    script.comment("基于 Ren'Py 8.5.3 00start.rpy: config.end_splash_transition, splashscreen_suppress_overlay")
    script.define("config.splashscreen_suppress_overlay", "True")
    script.blank()
    script.label("splashscreen")
    script.raw("scene")
    script.raw(f"show solid Solid({bg})")
    script.with_stmt("None")
    script.raw(f"show {logo}:")
    script.raw("    alpha 0.0")
    script.raw(f"    linear {fi} alpha 1.0")
    script.with_stmt("None")
    script.pause(hold)
    script.raw(f"show {logo}:")
    script.raw("    alpha 1.0")
    script.raw(f"    linear {fo} alpha 0.0")
    script.with_stmt("None")
    script.raw("scene")
    script.define("config.end_splash_transition", "fade")
    script.return_()
    return script


def _pattern_nvl_mode(params: dict) -> RenPyScript:
    """NVL 模式适配
    params: {} (无参数)
    """
    script = RenPyScript()
    script.comment("NVL Mode Configuration")
    script.raw("define gui.nvl_height = 115")
    script.raw("define gui.nvl_spacing = 15")
    script.raw("define gui.nvl_thought_height = 115")
    script.raw("define gui.nvl_thought_spacing = 15")
    script.raw("")
    script.raw("define config.nvl_list_length = None")
    script.raw("define config.nvl_layer = \"screens\"")
    script.blank()
    return script


def _pattern_save_load(params: dict) -> RenPyScript:
    """存档/读档界面增强
    params:
      auto_slots: 自动存档数 (默认 6)
    """
    auto = params.get("auto_slots", 6)
    script = RenPyScript()
    script.comment("Save/Load Configuration")
    script.raw(f"define config.has_autosave = True")
    script.raw(f"define config.autosave_slots = {auto}")
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
    script.raw('scene')
    script.raw(f'show solid Solid({bg})')
    script.with_stmt("None")

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
    script.with_stmt("fade")
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
    script.raw("screen show_time():")
    script.raw("    if game_time == \"day\":")
    script.raw("        text \"☀️ 白天\" xalign 0.0 yalign 0.0 color \"#FFD700\" size 20")
    script.raw("    elif game_time == \"evening\":")
    script.raw("        text \"🌅 傍晚\" xalign 0.0 yalign 0.0 color \"#FF8C00\" size 20")
    script.raw("    else:")
    script.raw("        text \"🌙 夜晚\" xalign 0.0 yalign 0.0 color \"#87CEEB\" size 20")
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
        script.raw("screen affection_status():")
        script.raw("    vbox:")
        script.raw("        style_prefix \"pref\"")
        script.raw("        xalign 0.5 yalign 0.5")
        for ch in chars:
            v = ch["var"]
            display = ch.get("name", v)
            script.raw(f"        label \"{display}: [get_tier_name({v}_affection_tier)]\"")
            script.raw(f"        bar value AnimatedValue(value={v}_affection, range={v}_affection_max) xmaximum 400")
            script.raw(f"        null height 10")

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
    基于 Ren'Py 8.5.3 官方:
      - config.after_load_callbacks (renpy/common/00start.rpy)
      - config.before_load_callbacks
      - config.after_load_transition
    params:
      version: 当前游戏版本 (默认 "1.0")
      migrations: [(旧版本, 迁移代码), ...]
      use_before: 是否注册 before_load_callbacks (默认 False)
    """
    version = params.get("version", "1.0")
    migrations = params.get("migrations", [])
    use_before = params.get("use_before", False)
    script = RenPyScript()
    script.comment("Save Migration System")
    script.comment("基于 Ren'Py 8.5.3 config.after_load_callbacks / before_load_callbacks")
    script.default("save_version", '"0.0"')
    script.blank()
    script.python("""
def after_load_migration():
    current = config.version
    saved = save_version
    if saved == current:
        return
    migrations = """ + repr(migrations) + """
    for old_ver, code in migrations:
        if saved <= old_ver and current > old_ver:
            # 安全执行迁移代码（仅限可信来源）
            renpy.log("Running migration: " + old_ver)
            exec(code, {"__builtins__": __builtins__}, globals())
    renpy.set_variable("save_version", current)
""")
    script.blank()
    script.python("config.after_load_callbacks.append(after_load_migration)")
    if use_before:
        script.blank()
        script.python("""
def before_load_migration():
    renpy.notify("正在升级存档...")
""")
        script.python("config.before_load_callbacks.append(before_load_migration)")
    script.blank()
    script.comment("加载过渡效果")
    script.raw("define config.after_load_transition = dissolve")
    script.blank()
    return script


def _pattern_layeredimage(params: dict) -> RenPyScript:
    """
    LayeredImage 立绘系统。
    基于 Ren'Py 8.5.3 官方:
      - doc/layeredimage.html
      - renpy/common/00layeredimage_ren.py
    支持:
      - 多组(group)多层(attribute) + auto 模式
      - image_format / format_function
      - 条件层 (if_all / if_any / if_not)
      - always 层
      - size / at / behind
      - group multiple 支持

    params:
      name: 立绘变量名 (默认 "sprite")
      layers: 图层配置列表 [{...}, ...]
      image_format: 图片路径模板 (如 "images/sprites/{image}.png")
      size: (宽, 高) 元组 (可选)
      at: ATL transform 列表 (可选)
      behind: 在哪些属性之后显示 (可选)

    图层条目支持:
      {"type": "group", "attribute": "face", "dir": "face",
       "default": "neutral", "auto": true, "multiple": false,
       "variants": [{"attribute": "happy", "file": "happy.png"}, ...]}
      {"type": "always", "file": "base.png"}
      {"type": "if", "condition": "flag", "file": "special.png",
       "if_all": ["flag1"], "if_any": ["flag2"], "if_not": ["flag3"]}
    """
    script = RenPyScript()
    name = params.get("name", "sprite")
    size = params.get("size")
    at_transform = params.get("at")
    behind = params.get("behind")
    image_format = params.get("image_format")
    layers = params.get("layers", [])

    script.blank()
    script.comment("LayeredImage: " + name)
    script.comment("基于 Ren'Py 8.5.3 00layeredimage_ren.py")

    header = "layeredimage " + name
    if at_transform:
        if isinstance(at_transform, str):
            header += " at " + at_transform
        else:
            header += " at " + " ".join(at_transform)
    if behind:
        if isinstance(behind, str):
            header += " behind " + behind
        else:
            header += " behind " + " ".join(behind)
    if size:
        header += " size (" + str(size[0]) + ", " + str(size[1]) + ")"
    script.line(header + ":")
    script._indent_level += 1

    if image_format:
        script.line("image_format " + image_format)
        script.blank()

    for layer in layers:
        layer_type = layer.get("type", "group")

        if layer_type == "always":
            file = layer.get("file", "")
            script.line("always:")
            script._indent_level += 1
            if layer.get("if_all"):
                script.line("if_all " + _fmt_attrs(layer["if_all"]))
            if layer.get("if_any"):
                script.line("if_any " + _fmt_attrs(layer["if_any"]))
            if layer.get("if_not"):
                script.line("if_not " + _fmt_attrs(layer["if_not"]))
            if layer.get("at"):
                script.line("at " + _fmt_attrs(layer["at"]))
            script.line('"' + file + '"')
            script._indent_level -= 1
            script.blank()

        elif layer_type == "if":
            condition = layer.get("condition", "True")
            file = layer.get("file", "")
            script.line("if " + condition + ":")
            script._indent_level += 1
            if layer.get("if_all"):
                script.line("if_all " + _fmt_attrs(layer["if_all"]))
            if layer.get("if_any"):
                script.line("if_any " + _fmt_attrs(layer["if_any"]))
            if layer.get("if_not"):
                script.line("if_not " + _fmt_attrs(layer["if_not"]))
            script.line('"' + file + '"')
            script._indent_level -= 1
            script.blank()

        else:  # group
            attr_name = layer.get("attribute", "base")
            auto_mode = layer.get("auto", False)
            multiple = layer.get("multiple", False)
            prefix = layer.get("prefix")

            if auto_mode:
                line = "group " + attr_name + " auto"
                if prefix:
                    line += " prefix " + prefix
                script.line(line + ":")
                script._indent_level += 1
                script._indent_level -= 1
            else:
                line = "group " + attr_name
                if multiple:
                    line += " multiple"
                script.line(line + ":")
                script._indent_level += 1

                if layer.get("if_all"):
                    script.line("if_all " + _fmt_attrs(layer["if_all"]))
                if layer.get("if_any"):
                    script.line("if_any " + _fmt_attrs(layer["if_any"]))
                if layer.get("if_not"):
                    script.line("if_not " + _fmt_attrs(layer["if_not"]))
                if layer.get("at"):
                    script.line("at " + _fmt_attrs(layer["at"]))

                variants = layer.get("variants", [])
                for v in variants:
                    v_attr = v.get("attribute", "default")
                    v_file = v.get("file", v_attr + ".png")
                    v_default = v.get("default", False)

                    line_v = "attribute " + v_attr
                    if v_default:
                        line_v += " default"
                    script.line(line_v + ":")
                    script._indent_level += 1
                    if v.get("if_all"):
                        script.line("if_all " + _fmt_attrs(v["if_all"]))
                    if v.get("if_any"):
                        script.line("if_any " + _fmt_attrs(v["if_any"]))
                    if v.get("if_not"):
                        script.line("if_not " + _fmt_attrs(v["if_not"]))
                    if v.get("variant"):
                        script.line("variant " + v["variant"])
                    script.line('"' + v_file + '"')
                    script._indent_level -= 1

                script._indent_level -= 1
            script.blank()

    script._indent_level -= 1
    return script

def _pattern_fault_tolerance(params: dict) -> RenPyScript:
    """
    容错性配置。注意：exception_handler 会吞掉指定异常，开发调试时慎用。

    基于 Ren'Py 8.5.3:
      - config.exception_handler
      - config.load_failed_label
      - config.missing_label_callback / missing_image_callback
      - config.after_load_callbacks

    params:
      use_exception_handler: 是否启用异常吞噬（默认 False，建议仅发布版本设为 True）
      exception_types: 要吞噬的异常类型列表（默认 ["NameError","TypeError","KeyError","IndexError"]）
    """
    script = RenPyScript()
    use_handler = params.get("use_exception_handler", False)
    exc_types = params.get("exception_types", ["NameError","TypeError","KeyError","IndexError"])

    script.comment("Fault Tolerance")
    script.comment("config.developer = True 开启开发者模式，显示完整错误信息")
    script.define("config.developer", "True")
    script.blank()

    if use_handler:
        exc_list = ", ".join(f'"{t}"' for t in exc_types)
        script.comment("WARNING: exception_handler 会静默吞异常，开发调试时禁用")
        script.python("""
def _ft_handler(exception, traceback):
    for p in [""" + exc_list + """]:
        if p in str(exception):
            renpy.notify("遇到小问题，已跳过。")
            return True
    return False
config.exception_handler = _ft_handler
""")
        script.blank()

    script.python("""
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


# ── 社区高频需求：手机/背包/音乐室 ─────────────────────

def _pattern_phone(params: dict) -> RenPyScript:
    """
    手机短信系统。
    params:
      contacts: [{"name": "艾琳", "avatar": "eileen_icon"}, ...]
      style: "smart" | "flip" (默认 "smart")
    """
    contacts = params.get("contacts", [])
    style = params.get("style", "smart")
    script = RenPyScript()
    script.comment("Phone Messaging System")
    script.default("phone_messages", "[]")
    script.default("phone_visible", "False")
    script.blank()

    script.python("""
class PhoneMessage:
    def __init__(self, sender, text, incoming=True):
        self.sender = sender
        self.text = text
        self.incoming = incoming
        self.time = renpy.time.time()

def phone_send(sender, text, incoming=True):
    phone_messages.append(PhoneMessage(sender, text, incoming))
    if incoming:
        renpy.notify(f"{sender}: {text[:20]}")

def phone_clear():
    phone_messages[:] = []
""")
    script.blank()

    # 手机界面
    script.raw("screen phone_ui():")
    script.raw("    zorder 100")
    script.raw("    if phone_visible:")
    script.raw("        frame:")
    script.raw("            xalign 0.95 yalign 0.5")
    script.raw("            xsize 320 ysize 500")
    script.raw("            background Frame(\"gui/phone_bg.png\")")
    script.raw("            viewport:")
    script.raw("                ysize 420")
    script.raw("                scrollbars \"vertical\"")
    script.raw("                mousewheel True")
    script.raw("                vbox:")
    script.raw("                    for msg in phone_messages:")
    script.raw("                        if msg.incoming:")
    script.raw('                            text "[msg.sender]" color "#888" size 14')
    script.raw('                            text "[msg.text]" color "#fff" size 16')
    script.raw("                        else:")
    script.raw('                            text "[msg.text]" color "#0f0" size 16 xalign 1.0')
    script.raw("                        null height 8")
    script.raw("            textbutton \"关闭\" action SetVariable(\"phone_visible\", False) xalign 0.5")
    script.blank()
    return script


def _pattern_inventory(params: dict) -> RenPyScript:
    """
    背包道具系统。
    params:
      slots: 初始槽位数 (默认 8)
      items: [{"id": "key", "name": "钥匙", "desc": "开锁用", "icon": "item_key"}, ...]
    """
    slots = params.get("slots", 8)
    items = params.get("items", [])
    script = RenPyScript()
    script.comment("Inventory System")
    script.default("inv_items", "[]")
    script.default("inv_slots", str(slots))
    script.blank()

    script.python("""
def inv_add(item_id, count=1):
    for it in inv_items:
        if it["id"] == item_id:
            it["count"] += count
            return True
    if len(inv_items) < inv_slots:
        inv_items.append({"id": item_id, "count": count})
        renpy.notify("获得道具")
        return True
    renpy.notify("背包已满")
    return False

def inv_remove(item_id, count=1):
    for it in inv_items:
        if it["id"] == item_id and it["count"] >= count:
            it["count"] -= count
            if it["count"] == 0:
                inv_items.remove(it)
            return True
    return False

def inv_has(item_id, count=1):
    for it in inv_items:
        if it["id"] == item_id and it["count"] >= count:
            return True
    return False
""")
    script.blank()

    # 物品定义
    for item in items:
        script.define(f'item_{item["id"]}_name', f'"{item.get("name", item["id"])}"')
        script.define(f'item_{item["id"]}_desc', f'"{item.get("desc", "")}"')

    script.blank()
    # 背包界面
    script.raw("screen inventory_ui():")
    script.raw("    frame:")
    script.raw("        xalign 0.5 yalign 0.5")
    script.raw(f"        grid 4 {max(1, slots // 4)}:")
    script.raw("            spacing 5")
    script.raw("            for i in range(inv_slots):")
    script.raw("                if i < len(inv_items):")
    script.raw("                    $ it = inv_items[i]")
    script.raw("                    imagebutton:")
    script.raw("                        idle \"item_placeholder\"")
    script.raw("                        action NullAction()")
    script.raw("                        tooltip eval(f\"item_{it['id']}_desc\")")
    script.raw("                else:")
    script.raw("                    frame:")
    script.raw("                        xsize 80 ysize 80")
    script.raw('                        text "-" xalign 0.5 yalign 0.5')
    script.blank()
    return script


def _pattern_music_room(params: dict) -> RenPyScript:
    """
    音乐室系统（基于官方 MusicRoom 类）。
    params:
      tracks: [{"file": "bgm_01.ogg", "title": "主题曲", "always_unlocked": false}, ...]
      screen_name: 屏幕名 (默认 "music_room")
    """
    tracks = params.get("tracks", [])
    screen_name = params.get("screen_name", "music_room")
    script = RenPyScript()
    script.comment("Music Room")
    script.comment("基于 Ren'Py 8.5.3 00musicroom.rpy MusicRoom 类")
    script.raw(f"define {screen_name} = MusicRoom(fadeout=1.0)")
    script.blank()

    for track in tracks:
        file = track["file"]
        always_unlocked = track.get("always_unlocked", False)
        script.raw(f'{screen_name}.add("{file}", always_unlocked={always_unlocked})')

    script.blank()
    script.raw(f"screen {screen_name}():")
    script.raw("    tag menu")
    script.raw(f'    use game_menu(_("音乐室"), scroll="viewport"):')
    script.raw("        vbox:")
    script.raw("            spacing 8")
    for track in tracks:
        title = track.get("title", track["file"])
        file = track["file"]
        script.raw(f'            textbutton _("{title}") action {screen_name}.Play("{file}")')
    script.raw("            null height 20")
    script.raw(f'            textbutton _("停止") action {screen_name}.Stop()')
    script.raw(f'            textbutton _("下一首") action {screen_name}.Next()')
    script.raw(f'            textbutton _("上一首") action {screen_name}.Previous()')
    script.raw(f'            textbutton _("随机") action {screen_name}.RandomPlay()')
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
            "phone": "手机短信系统(收发消息/通知)",
            "inventory": "背包道具系统(物品/使用/槽位)",
            "music_room": "音乐室(解锁BGM播放)",
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






