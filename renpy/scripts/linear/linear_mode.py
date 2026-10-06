#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""linear_mode.py — Ren'Py 游戏线性模式分析 / 添加 / 修改工具

针对三类游戏提供不同入口:

  analyze <游戏目录>
      分析游戏是否内置线性模式（game_mode / get_event_list / 切换按钮等），
      统计剧情场景候选与导航标签，给出后续命令建议。

  add <游戏目录> [--force] [--min-says N] [--include LBL] [--exclude LBL] [--list FILE]
      给未内置线性模式的游戏（纯沙盒）生成 zzz_linear_mode.rpy 补丁:
        * 悬浮按钮: 仅一个 Linear 开关 (自动线性播放)
        * 自动线性播放: 场景结束进入导航标签时自动跳到下一个剧情场景
        * Shift+L 打开场景目录: 手动上一/下一/跳转、变量助手都在目录里
      UI 文本为英文（避免部分游戏无中文字体显示方块），注释为中文。

  modify <游戏目录> [--csv FILE] [--append-new] [--yes]
      针对已内置线性模式（get_event_list 事件表）的游戏:
        * 校验事件表: 表内事件标签是否存在、是否有 event_* 标签未入表
        * --csv 导出线性顺序
        * --append-new 把未入表的事件追加到列表尾部（带 .bak 备份）

游戏只发布 .rpyc 没有 .rpy 源码时，先用 setup/unrpyc.py 反编译再运行本工具。

用法示例:
    python linear_mode.py analyze "D:/games/MyGame-1.0-pc"
    python linear_mode.py add "D:/games/MyGame-1.0-pc"
    python linear_mode.py modify "D:/games/MyGame-1.0-pc" --csv events.csv
