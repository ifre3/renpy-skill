"""
Ren'Py 脚本生成器 — 用 Python 链式 API 生成 .rpy 文件

基于 Ren'Py 8.5.3 官方 AST (renpy/ast.py) 支持的语句类型：
  Say, Label, Jump, Call, Return, Menu, Python, If/While 块
  Show, Scene, Hide, With, ShowLayer, Camera (renpy/ast.py)
  Play, Stop, Queue, Pause (renpy/common/00action_audio.rpy)
  Define, Default (renpy/ast.py: 类 Define/Default)
  Pass (renpy/ast.py: 类 Pass)

用法：
    s = RenPyScript()
    s.character("e", "Eileen", color="#c8ffc8")
    s.label("start")
    s.scene("bg cafe", with_="fade")
    s.say("e", "Welcome to the cafe!")
    s.menu([("Coffee", "coffee"), ("Tea", "tea")])
    s.call("check_weather")       # Call 子程序
    s.jump("ending")              # Jump 跳转
    s.write("game/script.rpy")

参考：Ren'Py 8.5.3 SDK — renpy/ast.py, renpy/statements.py
"""

import os
import re
from typing import Union, List, Tuple, Optional, Any


# ── 块管理辅助 ─────────────────────────────────────


class BlockScope:
    """管理缩进块的进入/退出。"""

    def __init__(self, script: "RenPyScript", end_marker: str = ""):
        self.script = script
        self.end_marker = end_marker

    def __enter__(self):
        self.script._indent_level += 1
        return self

    def __exit__(self, *args):
        self.script._indent_level -= 1
        if self.end_marker:
            self.script.line(self.end_marker)


