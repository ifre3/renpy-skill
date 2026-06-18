"""
RenPyScript — Python 命令式生成 .rpy 代码

用法：
    script = RenPyScript()
    script.define("e", 'Character("Eileen", color="#c8ffc8")')
    script.label("start")
    script.scene("bg beach", with_="fade")
    script.show("eileen happy")
    script.say("e", "嘿，你醒了。")
    script.say(None, "阳光透过窗帘洒进来。")
    script.menu([
        ("你是谁？", "ask_who"),
        ("我饿了", "ask_food"),
    ])
    script.jump("end")

    script.label("end")
    script.say("e", "今天就到这里吧。")
    script.ret()

    print(script.render())       # 输出 .rpy 字符串
    script.write("script.rpy")   # 写入文件

参考：Ren'Py 8.5.3 Statement Equivalents (doc/statement_equivalents.html)
"""

import os
import textwrap

# 版本边界守卫 — 导入时自动检查 SDK 版本兼容性
import sys as _sys
_guard_path = os.path.dirname(os.path.abspath(__file__))
if _guard_path not in _sys.path:
    _sys.path.insert(0, _guard_path)
try:
    from _version_guard import check as _version_check, RENPY_MIN_STR as _RENPY_MIN_STR
except ImportError:
    _version_check = lambda: True
    _RENPY_MIN_STR = "8.0.0"


