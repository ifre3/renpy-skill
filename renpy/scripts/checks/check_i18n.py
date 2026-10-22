#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_i18n.py — Ren'Py 多语言切换链路静态测试（只读）。

把"切不到中文 / 语言按钮没反应"这一类问题在开工前测出来，是
fix_lang_button（修）、switch_default_language（修）的验收对应面。
不启动游戏，查四条链路：

  1. 语言清单     tl/<lang> 都有哪些语言
  2. 切换入口     screen 里的 Language("xx") 动作：
                    - 目标语言没有 tl 目录 → 点了没效果（显示级）
                    - 某语言有 tl 目录却没有任何入口 → 玩家切不过去（显示级），
                      除非代码里有 _preferences.language 自定义切换
  3. 默认语言     config.language = "xx" 指向不存在的语言（显示级）
  4. strings 块   某语言连 translate xx strings 都没有 → 引擎公共界面
                  （跳过/存档确认/设置）保持英文（提示级，不计退出码）

用法:
  python check_i18n.py <项目根目录或game目录>

退出码: 0=通过(可有提示级), 1=有显示级问题, 2=路径错误
"""

import os
import re
import sys
from pathlib import Path

# 契约层在 shared/（跨组共享，故按相对路径加入 sys.path）
_SHARED_CONTRACT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "../shared")
if _SHARED_CONTRACT_DIR not in sys.path:
    sys.path.insert(0, _SHARED_CONTRACT_DIR)

from base_checker import PROJECT, BaseChecker  # noqa: E402

# Language 动作：Language("xx") / Language('xx') / Language(None)
LANG_ACTION_RE = re.compile(r'Language\(\s*(?:"(\w+)"|\'(\w+)\'|(None))\s*\)')
DEFAULT_LANG_RE = re.compile(r'config\.language\s*=\s*(?:"(\w+)"|\'(\w+)\'|None)')
# config.default_language：只设 _preferences 初值，玩家可改且会被记住。
# 与 config.language 语义相反——后者优先级高于玩家选择，会把语言锁死。
SAFE_DEFAULT_RE = re.compile(
    r'config\.default_language\s*=\s*(?:"(\w+)"|\'(\w+)\'|None)')
CUSTOM_SWITCH_RE = re.compile(r'_preferences\.language|preferences\.language\s*=')
STRINGS_BLOCK_RE = re.compile(r'^\s*translate\s+(\w+)\s+strings', re.M)
# config.replace_text 钩子：无 tl 也能汉化的第三方机制（见
# references/replace_text_hook.md）。它与 tl/ 并存时会双重写同一句文本，
# 且钩子无条件生效、不受 Language() 控制 —— 必须报给使用者。
REPLACE_TEXT_RE = re.compile(r'config\.replace_text\s*(?:=|\.append)')
# 混淆载荷特征：exec(zlib.decompress( ... )) 双层解压
OBFUSCATED_EXEC_RE = re.compile(
    r'exec\s*\(\s*(?:zlib\.decompress|__import__|eval)\s*[\(\.]')


def find_game_dir(base: Path):
    """接受项目根目录或 game 目录。"""
    if (base / "game").is_dir():
        return base / "game"
    if base.name == "game" and base.is_dir():
        return base
    return None


def scan(game_dir: Path):
    """扫 game/**/*.rpy，返回 (lang_actions, config_langs, has_custom_switch)。"""
    lang_actions = []     # (lang_or_None, 文件, 行号, in_tl)
    config_langs = []     # config.language 赋值（优先级最高，会锁死语言）
    safe_defaults = []    # config.default_language 赋值（只设初值，玩家可改）
    hook_hits = []        # config.replace_text 赋值点（非 tl 汉化机制）
    obf_hits = []         # exec(zlib.decompress(...)) 混淆载荷
    has_custom_switch = False
    strings_langs = set()
    for p in sorted(game_dir.rglob("*.rpy")):
        in_tl = "tl" in p.parts
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for m in STRINGS_BLOCK_RE.finditer(text):
            strings_langs.add(m.group(1))
        for lineno, line in enumerate(text.splitlines(), 1):
            s = line.split("#", 1)[0]
            for m in LANG_ACTION_RE.finditer(s):
                lang = m.group(1) or m.group(2)
                # tl 目录里的语言按钮副本不重复计数
                lang_actions.append((lang, p, lineno, in_tl))
            for m in DEFAULT_LANG_RE.finditer(s):
                config_langs.append((m.group(1), p, lineno))
            for m in SAFE_DEFAULT_RE.finditer(s):
                safe_defaults.append((m.group(1), p, lineno))
            if not in_tl and CUSTOM_SWITCH_RE.search(s):
                has_custom_switch = True
            if REPLACE_TEXT_RE.search(s):
                hook_hits.append((p, lineno))
            if OBFUSCATED_EXEC_RE.search(s):
                obf_hits.append((p, lineno))
    return (lang_actions, config_langs, has_custom_switch, strings_langs,
            safe_defaults, hook_hits, obf_hits)


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Ren'Py 多语言切换链路静态测试")
    ap.add_argument("path", help="项目根目录或 game 目录")
    # 统一 CLI 会把 -l/--language 原样转发给 all 中的每个检查器；本检查
    # 按 tl/ 下所有语言目录枚举，不依赖指定语言，该参数仅用于保持命令兼容。
    # 2026-10-06 修：本参数曾缺失，`all <项目> -l schinese` 的 langcheck 撞
    # argparse rc=2，被门面归一成失败项 → all 在任何项目上都返回 1（假阳性）。
    ap.add_argument("-l", "--language", "--lang", dest="lang", default=None,
                    help="兼容 all 透传（当前不参与检查逻辑）")
    args = ap.parse_args()
    _ = args.lang  # 契约声明本检查不吃指定语言（takes=PROJECT, requires_tl=False）

    game_dir = find_game_dir(Path(args.path))
    if not game_dir:
        print("[错误] 未找到 game/ 目录: %s" % args.path, file=sys.stderr)
        return 2

    tl_root = game_dir / "tl"
    tl_langs = sorted(d.name for d in tl_root.iterdir() if d.is_dir()) if tl_root.is_dir() else []
    (lang_actions, config_langs, has_custom_switch,
     strings_langs, safe_defaults, hook_hits, obf_hits) = scan(game_dir)

    problems = 0

    print("=" * 60)
    print("🌐 多语言链路测试")
    print("=" * 60)

    # 垃圾语言目录：None/true/false 这类工具残留，Ren'Py 会当成一种语言
    junk_langs = [l for l in tl_langs if l in ("None", "none", "True", "False", "true", "false")]
    for l in junk_langs:
        print("⚠️  tl/%s 是垃圾语言目录（工具残留/占位产物），建议删除" % l)
        problems += 1
    tl_langs = [l for l in tl_langs if l not in junk_langs]

    print("  tl 语言: %s" % (", ".join(tl_langs) if tl_langs else "（无翻译目录）"))
    print("  Language() 动作: %d 处；config.language 赋值: %d 处；"
          "config.default_language 赋值: %d 处"
          % (len(lang_actions), len(config_langs), len(safe_defaults)))

    if not tl_root.is_dir() and not lang_actions and not config_langs:
        print("\nℹ️  项目未启用多语言（无 game/tl/ 目录，也无语言切换代码）。")
        print("   要加翻译先跑: python setup/setup_i18n.py --path <项目> --lang <语言>")
        return 0

    # ---- 1. 切换入口目标 ----
    print("\n-- 切换入口目标")
    targets = {lang for lang, *_ in lang_actions if lang}
    # english 是基线语言（无 tl 目录也合法）
    bad_targets = sorted(t for t in targets if not (tl_root / t).is_dir() and t.lower() not in ("english", "en"))
    if bad_targets:
        print("❌ %d 个 Language() 目标没有对应 tl 目录，点了没效果:" % len(bad_targets))
        for t in bad_targets:
            sites = [(f, ln) for lang, f, ln, _ in lang_actions if lang == t][:3]
            for f, ln in sites:
                print("   %s → 引用位置: %s:%d" % (t, f.relative_to(game_dir), ln))
        problems += len(bad_targets)
    elif targets:
        print("✅ Language() 目标 %s 都存在" % ", ".join(sorted(targets)))

    # ---- 2. 每语言是否有入口 ----
    print("\n-- 每语言切换入口")
    reachable = set(targets)
    for lang, _p, _ln, _tl in lang_actions:
        if lang:
            reachable.add(lang)
    for lang in tl_langs:
        if lang in reachable:
            print("   ✅ %-12s 有切换入口" % lang)
        elif has_custom_switch:
            print("   ℹ️  %-12s 无 Language() 按钮，但存在 _preferences.language 自定义切换" % lang)
        elif (tl_root / lang).is_dir() and _lang_has_content(tl_root / lang):
            print("   ⚠️  %-12s 有翻译但没有切换入口，玩家切不过去" % lang)
            print("        → 跑 fix_lang_button 补语言按钮（默认试运行，--apply 落盘）")
            problems += 1
        else:
            print("   · %-12s 目录为空，跳过" % lang)

    # ---- 3. 默认语言 ----
    print("\n-- 默认语言")
    # 项目里存在任何 Language() 切换入口 → 说明作者想让玩家能切，
    # 此时 config.language 会覆盖玩家选择，是真冲突而非风格问题。
    switchable = bool(lang_actions) or has_custom_switch
    if not config_langs:
        print("ℹ️  未设置 config.language（Ren'Py 默认基线语言）")
    for lang, p, ln in safe_defaults:
        rel = p.relative_to(game_dir)
        if lang is None or (lang not in tl_langs and lang.lower() in ("english", "en")):
            print("   ✅ %s:%d config.default_language = %s（基线语言）" % (rel, ln, lang))
        elif lang in tl_langs:
            print("   ✅ %s:%d config.default_language = %s（初值，玩家可改）" % (rel, ln, lang))
        else:
            print("   ⚠️  %s:%d config.default_language = %s 没有 tl 目录" % (rel, ln, lang))
            problems += 1
    for lang, p, ln in config_langs:
        rel = p.relative_to(game_dir)
        if lang is None:
            print("   · %s:%d config.language = None（基线语言）" % (rel, ln))
        elif lang in tl_langs:
            print("   ✅ %s:%d 默认语言 %s 存在" % (rel, ln, lang))
        elif lang.lower() in ("english", "en") and "english" not in tl_langs:
            print("   · %s:%d 默认语言 english（基线语言，无需 tl 目录）" % (rel, ln))
        else:
            print("   ⚠️  %s:%d 默认语言 %s 没有 tl 目录，启动即回退基线" % (rel, ln, lang))
            problems += 1
        if lang is not None and switchable:
            print("        ⚠️ config.language 优先级高于玩家选择：")
            print("           _init_language() 算 `RENPY_LANGUAGE or config.language")
            print("           or _preferences.language`，设了它每次启动都强制 %s，" % lang)
            print("           偏好里的切换点了也会被覆盖回去。")
            print("           → 只想设初值请用 config.default_language" )
            problems += 1

    # ---- 4. replace_text 钩子（非 tl 汉化机制）----
    print("\n-- replace_text 钩子（非 tl 汉化）")
    if not hook_hits:
        print("✅ 未发现 config.replace_text（汉化只走 tl/）")
    else:
        for p, ln in hook_hits:
            print("   ⚠️  %s:%d 存在 config.replace_text 赋值" % (p.relative_to(game_dir), ln))
        if tl_langs:
            print("        ⚠️ 与 tl/ 并存：两条链会同时作用。")
            print("           钩子在渲染前生效且不受 Language() 控制 —— 切成英文时")
            print("           tl 译文撤了，钩子仍会把英文改成中文。")
            print("           → 见 references/replace_text_hook.md 4.1 节「先搬后删」")
        else:
            print("        ℹ️ 无 tl/：中文完全依赖此钩子（第三方机翻的典型形态）。")
            print("           → 见 references/replace_text_hook.md（识别/拆除/质量判据）")
        problems += len(hook_hits)

    if obf_hits:
        print("\n-- 混淆载荷")
        for p, ln in obf_hits:
            print("   ⚠️  %s:%d 疑似 exec(zlib.decompress(...)) 混淆加载"
                  % (p.relative_to(game_dir), ln))
        print("        第三方机翻/引流常这样藏。先解出来读，别整块删")
        print("        → references/replace_text_hook.md 第 2、4 节")
        problems += len(obf_hits)

    # ---- 5. strings 块（提示级）----
    print("\n-- 引擎 strings 覆盖（提示级）")
    for lang in tl_langs:
        if lang in strings_langs:
            print("   ✅ %-12s 有 translate strings 块" % lang)
        else:
            print("   ⚠️  %-12s 无 strings 块：跳过/存档/设置等引擎界面保持英文（不计失败）" % lang)

    print("\n" + "=" * 60)
    print("检查完成，问题总数: %d" % problems)
    if problems == 0:
        print("🎉 多语言链路静态检查全部通过")
        return 0
    print("⚠️  请处理以上问题")
    return 1


def _lang_has_content(lang_dir: Path) -> bool:
    """语言目录里有真实内容（翻译文件）才值得报"没有入口"。"""
    return any(lang_dir.rglob("*.rpy"))


class I18nChecker(BaseChecker):
    """多语言链路检测（只读）。无 tl 目录时自动降级为提示，不算失败。"""

    name = "langcheck"
    summary = "多语言链路测试：Language 入口 / 默认语言 / strings 覆盖"
    takes = PROJECT
    requires_tl = False


#: 门面发现用的实例（契约见 shared/base_checker.py）
CHECKER = I18nChecker()


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
