# -*- coding: utf-8 -*-
"""门面注册表：检查器元数据从各脚本自己的 CHECKER 读取，不再手写 TOOL_DESC。

为什么（2026-10-06，见 shared/base_checker.py docstring）：
门面过去有两张手写表——TOOL_SCRIPTS（34 项 子命令→路径）与 TOOL_DESC（34 项
描述），外加两个硬编码集合 NEEDS_TL_DIR / TL_DIR_TOOLS。它们会漂且漂了不报错：
`check_i18n.py` 漏声明 `-l`，而 `all` 把 `-l` 原样转发给每个检查器，于是它在任何
项目上都撞 argparse rc=2、被门面归一成失败项，`all` 恒定返回 1（假阳性）。

现在：检查器的 name / summary / takes / requires_tl 由各脚本自己的 CHECKER 声明，
门面只保留"子命令名 → 脚本路径"这一层映射（路径是文件系统的客观事实，不该由脚本
自报）。写入类工具（fix_* / setup_* / linear / unrpyc）没有检查器契约，仍走手写描述，
但集中在一张表里，且新增项由 test_registrations 断言齐全。
"""

import importlib
import os
import sys

#: scripts/ 根目录（本文件在 shared/ 下，故取上级）
TOOLS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SHARED_DIR = os.path.join(TOOLS_DIR, "shared")
if _SHARED_DIR not in sys.path:
    sys.path.insert(0, _SHARED_DIR)

from base_checker import TL_DIR  # noqa: E402

#: 子命令名 → 脚本路径。路径是文件系统事实，故仍在此声明；脚本不在本表里。
TOOL_SCRIPTS = {
    # ── 检查器（name/summary/takes/requires_tl 由脚本自己的 CHECKER 提供）──
    "ui": os.path.join("checks", "check_ui_text.py"),
    "misuse": os.path.join("checks", "check_translation_misuse.py"),
    "func": os.path.join("checks", "check_func_text.py"),
    "auto": os.path.join("checks", "check_auto_trans.py"),
    "duplicate": os.path.join("checks", "check_duplicate_translations.py"),
    "button": os.path.join("checks", "check_button_missing_translation.py"),
    "label": os.path.join("checks", "check_label_issues.py"),
    "type": os.path.join("checks", "check_type_safety.py"),
    "lint": os.path.join("checks", "lint_check.py"),
    "integrity": os.path.join("checks", "check_translation_integrity.py"),
    "untranslated": os.path.join("checks", "check_untranslated.py"),
    "charname": os.path.join("checks", "check_charname_translation.py"),
    "crash": os.path.join("checks", "check_crash_risks.py"),
    "fontcheck": os.path.join("checks", "check_fonts.py"),
    "langcheck": os.path.join("checks", "check_i18n.py"),
    "typography": os.path.join("checks", "check_typography.py"),
    "tlcheck": os.path.join("checks", "tl_check.py"),
    "fmtlint": os.path.join("checks", "lint_rpy.py"),
    # 覆盖对照：untranslated 只扫 tl 内部，看不见「源脚本没有译文文件」的缺口
    "tlcoverage": os.path.join("checks", "check_tl_coverage.py"),
    # 载荷体检：只为没有 tl 目录的第三方机翻而生（requires_tl=False 是刻意的）。
    "payloadscan": os.path.join("checks", "check_payload.py"),
    # ── 写入/修补类（非检查器，无契约）──
    "namebox": os.path.join("translate", "sync_namebox_translation.py"),
    "fixtags": os.path.join("translate", "fix_missing_tags.py"),
    "fixcomments": os.path.join("translate", "fix_translation_comments.py"),
    "patchsay": os.path.join("translate", "patch_renpy_say.py"),
    "linear": os.path.join("linear", "linear_mode.py"),
    "i18n": os.path.join("setup", "setup_i18n.py"),
    "lang": os.path.join("setup", "switch_default_language.py"),
    "fonts": os.path.join("setup", "add_fonts.py"),
    "langbtn": os.path.join("setup", "fix_lang_button.py"),
    "perfpanel": os.path.join("setup", "add_performance_panel.py"),
    "rmsuffix": os.path.join("setup", "remove_translated.py"),
    "urm": os.path.join("setup", "urm_install.py"),
    "unrpyc": os.path.join(".", "unrpyc.py"),
    "tablet": os.path.join("setup", "patch_android_tablet.py"),
    "optimize": os.path.join("sdk", "optimize_assets.py"),
    # ── 润色编排（写批次 JSON/提示词/账本到 -o 目录，不改 tl 文件本身）──
    "polish": os.path.join("polish", "plan_batches.py"),
}

