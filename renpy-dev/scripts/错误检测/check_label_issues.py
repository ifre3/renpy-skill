#!/usr/bin/env python3
"""
Ren'Py 标签问题检测脚本。

检测范围:
  1. [UNDEFINED_LABEL] call/jump 到的标签未定义
  2. [UNREACHABLE_CODE] 标签后有 return 但还有代码（return 后面的代码不可达）
  3. [ORPHAN_LABEL] 孤立的标签（没有被任何 jump/call 引用）
  4. [DUPLICATE_LABEL] 同一文件中重复定义标签
  5. [MISPLACED_RETURN] return 不在标签块内
  6. [MISSING_RETURN] 标签块缺少 return 语句
  7. [INVALID_LABEL_NAME] 标签名不符合 Ren'Py 规范
  8. [CALL_WITHOUT_FROM] call 语句没有 from（可能导致返回问题）

用法:
  python tools/check_label_issues.py [path]
  python tools/check_label_issues.py game/chapters/ch1.rpy
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ── 标签名合法性检查 ──
_LABEL_NAME_RE = re.compile(r'^[a-z_][a-z0-9_]*$')

# ── 标签定义 ──
# 注意用 \s* 而非 \s+：Ren'Py 的 label 通常顶格书写（label start:），
# 旧正则要求前置缩进，导致几乎所有标签都被漏掉、jump 全被误报为未定义。
_LABEL_DEF_RE = re.compile(r'^\s*label\s+([A-Za-z_]\w*)\s*:')

# ── jump 到标签 ──
_JUMP_RE = re.compile(r'\bjump\s+([A-Za-z_]\w*)')

# ── call 到标签（排除 call screen / call function） ──
_CALL_LABEL_RE = re.compile(
    r'\bcall\s+([A-Za-z_]\w*)(?:\s|\(|$)'
)

# ── return 语句（必须位于语句位置，避免匹配对白里的 "return" 一词） ──
_RETURN_RE = re.compile(r'^\s*return\b')

# ── 声明类语句（初始化时执行，不是控制流） ──
# 这些语句出现在 label 块范围内不代表可执行流程，不能算「return 之后的不可达代码」。
_DECL_RE = re.compile(
    r'^\s*(?:init|image|define|default|screen|style|transform|layeredimage'
    r'|translate|python|movie|solid|animation)\b'
)


def _indent_width(line: str) -> int:
    """行首缩进宽度（tab 按 4 计）。"""
    width = 0
    for ch in line:
        if ch == " ":
            width += 1
        elif ch == "\t":
            width += 4
        else:
            break
    return width


def _body_base_indent(lines: list[str], start: int, end: int) -> Optional[int]:
    """label 体第一条有效语句的缩进，作为该 label 的基准缩进。"""
    for i in range(start, end):
        s = lines[i].strip()
        if not s or s.startswith("#"):
            continue
        return _indent_width(lines[i])
    return None

# ── python 块标记 ──
_INIT_PYTHON_RE = re.compile(r'^\s*init\s*(?:-\s*\d+\s*)?python\s*(?:\(?|$)')
_INIT_BLOCK_RE = re.compile(r'^\s*init\b')
_PYTHON_BLOCK_START = re.compile(r'^\s+python\s*(?:\(?|$)')
_PYTHON_BLOCK_END = re.compile(r'\)')


# ── 检测结果 ──

@dataclass
class Finding:
    file: str
    line: int
    line_content: str
    severity: str  # ERROR / WARNING / INFO
    issue: str     # 问题类型
    message: str
    fix: str


@dataclass
class LabelInfo:
    name: str
    file: str
    line: int
    line_content: str
    has_return: bool = False
    return_lines: list[int] = field(default_factory=list)
    body_start: int = 0
    body_end: int = 0


class Report:
    def __init__(self) -> None:
        self.findings: list[Finding] = []
        self._scanned_files: int = 0
        # 全局标签表：label 名 -> 定义列表。_check_issues 用它判断 jump/call
        # 的目标是否存在，必须由扫描过程登记（此前是个从未写入的空 list，
        # 导致所有 jump/call 都被误报为 UNDEFINED_LABEL）。
        self._labels: dict[str, list[LabelInfo]] = {}

    def count(self, sev: str) -> int:
        return sum(1 for f in self.findings if f.severity == sev)

    def add(self, finding: Finding) -> None:
        self.findings.append(finding)

    def summary(self) -> str:
        lines = [
            "",
            "=" * 72,
            "  Ren'Py 标签问题检测",
            "=" * 72,
            f"  扫描文件: {self._scanned_files} 个",
            f"  发现标签: {len(self._labels)} 个",
            f"  问题统计: {len(self.findings)} (ERROR: {self.count('ERROR')}, "
            f"WARNING: {self.count('WARNING')}, INFO: {self.count('INFO')})",
            "=" * 72,
            "",
        ]
        if self.findings:
            # 按严重程度分组
            for sev in ("ERROR", "WARNING", "INFO"):
                sev_findings = [f for f in self.findings if f.severity == sev]
                if not sev_findings:
                    continue
                prefix = {"ERROR": "✗", "WARNING": "!", "INFO": "i"}[sev]
                lines.append(f"  [{sev}] {len(sev_findings)} 个问题")
                for f in sev_findings:
                    lines.append(
                        f"    {prefix} [{f.issue}] {f.file}:{f.line}"
                    )
                    lines.append(f"       内容: {f.line_content.strip()}")
                    lines.append(f"       说明: {f.message}")
                    if f.fix:
                        lines.append(f"       修复: {f.fix}")
                    lines.append("")
        lines.append("=" * 72)
        return "\n".join(lines)


# ── Ren'Py 代码行解析 ──

def _is_python_block_line(
    lines: list[str], idx: int
) -> tuple[bool, bool]:
    """判断第 idx 行是否落在 python 块内（返回 (in_init_python, in_python_block)）。

    保留该函数是为了兼容外部调用；内部扫描已改用单遍状态机
    ``_iter_non_python_lines``。注意：此函数每调用一次都要遍历 ``lines[:idx+1]``，
    在循环里逐行调用会退化成 O(n²)（本文件曾因此在数万行的 tl 文件上卡死）。
    """
    state = _PythonBlockState()
    in_init = in_block = False
    for i in range(idx + 1):
        in_init, in_block = state.feed(lines[i])
    return in_init, in_block


class _PythonBlockState:
    """python 块状态机（单遍推进，O(1) 每行）。

    与旧实现语义一致：先吃进当前行更新状态，再看该行是否处于块内
    （因此 ``init python:`` 这一行本身也算块内行，会被跳过）。
    """

    __slots__ = ("in_init_python", "in_python_block")

    def __init__(self) -> None:
        self.in_init_python = False
        self.in_python_block = False

    def feed(self, line: str) -> tuple[bool, bool]:
        if _INIT_PYTHON_RE.match(line):
            # 一行式 init python(...)：不进块；以冒号结尾则进块
            if "(" in line and ")" in line:
                pass
            elif line.rstrip().endswith(":"):
                self.in_init_python = True
        elif self.in_init_python:
            if re.match(r"^\s*python\s", line):
                self.in_init_python = False
            elif line.strip() and not line.strip().startswith("#"):
                # 有缩进继续留在块内，回到顶格（非注释）则退出
                if not (line.startswith("    ") or line.startswith("\t")):
                    self.in_init_python = False
        elif _PYTHON_BLOCK_START.match(line):
            if ")" in line:
                pass
            elif line.rstrip().endswith(":"):
                self.in_python_block = True
        elif self.in_python_block:
            if re.match(r"^\s+python\s", line):
                self.in_python_block = False
            elif line.strip() == ")":
                self.in_python_block = False
        return self.in_init_python, self.in_python_block


def _iter_non_python_lines(raw_lines: list[str]):
    """单遍产出不在 python 块内的行（生成器，O(n)）。"""
    state = _PythonBlockState()
    for line in raw_lines:
        in_init, in_block = state.feed(line)
        if in_init or in_block:
            continue
        yield line


def _extract_lines(
    filepath: Path,
) -> Optional[list[str]]:
    """读取文件，跳过纯 Python 块内的行（init python 块等）。"""
    try:
        raw_lines = filepath.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception as e:
        print(f"  [SKIP] {filepath}: {e}", file=sys.stderr)
        return None

    return list(_iter_non_python_lines(raw_lines))


# ── 规则检测 ──


def _detect_duplicate_labels(
    filepath: Path,
    lines: list[str],
    report: Report,
) -> dict[str, list[LabelInfo]]:
    """检测重复标签。"""
    labels: dict[str, list[LabelInfo]] = defaultdict(list)
    for idx, line in enumerate(lines, start=1):
        m = _LABEL_DEF_RE.match(line)
        if m:
            name = m.group(1)
            labels[name].append(LabelInfo(
                name=name,
                file=str(filepath),
                line=idx,
                line_content=line,
            ))
    return labels


def _mask_strings(line: str) -> str:
    """把双引号字符串内容替换成等长空格。

    jump/call 只能在语句位置出现，但对白文案里常有 "jump you/me/to..."
    这类普通英文，直接在整行上匹配会把它们当成跳转目标（实测占假报的九成）。
    """
    return re.sub(r'"(?:[^"\\]|\\.)*"', lambda m: " " * len(m.group(0)), line)


def _detect_jump_targets(
    lines: list[str],
    filepath: str,
) -> list[tuple[str, int, str]]:
    """收集所有 jump/call 引用的标签名。
    返回: [(label_name, line_num, line_content), ...]
    """
    refs: list[tuple[str, int, str]] = []
    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith('#') or stripped.startswith('"""') or stripped.startswith("'''"):
            continue

        masked = _mask_strings(line)

        for m in _JUMP_RE.finditer(masked):
            refs.append((m.group(1), idx, line))

        for m in _CALL_LABEL_RE.finditer(masked):
            call_name = m.group(1)
            # call screen <name> / call expression ... 不是标签跳转。
            # （旧实现比较的是匹配之后的文本，`call screen foo` 会被当成
            #  对名为 screen 的标签的调用，产生 10 条假 ERROR。）
            if call_name in ("screen", "expression"):
                continue
            refs.append((call_name, idx, line))

    return refs


