"""
Ren'Py 项目脚手架 — 从 JSON schema 生成完整游戏项目

用法：
    scaffold = Scaffold("D:/projects/my_game")
    scaffold.from_json('{
        "name": "我的故事",
        "version": "0.1",
        "resolution": [1280, 720],
        "characters": [
            {"var": "e", "name": "艾琳", "color": "#c8ffc8", "image": "eileen"}
        ],
        "font": "SourceHanSansSC",
        "has_gallery": true,
        "languages": ["chinese"]
    }')
    scaffold.build()

或使用声明式 API：
    scaffold.set_name("我的故事")
         .set_resolution(1280, 720)
         .add_character("e", "艾琳", color="#c8ffc8")
         .build()
"""

import os
import json
import shutil
import sys as _sys

# 版本边界守卫
_guard_path = os.path.dirname(os.path.abspath(__file__))
if _guard_path not in _sys.path:
    _sys.path.insert(0, _guard_path)
try:
    from _version_guard import check as _version_check, RENPY_MIN_STR as _RENPY_MIN_STR
except ImportError:
    _version_check = lambda: True
    _RENPY_MIN_STR = "8.0.0"


class Scaffold:
    """Ren'Py 项目脚手架生成器。"""

    # 标准目录结构
    DIRS = ["game", "game/images", "game/audio", "game/video",
            "game/gui", "game/saves"]

    def __init__(self, project_dir: str):
        self.project_dir = os.path.abspath(project_dir)
        self.config = {
            "name": "Untitled",
            "version": "0.1",
            "resolution": (1280, 720),
            "gui_theme": "default",
            "characters": [],
            "font": None,
            "developer": True,
            "languages": [],
            "addons": [],
        }

    # ── 声明式 API ─────────────────────────────────────

    def set_name(self, name: str):
        self.config["name"] = name
        return self

    def set_version(self, version: str):
        self.config["version"] = version
        return self

    def set_resolution(self, width: int, height: int):
        self.config["resolution"] = (width, height)
        return self

    def set_font(self, font_name: str):
        self.config["font"] = font_name
        return self

    def add_character(self, var: str, display_name: str,
                      color: str = None, image: str = None):
        self.config["characters"].append({
            "var": var, "name": display_name,
            "color": color, "image": image,
        })
        return self

    def enable_developer(self, dev: bool = True):
        self.config["developer"] = dev
        return self

    def add_language(self, code: str):
        self.config["languages"].append(code)
        return self

    def add_addon(self, addon: str):
        self.config["addons"].append(addon)
        return self

    def from_json(self, json_str: str):
        """从 JSON 字符串加载配置。"""
        data = json.loads(json_str)
        for key in data:
            if key == "resolution":
                self.config["resolution"] = tuple(data["resolution"])
            elif key == "characters":
                self.config["characters"] = data["characters"]
            elif key in self.config:
                self.config[key] = data[key]
        return self

    def from_json_file(self, path: str):
        """从 JSON 文件加载配置。"""
        with open(path, "r", encoding="utf-8") as f:
            return self.from_json(f.read())

    # ── 文件生成 ───────────────────────────────────────

    def _mkdirs(self):
        """创建标准目录结构。"""
        for rel in self.DIRS:
            os.makedirs(os.path.join(self.project_dir, rel), exist_ok=True)

    def _generate_options_rpy(self) -> str:
        """生成 options.rpy"""
        config = self.config
        lines = [
            "## options.rpy — 项目基本配置",
            f"## 生成日期: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            f"define config.name = \"{config['name']}\"",
            f"define config.version = \"{config['version']}\"",
            "",
        ]

        if config.get("gui_theme"):
            lines.append(f"define gui.init({config['resolution'][0]}, {config['resolution'][1]})")
            lines.append("")

        if config.get("font"):
            lines.append(f"define gui.text_font = \"{config['font']}\"")
            lines.append(f"define gui.name_text_font = \"{config['font']}\"")
            lines.append(f"define gui.interface_text_font = \"{config['font']}\"")
            lines.append(f"define gui.button_text_font = \"{config['font']}\"")
            lines.append(f"define gui.choice_button_text_font = \"{config['font']}\"")
            lines.append("")

        if config.get("developer"):
            lines.append("define config.developer = True")
            lines.append("")

        lines.append(f"define config.save_directory = \"{config['name'].replace(' ', '-').lower()}-{config['version']}\"")
        lines.append("")
        lines.append("init python:")
        lines.append("    if renpy.android or renpy.ios:")
        lines.append("        config.developer = False")
        lines.append("")

        return "\n".join(lines)

    def _generate_characters_rpy(self) -> str:
        """生成 characters.rpy"""
        chars = self.config["characters"]
        if not chars:
            return "# (无角色定义)\n"

        lines = ["## characters.rpy — 角色定义", ""]
        for ch in chars:
            args = [f"Character(\"{ch['name']}\""]
            if ch.get("color"):
                args.append(f"color=\"{ch['color']}\"")
            if ch.get("image"):
                args.append(f"image=\"{ch['image']}\"")
            args[-1] = args[-1] + ")"
            line = f"define {ch['var']} = {', '.join(args)}"
            lines.append(line)

        lines.append("")
        return "\n".join(lines)

    def _generate_screens_rpy(self) -> str:
        """生成 screens.rpy 骨架。"""
        return """## screens.rpy — 界面定义
##
## 由脚手架生成，包含默认界面骨架。
## 完整 screen 定义参考 Ren'Py SDK doc/screens.html


screen navigation():
    vbox:
        style_prefix "navigation"
        xalign 0.5 yalign 0.5
        spacing 20

        textbutton "开始游戏" action Start()
        textbutton "读取存档" action ShowMenu("load")
        textbutton "设置" action ShowMenu("preferences")
        textbutton "关于" action ShowMenu("about")
        textbutton "退出" action Quit(confirm=False)


style navigation_button is gui_button
style navigation_button_text is gui_button_text

style navigation_button:
    size_group "navigation"
    xminimum 200
"""

    def _generate_script_rpy(self) -> str:
        """生成 script.rpy — 游戏主入口。"""
        return """## script.rpy — 游戏主脚本
##
## 从这里开始写你的故事。

label start:
    scene bg generic
    with fade

    "欢迎来到你的故事。"

    return
"""

    def _generate_gui_rpy(self) -> str:
        """生成 gui.rpy 骨架。"""
        return """## gui.rpy — GUI 配置
##
## GUI 数值由 gui.init() 自动计算。
## 参考 Ren'Py SDK doc/screens.html 及 tutorial 项目。
"""

    # ── 构建 ───────────────────────────────────────────

    def _generate_fault_tolerance_rpy(self) -> str:
        """生成 error_handling.rpy — 容错性配置。"""
        return """## error_handling.rpy — 容错性配置
## 基于 Ren'Py 8.5.3 官方文档自动生成

define config.developer = True

init python:
    # 1. 全局异常处理器 (doc/config.html)
    def _game_exception_handler(exception, traceback):
        msg = str(exception)
        for p in ["NameError","TypeError","KeyError","IndexError"]:
            if p in msg:
                renpy.notify("[风格] 遇到一个小问题，已自动跳过。")
                return True
        return False
    config.exception_handler = _game_exception_handler

    # 2. 存档加载失败跳转 (doc/config.html)
    config.load_failed_label = "load_failed"

    # 3. 缺失 label 兜底 (doc/config.html)
    def _missing_label(name):
        return "missing_label"
    config.missing_label_callback = _missing_label

    # 4. 缺失图片兜底 (doc/config.html)
    def _missing_image(name):
        return "bg placeholder"
    config.missing_image_callback = _missing_image

    # 5. 存档调试 (doc/config.html)
    config.save_dump = True

    # 6. 版本迁移 (renpy/common/00start.rpy)
    def _after_load():
        pass
    config.after_load_callbacks.append(_after_load)

label load_failed:
    "存档版本过旧，已重置到最新版本。"
    jump start

label missing_label:
    "剧情跳转到了一个尚未写好的部分。"
    jump start

label after_warp:
    "Warp 跳转模式 — 测试用。"
    return
"""

    def build(self) -> list:
        """生成完整项目骨架。返回生成的文件列表。"""
        self._mkdirs()

        files = {
            "game/options.rpy": self._generate_options_rpy(),
            "game/characters.rpy": self._generate_characters_rpy(),
            "game/screens.rpy": self._generate_screens_rpy(),
        }

        # 容错性配置（可选）
        if self.config.get("error_handler", True):
            files["game/error_handling.rpy"] = self._generate_fault_tolerance_rpy()
        created = []
        for rel, content in files.items():
            path = os.path.join(self.project_dir, rel)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            created.append(path)

        # addon scripts from self.config["addons"]
        for addon in self.config.get("addons", []):
            path = os.path.join(self.project_dir, "game", f"_{addon}.rpy")
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"## {addon} - 由脚手架生成\n")
            created.append(path)

        # language directories
        for lang in self.config.get("languages", []):
            os.makedirs(os.path.join(self.project_dir, "game", "tl", lang), exist_ok=True)

        return created

    def quickstart(self) -> list:
        """快速生成标准项目骨架（最小集）。"""
        mini = Scaffold(self.project_dir)
        mini.config = {
            "name": "MyGame",
            "version": "0.1",
            "resolution": (1280, 720),
            "gui_theme": "default",
            "characters": [],
            "developer": True,
            "languages": [],
            "addons": [],
        }
        return mini.build()


# ── CLI ─────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Ren'Py 项目脚手架")
    parser.add_argument("project_dir", help="项目输出目录")
    parser.add_argument("--json", help="JSON 配置文件路径")
    parser.add_argument("--name", default=None, help="游戏名称")
    parser.add_argument("--resolution", nargs=2, type=int, default=None,
                        help="分辨率 (宽 高)")
    parser.add_argument("--font", default=None, help="字体文件名")
    parser.add_argument("--quick", action="store_true", help="快速生成最小骨架")

    args = parser.parse_args()
    scaffold = Scaffold(args.project_dir)

    if args.quick:
        files = scaffold.quickstart()
    else:
        if args.json:
            scaffold.from_json_file(args.json)
        if args.name:
            scaffold.set_name(args.name)
        if args.resolution:
            scaffold.set_resolution(*args.resolution)
        if args.font:
            scaffold.set_font(args.font)
        files = scaffold.build()

    print(f"✅ 项目已创建: {args.project_dir}")
    for f in files:
        print(f"   📄 {f}")


if __name__ == "__main__":
    main()