#: 非检查器工具的描述（检查器的描述来自 CHECKER.summary，不在此重复）
TOOL_DESC = {
    "lint": "调用 SDK lint 和翻译专项检查",
    "namebox": "同步角色名字框翻译（按术语表）",
    "fixtags": "尝试修复丢失的文本标签（低置信度只生成人工清单）",
    "fixcomments": "翻译注释中的术语反向恢复为英文原文",
    "patchsay": "修补 renpy.say() 硬编码英文（按 translate/renpy_say_replacements.csv）",
    "linear": "线性模式: analyze 分析 / add 生成补丁 / modify 校验事件表",
    "i18n": "多语言初始化（重构版，位于 setup/setup_i18n.py）",
    "lang": "切换默认语言（需先跑 i18n）",
    "fonts": "添加字体（需先跑 i18n 生成 fonts_common.rpy）",
    "langbtn": "修复语言按钮写死/缺目标语言项（默认试运行，--apply 写入）",
    "perfpanel": "添加/移除性能浮层（--remove）",
    "rmsuffix": "移除文件名 _translated 重复后缀",
    "urm": "URM 安装/卸载/体检（不代下载，--apply 才落盘）",
    "unrpyc": "下载 unrpyc 并反编译 .rpyc",
    "tablet": "安卓平板变体强制补丁（需拷入 SDK 内运行）",
    "optimize": "批量压缩图片/音频（全量降级时退出码 1，见 --help）",
    "polish": "润色批次规划：场景感知切批 + 提示词 + 账本（写到 -o，不碰 tl）",
}

#: all 的执行顺序（分组只影响 `list` 的展示与 all 的先后，不影响正确性）
CHECK_GROUP = ["ui", "misuse", "func", "auto", "charname"]
CRASH_GROUP = ["crash"]
# 字体/多语言链路测试：只读、吃 <项目>，无 tl 目录时自动降级为提示
I18N_GROUP = ["fontcheck", "langcheck"]
# tl 翻译文件质检（三级报告）。历史上住在 sdk/ 且未注册，导致 all 拿不到它；
# 2026-10-12 移入 checks/ 并纳入 all。
# fmtlint 是 tl 文件的「格式层」lint（引号/块ID/行尾/缩进/超长行/长度比），
# 与 tlcheck 的「语义层」（标签结构/插值/转义/崩溃级）互补；两者都吃 tl 目录。
# 2026-10-11 归位：此前 lint_rpy + lint_report 共 395 行住在 checks/ 却不入
# CLI 也不入 all，自动化链路永远跑不到。
TL_GROUP = ["tlcheck", "fmtlint"]

# 结构性检查：同样只读、同样吃 <项目>，但历史上未纳入 all。
# 文档（SKILL.md 注意事项 / scripts/README）承诺 all 覆盖「变量完整性 / 标签问题 /
# 空译文」，故必须在此列出，否则用户按文档跑 all 拿不到报告。
#: 第三方机翻（`config.replace_text` 载荷）体检。只读、不需要 tl——恰恰相反，
#: 「**没有** tl 目录」是它最常见的场景，requires_tl=False 是刻意的，所以不并入
#: STRUCT_GROUP（那组多为缺 tl 时空转或报错，语义相反）。
PAYLOAD_GROUP = ["payloadscan"]
STRUCT_GROUP = ["integrity", "label", "type", "duplicate", "button", "typography",
                "tlcoverage"]