def _detect_return_statements(
    labels: dict[str, list[LabelInfo]],
    lines: list[str],
    filepath: str,
) -> None:
    """为每个标签检测 return 语句。"""
    for label_name, label_entries in labels.items():
        for entry in label_entries:
            # 查找该标签块内的 return
            start = entry.line - 1  # 0-indexed
            # 找到下一个标签或文件末尾
            end = len(lines)
            for i in range(start + 1, len(lines)):
                if _LABEL_DEF_RE.match(lines[i]):
                    end = i
                    break

            has_return = False
            return_line_nums = []
            unreachable = []
            base_indent = _body_base_indent(lines, start + 1, end)
            for i in range(start + 1, end):
                # 只认标签体同级的 return；嵌套在 if/menu 里的 return 不终止标签
                if base_indent is not None and _indent_width(lines[i]) != base_indent:
                    continue
                if _RETURN_RE.search(lines[i]):
                    has_return = True
                    return_line_nums.append(i + 1)
                    # 检查 return 后面是否有非空非注释代码
                    for j in range(i + 1, end):
                        stripped = lines[j].strip()
                        if stripped and not stripped.startswith('#') and not stripped.startswith('"'):
                            unreachable.append((j + 1, lines[j]))
                    break  # 只检查第一个 return 后面的

            entry.has_return = has_return
            entry.return_lines = return_line_nums