class RenPyScript:
    """Ren'Py 脚本生成器。

    参考 Ren'Py 8.5.3 官方 AST 节点 (renpy/ast.py):
      Say, Label, Jump, Call, Return, Menu, Python, If, While,
      Show, Scene, Hide, With, ShowLayer, Camera, Pass,
      Define, Default, Image, Transform, Init
    """

    def __init__(self, indent: int = 4):
        """
        初始化脚本生成器。

        Args:
            indent: 缩进空格数（默认 4，符合 Ren'Py 官方规范）
        """
        self.lines: List[str] = []
        self._indent_level: int = 0
        self._indent_str: str = " " * indent
        self.errors: List[str] = []
        self.warnings: List[str] = []

    # ── 内部工具 ─────────────────────────────────────

    def _indent(self) -> str:
        """返回当前缩进字符串。"""
        return self._indent_str * self._indent_level

    def _escape_quotes(self, text: str) -> str:
        """
        转义文本中的引号，防止生成的 Ren'Py 代码语法错误。
        Ren'Py 使用双引号字符串，内部双引号必须转义。
        """
        return text.replace("\\", "\\\\").replace('"', '\\"')

    def _quote(self, text: str) -> str:
        """用双引号包裹文本（自动转义）。"""
        return '"' + self._escape_quotes(text) + '"'

    def line(self, code: str) -> "RenPyScript":
        """添加一行代码（自带缩进）。"""
        self.lines.append(self._indent() + code)
        return self

    def blank(self) -> "RenPyScript":
        """添加空行。"""
        self.lines.append("")
        return self

    def comment(self, text: str) -> "RenPyScript":
        """添加注释行。"""
        self.lines.append(self._indent() + "# " + text)
        return self

    # ── init 块 ──────────────────────────────────────

    def init(self, priority: int = 0, hide: bool = False) -> BlockScope:
        """
        开启 init 块（对应 AST: class Init）。

        Args:
            priority: 优先级（-9999 ~ 9999，官方默认 0）
            hide: 是否隐藏（init hide）

        参考：renpy/ast.py class Init
        """
        prefix = "init"
        if priority:
            prefix += f" {priority}"
        if hide:
            prefix += " hide"
        self.line(prefix + ":")
        return BlockScope(self)

    # ── Label 与流程控制 ──────────────────────────

    def label(self, name: str, hide: bool = False) -> BlockScope:
        """
        创建 label（对应 AST: class Label）。

        Args:
            name: label 名称
            hide: True 则生成 label hide 语句

        参考：renpy/ast.py class Label
        """
        prefix = "label" + (" hide" if hide else "")
        self.line(f"{prefix} {name}:")
        return BlockScope(self)

    def call(self, label: str, *args: str, pass_args: Optional[str] = None) -> "RenPyScript":
        """
        生成 call 语句（对应 AST: class Call）。

        Args:
            label: 目标 label 名
            pass_args: 可选，传递参数表达式，如 "score=100"

        参考：renpy/ast.py class Call
        """
        line = f"call {label}"
        if pass_args:
            line += f" pass ({pass_args})"
        if args:
            line += " " + " ".join(args)
        return self.line(line)

    def call_expression(self, expr: str) -> "RenPyScript":
        """
        生成 call expression 语句（运行时表达式求值跳转）。

        参考：renpy/ast.py class Call
        """
        return self.line(f"call expression {expr}")

    def jump(self, label: str) -> "RenPyScript":
        """
        生成 jump 语句（对应 AST: class Jump，无条件 GOTO）。

        Args:
            label: 目标 label 名

        参考：renpy/ast.py class Jump
        """
        return self.line(f"jump {label}")

    def jump_expression(self, expr: str) -> "RenPyScript":
        """
        生成 jump expression 语句（运行时表达式求值跳转）。
        """
        return self.line(f"jump expression {expr}")

    def return_(self) -> "RenPyScript":
        """
        生成 return 语句（对应 AST: class Return）。

        参考：renpy/ast.py class Return
        """
        return self.line("return")

    def pass_(self) -> "RenPyScript":
        """
        生成 pass 语句（对应 AST: class Pass，空操作）。

        参考：renpy/ast.py class Pass
        """
        return self.line("pass")

    # ── 条件与循环块 ──────────────────────────────

    def if_(self, condition: str) -> BlockScope:
        """
        开启 if 块（对应 AST: class If）。

        Args:
            condition: 条件表达式，如 "score >= 100"

        参考：renpy/ast.py class If
        """
        self.line(f"if {condition}:")
        return BlockScope(self)

    def elif_(self, condition: str) -> "RenPyScript":
        """elif 分支（必须在 if 块内）。"""
        self._indent_level -= 1
        self.line(f"elif {condition}:")
        self._indent_level += 1
        return self

    def else_(self) -> "RenPyScript":
        """else 分支（必须在 if 块内）。"""
        self._indent_level -= 1
        self.line("else:")
        self._indent_level += 1
        return self

    def endif(self) -> "RenPyScript":
        """关闭 if 块（缩进复位）。"""
        return self

    def while_(self, condition: str) -> BlockScope:
        """
        开启 while 循环块（对应 AST: class While）。

        Args:
            condition: 循环条件表达式

        参考：renpy/ast.py class While
        """
        self.line(f"while {condition}:")
        return BlockScope(self)

    # ── 对话 ─────────────────────────────────────────

    def say(self, who: Optional[str], what: str, interact: bool = True) -> "RenPyScript":
        """
        生成 say 语句（对应 AST: class Say）。

        Args:
            who: 角色变量名，None 为旁白
            what: 对话文本
            interact: True 则等待交互（默认）

        参考：renpy/ast.py class Say
        """
        text = self._quote(what)
        if who is None:
            return self.line(text)
        else:
            if interact:
                return self.line(f'{who} {text}')
            else:
                return self.line(f'{who} {text} nointeract')

    def extend(self, what: str) -> "RenPyScript":
        """
        生成 extend 语句（续接上一句对话）。
        """
        return self.line(self._quote(what))

    def menu(self, items: List[Tuple[str, str]], with_=None) -> "RenPyScript":
        """
        生成 menu 语句（对应 AST: class Menu）。

        Args:
            items: [(显示文本, 跳转label), ...]
            with_: 可选，转场效果

        参考：renpy/ast.py class Menu
        """
        self.line("menu:")
        self._indent_level += 1
        for caption, target in items:
            self.line(f'{self._quote(caption)}:')
            self._indent_level += 1
            self.line(f'jump {target}')
            self._indent_level -= 1
        if with_:
            self.line(f'with {with_}')
        self._indent_level -= 1
        return self

    # ── 角色 ─────────────────────────────────────────

    def character(self, var: str, name: str, kind: str = "character", **kwargs) -> "RenPyScript":
        """
        生成 define 角色语句。

        Args:
            var: 角色变量名
            name: 显示名称
            kind: Character 类型（默认 "character" → Character）
            **kwargs: 额外参数 (color, image, callback, ctc 等)

        参考：Ren'Py 8.5.3 — renpy/character.py
              Character 支持 color, who_color, what_color, image,
              callback, ctc, ctc_position, ctc_pause, cbs 等参数
        """
        kwargs_str = ""
        if kwargs:
            parts = [f'{k}={self._quote(str(v)) if isinstance(v, str) else str(v)}'
                     for k, v in kwargs.items()]
            kwargs_str = ", " + ", ".join(parts)

        if kind == "character":
            kind_str = "Character"
        else:
            kind_str = kind

        quoted_name = self._quote(name)
        return self.line(f'define {var} = {kind_str}({quoted_name}{kwargs_str})')

    # ── 场景与图片 ──────────────────────────────────

    def scene(self, img: str, with_: Optional[str] = None) -> "RenPyScript":
        """
        生成 scene 语句（对应 AST: class Scene，清除画面并显示背景）。

        Args:
            img: 图片名
            with_: 可选转场，如 "fade", "dissolve"

        参考：renpy/ast.py class Scene
        """
        line = f"scene {img}"
        if with_:
            self.line(line)
            return self.with_(with_)
        return self.line(line)

    def show(self, img: str, at: Optional[str] = None,
             onlayer: Optional[str] = None,
             as_name: Optional[str] = None,
             with_: Optional[str] = None) -> "RenPyScript":
        """
        生成 show 语句（对应 AST: class Show）。

        Args:
            img: 图片名（可包含属性，如 "eileen happy"）
            at: 可选，transform 名称
            onlayer: 可选，指定图层（如 "front", "overlay"）
            as_name: 可选，别名（如 show eileen as sister）
            with_: 可选，转场效果

        参考：renpy/ast.py class Show
        """
        line = f"show {img}"
        if at:
            line += f" at {at}"
        if onlayer:
            line += f" onlayer {onlayer}"
        if as_name:
            line += f" as {as_name}"
        self.line(line)
        if with_:
            return self.with_(with_)
        return self

    def show_expression(self, expr: str, at: Optional[str] = None,
                         onlayer: Optional[str] = None,
                         as_name: Optional[str] = None,
                         with_: Optional[str] = None) -> "RenPyScript":
        """
        生成 show expression 语句。

        Args:
            expr: Python 表达式，应为图片 displayable
            at: 可选，transform 名称
            onlayer: 可选，显示图层
            as_name: 可选，别名 tag
            with_: 可选，转场效果

        参考：renpy/ast.py class Show
        """
        line = f"show expression {expr}"
        if at:
            line += f" at {at}"
        if onlayer:
            line += f" onlayer {onlayer}"
        if as_name:
            line += f" as {as_name}"
        self.line(line)
        if with_:
            return self.with_(with_)
        return self

    def hide(self, img: str, with_: Optional[str] = None) -> "RenPyScript":
        """
        生成 hide 语句（对应 AST: class Hide）。

        Args:
            img: 图片 tag
            with_: 可选转场

        参考：renpy/ast.py class Hide
        """
        line = f"hide {img}"
        self.line(line)
        if with_:
            return self.with_(with_)
        return self

    def show_layer(self, layer: str, at: Optional[str] = None) -> "RenPyScript":
        """
        生成 show_layer 语句（对应 AST: class ShowLayer）。

        Args:
            layer: 图层名称
            at: 可选 transform

        参考：renpy/ast.py class ShowLayer
        """
        line = f"show_layer {layer}"
        if at:
            line += f" at {at}"
        return self.line(line)

    def camera(self, layer: str = "master", at: Optional[str] = None) -> "RenPyScript":
        """
        生成 camera 语句（对应 AST: class Camera，控制摄像机）。

        Args:
            layer: 图层名，默认 "master"
            at: 可选 transform

        参考：renpy/ast.py class Camera
        """
        line = f"camera {layer}"
        if at:
            line += f" at {at}"
        return self.line(line)

    def with_(self, transition: str) -> "RenPyScript":
        """
        生成 with 语句（对应 AST: class With，转场效果）。

        Args:
            transition: 转场名，如 "fade", "dissolve", "pixellate"

        参考：renpy/ast.py class With
        """
        return self.line(f"with {transition}")

    # ── Python 块 ────────────────────────────────────

    def python(self, code: str = "", hide: bool = False) -> "RenPyScript":
        """
        生成单行或多行 python 块（对应 AST: class Python）。

        Args:
            code: Python 代码（多行用 \\n 分隔）
            hide: True 则生成 python hide（不记录存档）

        参考：renpy/ast.py class Python
        """
        prefix = "python" + (" hide" if hide else "")
        if "\n" in code or not code.strip():
            self.line(f"{prefix}:")
            self._indent_level += 1
            for codeline in code.split("\n"):
                self.line(codeline)
            self._indent_level -= 1
        else:
            self.line(f"{prefix}:")
            self._indent_level += 1
            self.line(code)
            self._indent_level -= 1
        return self

    def early_python(self, code: str) -> "RenPyScript":
        """
        生成 early python 块（对应 AST: class EarlyPython，在解析早期执行）。

        参考：renpy/ast.py class EarlyPython
        """
        self.line("python early:")
        self._indent_level += 1
        for codeline in code.split("\n"):
            self.line(codeline)
        self._indent_level -= 1
        return self

    # ── 变量定义 ─────────────────────────────────────

    def define(self, var: str, value: str) -> "RenPyScript":
        """
        生成 define 语句（对应 AST: class Define，编译时常量）。

        Args:
            var: 变量名
            value: 值的表达式

        参考：renpy/ast.py class Define
        """
        return self.line(f"define {var} = {value}")

    def default(self, var: str, value: str) -> "RenPyScript":
        """
        生成 default 语句（对应 AST: class Default，存档持久化变量）。

        Args:
            var: 变量名
            value: 初始值表达式

        注意：修改 default 初始值不会影响已存在的存档
        参考：renpy/ast.py class Default
        """
        return self.line(f"default {var} = {value}")

    # ── 图片与 transform ─────────────────────────────

    def image(self, name: str, expr: str) -> "RenPyScript":
        """
        生成 image 语句（对应 AST: class Image）。

        Args:
            name: 图片名
            expr: 显示表达式，如 '"bg.png"'

        参考：renpy/ast.py class Image
        """
        return self.line(f"image {name} = {expr}")

    def transform(self, name: str, body: str) -> "RenPyScript":
        """
        生成 transform 语句（对应 AST: class Transform，ATL 变换）。

        Args:
            name: transform 名称
            body: ATL 定义体（多行用 \\n）

        参考：renpy/ast.py class Transform
        """
        self.line(f"transform {name}:")
        self._indent_level += 1
        for line in body.split("\n"):
            self.line(line)
        self._indent_level -= 1
        return self

    # ── 音频 ─────────────────────────────────────────

    def play(self, channel: str, file: str, **kwargs) -> "RenPyScript":
        """
        生成 play 语句（播放音频）。

        Args:
            channel: 频道名，如 "music", "sound", "voice"
            file: 音频文件路径
            **kwargs: 可选参数: loop, fadein, fadeout, volume 等

        参考：Ren'Py 8.5.3 — renpy/common/00action_audio.rpy class Play
              renpy/audio/audio.py renpy.music.play()
        """
        kw_str = " " + " ".join(f"{k} {v}" for k, v in kwargs.items()) if kwargs else ""
        return self.line(f"play {channel} {self._quote(file)}{kw_str}")

    def stop(self, channel: str) -> "RenPyScript":
        """
        生成 stop 语句（停止音频播放）。

        Args:
            channel: 频道名

        参考：renpy/common/00action_audio.rpy class Stop
        """
        return self.line(f"stop {channel}")

    def queue(self, channel: str, file: str) -> "RenPyScript":
        """
        生成 queue 语句（排队播放音频）。

        Args:
            channel: 频道名
            file: 音频文件

        参考：renpy/common/00action_audio.rpy class Queue
        """
        return self.line(f"queue {channel} {self._quote(file)}")

    # ── 其他控制 ─────────────────────────────────────

    def pause(self, delay: Optional[float] = None) -> "RenPyScript":
        """
        生成 pause 语句（暂停等待）。

        Args:
            delay: 秒数，None 等待用户点击
        """
        if delay is None:
            return self.line("pause")
        return self.line(f"pause {delay}")

    def window_show(self, transition: Optional[str] = None) -> "RenPyScript":
        """
        生成 window show 语句（显示对话窗口）。

        Args:
            transition: 可选转场

        参考：renpy/common/00window.rpy
        """
        line = "window show"
        if transition:
            line += f" {transition}"
        return self.line(line)

    def window_hide(self, transition: Optional[str] = None) -> "RenPyScript":
        """
        生成 window hide 语句（隐藏对话窗口）。
        """
        line = "window hide"
        if transition:
            line += f" {transition}"
        return self.line(line)

    def end(self) -> "RenPyScript":
        """
        添加结束注释标记（可选，仅用于可读性）。
        """
        return self.line("# end")

    # ── screen 定义 ──────────────────────────────────

    def _raw(self, code: str) -> "RenPyScript":
        """添加一行不加缩进的代码（旧 patterns 兼容）。"""
        self.lines.append(code)
        return self

    def screen(self, name: str, tag: Optional[str] = None) -> BlockScope:
        """
        开启 screen 定义块（对应 AST: class Screen）。

        Args:
            name: screen 名称
            tag: 可选，screen tag

        参考：renpy/ast.py class Screen
        """
        line = f"screen {name}"
        if tag:
            line += f" tag {tag}"
        self.line(line + ":")
        return BlockScope(self)

    def style(self, name: str, parent: Optional[str] = None) -> BlockScope:
        """
        开启 style 定义块（对应 AST: class Style）。

        Args:
            name: style 名称
            parent: 可选，父 style 名

        参考：renpy/ast.py class Style
        """
        line = f"style {name}"
        if parent:
            line += f" is {parent}"
        self.line(line + ":")
        return BlockScope(self)

    # ── 输出 ─────────────────────────────────────────

    def render(self) -> str:
        """返回生成的完整脚本字符串。自动执行基本语法验证，警告存入 self.warnings。"""
        text = "\n".join(self.lines)
        # 自动调用 validate()，结果存入 self.warnings
        self.warnings = []
        validation_errors = self.validate()
        for err in validation_errors:
            if err not in self.warnings:
                self.warnings.append(err)
        return text

    def write(self, path: str, exists_ok: bool = True, encoding: str = "utf-8") -> "RenPyScript":
        """
        将生成的脚本写入 .rpy 文件（UTF-8 编码）。

        Args:
            path: 输出文件路径
            exists_ok: 如果文件已存在，是否覆盖（True=覆盖+备份, False=抛异常）
            encoding: 编码（默认 utf-8，符合 Ren'Py 规范）

        Raises:
            FileExistsError: exists_ok=False 且文件已存在时
        """
        dir_name = os.path.dirname(path)
        if dir_name and not os.path.isdir(dir_name):
            os.makedirs(dir_name, exist_ok=True)
        if os.path.exists(path):
            if not exists_ok:
                raise FileExistsError(f"{path} 已存在。设置 exists_ok=True 覆盖，或使用其他路径。")
            # 备份已有文件
            import shutil
            bak = path + ".bak"
            shutil.copy2(path, bak)
        with open(path, "w", encoding=encoding) as f:
            f.write(self.render())
        return self

    def validate(self) -> List[str]:
        """
        基本语法验证：检查常见问题。

        Returns:
            错误消息列表（空列表 = 无错误）
        """
        errors = []
        text = self.render()

        for i, line in enumerate(text.split("\n"), 1):
            if line.count('"') % 2 != 0:
                errors.append(f"行 {i}: 引号未闭合 — {line.strip()}")

        labels = []
        for line in text.split("\n"):
            m = re.match(r'^\s*label\s+(\S+)\s*:', line)
            if m:
                labels.append(m.group(1))

        seen = set()
        for lbl in labels:
            if lbl in seen:
                errors.append(f"重复 label: {lbl}")
            seen.add(lbl)

        targets = set()
        for line in text.split("\n"):
            m = re.match(r'^\s*(?:jump|call)\s+(\S+)', line)
            if m and not m.group(1).startswith("expression"):
                targets.add(m.group(1))

        for t in targets:
            if t not in seen and not t.startswith("_"):
                errors.append(f"可能的悬空引用: {t} — 目标 label 不存在")

        return errors


