#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ren'Py Translation (.rpy) Linter
=================================
Checks:
  [E001] Unclosed quote
  [E002] old/new mismatch
  [E003] Empty new translation
  [E004] Encoding issues (non-UTF-8 读不出来)
  [E005] Duplicate translate block ID within file
  [E006] Trailing whitespace
  [E007] No trailing newline
  [E008] Mixed indentation
  [E009] Suspicious inline variable format
  [E010] Line too long (>200 chars)
  [E011] old/new length ratio too extreme (possible missing translation)

## 定位：tl 文件的「格式层」lint，与 tl_check 互补不重叠

`tl_check`（门面 `tlcheck`）看的是**语义**：标签结构、插值、转义、崩溃级问题。
本脚本看的是**格式**：引号闭合、块 ID 重复、行尾空白、缩进混用、超长行、长度比。
两者扫同一批文件但查不同维度，都要跑。

门面子命令 `fmtlint`，参与 `all`（2026-10-11 归位：此前 395 行 lint_rpy +
lint_report 住在 checks/ 却不入 CLI 也不入 all，等于在自动化链路里跑不到）。

## 2026-10-11 两处修正（真实项目 Dissonance 0.14 实测）

- **E004 BOM 不再是问题**：tl 文件普遍带 UTF-8 BOM（实测 27/27 个文件都有），
  引擎与 tl_check 都按 `utf-8-sig` 正常处理。把它报成 issue 会让本检查器在
  **任何**合规项目上恒定返回 1 —— 与「退出码 1 = 查出了问题」的约定冲突。
  现在 E004 只保留「文件读不出来」这一真正的编码故障。
- **退出码语义**：`main()` 过去写 `sys.exit(main() or 0)`,而 `main()` 用
  `print` 后无返回值 → 恒为 0,门面永远看不到问题。现在返回 1/0。