class RenPyScript:
    """Ren'Py 脚本代码生成器，链式 API。"""

    INDENT = "    "

    def __init__(self):
        self._lines = []        # list of (indent_level, code, is_python)
        self._indent = 0
        self._pending_indent = 0  # indent after next label/block

    # ── 基础操作 ──────────────────────────────────────────

    def _add(self, code: str, is_python: bool = False):
        lines = code.split("\n")
        for i, line in enumerate(lines):
            if i == 0:
                ind = self._indent
            else:
                ind = self._pending_indent if self._pending_indent > 0 else self._indent
            self._lines.append((ind, line, is_python))
        # reset pending indent after consumption
        if self._pending_indent > 0 and not is_python:
            pass  # keep pending for next line

    def _raw(self, code: str):
        """Add raw .rpy line (no indent, no prefix)."""
        self._add(code, is_python=False)

    def _py(self, code: str):
        """Add a Python line: $ code"""
        self._add(code, is_python=True)

    # ── 缩进上下文 ────────────────────────────────────────

    def _block(self):
        """Enter a block (increase indent)."""
        self._indent += 1

    def _end_block(self):
        """Exit a block (decrease indent)."""
        if self._indent > 0:
            self._indent -= 1

    # ── 页面 / 文件生命周期 ────────────────────────────────

    def init(self, priority: int = 0):
        """init block, optionally with priority."""
        if priority:
            self._raw(f"init {priority}:")
        else:
            self._raw("init:")
        self._block()
        return self

    def end_init(self):
        self._end_block()
        return self

    def label(self, name: str):
        """label <name>:"""
        self._raw(f"label {name}:")
        self._block()
        return self

    def end_label(self):
        self._end_block()
        return self

    # ── 声明 ──────────────────────────────────────────────

    def define(self, name: str, value: str):
        """define <name> = <value>"""
        self._raw(f"define {name} = {value}")
        return self

    def default(self, name: str, value: str):
        """default <name> = <value>"""
        self._raw(f"default {name} = {value}")
        return self

    def image(self, name: str, displayable: str):
        """image <name> = <displayable>"""
        self._raw(f"image {name} = {displayable}")
        return self

    def transform(self, name: str, atl_block: str):
        """transform <name>:\n  <atl_block>"""
        self._raw(f"transform {name}:")
        for line in atl_block.strip().split("\n"):
            self._raw(f"    {line}")
        return self

    def screen(self, name: str, body: str):
        """screen <name>:\n  <body> (indented)"""
        self._raw(f"screen {name}:")
        for line in body.strip().split("\n"):
            self._raw(f"    {line}")
        return self

    def style(self, name: str, parent: str = "", props: dict = None):
        """style <name> [is <parent>]:\n    <props>"""
        if parent:
            self._raw(f"style {name} is {parent}:")
        else:
            self._raw(f"style {name}:")
        self._block()
        if props:
            for k, v in props.items():
                self._raw(f"{k} {v}")
        self._end_block()
        return self

    # ── 角色 ──────────────────────────────────────────────

    def character(self, var_name: str, display_name: str, **kwargs) -> str:
        """Generate define <var_name> = Character(...), return the var_name for use."""
        args = [f'"{display_name}"']
        for k, v in kwargs.items():
            if isinstance(v, str):
                args.append(f'{k}="{v}"')
            else:
                args.append(f"{k}={v}")
        self.define(var_name, f"Character({', '.join(args)})")
        return var_name

    # ── 叙事 ──────────────────────────────────────────────

    def say(self, who: str | None, what: str):
        """<who> "<what>"  或  "<what>" (narration)
        who = None → narration (用 narrator)
        """
        if who is None or who == "":
            self._raw(f'"{what}"')
        else:
            self._raw(f'{who} "{what}"')
        return self

    def narrator(self, text: str):
        """narrator "<text>" (等价于 renpy.say(None, text))"""
        self._raw(f'"{text}"')
        return self

    def show(self, name: str, at: str = "", onlayer: str = "", as_: str = "", zorder: int = None, behind: list = None, atl: str = ""):
        """show <name> [at <transforms>] [onlayer <layer>] [as <tag>] [zorder <n>] [behind <tags>]"""
        parts = ["show", name]
        if at:
            parts.extend(["at", at])
        if onlayer:
            parts.extend(["onlayer", onlayer])
        if as_:
            parts.extend(["as", as_])
        if zorder is not None:
            parts.extend(["zorder", str(zorder)])
        if behind:
            parts.extend(["behind"] + behind)
        if atl:
            parts.extend(["at", atl])
        self._raw(" ".join(parts))
        return self

    def scene(self, name: str = "", with_: str = ""):
        """scene [<name>] [with <transition>]"""
        parts = ["scene"]
        if name:
            parts.append(name)
        if with_:
            parts.extend(["with", with_])
        self._raw(" ".join(parts))
        return self

    def hide(self, name: str):
        """hide <name>"""
        self._raw(f"hide {name}")
        return self

    def with_(self, transition: str):
        """with <transition>"""
        self._raw(f"with {transition}")
        return self

    def pause(self, duration: float = None):
        """pause [<duration>]"""
        if duration is not None:
            self._raw(f"pause {duration}")
        else:
            self._raw("pause")
        return self

    # ── 菜单 / 分支 ──────────────────────────────────────

    def menu(self, items: list):
        """
        显示菜单。items = [(label, target_or_none), ...]
        target_or_none = None 时当作 caption（不可选）
        """
        self._raw("menu:")
        self._block()
        for label, target in items:
            if target is None:
                self._raw(f'"{label}":')
            else:
                self._raw(f'"{label}":')
                self._block()
                self.jump(target)
                self._end_block()
        self._end_block()
        return self

    def menu_choice(self, label: str, target: str):
        """Single menu option shorthand."""
        return self.menu([(label, target)])

    def if_(self, condition: str):
        """if <condition>:"""
        self._raw(f"if {condition}:")
        self._block()
        return self

    def elif_(self, condition: str):
        """elif <condition>:"""
        self._end_block()
        self._raw(f"elif {condition}:")
        self._block()
        return self

    def else_(self):
        """else:"""
        self._end_block()
        self._raw("else:")
        self._block()
        return self

    def end_if(self):
        """End if/elif/else block."""
        self._end_block()
        return self

    # ── 控制流 ──────────────────────────────────────────

    def jump(self, target: str):
        """jump <target>"""
        self._raw(f"jump {target}")
        return self

    def call(self, target: str, *args, **kwargs):
        """call <target> [<args>] [<kwargs>]"""
        extra = ""
        if args:
            extra += " " + " ".join(str(a) for a in args)
        if kwargs:
            extra += " " + " ".join(f"{k}={v}" for k, v in kwargs.items())
        self._raw(f"call {target}{extra}")
        return self

    def ret(self):
        """return"""
        self._raw("return")
        return self

    # ── 音频 ──────────────────────────────────────────────

    def play(self, kind: str, file: str, loop: bool = False, fadein: float = None, fadeout: float = None):
        """
        play <music|sound|audio> <file> [loop] [fadein <n>] [fadeout <n>]
        """
        parts = ["play", kind, file]
        if loop:
            parts.append("loop")
        if fadein is not None:
            parts.extend(["fadein", str(fadein)])
        if fadeout is not None:
            parts.extend(["fadeout", str(fadeout)])
        self._raw(" ".join(parts))
        return self

    def stop(self, kind: str, fadeout: float = None):
        """stop <music|sound|audio> [fadeout <n>]"""
        parts = ["stop", kind]
        if fadeout is not None:
            parts.extend(["fadeout", str(fadeout)])
        self._raw(" ".join(parts))
        return self

    def queue(self, kind: str, file: str, loop: bool = False):
        """queue <music|sound|audio> <file> [loop]"""
        parts = ["queue", kind, file]
        if loop:
            parts.append("loop")
        self._raw(" ".join(parts))
        return self

    # ── Python 内联 ─────────────────────────────────────

    def py(self, code: str):
        """$ <code>"""
        self._raw(f"$ {code}")
        return self

    def python_block(self, code: str, hide: bool = False):
        """
        python [hide]:\n  <code>
        """
        self._raw(f"python{' hide' if hide else ''}:")
        self._block()
        for line in code.strip().split("\n"):
            self._raw(line)
        self._end_block()
        return self

    # ── 窗口 / 界面 ─────────────────────────────────────

    def window_show(self, trans: str = None):
        """window show [<trans>]"""
        if trans:
            self._raw(f"window show {trans}")
        else:
            self._raw("window show")
        return self

    def window_hide(self, trans: str = None):
        """window hide [<trans>]"""
        if trans:
            self._raw(f"window hide {trans}")
        else:
            self._raw("window hide")
        return self

    def window_auto(self):
        """window auto"""
        self._raw("window auto")
        return self

    # ── 测试 ──────────────────────────────────────────────

    def testcase(self, name: str):
        """testcase <name>:"""
        self._raw(f"testcase {name}:")
        self._block()
        return self

    def end_testcase(self):
        self._end_block()
        return self

    def assert_(self, condition: str):
        """assert <condition>"""
        self._raw(f"assert {condition}")
        return self

    # ── 实用辅助 ────────────────────────────────────────

    def comment(self, text: str):
        """# <text>"""
        for line in text.strip().split("\n"):
            self._raw(f"# {line}")
        return self

    def blank(self):
        """Blank line."""
        self._add("")
        return self

    def include(self, rpy_code: str):
        """Include raw .rpy code."""
        for line in rpy_code.strip().split("\n"):
            self._raw(line)
        return self

    # ── 高级模式方法 ────────────────────────────────────

    def affection_system(self, characters: list, tiers: int = 3, points_per_tier: int = 10):
        """
        Generate a complete affection system.
        characters = ["eileen", "lucy"]
        Creates vars, check labels, and a screen.

        Returns self for chaining.
        """
        # 定义变量
        self.comment("Affection System")
        for char in characters:
            for tier_name in ["points", "tier", "flag", "max_points"]:
                self.default(f"{char}_affection_{tier_name}", "0")
            self.default(f"{char}_affection_max_points", str(points_per_tier * tiers))

        # check 函数：自动升级
        self.py("")
        self.python_block("""
def check_affection(char):
    max_pt = globals()[f"{char}_affection_max_points"]
    pt = globals()[f"{char}_affection_points"]
    old_tier = globals()[f"{char}_affection_tier"]
    new_tier = min(int(pt / (max_pt / """ + str(tiers) + """)), """ + str(tiers) + """)
    if new_tier > old_tier:
        globals()[f"{char}_affection_tier"] = new_tier
        globals()[f"{char}_affection_flag"] = True
""".strip())
        return self

    def change_affection(self, char: str, delta: int, show_notify: bool = True):
        """Add or subtract affection points for a character."""
        self.py(f"{char}_affection_points = max(0, min({char}_affection_points + {delta}, {char}_affection_max_points))")
        self.py(f"check_affection('{char}')")
        if show_notify:
            self.py(f"renpy.notify('{char} 好感度变化: {delta:+d}')")
        return self

    def gallery_screen(self, name: str, images: list, cols: int = 2, rows: int = 2):
        """
        Generate an image gallery screen.
        images = [("bg_beach_unlock", "bg beach", "gallery_thumb_beach"), ...]
        """
        per_page = cols * rows
        self.comment(f"Gallery Screen: {name}")
        self.default(f"{name}_unlocked", "[]")
        self.default(f"{name}_page", "0")

        # unlock button
        self.py("")
        self.label(f"{name}_unlock_all")
        self.py(f"{name}_unlocked = [{', '.join(f'\"{img[0]}\"' for img in images)}]")
        self.ret()
        self.end_label()

        # screen
        self.screen(name, f"""
grid {cols} {rows}:
    spacing 10
    xalign 0.5 yalign 0.5
    for i in range({per_page}):
        $ idx = {name}_page * {per_page} + i
        if idx < len({name}_unlocked):
            imagebutton:
                idle {name}_unlocked[idx]
                action ShowMenu(...)
        else:
            null
textbutton "上一页" xalign 0.3 yalign 0.95 action SetVariable("{name}_page", max(0, {name}_page - 1))
textbutton "下一页" xalign 0.7 yalign 0.95 action SetVariable("{name}_page", min({name}_page + 1, {len(images)} // {per_page}))
""")
        return self

    # ── 渲染 ──────────────────────────────────────────────

    def render(self) -> str:
        """Generate the complete .rpy string."""
        result = []
        for indent, code, is_python in self._lines:
            ind = self.INDENT * indent
            line = code
            # Python line gets $ prefix at indentation level 0
            # (Within python blocks, it's already indented correctly)
            result.append(f"{ind}{line}")
        return "\n".join(result)

    def write(self, path: str, encoding: str = "utf-8"):
        """Write the rendered .rpy to a file."""
        content = self.render()
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding=encoding) as f:
            f.write(content)
        return path

    # ── 便捷工厂 ────────────────────────────────────────

    @classmethod
    def quick(cls, lines: list[str]) -> "RenPyScript":
        """
        Quick mode: pass a list of .rpy lines directly.
        Useful for simple scripts.
        """
        script = cls()
        for line in lines:
            script._raw(line)
        return script

    @classmethod
    def from_file(cls, path: str) -> "RenPyScript":
        """Read an existing .rpy file into a RenPyScript for editing."""
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return cls.quick(content.split("\n"))