FIX_GROUP = ["fixtags", "fixcomments", "patchsay", "langbtn"]
#: 润色编排：只读 tl（回扫场景 label）+ 写 -o 目录的批次/提示词/账本。
#: 不进 all —— 它需要 --pool/--candidates 等专属参数，all 只透传项目路径。
POLISH_GROUP = ["polish"]
SETUP_GROUP = ["i18n", "lang", "fonts", "perfpanel", "rmsuffix", "unrpyc", "tablet", "optimize"]

ALL_GROUP = (CHECK_GROUP + CRASH_GROUP + I18N_GROUP + STRUCT_GROUP
             + TL_GROUP + PAYLOAD_GROUP + ["untranslated"])

DEFAULT_LANG = "schinese"

# 检查器子命令名（ALL_GROUP 之外还有 charname 等；lint 不是检查器但归 all 之外的只读组）
CHECKER_NAMES = (
    "ui", "misuse", "func", "auto", "duplicate", "button", "label", "type",
    "integrity", "untranslated", "charname", "crash", "fontcheck", "langcheck",
    "tlcheck", "fmtlint", "typography", "payloadscan", "tlcoverage",
)

_CHECKER_CACHE = {}


def script_path(name):
    """子命令名 → 绝对路径。"""
    return os.path.join(TOOLS_DIR, TOOL_SCRIPTS[name])


def load_checker(name):
    """导入某检查器脚本并返回它的 CHECKER 实例。

    脚本目录按需加入 sys.path（同组内 `from common import ...` 依赖），导入后取
    模块级 CHECKER。缓存结果——门面一次运行里每个检查器只用一次，但 all 与 list
    都会用到。
    """
    if name in _CHECKER_CACHE:
        return _CHECKER_CACHE[name]
    if name not in CHECKER_NAMES:
        raise KeyError(f"{name} 不是检查器（无 CHECKER 契约）")
    script_dir = os.path.dirname(script_path(name))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    mod_name = os.path.splitext(os.path.basename(TOOL_SCRIPTS[name]))[0]
    mod = importlib.import_module(mod_name)
    ck = getattr(mod, "CHECKER", None)
    if ck is None:
        raise AttributeError(f"{TOOL_SCRIPTS[name]} 没有模块级 CHECKER")
    if ck.name != name:
        raise ValueError(f"{TOOL_SCRIPTS[name]} 的 CHECKER.name={ck.name!r} "
                         f"与门面子命令名 {name!r} 不一致")
    _CHECKER_CACHE[name] = ck
    return ck


def summary(name):
    """描述文案：检查器取 CHECKER.summary，其余取 TOOL_DESC。"""
    if name in CHECKER_NAMES:
        return load_checker(name).summary
    return TOOL_DESC[name]


def requires_tl(name):
    """是否必须有 game/tl/<lang> 才能给出有意义的报告。"""
    if name in CHECKER_NAMES:
        return load_checker(name).requires_tl
    return name in TL_DIR_WRITERS


def takes_tl_dir(name):
    """门面是否需要把位置参数从 `<项目>` 换成 tl_dir。"""
    return name in CHECKER_NAMES and load_checker(name).takes == TL_DIR


#: 需要 tl 目录的非检查器工具（historically 手写的 NEEDS_TL_DIR 的一部分）
TL_DIR_WRITERS = {"namebox", "fixcomments"}


def all_takes_tl_dir():
    """all 里的检查器中，吃 tl_dir 的那些。"""
    return [n for n in ALL_GROUP if takes_tl_dir(n)]


def all_requires_tl():
    """all 里必须有 tl 目录才能跑的那些（替代手写集合 NEEDS_TL_DIR）。"""
    return [n for n in ALL_GROUP if requires_tl(n)]