# ── 便捷函数 ──────────────────────────────────────────


def demo_script() -> RenPyScript:
    """生成一个包含所有主要语句类型的示例脚本。"""
    s = RenPyScript()

    s.comment("Ren'Py 示例脚本 — 展示所有语句类型")
    s.comment("基于 Ren'Py 8.5.3 AST (renpy/ast.py)")
    s.blank()

    s.character("e", "Eileen", color="#c8ffc8")
    s.character("l", "Lucy", color="#c8c8ff")
    s.blank()

    s.define("config.name", '"My Game"')
    s.define("config.version", '"1.0"')
    s.blank()

    s.default("player_level", "1")
    s.default("gold", "100")
    s.blank()

    s.label("start")
    s.scene("bg cafe", with_="fade")
    s.show("eileen happy", with_="dissolve")
    s.say("e", "Hello! Welcome to our cafe!")
    s.say("l", "Would you like to see the menu?")
    s.menu([
        ("Yes, please!", "menu_yes"),
        ("Maybe later.", "menu_no"),
    ])
    s.blank()

    s.label("menu_yes")
    s.say("e", "Great choice!")
    s.pause(1.0)
    s.jump("ending")
    s.blank()

    s.label("menu_no")
    s.say("e", "Take your time!")
    s.blank()

    s.label("ending")
    s.say(None, "Let's check the weather...")
    s.call("check_weather", pass_args="season=\"spring\"")
    s.return_()
    s.blank()

    s.label("check_weather")
    s.say("e", "The weather is lovely today!")
    s.play("sound", "audio/bell.ogg")
    s.return_()
    s.blank()

    s.label("python_demo")
    s.python("""
gold += 50
player_level += 1
renpy.notify("Level up!")
""")
    s.say(None, "You leveled up!")
    s.blank()

    s.label("loop_demo")
    s.default("counter", "0")
    s.while_("counter < 3")
    s.say(None, "Looping...")
    s.python("counter += 1")
    s.say(None, "Done looping!")

    s.end()

    return s


# ── CLI ─────────────────────────────────────────────


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Ren'Py 脚本生成器（支持 Unicode 和引号转义）")
    parser.add_argument("--output", "-o", default="output.rpy",
                        help="输出文件路径")
    parser.add_argument("--demo", action="store_true",
                        help="生成示例脚本")
    parser.add_argument("--validate", action="store_true",
                        help="验证生成的脚本")

    args = parser.parse_args()

    if args.demo:
        s = demo_script()
        s.write(args.output)
        print(f"✅ 示例脚本已生成：{args.output}")

        if args.validate:
            errors = s.validate()
            if errors:
                print(f"⚠️  发现 {len(errors)} 个问题:")
                for e in errors:
                    print(f"   {e}")
            else:
                print("✅ 验证通过，未发现问题")
    else:
        print("使用 --demo 生成示例脚本")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