def _check_issues(
    filepath: Path,
    labels: dict[str, list[LabelInfo]],
    all_labels_global: dict[str, list[LabelInfo]],
    lines: list[str],
    report: Report,
) -> None:
    """检测所有标签问题。"""
    refs = _detect_jump_targets(lines, str(filepath))
    refs_label_names = set(r[0] for r in refs)

    for label_name, label_entries in labels.items():
        for entry in label_entries:
            # ── DUPLICATE_LABEL ──
            if len(label_entries) > 1:
                report.add(Finding(
                    file=str(filepath),
                    line=entry.line,
                    line_content=entry.line_content,
                    severity="ERROR",
                    issue="DUPLICATE_LABEL",
                    message=f"标签 '{label_name}' 在 {filepath.name} 中重复定义（共 {len(label_entries)} 次）",
                    fix="删除多余的标签定义，确保每个标签名只出现一次",
                ))

            # ── UNREACHABLE_CODE ──
            if entry.return_lines:
                start = entry.line - 1
                end = len(lines)
                for i in range(start + 1, len(lines)):
                    if _LABEL_DEF_RE.match(lines[i]):
                        end = i
                        break
                base_indent = _body_base_indent(lines, start + 1, end)
                for ret_line in entry.return_lines:
                    for j in range(ret_line, end):
                        stripped = lines[j].strip()
                        if not stripped or stripped.startswith('#') or stripped.startswith('"'):
                            continue
                        # 声明/定义类语句（init/image/define/screen...）不是控制流，不算不可达
                        if _DECL_RE.match(lines[j]):
                            continue
                        # 只统计与标签体同级的语句，更深缩进属于子块
                        if base_indent is not None and _indent_width(lines[j]) > base_indent:
                            continue
                        report.add(Finding(
                            file=str(filepath),
                                line=j + 1,
                                line_content=lines[j],
                                severity="WARNING",
                                issue="UNREACHABLE_CODE",
                                message=f"标签 '{label_name}' 在第 {ret_line} 行有 return，但第 {j+1} 行还有代码（不可达）",
                                fix="删除 return 之后的代码，或调整代码结构",
                        ))
                        break  # 只报一次

            # ── MISSING_RETURN ──
            if not entry.has_return:
                # 检查是否是屏幕初始化标签、start 标签等特殊标签
                special_labels = {"start", "label", "init", "_label"}
                if label_name not in special_labels:
                    # 跳过一些已知的不需要 return 的特殊标签
                    if label_name.startswith("_call_") or label_name.endswith("_skip"):
                        continue
                    report.add(Finding(
                        file=str(filepath),
                        line=entry.line,
                        line_content=entry.line_content,
                        severity="WARNING",
                        issue="MISSING_RETURN",
                        message=f"标签 '{label_name}' 缺少 return 语句",
                        fix="在标签块末尾添加 return",
                    ))

    # ── UNDEFINED_LABEL ──
    for ref_name, ref_line, ref_content in refs:
        if ref_name not in all_labels_global:
            report.add(Finding(
                file=str(filepath),
                line=ref_line,
                line_content=ref_content,
                severity="ERROR",
                issue="UNDEFINED_LABEL",
                message=f"jump/call 引用了未定义的标签 '{ref_name}'",
                fix=f"检查标签名拼写，或添加标签定义: label {ref_name}:",
            ))

    # ── ORPHAN_LABEL ──
    for label_name, label_entries in labels.items():
        for entry in label_entries:
            if label_name not in refs_label_names and label_name != "start":
                # 检查是否被 call 间接引用（call label_name from ...）
                # 以及是否作为 screen 参数引用
                is_screen_param = False
                for ref_name, _, ref_content in refs:
                    if ref_name == label_name:
                        # 再检查是否是在 call screen 后面的参数
                        if "call screen" in ref_content:
                            is_screen_param = True
                            break

                if not is_screen_param:
                    report.add(Finding(
                        file=str(filepath),
                        line=entry.line,
                        line_content=entry.line_content,
                        severity="INFO",
                        issue="ORPHAN_LABEL",
                        message=f"标签 '{label_name}' 没有被任何 jump/call 引用",
                        fix="确认是否遗漏了跳转到此标签的代码，或这是一个死代码",
                    ))