"""

import argparse
import datetime
import importlib.util
import keyword
import os
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TOOLS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_backup_module():
    """从 shared/backup.py 按路径加载，避免非 ASCII 包名导入问题。"""
    path = os.path.join(TOOLS_DIR, "shared", "backup.py")
    spec = importlib.util.spec_from_file_location("lm_backup_module", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


backup = _load_backup_module()

# ---------------------------------------------------------------------------
# 脚本解析
# ---------------------------------------------------------------------------

LABEL_RE = re.compile(r"^(\s*)label\s+([A-Za-z_]\w*)\s*(\([^)]*\))?\s*:")
IDENT_RE = re.compile(r"[A-Za-z_]\w*")
EVENT_DEF_RE = re.compile(r"^\s*(?:define|default)\s+([A-Za-z_]\w*)\s*=\s*Event\s*\(", re.M)

# Ren'Py 引擎特殊标签：永不作为剧情场景、永不重定向
SPECIAL_LABELS = {
    "start", "after_load", "quit", "main_menu", "before_main_menu",
    "splashscreen", "after_warp", "install", "_gallery", "_slideshow",
    "_confirm_screen",
}

# 明显的分支桩/小游戏内部标签（配合对话密度规则双保险）
STUB_PATTERNS = [
    r"^(yes|no|idk|maybe)\d*(cp\d+)?$",
    r"^goto\w*$",
    r"^target\w*$",
    r"\w*shotdone$",
    r"^\w+score$",
    r"\w*pageantend$",
    r"^\w*menu(\d+|cp\d+)?$",
    r"^\w+desire$",
    r"^(fav\w+|nofav|whythatquestion\w*)$",
]

# 这些目录/文件不参与解析
SKIP_DIRS = {"tl", "cache", "saves"}
SKIP_FILES_PREFIX = ("zzz_linear_mode")


class LabelInfo(object):
    __slots__ = ("name", "file", "line", "params", "says", "lines", "end")

    def __init__(self, name, file, line, params):
        self.name = name
        self.file = file
        self.line = line
        self.params = params
        self.says = 0
        self.lines = 0
        self.end = line

    @property
    def hint(self):
        return "%s:%d" % (os.path.basename(self.file), self.line)


def parse_game(game_dir):
    """解析 game/ 下所有 .rpy 的 label 定义与对话密度。

    返回 (labels: dict[name, LabelInfo], files: list[str], duplicates: list)
    """
    game_dir = os.path.normpath(game_dir)
    labels = {}
    duplicates = []
    rpy_files = []

    for root, dirs, files in os.walk(game_dir):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in files:
            if fn.lower().endswith(".rpy"):
                rpy_files.append(os.path.join(root, fn))

    rpy_files.sort()
    for path in rpy_files:
        base = os.path.basename(path)
        if base.startswith(SKIP_FILES_PREFIX):
            continue
        try:
            with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
                raw = fh.read()
        except OSError as exc:
            print("  [WARN] 无法读取 %s: %s" % (path, exc))
            continue

        lines = raw.splitlines()
        current = None
        body_says = 0
        body_lines = 0
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            m = LABEL_RE.match(line)
            if m and not stripped.startswith("#"):
                if current is not None:
                    current.says = body_says
                    current.lines = body_lines
                    current.end = i - 1
                name = m.group(2)
                info = LabelInfo(name, path, i, m.group(3))
                if name in labels:
                    duplicates.append((name, labels[name].hint, info.hint))
                else:
                    labels[name] = info
                current = info
                body_says = 0
                body_lines = 0
                continue
            if current is not None:
                body_lines += 1
                if stripped and not stripped.startswith("#"):
                    if stripped[0] in "\"'" or stripped.startswith("renpy.say"):
                        body_says += 1
        if current is not None:
            current.says = body_says
            current.lines = body_lines
            current.end = len(lines)

    return labels, rpy_files, duplicates


def file_sort_key(path):
    """script.rpy / scriptcp2.rpy 排最前并按章节号排序，其余按文件名。"""
    base = os.path.basename(path).lower()
    if base == "script.rpy":
        return (0, 0, base)
    m = re.match(r"^script(?:cp(\d+))?\.rpy$", base)
    if m:
        return (0, int(m.group(1) or 0) + 1, base)
    return (1, 0, base)


def is_stub(name):
    return any(re.match(p, name) for p in STUB_PATTERNS)


def classify(labels, min_says=4):
    """把标签分成 story / nav / special 三类。

    story: 剧情场景候选（对话密度达标、无参数、非桩/特殊标签）
    nav:   其余普通标签（自动跳过的目标）
    """
    story, nav = {}, {}
    for name in sorted(labels, key=lambda n: (file_sort_key(labels[n].file), labels[n].line)):
        info = labels[name]
        if name in SPECIAL_LABELS or name.startswith("_"):
            continue
        if info.params:
            nav[name] = info
            continue
        if is_stub(name):
            nav[name] = info
            continue
        if info.says >= min_says or (info.lines >= 40 and info.says >= 2):
            story[name] = info
        else:
            nav[name] = info
    return story, nav


def ordered_story(story):
    """按 (文件序, 行号) 排出线性顺序。"""
    return sorted(story.values(), key=lambda i: (file_sort_key(i.file), i.line))


# ---------------------------------------------------------------------------
# 线性机制检测
# ---------------------------------------------------------------------------

LINEAR_MARKERS = [
    ("game_mode 变量", re.compile(r"^\s*(default|define)\s+game_mode\b", re.M)),
    ("linear 模式判定", re.compile(r"[\"']linear[\"']")),
    ("get_event_list 事件表", re.compile(r"def\s+get_event_list\s*\(")),
    ("pick_event 驱动函数", re.compile(r"def\s+pick_event\s*\(")),
    ("模式切换按钮", re.compile(r"SetVariable\(\s*[\"']game_mode[\"']")),
    ("linear_mode 变量", re.compile(r"\blinear_mode\b")),
]


def detect_linear(game_dir, rpy_files):
    """返回 (hits: list[(名称, [file:line...])], event_list_file, event_ids)"""
    hits = {name: [] for name, _ in LINEAR_MARKERS}
    event_list_file = None
    event_ids = []

    for path in rpy_files:
        base = os.path.basename(path)
        if base.startswith(SKIP_FILES_PREFIX):
            continue
        try:
            with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
                text = fh.read()
        except OSError:
            continue

        for name, rx in LINEAR_MARKERS:
            found = False
            for m in rx.finditer(text):
                line_no = text.count("\n", 0, m.start()) + 1
                if name == "linear 模式判定":
                    # 只统计条件比较，忽略动画 transform 的 linear
                    ctx = text[max(0, m.start() - 30):m.start()]
                    if "==" not in ctx and "if " not in ctx:
                        continue
                hits[name].append("%s:%d" % (base, line_no))
                found = True
            if not found:
                hits[name] = hits[name]

        m = re.search(r"def\s+get_event_list\s*\(", text)
        if m and event_list_file is None:
            event_list_file = path
            block = find_event_list_block(path)
            if block:
                with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
                    lines = fh.read().splitlines()
                body = "\n".join(lines[block[0] - 1:block[1]])
                body = re.sub(r"#.*$", "", body, flags=re.M)
                seen = set()
                for token in IDENT_RE.findall(body):
                    if token not in seen and not keyword.iskeyword(token):
                        seen.add(token)
                        event_ids.append(token)

    return hits, event_list_file, event_ids


def build_event_map(game_dir):
    """扫描 define <var> = Event(id="...", ...) 定义, 返回 {变量名: (id, hint)}。

    事件表里引用的是 Event 对象变量, 真正的跳转标签是 Event 的 id。
    """
    event_map = {}
    for root, dirs, files in os.walk(os.path.normpath(game_dir)):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in sorted(files):
            if not fn.lower().endswith(".rpy") or fn.startswith(SKIP_FILES_PREFIX):
                continue
            path = os.path.join(root, fn)
            try:
                with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
                    text = fh.read()
            except OSError:
                continue
            for m in EVENT_DEF_RE.finditer(text):
                var = m.group(1)
                tail = text[m.start():m.start() + 3000]
                close = tail.find("\n)")
                if close == -1:
                    close = tail.find(")\n") + 1
                slice_ = tail[:close if close > 0 else 3000]
                idm = re.search(r'\bid\s*=\s*["\']([^"\']+)["\']', slice_)
                hint = "%s:%d" % (fn, text.count("\n", 0, m.start()) + 1)
                event_map[var] = (idm.group(1) if idm else None, hint)
    return event_map


def extract_router(game_dir, router_label):
    """从 <router_label> 标签体内提取 'if <cond>: / jump <label>' 路由链。

    沙盒游戏的剧情分发通常是路由标签开头一长串 if/jump; FF 快进按这张表
    逐日判定下一个剧情天。返回 [(cond, label), ...]，解析不到返回 []。
    """
    if_re = re.compile(r"^    if (.+):\s*$")
    jump_re = re.compile(r"^        jump ([A-Za-z_]\w*)\s*$")
    for root, dirs, files in os.walk(os.path.normpath(game_dir)):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in sorted(files):
            if not fn.lower().endswith(".rpy") or fn.startswith(SKIP_FILES_PREFIX):
                continue
            path = os.path.join(root, fn)
            try:
                with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
                    lines = fh.read().splitlines()
            except OSError:
                continue
            start = None
            for i, line in enumerate(lines):
                if re.match(r"^label\s+%s\s*[:(]" % re.escape(router_label), line):
                    start = i + 1
                    break
            if start is None:
                continue
            entries = []
            i = start
            while i < len(lines):
                line = lines[i]
                if line and not line[0].isspace():
                    break  # 回到顶层 = 标签结束
                m = if_re.match(line)
                if m:
                    j = i + 1
                    while j < len(lines) and not lines[j].strip():
                        j += 1
                    jm = jump_re.match(lines[j]) if j < len(lines) else None
                    if jm:
                        entries.append((m.group(1).strip(), jm.group(1)))
                        i = j + 1
                        continue
                i += 1
            return entries
    return []



# ---------------------------------------------------------------------------
# 子命令: analyze
# ---------------------------------------------------------------------------

def cmd_analyze(args):
    game_dir = resolve_game_dir(args.game_dir)
    print("=" * 62)
    print("线性模式分析: %s" % game_dir)
    print("=" * 62)

    labels, rpy_files, duplicates = parse_game(game_dir)
    if not rpy_files:
        print("[ERROR] 未找到 .rpy 源码。游戏只发布了 .rpyc 时，先运行:")
        print("        python scripts/unrpyc.py <游戏>/game")
        return 2

    story, nav = classify(labels, min_says=args.min_says)
    print("源码文件: %d 个 | 标签: %d 个 (重复: %d)" % (len(rpy_files), len(labels), len(duplicates)))
    print("场景候选: %d 个 | 导航/辅助标签: %d 个" % (len(story), len(nav)))

    hits, event_list_file, event_ids = detect_linear(game_dir, rpy_files)
    core = [n for n in hits if hits[n] and n != "linear 模式判定"]
    if len(core) >= 2 or event_ids:
        print("\n[+] 检测到已内置线性机制:")
        for name in core:
            locs = hits[name][:3]
            more = "" if len(hits[name]) <= 3 else " ...共 %d 处" % len(hits[name])
            print("    %-18s %s%s" % (name, ", ".join(locs), more))
        if event_list_file:
            print("    事件表: %s (%d 个事件)" % (os.path.basename(event_list_file), len(event_ids)))
        print("\n  结论: 游戏自带线性模式。用 modify 子命令校验/扩充事件表:")
        print("    python linear_mode.py modify \"%s\"" % game_dir)
    else:
        print("\n[-] 未检测到线性机制（纯沙盒/纯线性叙事）。")
        print("  可用 add 生成剧情目录补丁（悬浮按钮 + 顺序目录 + 自动跳过导航）:")
        print("    python linear_mode.py add \"%s\"" % game_dir)

    if duplicates:
        print("\n[WARN] 重复标签定义（Ren'Py 会告警，可能影响跳转）:")
        for name, a, b in duplicates[:8]:
            print("    %s: %s vs %s" % (name, a, b))

    seq = ordered_story(story)
    print("\n剧情场景顺序预览 (前 25 / 共 %d):" % len(seq))
    for i, info in enumerate(seq[:25], 1):
        print("  %3d. %-32s %s" % (i, info.name, info.hint))
    print("\n场景过少? 调整阈值: --min-says (默认 %d), 或用 --include 加入具体标签" % args.min_says)
    return 0


# ---------------------------------------------------------------------------
# 子命令: add
# ---------------------------------------------------------------------------

PATCH_TEMPLATE = r"""
## ============================================================================
## zzz_linear_mode.rpy — 线性模式 / 剧情目录补丁 (自动生成，可整体删除还原)
## 由 tools/linear/linear_mode.py 生成于 @DATE@
## 游戏: @GAME@
## 场景数: @COUNT@  (阈值 min_says=@MINSAYS@)
##
## 功能:
##   1. 屏幕右上角仅一个悬浮按钮: Linear = 线性模式开关
##   2. 开启后场景结束进入导航标签时, 自动跳到下一个剧情场景
##   3. Shift+L 打开场景目录: 手动上一/下一/跳转、变量助手 (补设 flag)
##
## 说明: 自动播放只重定向"顶层跳转"进入的导航标签; 场景内部 call 的子标签
##       不受影响。个别场景依赖未初始化的变量时, 用 Helper 补设后重跳。
## ============================================================================

