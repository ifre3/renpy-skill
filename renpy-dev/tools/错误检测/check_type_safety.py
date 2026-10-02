#!/usr/bin/env python3
"""
Ren'Py 类型安全检测 — 仅检测 100% 会崩溃的场景。

设计原则:
  1. 游戏几乎不崩 → 只报已知的真崩溃模式
  2. 常量参数 randint(1,100) 绝不报
  3. 只查 "变量 → randint/range 且变量来自 get_size()" 这条链

用法:
  python tools/check_type_safety.py [path]
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Finding:
    file: str
    line: int
    line_content: str
    severity: str
    pattern: str
    message: str
    fix: str


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)

    def count(self, sev: str) -> int:
        return sum(1 for f in self.findings if f.severity == sev)

    def summary(self) -> str:
        n = self.count("ERROR")
        lines = [
            "",
            "=" * 72,
            "  Ren'Py 类型安全检测 (仅 100% 崩溃模式)",
            "=" * 72,
            f"  发现: {len(self.findings)} (ERROR: {n})",
            "=" * 72,
            "",
        ]
        if self.findings:
            lines.append("")
            for i, f in enumerate(self.findings, 1):
                lines.append(f"  [{i}] [ERROR] {f.file}:{f.line}")
                lines.append(f"      {f.line_content.strip()}")
                lines.append(f"      修复: {f.fix}")
                lines.append("")
        return "\n".join(lines)


def _is_int_literal(s: str) -> bool:
    """字符串是否是纯整数常量(允许负号、下划线、空格)。"""
    s = s.strip()
    if s.startswith("-"):
        s = s[1:]
    return bool(re.fullmatch(r'[\d_,\s]+', s)) if s else False


def _all_args_literal(pattern: str, text: str) -> bool:
    """正则匹配后，检查所有参数捕获组是否都是字面整数。
    全是常量的话返回 True（应该排除）。"""
    m = re.search(pattern, text)
    if not m:
        return False  # 没匹配
    for g in m.groups():
        if g and not _is_int_literal(g):
            return False  # 有变量，不排除
    return True  # 全是常量，排除


# ── 规则：只查两条真正的崩溃链 ──

RULES = [
    # 链1: get_size() 返回值 直接传给 randint/range
    # 例如: randomobj.randint(0, cheight) 其中 cheight 来自 get_size()
    # 检测: randint/range 的参数是字母开头的变量（非常量）
    (
        r"(?P<a>[a-z_]\w*)\s*=\s*.*\.get_size\(\)",
        "get_size_assignment",
        ".get_size() 赋值 → 后续用于 randint/range 必崩",
        "在赋值处立即转换: w, h = int(w), int(h)",
    ),

    # 链2: randint 的参数是变量名（字母开头），不是常量数字
    # 例如: randint(0, cheight) cheight是变量 → 可能崩
    # 常量: randint(1, 100) → 不报
    (
        r"[a-z_]\w*\.(?:randint|randrange)\s*\(\s*(?P<a>[^,]+),\s*(?P<b>[^)]+)\s*\)",
        "variable_in_random_call",
        "randint/randrange 的参数是变量（非常量数字），变量可能是 float",
        "确认传入随机函数的变量都是 int 类型",
    ),
]


def scan_file(filepath: Path, report: Report) -> None:
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        print(f"  skip {filepath}: {e}", file=sys.stderr)
        return

    lines = content.splitlines()
    seen = set()

    # 第一遍：收集所有 get_size() 赋值的位置
    gs_vars = set()  # 从 get_size() 赋值的变量名
    for raw in lines:
        m = re.search(r"(?P<a>[a-z_]\w*(?:,\s*[a-z_]\w*)*)\s*=.*\.get_size\(\)", raw)
        if m:
            for var in m.group("a").split(","):
                gs_vars.add(var.strip())

    for idx, raw in enumerate(lines, start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith('"'):
            continue

        # 取 $ 行或行内 $ 后的 Python 部分
        if re.match(r'\s*\$', raw):
            python = raw
        elif "$" in raw:
            python = raw[raw.index("$") + 1:]
        else:
            continue

        for pattern, tag, message, fix in RULES:
            if tag == "get_size_assignment":
                m = re.search(r"([a-z_]\w*(?:,\s*[a-z_]\w*)*)\s*=.*\.get_size\(\)", python)
                if not m:
                    continue
                for var in m.group(1).split(","):
                    var = var.strip()
                    # 检查变量后面是否已有 int() 转换（同一文件或附近行）
                    # 简单方式：看整份内容里有没有 int(var)
                    if f"int({var})" not in content:
                        key = (str(filepath), idx, tag, var)
                        if key not in seen:
                            seen.add(key)
                            report.findings.append(Finding(
                                file=str(filepath), line=idx, line_content=raw,
                                severity="ERROR", pattern=tag,
                                message=message, fix=fix,
                            ))

            elif tag == "variable_in_random_call":
                # 排除全是常量参数的情况
                if _all_args_literal(
                    r"[a-z_]\w*\.(?:randint|randrange)\s*\(\s*[^,]+,\s*[^)]+\s*\)",
                    python
                ):
                    continue
                m = re.search(
                    r"(?P<fn>[a-z_]\w*\.(?:randint|randrange))\s*\(\s*(?P<a>[^,]+),\s*(?P<b>[^)]+)\s*\)",
                    python
                )
                if not m:
                    continue
                # 只要任一参数是变量（字母开头）就报
                a, b = m.group("a").strip(), m.group("b").strip()
                if _is_int_literal(a) and _is_int_literal(b):
                    continue
                key = (str(filepath), idx, tag)
                if key not in seen:
                    seen.add(key)
                    report.findings.append(Finding(
                        file=str(filepath), line=idx, line_content=raw,
                        severity="ERROR", pattern=tag,
                        message=message, fix=fix,
                    ))


def scan_directory(root: Path, report: Report) -> None:
    files = sorted(
        f for f in root.rglob("*")
        if f.is_file() and f.suffix in (".rpy", ".py")
    )
    files = [f for f in files if "renpy" not in str(f).lower() or "/renpy/" not in str(f).lower()]
    if not files:
        print(f"  no .rpy/.py in {root}")
        return
    print(f"  scanning {len(files)} files...")
    for fp in files:
        scan_file(fp, report)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ren'Py 类型安全检测 — 仅 100% 崩溃模式"
    )
    parser.add_argument("path", nargs="?", default=None, help="文件或目录")
    # 与统一 CLI 的 `all <项目> -l <lang>` 风格保持一致：本检查与语言无关，
    # 接受该参数仅为兼容统一入口的参数透传，不产生任何效果。
    parser.add_argument(
        "-l", "--language", default=None,
        help="语言代码（本检查与语言无关，仅为兼容统一 CLI 透传而接受）",
    )
    args = parser.parse_args()

    target = Path(args.path) if args.path else Path.cwd()
    if not target.exists():
        print(f"  path not found: {target}", file=sys.stderr)
        sys.exit(1)

    report = Report()
    if target.is_file():
        scan_file(target, report)
    else:
        scan_directory(target, report)

    print(report.summary())
    sys.exit(1 if report.count("ERROR") > 0 else 0)


if __name__ == "__main__":
    main()