def _detect_invalid_label_names(
    filepath: Path,
    lines: list[str],
    report: Report,
) -> None:
    """检测非法标签名。"""
    for idx, line in enumerate(lines, start=1):
        m = _LABEL_DEF_RE.match(line)
        if m:
            name = m.group(1)
            if not _LABEL_NAME_RE.match(name):
                report.add(Finding(
                    file=str(filepath),
                    line=idx,
                    line_content=line,
                    severity="ERROR",
                    issue="INVALID_LABEL_NAME",
                    message=f"标签名 '{name}' 不符合 Ren'Py 规范（应以字母或下划线开头，只包含字母、数字、下划线）",
                    fix=f"重命名为合法名称，如 '{name.lower().replace('-', '_').replace(' ', '_')}'",
                ))


def _register_labels(report: Report, labels: dict[str, list[LabelInfo]]) -> None:
    """把本文件的标签登记进全局标签表。"""
    for name, entries in labels.items():
        report._labels.setdefault(name, []).extend(entries)


def _run_checks(
    filepath: Path,
    lines: list[str],
    labels: dict[str, list[LabelInfo]],
    report: Report,
) -> None:
    """在标签已全部登记后，对本文件跑各项检查。"""
    # 为标签检测 return
    _detect_return_statements(labels, lines, str(filepath))

    # 检测非法标签名
    _detect_invalid_label_names(filepath, lines, report)

    # 检测问题（用全局标签表判断 jump/call 目标是否存在）
    _check_issues(filepath, labels, report._labels, lines, report)