default lm_overlay = True
default lm_auto = False
default lm_pos = 0
default lm_expr = ""

init -5 python:
    # (label, 来源提示) 的线性顺序表 — 想调整顺序/增删场景改这里即可
    LM_STORY = [
@STORY@
    ]
    LM_INDEX = {}
    for _i, (_lbl, _hint) in enumerate(LM_STORY):
        LM_INDEX[_lbl] = _i
    LM_STORY_SIZE = len(LM_STORY)
    # 永不重定向的引擎标签
    LM_PROTECT = set([
        "start", "after_load", "quit", "main_menu", "before_main_menu",
        "splashscreen", "_confirm_screen",
    ])

    # 剧情路由表 (linear_mode.py --router 从游戏路由标签的 if/jump 链提取):
    # (条件表达式, 目标标签) — FF 快进按此顺序判定下一个剧情天
    LM_ROUTER = [
@ROUTER@
    ]

    def lm_next_label():
        if renpy.store.lm_pos + 1 < LM_STORY_SIZE:
            return LM_STORY[renpy.store.lm_pos + 1][0]
        return None

    def lm_prev_label():
        if renpy.store.lm_pos - 1 >= 0:
            return LM_STORY[renpy.store.lm_pos - 1][0]
        return None

    def lm_in_call():
        # 处于 call 栈中说明是场景内部子流程, 不做重定向
        try:
            return bool(renpy.game.context().stack)
        except Exception:
            return False

    def lm_router_check():
        # 按游戏路由链顺序判定: 当前是否该进入某个剧情天, 返回标签或 None
        if not LM_ROUTER:
            return None
        ns = vars(renpy.store)
        for cond, lbl in LM_ROUTER:
            try:
                if eval(cond, ns):
                    return lbl
            except Exception:
                continue
        return None

    def lm_router_blocked():
        # 找出因缺失 flag 而卡住的剧情天: 把条件里的裸变量强制为 True 后
        # 条件能通过 = 只差这些变量。返回 (标签, [缺失变量]) 或 None
        if not LM_ROUTER:
            return None
        st = renpy.store
        import re as _lm_re
        for cond, lbl in LM_ROUTER:
            try:
                if eval(cond, vars(st)):
                    continue
            except Exception:
                continue
            idents = []
            for tok in _lm_re.findall(r"[A-Za-z_]\w*", cond):
                if tok in ("and", "or", "not", "True", "False", "totaldays", "day"):
                    continue
                if tok not in idents:
                    idents.append(tok)
            ns = dict(vars(st))
            forced = []
            for tok in idents:
                if not ns.get(tok):
                    ns[tok] = True
                    forced.append(tok)
            if not forced:
                continue
            try:
                if eval(cond, ns):
                    return (lbl, forced)
            except Exception:
                continue
        return None

    def lm_ff_to_story():
        # 快进到下个剧情天: 逐日推进日历 (等价于游戏 gotoX 的 totaldays+1 / 星期+1),
        # 每天先问路由链要不要触发剧情; 被缺 flag 卡住就停下提示 (Variable Helper 补)
        st = renpy.store
        for _ in range(120):
            lbl = lm_router_check()
            if lbl:
                renpy.jump(lbl)
                return
            blocked = lm_router_blocked()
            if blocked:
                renpy.notify("FF blocked at %s: set %s" % (blocked[0], ", ".join(blocked[1])))
                return
            st.totaldays = getattr(st, "totaldays", 1) + 1
            st.day = (getattr(st, "day", 1) % 7) + 1
        renpy.notify("FF: no story day within 120 days")

    # init 阶段也会触发 label 回调 (例: gui.init() -> call_in_new_context("_style_reset")
    # 执行 init label _style_reset), 那时 default 变量尚未建立, 直接读 st.lm_auto
    # 会抛 AttributeError 崩在启动。故所有 store 变量一律 getattr 兜底 + 整体 try。
    _lm_callback_warned = [False]

    def lm_label_callback(label, abnormal):
        try:
            st = renpy.store
            if getattr(st, "_in_replay", None):
                return
            if getattr(st, "main_menu", False):
                return
            idx = LM_INDEX.get(label)
            if idx is not None:
                # lm_pos 不存在 = 仍在 init 阶段, 不做任何写入
                if getattr(st, "lm_pos", None) is None:
                    return
                st.lm_pos = idx
                return
            if not getattr(st, "lm_auto", False):
                return
            if label in LM_PROTECT or label.startswith("_"):
                return
            if lm_in_call():
                return
            nxt = lm_next_label()
            if nxt and nxt != label:
                st.lm_pos = LM_INDEX[nxt]
                renpy.jump(nxt)
        except Exception:
            if not _lm_callback_warned[0]:
                _lm_callback_warned[0] = True
                try:
                    renpy.notify("Linear Mode: label callback error (ignored)")
                except Exception:
                    pass

    # 引擎版本自适应: Ren'Py 8.0+ 提供列表形式 config.label_callbacks,
    # 而 7.x (如 7.4.8) 只有单数 config.label_callback。
    # 旧版访问 label_callbacks 会抛 "not a known configuration variable" 直接崩在 init。
    try:
        config.label_callbacks.append(lm_label_callback)
    except Exception:
        _lm_prev_label_callback = config.label_callback
        if _lm_prev_label_callback is None:
            config.label_callback = lm_label_callback
        else:
            def _lm_label_callback_chain(label, abnormal):
                _lm_prev_label_callback(label, abnormal)
                lm_label_callback(label, abnormal)
            config.label_callback = _lm_label_callback_chain

    def lm_go(delta):
        lbl = lm_next_label() if delta > 0 else lm_prev_label()
        if lbl is None:
            renpy.notify("Linear Mode: no more scenes")
            return
        renpy.store.lm_pos = LM_INDEX[lbl]
        renpy.jump(lbl)

    def lm_run_expr():
        expr = (renpy.store.lm_expr or "").strip()
        if not expr:
            return
        try:
            exec(expr, vars(renpy.store))
            renpy.notify("OK: " + expr)
        except Exception as exc:
            renpy.notify("Error: %s" % exc)

    def lm_rows():
        # ("h", 标题) / ("s", label, 显示文本) — 目录按源文件分组
        rows = []
        last_file = None
        for i, (lbl, hint) in enumerate(LM_STORY):
            fname = hint.rsplit(":", 1)[0]
            if fname != last_file:
                last_file = fname
                rows.append(("h", "== %s ==" % fname))
            disp = "%d. %s   (%s)" % (i + 1, lbl, hint)
            if i == renpy.store.lm_pos:
                disp = "{color=#ffd166}{b}" + disp + "{/b}{/color}"
            rows.append(("s", lbl, disp))
        return rows

