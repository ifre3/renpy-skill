#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_fonts.py — Ren'Py 字体接入静态测试（只读）。

回答三个问题，不启动游戏：
  1. 引用的字体文件都在吗？   磁盘 + .rpa 归档名（shared/rpa_index），basename 回退
  2. 每个翻译语言接上字体了吗？CJK 语言（schinese/tchinese/japanese/korean）
     既没有语言内字体覆盖、也没有项目级 CJK 字体引用 → 切语言后必出方块
  3. （可选）字形级覆盖      装了 fontTools 才做：用 font['cmap'] 抽查样张字符

与 setup_fonts.py 的分工：那是"接入/生成配置"的写工具，本脚本是接入后的
验收测试。检测不到问题不是"不用配字体"的证明，只说明静态可查的都通了。

用法:
  python check_fonts.py <项目根目录或game目录>

退出码: 0=通过, 1=有缺失或 CJK 字体未接入, 2=路径错误
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


class FontsChecker(BaseChecker):
    """字体接入检测。"""

    name = "fontcheck"
    summary = "字体接入测试：引用存在性（含 .rpa）+ CJK 语言是否接字体"
    takes = PROJECT
    requires_tl = False


#: 门面发现用的实例（契约见 shared/base_checker.py）
CHECKER = FontsChecker()


sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shared"))
try:
    from rpa_index import archive_names, names_by_ext
except ImportError:  # 独立拷贝运行时退化为纯磁盘检查
    archive_names = None
    names_by_ext = None

FONT_EXTS = {".ttf", ".otf", ".ttc", ".woff", ".woff2"}
FONT_REF_RE = re.compile(r'["\']([^"\'\n]+?\.(?:ttf|otf|ttc|woff2?))["\']', re.I)
# 屏幕层运行时字体机制：say/preferences 等屏里 `font persistent.xxx` 在显示时
# 求值，优先级高于 translate style / translate python 的 gui.* 覆盖——
# 汉化字体补丁"按钮正常对白异常"的根因（AfterDark 0.26 实测）
RUNTIME_FONT_RE = re.compile(r'\bfont\s+persistent\.')

# CJK 语言 → 样张字符（字形级覆盖抽查用）+ 文件名启发式关键词
CJK_LANGS = {
    "schinese": "简体中文渲染测试，字体缺字会出现方块。",
    "tchinese": "繁體中文渲染測試，字體缺字會出現方塊。",
    "japanese": "ひらがなカタカナ、日本語フォントの確認。",
    "korean": "한국어 글꼴 테스트입니다.",
}
CJK_FONT_HINTS = (
    "noto", "sourcehan", "source-han", "source_han", "cjk", "sc", "tc",
    "wenkai", "kuaile", "yahei", "msyh", "simhei", "simsun", "simkai",
    "simfang", "fangsong", "dengxian", "pingfang", "hiragino", "meiryo",
    "msmincho", "malgun", "nanum", "zenhei", "kai", "song", "hei", "han",
    "zh", "chinese", "japan", "korean",
)

INFO_MISSING = "缺失"
WARN_NO_CJK = "CJK字体未接入"


def find_game_dir(base: Path):
    """接受项目根目录或 game 目录。"""
    if (base / "game").is_dir():
        return base / "game"
    if base.name == "game" and base.is_dir():
        return base
    return None


def collect_refs(game_dir: Path):
    """收集全部字体引用 (ref, 文件, 行号) 与每语言目录内的引用集合。"""
    refs = []
    per_lang = {}
    runtime_font_hits = []   # 屏幕层 `font persistent.*`：运行时压掉 translate 级覆盖
    for p in sorted(game_dir.rglob("*.rpy")):
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        lang = None
        parts = p.parts
        if "tl" in parts:
            i = list(parts).index("tl")
            if i + 1 < len(parts):
                lang = parts[i + 1]
        for lineno, line in enumerate(text.splitlines(), 1):
            s = line.split("#", 1)[0]
            for m in FONT_REF_RE.finditer(s):
                ref = m.group(1).strip()
                refs.append((ref, p, lineno))
                if lang:
                    per_lang.setdefault(lang, set()).add(ref.lower())
            if lang is None and RUNTIME_FONT_RE.search(s) and "_preferences.language" not in s:
                # 已做语言感知适配（表达式里含 _preferences.language）的不算
                runtime_font_hits.append((p, lineno, s.strip()[:100]))
    return refs, per_lang, runtime_font_hits


def build_index(game_dir: Path):
    """磁盘资源索引（basename + 去扩展名）+ 归档名字并入 + 引擎自带字体。"""
    idx = set()
    for f in game_dir.rglob("*"):
        if f.is_file() and f.suffix.lower() in FONT_EXTS:
            idx.add(f.name.lower())
            idx.add(f.stem.lower())
    # 引擎自带字体（renpy/common/DejaVuSans.ttf 等）：发行版的加载路径
    # 包含引擎 common 目录，screens 里的无障碍字体引用可以直接命中
    engine_common = game_dir.parent / "renpy" / "common"
    if engine_common.is_dir():
        for f in engine_common.iterdir():
            if f.is_file() and f.suffix.lower() in FONT_EXTS:
                idx.add(f.name.lower())
                idx.add(f.stem.lower())
    rpa_errors = []
    if archive_names is not None:
        rpa_names, errors = archive_names(game_dir)
        rpa_errors = errors
        for n in names_by_ext(rpa_names, FONT_EXTS):
            idx.add(n)
            idx.add(n.rsplit("/", 1)[-1])
            idx.add(Path(n).stem.lower())
    return idx, rpa_errors


def _found(ref: str, idx: set) -> bool:
    rl = ref.lower()
    return (
        rl in idx
        or os.path.splitext(rl)[0] in idx
        or os.path.basename(rl) in idx
        or os.path.splitext(os.path.basename(rl))[0] in idx
    )