"""

import io
import os
import re
import sys
from collections import defaultdict

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
else:  # pragma: no cover - 老 Python
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

_HERE = os.path.dirname(os.path.abspath(__file__))
_SHARED = os.path.join(os.path.dirname(_HERE), "shared")
if _SHARED not in sys.path:
    sys.path.insert(0, _SHARED)

try:
    from rpy_syntax import iter_bracket_groups
except ImportError:  # pragma: no cover - 独立拷贝运行时降级回正则
    iter_bracket_groups = None

ISSUE_TYPES = {
    "E001": "unclosed quote",
    "E002": "old/new mismatch",
    "E003": "empty new translation",
    "E004": "encoding issue (unreadable)",
    "E005": "duplicate block ID",
    "E006": "trailing whitespace",
    "E007": "no trailing newline",
    "E008": "mixed indent",
    "E009": "suspicious inline variable",
    "E009b": "bracketed plain word (likely translator style)",
    "E010": "line too long",
    "E011": "old/new length ratio extreme",
}

#: 分级：只有真问题进退出码，排版噪音与风格可疑只展示。
#:
#: 依据 2026-10-11 Dissonance 0.14 实测：
#: - **E010 超长行**（>200 字符）纯排版，不影响运行与显示，实测 1356 条。
#: - **E011 长度比** 的 0.3 阈值是按「同语系」定的。英→中天然压缩：长度比
#:   中位数 0.333、P10 0.25，30% 的句子落在 <0.3（实测 674 组）。按原阈值跑，
#:   任何合规的英→中项目都会恒定报几百条并让退出码恒为 1——与「退出码
#:   1 = 查出了问题」的约定冲突。故降为提示级：仍打印（人工可据此找漏翻），
#:   但不进退出码；真正的漏翻由 `untranslated`（new 为空/等于 old）负责。
#: - **E006 行尾空白 / E007 缺末尾换行** 同为排版级。
#: - **E009b「括号内容是普通词」**（如 `[总之]` `[嗯]` `[你]`）：中文台词里
#:   用方括号括语气词/括注是译者风格，原文无插值时引擎当普通文本显示，
#:   不会崩。实测 5 条全属此类。降为提示级；但**原文侧也有插值**时（说明
#:   译文在该插值旁多出括号）不降级，由人工核对。见 `_inline_var_level`。
#:
#: 仍进退出码的（真会导致块解析失败、译文丢失或显示错误）：E001 引号未闭合、
#: E002 old 无匹配 new、E003 空译文、E004 读不出来、E005 块 ID 重复、
#: E008 缩进混用、E009 可疑插值。
SEVERITY = {
    "E001": "problem",
    "E002": "problem",
    "E003": "problem",
    "E004": "problem",
    "E005": "problem",
    "E008": "problem",
    "E009": "problem",
    "E009b": "cosmetic",
    "E006": "cosmetic",
    "E007": "cosmetic",
    "E010": "cosmetic",
    "E011": "cosmetic",
}

#: 插值判定复用共享解析层 `rpy_syntax.iter_bracket_groups`，不用自己的正则。
#: 手写正则在真实项目上把四类合法写法全误判成 E009（2026-10-11 Dissonance
#: 0.14，13 条 E009 事后逐条核实**全为误报**）：
#:   · `[[Edited]` / `[[编辑]` —— Ren'Py 的转义方括号，不是插值
#:   · `[总之]` `[嗯]` `[你]`  —— 中文台词里用方括号括语气词，不是插值
#:   · `[cps=3]`               —— 文本标签参数（解析层会 mask 掉 {…} 内的）
#:   · `[config.version!t]` / `[control!s]` —— 合法插值的**转换标志**，
#:     早期正则只认 !t/!q/!i/!u，漏了 !s（还有 !c/!l）
#: 共享解析层已正确处理 `[[` 转义、嵌套方括号、表达式内字符串与文本标签。
INLINE_VAR_FALLBACK_RE = re.compile(r'(?<!\\)\[([^\]]*)\]')

#: 插值内容合法形态：标识符/属性链 + 可选转换标志（renpy/substitutions.py
#: 的 translate 分支：!t/!q/!i/!u/!s/!c/!l）。
VALID_VAR_RE = re.compile(r"^[a-zA-Z0-9_.\s]+(?:!t|!q|!i|!u|!s|!c|!l)?$")


#: 纯词括号（非标识符、非表达式）：如 `[总之]` `[嗯]` `[你]` `[cps=3]`。
#: 中文台词里括语气词/括注是译者风格，引擎当普通文本显示，不崩。
#: 但 `{cps=3}` 这类标签名被写进正文是真缺陷（会显示出来），另行识别。
#: `{cps=3}` 这类标签名被当成字面文本写进正文 —— 真缺陷，会显示出来。
#: 实测 1 条（YoshieEve L7867：`"{cps=3}[cps=3]…{/cps}"`）。形如
#: `名字=数字/字符串`，与纯语气词区分开，不降级。
TAG_ARG_RE = re.compile(r"^[a-z][a-z_]*\s*=\s*[^\[\]]{1,20}$", re.I)

PLAIN_WORD_RE = re.compile(r"^[^\s\[\]{}=!+\-*/%<>(),.:;'\"]{1,12}$")


def _inline_var_level(inner, orig_has_interp):
    """判定一个插值内容的严重度编码：E009（真问题）或 E009b（风格可疑）。

    `orig_has_interp` = 同一对的原文里是否存在插值。原文有插值而译文多出
    括号时，无法排除「译者把插值改写坏了」，不降级，交人工核对。
    """
    s = inner.strip()
    if VALID_VAR_RE.match(s):
        return None
    if TAG_ARG_RE.match(s):          # [cps=3] —— 标签名被写进正文，真缺陷
        return "E009"
    if PLAIN_WORD_RE.match(s) and not orig_has_interp:
        return "E009b"
    return "E009"


def _inline_vars(text, orig_has_interp=False):
    """返回 (内容, 严重度编码或 None)。优先用共享解析层。"""
    if iter_bracket_groups is not None:
        items = [(inner, None) for inner, _full in iter_bracket_groups(text)]
    else:
        items = [(v, None) for v in INLINE_VAR_FALLBACK_RE.findall(text)]
    return [(inner, _inline_var_level(inner, orig_has_interp)) for inner, _ in items]


def check_file(filepath, lang="schinese"):
    issues = []
    try:
        # utf-8-sig：有 BOM 的文件自动剥掉，与引擎/tl_check 的读法一致。
        # BOM 本身不是问题（tl 文件普遍带），只有读不出来才是 E004。
        with open(filepath, "r", encoding="utf-8-sig") as f:
            raw = f.read()
    except Exception as e:
        return [("E004", 0, "Cannot read file: %s" % e)]

    lines = raw.split("\n")
    total_lines = len(lines)

    # E007: trailing newline
    if not raw.endswith("\n"):
        issues.append(("E007", total_lines, "No trailing newline at end of file"))

    in_block = False
    block_label = None
    seen_identifiers = defaultdict(list)
    old_line = None
    old_lineno = 0
    new_line = None
    old_text = None
    new_text = None
    last_indent_type = None
    indent_reported = False

    # E009 需要「同一对里原文是否也有插值」才能定级，故不是逐行扫描，
    # 而是在收齐 old/new 之后统一处理：原文无插值 → 译文里的纯词括号多半
    # 是译者风格（E009b，提示级）；原文有插值 → 不降级，交人工核对。
    pending_orig = None
    last_orig_has_interp = False

    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped == "":
            continue

        # E006: trailing whitespace
        if line.rstrip("\r\n") != line.rstrip(" \t\r\n"):
            issues.append(("E006", lineno, "Trailing whitespace"))

        # E008: mixed indent
        if stripped and (line[0] in (" ", "\t")):
            indent_str = line[:len(line) - len(line.lstrip())]
            if indent_str:
                if "  " in indent_str and "\t" not in indent_str:
                    itype = "spaces"
                elif "\t" in indent_str:
                    itype = "tabs"
                else:
                    itype = "other"
                if last_indent_type is not None and last_indent_type != itype and not indent_reported:
                    issues.append(("E008", lineno, "Mixed indentation: was %s, now %s" % (last_indent_type, itype)))
                    indent_reported = True
                last_indent_type = itype

        # E009: 译文里的插值形态可疑（定级依赖原文是否有插值）
        #
        # 注意 tl 文件里绝大多数对话对是「原文注释行 + 译文行」形式（实测
        # Dissonance 0.14：44k 对话对里 old/new 只有 857 组），所以这里必须
        # 逐行扫，不能只挂在 `new ` 分支上——那样会漏掉 98% 的译文。
        # `last_orig_has_interp` 由下面的原文注释行/old 行更新。
        for inner, level in _inline_vars(stripped, last_orig_has_interp):
            if level:
                issues.append((level, lineno,
                               "Suspicious inline variable: [%s]" % inner))

        # E010: long line
        if len(line) > 200:
            issues.append(("E010", lineno, "Line too long (%d chars)" % len(line)))

        # 更新「当前对的原文是否有插值」：注释行或 old 行都算原文侧
        if stripped.startswith("#"):
            last_orig_has_interp = bool(_inline_vars(stripped))
        if stripped.startswith("translate %s" % lang):
            # Flush previous block
            if in_block and old_line is not None and new_line is None:
                issues.append(("E002", old_lineno,
                    "old line without matching new (block %s)" % block_label))
            in_block = True
            parts = stripped.split()
            block_label = parts[-1] if len(parts) >= 3 else "unknown"
            seen_identifiers[block_label].append(lineno)
            old_line = None
            new_line = None
            old_text = None
            new_text = None
            continue

        if not in_block:
            continue

        if stripped.startswith("old "):
            if old_line is not None and new_line is None:
                issues.append(("E002", old_lineno,
                    "old line without matching new (block %s)" % block_label))
            old_line = line
            old_lineno = lineno
            old_text = stripped[4:]
            pending_orig = old_text
            # Check quotes
            if old_text:
                if old_text.startswith('"') and not old_text.endswith('"'):
                    issues.append(("E001", lineno, "Unclosed quote in old line"))
                elif old_text.startswith("'") and not old_text.endswith("'"):
                    issues.append(("E001", lineno, "Unclosed quote in old line"))
            continue

        if stripped.startswith("new "):
            new_line = line
            new_text = stripped[4:]
            if new_text:
                if new_text.startswith('"') and not new_text.endswith('"'):
                    issues.append(("E001", lineno, "Unclosed quote in new line"))
                elif new_text.startswith("'") and not new_text.endswith("'"):
                    issues.append(("E001", lineno, "Unclosed quote in new line"))

            # E003: empty translation
            if new_text in ('""', "''"):
                issues.append(("E003", lineno,
                    "Empty new translation (block %s)" % block_label))

            # E009: old/new 形式下的译文侧（注释形式的在逐行分支已处理）

            # E011: length ratio
            if old_text and new_text:
                oc = old_text.strip('\'" \t')
                nc = new_text.strip('\'" \t')
                if oc and nc:
                    ratio = len(nc) / max(len(oc), 1)
                    if ratio > 3.5 or ratio < 0.3:
                        issues.append(("E011", lineno,
                            "Length ratio extreme: '%.40s...' %d -> '%.40s...' %d (%.1fx)" %
                            (oc, len(oc), nc, len(nc), ratio)))

            old_line = None
            new_line = None
            old_text = None
            new_text = None
            pending_orig = None
            continue

    # E005: duplicate identifiers
    for ident, positions in seen_identifiers.items():
        if len(positions) > 1:
            issues.append(("E005", positions[1],
                "Duplicate translate block ID '%s' (first at line %d)" %
                (ident, positions[0])))

    return issues


def _scan_and_report(root_dir, lang="schinese"):
    """扫一个目录并打印报告，返回 (退出码, 问题总数)。CLI 与 run_fmtlint 共用。"""
    rpy_files = []
    for root, dirs, filenames in os.walk(root_dir):
        dirs[:] = [name for name in dirs if not name.startswith((".", "_"))]
        rpy_files.extend(
            os.path.join(root, filename)
            for filename in filenames
            if filename.endswith(".rpy")
        )
    rpy_files.sort()

    print("=" * 70)
    print("  Ren'Py Translation Lint -- %d files" % len(rpy_files))
    print("=" * 70)
    print()

    total_issues = 0
    summary = defaultdict(int)
    problems = 0

    for filepath in rpy_files:
        filename = os.path.basename(filepath)
        issues = check_file(filepath, lang)
        if not issues:
            print("  OK  %s" % filename)
            continue

        print("\n  !!  %s (%d problems)" % (filename, len(issues)))
        issues.sort(key=lambda x: (x[1], x[0]))

        for code, lineno, msg in issues:
            # 早期版本在这里做 gbk 转码以适配 Windows 控制台；转码会把非 gbk
            # 字符（含大量 CJK 标点与罕见汉字）替换成 '?'，报告反而不可读。
            # stdout 已在模块头统一成 utf-8，直接打印。
            level = SEVERITY.get(code, "problem")
            mark = "  " if level == "cosmetic" else ""
            print("    %s[%s] L%6d %s: %s"
                  % (mark, code, lineno, ISSUE_TYPES.get(code, ""), msg))
            total_issues += 1
            summary[code] += 1
            if level != "cosmetic":
                problems += 1

    print()
    print("=" * 70)
    print("  Total: %d issues" % total_issues)
    if summary:
        print()
        print("  By type:")
        for code in sorted(summary):
            print("    [%s] %s: %d" % (code, ISSUE_TYPES.get(code, "other"), summary[code]))
        cosmetic = total_issues - problems
        if cosmetic:
            print()
            print("  注：其中 %d 条为排版级（缩进两个空格，如行尾空白/超长行/"
                  "长度比），不进退出码。英→中天然压缩使长度比中位数仅 0.33，"
                  "E011 的 0.3 阈值在合规项目上也会命中约 30%% 的句子——"
                  "真漏翻看 `untranslated`，不看这里。" % cosmetic)
    else:
        print("  All checks passed!")
    print("=" * 70)
    return (1 if problems else 0), total_issues


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Ren'Py Translation (.rpy) Linter")
    ap.add_argument("root_dir", help="翻译文件目录路径")
    ap.add_argument("-l", "--lang", default="schinese",
                    help="translate <lang> 块前缀（默认 schinese；换语言必须传，否则检测不到条目）")
    args = ap.parse_args()

    root_dir = args.root_dir
    if not os.path.isdir(root_dir):
        print("Directory not found: " + root_dir)
        return 2

    rc, _ = _scan_and_report(root_dir, args.lang)
    return rc


def run_fmtlint(tl_dir, lang="schinese"):
    """就地执行，返回 (退出码, 问题总数)。供 CHECKER.run 与测试复用。"""
    if not os.path.isdir(tl_dir):
        print("Directory not found: " + tl_dir)
        return 2, 0
    return _scan_and_report(tl_dir, lang)


# ── 检查器契约（门面子命令 fmtlint，参与 all）──
try:
    from base_checker import TL_DIR, BaseChecker
except ImportError:  # 独立拷贝运行时降级：无 CHECKER，门面也发现不了它
    TL_DIR, BaseChecker = "tl_dir", object
else:
    class FmtLintChecker(BaseChecker):
        """tl 文件「格式层」lint（门面子命令 fmtlint，参与 all）。

        与 tlcheck 的分工：tlcheck 查语义（标签结构/插值/转义/崩溃级），
        本检查器查格式（引号闭合/块 ID 重复/行尾空白/缩进混用/超长行/长度比）。
        两者扫同一批文件、查不同维度，都要跑。纯只读，无写操作。
        """

        name = "fmtlint"
        summary = "tl 文件格式层 lint：引号/块ID/行尾/缩进/超长行/长度比（语义问题看 tlcheck）"
        takes = TL_DIR
        requires_tl = True

        def run(self, ctx):
            rc, _ = run_fmtlint(str(ctx.tl_dir), ctx.lang)
            return 1 if rc != 0 else 0

    CHECKER = FmtLintChecker()


if __name__ == "__main__":
    sys.exit(main() or 0)
