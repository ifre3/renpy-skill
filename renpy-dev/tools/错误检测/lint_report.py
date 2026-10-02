#!/usr/bin/env python3
"""Analyze linter results - show actual issues filtered for real problems.

用法:
  python lint_report.py <翻译文件目录>
  python lint_report.py /path/to/translation/files
"""
import argparse
import os
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main():
    ap = argparse.ArgumentParser(description="Ren'Py 翻译 lint 报告分析")
    ap.add_argument("root", help="翻译文件目录路径")
    ap.add_argument("-l", "--lang", default="schinese",
                    help="translate <lang> 块前缀（默认 schinese；换语言必须传，否则检测不到条目）")
    args = ap.parse_args()
    tr_prefix = f"translate {args.lang}"

    root = args.root
    if not os.path.isdir(root):
        print(f"错误: 目录不存在: {root}")
        sys.exit(1)

    # --- E011: Length ratio extreme ---
    print("=== E011: Short translations (ratio < 0.3) ===")
    count = 0
    for fname in sorted(os.listdir(root)):
        if not fname.endswith(".rpy"):
            continue
        fp = os.path.join(root, fname)
        with open(fp, "r", encoding="utf-8") as f:
            lines = f.readlines()

        in_block = False
        old_text = None
        for i, line in enumerate(lines, 1):
            s = line.strip()
            if s.startswith(tr_prefix):
                in_block = True
                old_text = None
                continue
            if not in_block:
                continue
            if s.startswith("old "):
                old_text = s[4:].strip('"\' \t')
            elif s.startswith("new "):
                new_text = s[4:].strip('"\' \t')
                if old_text and new_text and len(old_text) > 10:
                    ratio = len(new_text) / max(len(old_text), 1)
                    if ratio < 0.3:
                        print("  %s:L%d (%.1fx) old=%s" % (fname, i, ratio, old_text[:60]))
                        count += 1
                        if count >= 12:
                            break
                old_text = None
        if count >= 12:
            break
    print()

    var_re = re.compile(r"\[([^\]]*)\]")

    # --- E009: Real issues (excluding [[ and !format) ---
    print("=== E009: Genuinely suspicious bracket patterns ===")
    for fname in sorted(os.listdir(root)):
        if not fname.endswith(".rpy"):
            continue
        fp = os.path.join(root, fname)
        with open(fp, "r", encoding="utf-8") as f:
            lines = f.readlines()

        real_issues = []
        for i, line in enumerate(lines, 1):
            s = line.strip()
            for m in var_re.finditer(s):
                start = m.start()
                inner = m.group(1)
                # Skip [[ (double bracket = escaped)
                if start > 0 and s[start - 1] == "[":
                    continue
                # Skip standard Ren'Py variables
                if re.match(r"^[a-zA-Z0-9_.]+(?:!t|!q|!i|!u)?$", inner):
                    continue
                # OK this is actually suspicious
                real_issues.append((i, inner, s[:100]))

        if real_issues:
            for lineno, v, context in real_issues[:4]:
                print("  %s:L%d [%s] %s" % (fname.replace("_translated.rpy", ""), lineno, v, context))
            if len(real_issues) > 4:
                print("  ... +%d more" % (len(real_issues) - 4))
            print()

    # --- File summary with counts ---
    print("=== Per-File Summary ===")
    print("%-40s %6s %6s %6s" % ("File", "E009", "E010", "E011"))
    print("-" * 60)

    for fname in sorted(os.listdir(root)):
        if not fname.endswith(".rpy"):
            continue
        e9 = e10 = e11 = 0
        fp = os.path.join(root, fname)
        with open(fp, "r", encoding="utf-8") as f:
            lines = f.readlines()

        in_block = False
        old_text = None
        for i, line in enumerate(lines, 1):
            s = line.strip()

            # E010
            if len(line) > 200:
                e10 += 1

            # E009
            for m in var_re.finditer(s):
                start = m.start()
                inner = m.group(1)
                if start > 0 and s[start - 1] == "[":
                    continue
                if re.match(r"^[a-zA-Z0-9_.]+(?:!t|!q|!i|!u)?$", inner):
                    continue
                e9 += 1

            # E011
            if s.startswith(tr_prefix):
                in_block = True
                old_text = None
                continue
            if not in_block:
                continue
            if s.startswith("old "):
                old_text = s[4:].strip('"\' \t')
            elif s.startswith("new "):
                new_text = s[4:].strip('"\' \t')
                if old_text and new_text and len(old_text) > 10:
                    ratio = len(new_text) / max(len(old_text), 1)
                    if ratio < 0.3 or ratio > 3.5:
                        e11 += 1
                old_text = None

        if e9 or e10 or e11:
            print("%-40s %6d %6d %6d" % (fname[:40], e9, e10, e11))


if __name__ == "__main__":
    main()