def scan_file(filepath: Path, report: Report) -> None:
    """扫描单个文件：先把标签登记到全局表，再检查。"""
    lines = _extract_lines(filepath)
    if lines is None:
        return

    labels = _detect_duplicate_labels(filepath, lines, report)
    _register_labels(report, labels)
    _run_checks(filepath, lines, labels, report)


def _is_translation_or_backup(path: Path) -> bool:
    """tl 翻译目录、隐藏目录（.xxx）与备份目录：翻译块不会定义 label，
    扫它们既无意义又会因文件巨大而拖慢扫描。"""
    for part in path.parts:
        low = part.lower()
        if low == "tl" or low.startswith(".") or "backup" in low:
            return True
    return False


def scan_directory(root: Path, report: Report, include_tl: bool = False) -> None:
    files = []
    for f in root.rglob("*"):
        if not f.is_file() or f.suffix not in (".rpy", ".py"):
            continue
        if "renpy" in str(f).lower() and "/renpy/" in str(f).lower():
            continue  # 引擎自带文件
        if not include_tl and _is_translation_or_backup(f):
            continue  # 翻译/备份目录
        files.append(f)
    files.sort()
    report._scanned_files = len(files)  # type: ignore[attr-defined]
    if not files:
        print(f"  在 {root} 中未找到 .rpy/.py 文件")
        return
    print(f"  扫描 {len(files)} 个文件...")

    # 两遍扫描：先登记全部标签，再检查引用。否则文件按名称顺序处理时，
    # 后面的文件里定义的标签会被前面的 jump/call 误判为未定义。
    cached: list[tuple[Path, list[str], dict[str, list[LabelInfo]]]] = []
    for fp in files:
        lines = _extract_lines(fp)
        if lines is None:
            continue
        labels = _detect_duplicate_labels(fp, lines, report)
        _register_labels(report, labels)
        cached.append((fp, lines, labels))

    for fp, lines, labels in cached:
        _run_checks(fp, lines, labels, report)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ren'Py 标签问题检测"
    )
    parser.add_argument(
        "path", nargs="?", default=None,
        help="要扫描的文件或目录",
    )
    parser.add_argument(
        "--severity", choices=("all", "warning", "error"), default="all",
        help="只显示 >= 此严重程度的问题 (默认: all)",
    )
    # 与统一 CLI 的 `all <项目> -l <lang>` 风格保持一致：本检查与语言无关，
    # 接受该参数仅为兼容统一入口的参数透传，不产生任何效果。
    parser.add_argument(
        "-l", "--language", default=None,
        help="语言代码（本检查与语言无关，仅为兼容统一 CLI 透传而接受）",
    )
    parser.add_argument(
        "--include-tl", action="store_true",
        help="同时扫描 tl/ 翻译目录（默认跳过：翻译块不定义 label，且文件巨大拖慢扫描）",
    )
    args = parser.parse_args()

    target = Path(args.path) if args.path else Path.cwd()
    if not target.exists():
        print(f"  路径不存在: {target}", file=sys.stderr)
        sys.exit(1)

    report = Report()
    if target.is_file():
        report._scanned_files = 1  # type: ignore[attr-defined]
        scan_file(target, report)
    else:
        scan_directory(target, report, include_tl=args.include_tl)

    # 过滤
    severity_order = {"INFO": 0, "WARNING": 1, "ERROR": 2}
    min_severity = {"all": 0, "warning": 1, "error": 2}.get(args.severity, 0)
    if args.severity != "all":
        report.findings = [
            f for f in report.findings
            if severity_order.get(f.severity, 0) >= min_severity
        ]

    print(report.summary())

    err_count = report.count("ERROR")
    warn_count = report.count("WARNING")
    if err_count > 0:
        sys.exit(2)  # 有错误
    elif warn_count > 0:
        sys.exit(0)  # 只有警告，不视为失败
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