screen lm_overlay():
    zorder 100
    if not main_menu and lm_overlay:
        frame:
            xpos 0.99
            xanchor 1.0
            ypos 0.015
            background Solid("#000000a8")
            padding (8, 4)
            if lm_auto:
                textbutton "Linear: ON" action ToggleVariable("lm_auto") text_size 16 text_color "#ffd166"
            else:
                textbutton "Linear: OFF" action ToggleVariable("lm_auto") text_size 16 text_color "#aaaaaa"
        key "shift_K_l" action Show("lm_directory")

screen lm_directory():
    modal True
    zorder 101
    add Solid("#000000e6")
    frame:
        xalign 0.5
        yalign 0.5
        xmaximum 1200
        ysize 820
        background Solid("#101014f5")
        padding (24, 18)
        vbox:
            spacing 10
            # Ren'Py 的 [] 插值不支持算术表达式 ([lm_pos+1] 会 NameError), 先算好再直接传给 text
            $ lm_dir_title = "Linear Mode — Scene Directory " + str(lm_pos + 1) + "/" + str(LM_STORY_SIZE)
            text lm_dir_title size 30 color "#ffd166"
            hbox:
                spacing 14
                textbutton "Next Scene" action Function(lm_go, 1)
                textbutton "Prev Scene" action Function(lm_go, -1)
                if LM_ROUTER:
                    textbutton "FF >>" action Function(lm_ff_to_story)
                if lm_auto:
                    textbutton "Linear: ON" action ToggleVariable("lm_auto") text_color "#ffd166"
                else:
                    textbutton "Linear: OFF" action ToggleVariable("lm_auto")
                textbutton "Variable Helper" action Show("lm_helper")
                textbutton "Close" action Hide("lm_directory")
            viewport id "lm_vp":
                mousewheel True
                scrollbars "vertical"
                yfill True
                vbox:
                    spacing 2
                    for row in lm_rows():
                        if row[0] == "h":
                            text row[1] size 20 color "#7f8fa6" yoffset 8
                        else:
                            textbutton row[2]:
                                action [Jump(row[1]), Hide("lm_directory")]
                                background "#00000000"
                                hover_background "#2d3436"
                                text_size 20
                                xfill True
                                xpadding 8

