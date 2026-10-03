#!/usr/bin/env python3
"""
Ren'Py Translation (.rpy) Linter
=================================
Checks:
  [E001] Unclosed quote
  [E002] old/new mismatch
  [E003] Empty new translation
  [E004] Encoding issues (BOM, non-UTF-8)
  [E005] Duplicate translate block ID within file
  [E006] Trailing whitespace
  [E007] No trailing newline
  [E008] Mixed indentation
  [E009] Suspicious inline variable format
  [E010] Line too long (>200 chars)
  [E011] old/new length ratio too extreme (possible missing translation)
"""

import os
import re
import sys
from collections import defaultdict

ISSUE_TYPES = {
    "E001": "unclosed quote",
    "E002": "old/new mismatch",
    "E003": "empty new translation",
    "E004": "encoding issue",
    "E005": "duplicate block ID",
    "E006": "trailing whitespace",
    "E007": "no trailing newline",
    "E008": "mixed indent",
    "E009": "suspicious inline variable",
    "E010": "line too long",
    "E011": "old/new length ratio extreme",
}

INLINE_VAR_RE = re.compile(r'(?<!\\)\[([^\]]*)\]')


def check_file(filepath, lang="schinese"):
    issues = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            raw = f.read()
    except Exception as e:
        return [("E004", 0, "Cannot read file: %s" % e)]

    lines = raw.split("\n")
    total_lines = len(lines)

    # E004: BOM
    if raw.startswith("\ufeff"):
        issues.append(("E004", 1, "File has UTF-8 BOM"))

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

        # E009: variable format
        for v in INLINE_VAR_RE.findall(stripped):
            if not re.match(r'^[a-zA-Z0-9_.]+$', v) and not v.startswith("#"):
                issues.append(("E009", lineno, "Suspicious inline variable: [%s]" % v))

        # E010: long line
        if len(line) > 200:
            issues.append(("E010", lineno, "Line too long (%d chars)" % len(line)))

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
            continue

    # E005: duplicate identifiers
    for ident, positions in seen_identifiers.items():
        if len(positions) > 1:
            issues.append(("E005", positions[1],
                "Duplicate translate block ID '%s' (first at line %d)" %
                (ident, positions[0])))

    return issues


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
        sys.exit(1)

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

    for filepath in rpy_files:
        filename = os.path.basename(filepath)
        issues = check_file(filepath, args.lang)
        if not issues:
            print("  OK  %s" % filename)
            continue

        print("\n  !!  %s (%d problems)" % (filename, len(issues)))
        issues.sort(key=lambda x: (x[1], x[0]))

        for code, lineno, msg in issues:
            safe_msg = str(msg).encode('gbk', errors='replace').decode('gbk')
            desc = ISSUE_TYPES.get(code, "").encode('gbk', errors='replace').decode('gbk')
            print("    [%s] L%6d %s: %s" % (code, lineno, desc, safe_msg))
            total_issues += 1
            summary[code] += 1

    print()
    print("=" * 70)
    print("  Total: %d issues" % total_issues)
    if summary:
        print()
        print("  By type:")
        for code in sorted(summary):
            desc = ISSUE_TYPES.get(code, "other")
            print("    [%s] %s: %d" % (code, desc, summary[code]))
    else:
        print("  All checks passed!")
    print("=" * 70)
    return 1 if total_issues else 0


if __name__ == "__main__":
    sys.exit(main() or 0)