# ── 命令行快速生成 ─────────────────────────────────────

def main():
    """CLI: python bridge.py <output.rpy>"""
    import sys

    script = RenPyScript()

    # 示例：生成一个带好感度系统的简短游戏开局
    script.comment("Generated by RenPyScript bridge")
    script.blank()
    script.define("config.name", '"我的故事"')
    script.define("config.version", '"0.1"')
    script.define("gui.init", "(1280, 720)")
    script.blank()

    # 角色
    e = script.character("e", "艾琳", color="#c8ffc8")
    l = script.character("l", "陆辰", color="#c8c8ff")

    # 好感度系统
    script.affection_system(["e", "l"])
    script.blank()

    # 游戏开始
    script.label("start")
    script.scene("bg classroom", with_="fade")
    script.show("eileen happy")
    script.with_("dissolve")
    script.say("l", "嘿，你听说了吗？")
    script.say("e", "听说什么？")
    script.menu([
        ("关于考试的事", "exam"),
        ("没什么，算了", "skip"),
    ])

    script.label("exam")
    script.change_affection("e", 5)
    script.say("l", "下周就要期中考了。")
    script.jump("end")

    script.label("skip")
    script.change_affection("e", -2)
    script.say("l", "好吧，那就不说了。")
    script.jump("end")

    script.label("end")
    script.say("e", "那我先走了。")
    script.ret()

    if len(sys.argv) > 1:
        path = script.write(sys.argv[1])
        print(f"✅ 已写入 {path}")
    else:
        print(script.render())


if __name__ == "__main__":
    main()