screen lm_helper():
    modal True
    zorder 102
    add Solid("#000000d9")
    frame:
        xalign 0.5
        yalign 0.5
        xmaximum 1000
        background Solid("#101014f5")
        padding (24, 18)
        vbox:
            spacing 10
            text "Variable Helper — 在 store 里执行 python 赋值" size 26 color "#ffd166"
            text "例: some_flag = True    day122 = True    c_lisa_love = 10" size 20 color "#aaaaaa"
            input default "" value VariableInputValue("lm_expr") length 200
            hbox:
                spacing 14
                textbutton "Run" action [Function(lm_run_expr), SetVariable("lm_expr", "")]
                textbutton "Close" action Hide("lm_helper")

init python:
    config.overlay_screens.append("lm_overlay")
"""


def resolve_game_dir(path):
    """接受项目根目录或 game/ 目录，统一返回 game 目录。"""
    path = os.path.normpath(os.path.abspath(path))
    if os.path.isdir(os.path.join(path, "game")):
        return os.path.join(path, "game")
    return path


def cmd_add(args):
    game_dir = resolve_game_dir(args.game_dir)
    if not os.path.isdir(game_dir):
        print("[ERROR] 目录不存在: %s" % game_dir)
        return 2

    out_path = os.path.join(game_dir, args.out or "zzz_linear_mode.rpy")
    if os.path.exists(out_path) and not args.force:
        print("[ERROR] 补丁已存在: %s (覆盖请加 --force, 会先做 .bak 备份)" % out_path)
        return 2

    labels, rpy_files, duplicates = parse_game(game_dir)
    if not rpy_files:
        print("[ERROR] 未找到 .rpy 源码; 先用 scripts/unrpyc.py 反编译 .rpyc")
        return 2

    hits, event_list_file, event_ids = detect_linear(game_dir, rpy_files)
    core = [n for n in hits if hits[n] and n != "linear 模式判定"]
    if (len(core) >= 2 or event_ids) and not args.force:
        print("[ERROR] 该游戏已内置线性机制 (%s); 直接用 modify 校验/扩充。" % ", ".join(core))
        print("        确认要额外叠加目录补丁时, 加 --force")
        return 2

    story, nav = classify(labels, min_says=args.min_says)
    story_map = {i.name: i for i in story.values()}

    include = [x.strip() for x in (args.include or []) if x.strip()]
    exclude = set(x.strip() for x in (args.exclude or []) if x.strip())
    for name in include:
        if name not in labels:
            print("[ERROR] --include 的标签不存在: %s" % name)
            return 2
        story_map[name] = labels[name]
    for name in exclude:
        story_map.pop(name, None)

    if args.list:
        seq = []
        with open(args.list, "r", encoding="utf-8-sig") as fh:
            for line in fh:
                line = re.sub(r"#.*$", "", line).strip()
                if not line:
                    continue
                name = line.split()[0]
                if name not in labels:
                    print("[ERROR] --list 中的标签不存在: %s" % name)
                    return 2
                seq.append(labels[name])
        if not seq:
            print("[ERROR] --list 文件为空: %s" % args.list)
            return 2
    else:
        seq = ordered_story(story_map)

    if not seq:
        print("[ERROR] 场景候选为空; 降低 --min-says (当前 %d) 或用 --include 指定标签" % args.min_says)
        return 2

    story_lines = "\n".join(
        '        ("%s", "%s"),' % (info.name, info.hint) for info in seq
    )

    router_block = ""
    if args.router:
        router_entries = extract_router(game_dir, args.router)
        if not router_entries:
            print("[ERROR] 未在 label %s 中找到 if/jump 路由链" % args.router)
            return 2
        router_block = "".join("        (%r, %r),\n" % (c, l) for c, l in router_entries)

    patch = (
        PATCH_TEMPLATE
        .replace("@DATE@", datetime.date.today().isoformat())
        .replace("@GAME@", os.path.basename(os.path.dirname(game_dir)))
        .replace("@COUNT@", str(len(seq)))
        .replace("@MINSAYS@", str(args.min_says))
        .replace("@STORY@", story_lines)
        .replace("@ROUTER@", router_block)
    )

    if os.path.exists(out_path):
        backup.create_bak(out_path)
    backup.atomic_write_text(out_path, patch, encoding="utf-8", newline="\n")

    print("=" * 62)
    print("已生成线性模式补丁: %s" % out_path)
    print("场景: %d 个 | 导航标签(自动跳过目标): %d 个 | 阈值 min_says=%d"
          % (len(seq), len(nav), args.min_says))
    if args.router:
        n_router = len([1 for l in router_block.splitlines() if l.strip()])
        print("剧情路由链: %d 条 (来自 label %s)" % (n_router, args.router))
    print("-" * 62)
    print("游戏内用法:")
    print("  1. 启动/读档进入游戏, 右上角只有一个悬浮按钮: Linear = 线性模式开关")
    print("  2. 开启 Linear 后, 场景结束会自动跳进下一个剧情场景, 跳过地图/日程导航")
    print("  3. 跳转后报变量缺失时, 按 Shift+L 打开目录, 用 Variable Helper 补设 flag 再跳")
    print("  4. Shift+L 随时打开场景目录 (手动上一/下一/跳转)")
    if args.router:
        print("  5. 目录里的 FF >> = 快进到下个剧情天: 自动逐日推进日历跳过日常,")
        print("     被前置 flag 卡住时会提示缺哪个变量 (Variable Helper 补后再按)")
    print("-" * 62)
    print("微调: 直接编辑 %s 里的 LM_STORY 列表 (顺序/增删)" % os.path.basename(out_path))
    print("还原: 删除该文件即可, 不改动任何原游戏脚本")
    return 0


# ---------------------------------------------------------------------------
# 子命令: modify
# ---------------------------------------------------------------------------

def find_event_list_block(path):
    """定位 get_event_list 的 return [ ... ] 行号范围。返回 (start_line, end_line) 或 None"""
    with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
        lines = fh.read().splitlines()
    start = None
    for i, line in enumerate(lines, 1):
        if re.search(r"def\s+get_event_list\s*\(", line):
            start = i
            break
    if start is None:
        return None
    ret = None
    for j in range(start - 1, min(start + 30, len(lines))):
        if re.search(r"return\s*\[", lines[j]):
            ret = j
            break
    if ret is None:
        return None
    # 与 return [ 同缩进的 ']' 即列表结束
    indent = len(lines[ret]) - len(lines[ret].lstrip())
    for k in range(ret + 1, len(lines)):
        stripped = lines[k].strip()
        if stripped.startswith("]") and (len(lines[k]) - len(lines[k].lstrip())) == indent:
            return (ret + 1, k + 1)  # 1-based: 内容行范围(含)
    return None


def cmd_modify(args):
    game_dir = resolve_game_dir(args.game_dir)
    labels, rpy_files, duplicates = parse_game(game_dir)
    if not rpy_files:
        print("[ERROR] 未找到 .rpy 源码; 先用 scripts/unrpyc.py 反编译 .rpyc")
        return 2

    hits, event_list_file, event_ids = detect_linear(game_dir, rpy_files)
    if not event_ids:
        print("[ERROR] 未找到 get_event_list 事件表; 该游戏可能不适合 modify,")
        print("        纯沙盒游戏请用 add 生成剧情目录补丁")
        return 2

    print("=" * 62)
    print("线性模式校验: %s" % game_dir)
    print("=" * 62)
    print("事件表: %s (%d 个条目)" % (os.path.relpath(event_list_file, game_dir), len(event_ids)))

    # 表条目是 Event 对象变量; 跳转标签 = Event(id=...) 的 id
    event_map = build_event_map(game_dir)
    order = []          # (变量名, id, hint)
    unknown = []        # 表里引用但找不到 Event 定义的变量
    for var in event_ids:
        if var in event_map:
            order.append((var, event_map[var][0], event_map[var][1]))
        else:
            unknown.append(var)
    if unknown:
        print("[WARN] %d 个表内变量没有 Event() 定义 (非事件对象或定义缺失):" % len(unknown))
        for var in unknown[:10]:
            print("    %s" % var)

    missing = [(var, eid) for var, eid, _ in order if not eid or eid not in labels]
    if missing:
        print("\n[ERROR] %d 个事件的跳转标签未找到定义 (线性模式跑到会崩溃):" % len(missing))
        for var, eid in missing[:15]:
            print("    %s -> label '%s'" % (var, eid or "?"))
        if len(missing) > 15:
            print("    ... 共 %d 个" % len(missing))
    else:
        print("[OK] 事件表内所有跳转标签都有定义")

    listed = set(var for var, _, _ in order)
    unlisted = []
    for var in sorted(event_map, key=lambda v: event_map[v][1]):
        if var not in listed:
            eid, hint = event_map[var]
            unlisted.append((var, eid, hint))

    if unlisted:
        print("\n[WARN] %d 个事件对象未进事件表 (线性模式永远不会触发):" % len(unlisted))
        for var, eid, hint in unlisted:
            print("    %-36s id=%-28s %s" % (var, eid or "?", hint))
        print("  追加到表尾: python linear_mode.py modify \"%s\" --append-new" % args.game_dir)
    else:
        print("[OK] 没有 Event 对象遗漏出表")

    for name in ("game_mode 变量", "模式切换按钮"):
        if hits[name]:
            print("[OK] %s: %s" % (name, ", ".join(hits[name][:2])))

    if args.csv:
        rows = ["order,event_var,event_id,label_defined,event_def_location"]
        for i, (var, eid, hint) in enumerate(order, 1):
            ok = eid and eid in labels
            rows.append("%d,%s,%s,%s,%s" % (i, var, eid or "?", "yes" if ok else "NO", hint))
        for var, eid, hint in unlisted:
            rows.append(",%s,%s,no,%s" % (var, eid or "?", hint))
        with open(args.csv, "w", encoding="utf-8-sig", newline="") as fh:
            fh.write("\n".join(rows) + "\n")
        print("\n已导出: %s" % args.csv)

    if args.append_new:
        if not unlisted:
            print("\n[OK] 无需追加: 所有 Event 对象都已在事件表中")
            return 0
        block = find_event_list_block(event_list_file)
        if block is None:
            print("[ERROR] 未能定位 get_event_list 的 return [ ... ] 范围")
            return 2
        with open(event_list_file, "rb") as fh:
            raw = fh.read()
        newline = "\r\n" if b"\r\n" in raw else "\n"
        with open(event_list_file, "r", encoding="utf-8-sig", errors="replace") as fh:
            lines = fh.read().splitlines()

        end_line = block[1]  # 1-based, ']' 所在行
        insert_at = end_line - 1
        indent = "      "
        added = [indent + "# appended by linear_mode.py %s" % datetime.date.today().isoformat()]
        for var, eid, hint in unlisted:
            added.append("%s%s," % (indent, var))
        lines[insert_at:insert_at] = added

        if not args.yes:
            print("\n将向 %s 的列表尾部追加 %d 个事件:" % (
                os.path.relpath(event_list_file, game_dir), len(unlisted)))
            for var, eid, hint in unlisted:
                print("    %s (id=%s, %s)" % (var, eid or "?", hint))
            ans = input("确认追加? [y/N] ").strip().lower()
            if ans != "y":
                print("已取消, 未写入")
                return 1

        backup.create_bak(event_list_file)
        backup.atomic_write_text(
            event_list_file, "\n".join(lines) + "\n",
            encoding="utf-8", newline=newline)
        print("[OK] 已追加 %d 个事件 (原文件备份为 .bak)" % len(unlisted))
    return 0


# ---------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Ren'Py 线性模式分析/添加/修改工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例:\n"
               "  python linear_mode.py analyze MyGame-1.0-pc\n"
               "  python linear_mode.py add MyGame-1.0-pc --min-says 3\n"
               "  python linear_mode.py modify MyGame-pc --csv events.csv\n",
    )
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("analyze", help="分析线性机制与场景结构")
    p.add_argument("game_dir")
    p.add_argument("--min-says", type=int, default=4, help="场景判定对话行数阈值 (默认 4)")
    p.set_defaults(func=cmd_analyze)

    p = sub.add_parser("add", help="为纯沙盒游戏生成线性模式补丁")
    p.add_argument("game_dir")
    p.add_argument("--out", default="zzz_linear_mode.rpy", help="输出文件名 (game/ 下)")
    p.add_argument("--min-says", type=int, default=4, help="场景判定对话行数阈值 (默认 4)")
    p.add_argument("--include", action="append", help="强制纳入的标签 (可多次)")
    p.add_argument("--exclude", action="append", help="强制排除的标签 (可多次)")
    p.add_argument("--list", help="用文本文件指定场景顺序 (每行一个 label, # 后为注释)")
    p.add_argument("--router", help="从该 label 提取 if/jump 剧情路由链, 启用 FF >> 快进 (例: schoolmorning)")
    p.add_argument("--force", action="store_true", help="覆盖已有补丁/无视已检测到线性机制")
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("modify", help="校验/扩充已有线性事件表")
    p.add_argument("game_dir")
    p.add_argument("--csv", help="导出线性顺序 CSV 路径")
    p.add_argument("--append-new", action="store_true", help="把未入表的 event_* 标签追加到表尾")
    p.add_argument("--yes", action="store_true", help="跳过追加确认")
    p.set_defaults(func=cmd_modify)

    args = ap.parse_args(argv)
    if not getattr(args, "func", None):
        ap.print_help()
        return 0
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