def _looks_cjk(font_name: str) -> bool:
    low = font_name.lower()
    return any(k in low for k in CJK_FONT_HINTS)


def check_glyphs(font_path: Path, sample: str):
    """可选字形级检查：返回缺失字符列表；fontTools 不可用或文件不在磁盘上则返回 None。"""
    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        return None
    if not font_path.is_file():
        return None
    try:
        cmap = TTFont(str(font_path), fontNumber=0, lazy=True).getBestCmap() or {}
        return sorted({ch for ch in sample if ord(ch) not in cmap and not ch.isspace()})
    except Exception:
        return None


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Ren'Py 字体接入静态测试")
    ap.add_argument("path", help="项目根目录或 game 目录")
    # 统一 CLI 会把 -l/--language 原样转发给 all 中的每个检查器；本检查
    # 按语言目录枚举，不依赖指定语言，该参数仅用于保持命令兼容。
    ap.add_argument("-l", "--language", "--lang", dest="lang", default=None,
                    help="兼容 all 透传（当前不参与检查逻辑）")
    args = ap.parse_args()

    game_dir = find_game_dir(Path(args.path))
    if not game_dir:
        print("[错误] 未找到 game/ 目录: %s" % args.path, file=sys.stderr)
        return 2

    refs, per_lang, runtime_font_hits = collect_refs(game_dir)
    idx, rpa_errors = build_index(game_dir)
    for err in rpa_errors:
        print("⚠️  归档索引解析失败（忽略）: %s" % err)
    if archive_names is not None and not rpa_errors:
        print("ℹ️  已并入归档名字清单")

    problems = 0

    # ---- 1. 引用存在性 ----
    print("=" * 60)
    print("🔤 字体引用存在性（%d 处引用）" % len(refs))
    print("=" * 60)
    missing = sorted({(r, str(p.relative_to(game_dir)), ln) for r, p, ln in refs if not _found(r, idx)})
    if missing:
        print("\n❌ 缺失 %d 个字体文件:" % len(missing))
        for ref, rel, ln in missing[:30]:
            print("   %s\n     → 引用位置: %s:%d" % (ref, rel, ln))
        if len(missing) > 30:
            print("   ... 其余 %d 条省略" % (len(missing) - 30))
        problems += len(missing)
    else:
        print("\n✅ 所有引用的字体文件都存在（含归档内）")

    # ---- 1b. 运行时字体机制 ----
    if runtime_font_hits:
        print("\n⚠️  检测到 %d 处屏幕层运行时字体（font persistent.*）：" % len(runtime_font_hits))
        print("    这类属性在显示时求值，优先级高于 translate style / translate python")
        print("    的字体覆盖——汉化字体补丁会出现「按钮正常、对白异常」。")
        print("    需把表达式改为语言感知，例：")
        print('      font ("Fonts/SourceHanSansLite.ttf" if _preferences.language == "schinese" else persistent.pref_text_font)')
        for rel, ln, s in runtime_font_hits[:10]:
            print("   %s:%d  %s" % (rel, ln, s))
        problems += len(runtime_font_hits)
    else:
        print("✅ 无屏幕层运行时字体覆盖，translate 级字体补丁可全量生效")

    # ---- 2. CJK 语言接入 ----
    print("\n" + "=" * 60)
    print("🌐 翻译语言字体接入")
    print("=" * 60)
    tl_root = game_dir / "tl"
    langs = sorted(d.name for d in tl_root.iterdir() if d.is_dir()) if tl_root.is_dir() else []
    junk = [l for l in langs if l in ("None", "none", "True", "False", "true", "false")]
    for l in junk:
        print("   ⚠️  tl/%s 是垃圾语言目录（工具残留/占位产物），建议删除" % l)
        problems += 1
    langs = [l for l in langs if l not in junk]
    if not langs:
        print("ℹ️  无有效翻译语言（未启用多语言）")
    for lang in langs:
        sample = CJK_LANGS.get(lang)
        if sample is None:
            print("   · %-12s 非CJK语言，跳过接入检查" % lang)
            continue
        wired = False
        for ref in per_lang.get(lang, ()):
            if _found(ref, idx):
                wired = True
                break
        if not wired:
            # 语言目录内有任何 CJK 风格字体引用也算接入（文件可能随后补）
            wired = any(_looks_cjk(r) for r in per_lang.get(lang, ()))
        if not wired:
            # 项目级：任何被引用的字体名带 CJK 特征（font_replacement_map /
            # 语言切换脚本都在 .rpy 引用里，已被上面的引用收集覆盖）
            wired = any(_looks_cjk(r) for r, _, _ in refs)
        if wired:
            print("   ✅ %-12s 已接入 CJK 字体" % lang)
        else:
            print("   ⚠️  %-12s 未发现任何 CJK 字体引用：切换后文本大概率显示方块" % lang)
            print("        → 用 setup_fonts.py fonts 子命令接入，或在 tl/%s 内做字体覆盖" % lang)
            problems += 1
            # 样张字形检查在缺接入时无意义，跳过

        if wired:
            for ref in per_lang.get(lang, ()):
                low = ref.lower()
                cand = game_dir / low
                if cand.is_file():
                    miss = check_glyphs(cand, sample)
                    if miss:
                        print("        （fontTools）%s 缺 %d 个样张字形: %s"
                              % (os.path.basename(ref), len(miss), "".join(miss[:10])))
                    break

    print("\n" + "=" * 60)
    print("检查完成，问题总数: %d" % problems)
    if problems == 0:
        print("🎉 字体接入静态检查全部通过")
        return 0
    print("⚠️  请处理以上问题")
    return 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
