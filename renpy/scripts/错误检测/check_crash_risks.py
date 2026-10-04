#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_crash_risks.py — Ren'Py 运行时崩溃风险静态检测

扫描 .rpy 文件中可能导致运行时崩溃的代码模式，覆盖以下类别：

  [CRITICAL] builtin_shadow       — 内置函数名被赋值遮蔽 (str/int/float/list/...)
  [CRITICAL] translation_shadow   — Ren'Py 翻译函数 _ 被赋值/解包遮蔽，导致 _("...") TypeError
  [CRITICAL] map_misuse           — Python3 map() 返回迭代器后的误用
  [WARNING]  globals_access       — globals()["dynamic_key"] 动态访问无保护
  [WARNING]  unsafe_intconv       — int()/float() 转换无 try-except
  [WARNING]  div_zero             — 除法运算潜在除零
  [WARNING]  none_concat          — 字符串拼接可能涉及 None
  [INFO]     bare_except          — 裸 except 吞掉异常 (可能隐藏 bug)

用法:
  python check_crash_risks.py <项目目录> [--fix-suggestions]
  python check_crash_risks.py <项目目录> --severity CRITICAL
  python check_crash_risks.py <项目目录> --no-tl          # 跳过翻译目录

选项:
  --fix-suggestions  显示修复建议
  --severity LEVEL   只显示指定级别 (CRITICAL/WARNING/INFO)
  --no-tl            跳过 tl/ 翻译目录
"""
import argparse
import os
import re
import sys
from collections import defaultdict

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── 内置函数名列表（被遮蔽后会导致 TypeError） ──
BUILTIN_NAMES = {
    "int", "float", "str", "bool", "list", "dict", "set", "tuple",
    "type", "len", "sum", "abs", "round", "min", "max",
    "sorted", "filter", "map", "range", "print", "input", "open",
    "format", "next", "iter", "enumerate", "zip",
    "hasattr", "getattr", "setattr", "isinstance", "issubclass",
    "callable", "repr", "chr", "ord", "hex", "oct", "bin", "pow",
}

# ── 严重级别排序 ──
SEVERITY_ORDER = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}
SEVERITY_SYMBOL = {"CRITICAL": "!!", "WARNING": "!", "INFO": "."}


class Finding:
    """一条检测结果"""
    def __init__(self, file, line_no, line, category, severity, message, suggestion=""):
        self.file = file
        self.line_no = line_no
        self.line = line.strip()
        self.category = category
        self.severity = severity
        self.message = message
        self.suggestion = suggestion

    def __lt__(self, other):
        return SEVERITY_ORDER.get(self.severity, 9) < SEVERITY_ORDER.get(other.severity, 9)


def find_rpy_files(root, skip_tl=True, include_engine=False):
    """递归查找所有 .rpy 文件

    - skip_tl: 跳过 tl/ 翻译目录
    - include_engine: 默认跳过游戏自带引擎运行时目录 (renpy/ 等)，
      引擎源码 (renpy/common 等) 大量使用 _ 作占位符和内置名遮蔽，
      属正常写法，扫描只会产生误报。
    """
    results = []
    SKIP_DIRS = ("renpy", "lib", "cache", "saves")
    for dirpath, dirnames, filenames in os.walk(root):
        base = os.path.basename(dirpath)
        # 跳过翻译目录
        if skip_tl and base == "tl":
            dirnames[:] = []
            continue
        # 跳过隐藏目录 (.git, .fix_name_backup 等)
        if dirpath != root and base.startswith("."):
            dirnames[:] = []
            continue
        # 跳过引擎运行时目录（renpy/、lib/ 等）
        if not include_engine and dirpath != root:
            top = os.path.relpath(dirpath, root).split(os.sep)[0]
            if top.lower() in SKIP_DIRS:
                dirnames[:] = []
                continue
        for fn in filenames:
            if fn.endswith(".rpy"):
                results.append(os.path.join(dirpath, fn))
    return sorted(results)


# 作用域头部：def / screen / python / init python / label
HEADER_RE = re.compile(
    r'^\s*(def\s|screen\s|python\s|python\b|init\s(?:-?\d+\s+)?python|label\s)'
)


def _indent(line):
    m = re.match(r'^(\s*)', line)
    return len(m.group(1)) if m else 0


def find_enclosing_scope(lines, idx):
    """返回包含 idx 行的最小作用域 (start, end)，0-based 左闭右开。

    向上找最近的缩进更小的作用域头部（def/screen/python/label），
    再向下找到该块的结束位置。找不到任何头部则返回 (0, len(lines))，
    表示 store 全局作用域。
    """
    cur_indent = _indent(lines[idx])
    scope_start = -1
    scope_indent = -1
    for j in range(idx - 1, -1, -1):
        s = lines[j]
        if not s.strip() or s.strip().startswith("#"):
            continue
        indent = _indent(s)
        if indent < cur_indent:
            if HEADER_RE.search(s):
                scope_start = j
                scope_indent = indent
                break
            cur_indent = indent
    if scope_start < 0:
        return (0, len(lines))  # store 级
    end = len(lines)
    for j in range(scope_start + 1, len(lines)):
        s = lines[j]
        if not s.strip() or s.strip().startswith("#"):
            continue
        if _indent(s) <= scope_indent:
            end = j
            break
    return (scope_start, end)


def scope_uses_func(lines, scope, name):
    """检查作用域内是否实际调用了 name(...)（排除头部行与注释行）"""
    start, end = scope
    pat = re.compile(rf'(?<![\w.]){re.escape(name)}\s*\(')
    for j in range(start, end):
        s = lines[j]
        stripped = s.strip()
        if j == start and HEADER_RE.search(s):
            continue  # 跳过作用域头部行本身
        if stripped.startswith("#"):
            continue
        if pat.search(s):
            return True
    return False


def read_lines(filepath):
    """读取文件行，自动处理编码"""
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            with open(filepath, encoding=enc) as f:
                return f.readlines()
        except (UnicodeDecodeError, IOError):
            continue
    return []


# ═══════════════════════════════════════════════════════════════
#  检测器
# ═══════════════════════════════════════════════════════════════

def check_builtin_shadow(filepath, lines):
    """检测内置函数名被赋值遮蔽"""
    findings = []
    # $ str = ... / $ int = ... /  str = ... in python blocks
    pattern = re.compile(
        r'(?:\$\s+|^\s*)(int|float|str|bool|list|dict|set|tuple|type|len|sum|abs|round|min|max|sorted|filter|map|range|print|input|open|format|next|iter|enumerate|zip|hasattr|getattr|setattr|isinstance|callable|repr|chr|ord|hex|oct|bin|pow)\s*=\s*[^=]'
    )
    for i, line in enumerate(lines, 1):
        # 跳过注释行
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        m = pattern.search(line)
        if m:
            name = m.group(1)
            # 作用域核实：局部作用域（def/screen/python 块）内若从未调用
            # 该名字的函数形式，遮蔽无害，不报（避免 screen 内重名误报）。
            scope = find_enclosing_scope(lines, i - 1)
            in_local_scope = scope != (0, len(lines))
            if in_local_scope and not scope_uses_func(lines, scope, name):
                continue
            where = "当前作用域" if in_local_scope else "store 全局"
            findings.append(Finding(
                filepath, i, line, "builtin_shadow", "CRITICAL",
                f"内置函数 '{name}' 被赋值遮蔽，{where}后续调用 {name}() 将触发 TypeError",
                f"将变量重命名为 {name}_val 或其他不冲突的名称"
            ))
    return findings


def check_translation_shadow(filepath, lines):
    """检测 Ren'Py 翻译函数 _ 被赋值或解包遮蔽

    典型错误模式（触发 TypeError: 'int' object is not callable）：
      $ a, b, _ = some_func()          # _ 被赋值为返回值
      $ _ = some_value                 # _ 被直接赋值
      major, minor, _ = get_version()  # python block 中解包
    """
    findings = []

    # 匹配 $ a, b, _ = ... 或 $ _ = ... 或 python block 中 a, b, _ = ...
    # 捕获 _ 在赋值左侧（单独、或作为元组解包最后一项）
    # 模式1：元组解包中含 _ ，如 a, b, _ = ...  或  a, _, c = ...
    unpack_pattern = re.compile(
        r'(?:^\s*\$\s*|^\s*)(?:[\w]+\s*,\s*)*_\s*(?:,\s*[\w]+\s*)*=\s*[^=]'
    )
    # 模式2：直接赋值 $ _ = ...
    direct_pattern = re.compile(
        r'(?:^\s*\$\s*)_\s*=\s*[^=]'
    )

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        # 检查直接赋值 $ _ = ...
        if direct_pattern.match(line):
            scope = find_enclosing_scope(lines, i - 1)
            in_local_scope = scope != (0, len(lines))
            if in_local_scope and not scope_uses_func(lines, scope, "_"):
                continue
            findings.append(Finding(
                filepath, i, line, "translation_shadow", "CRITICAL",
                "变量 '_' 被赋值，遮蔽 Ren'Py 内置翻译函数，同屏幕/作用域内 _(\"...\") 调用将触发 TypeError",
                "将占位变量重命名，如 _ignored、_val、_unused 等"
            ))
            continue
        # 检查解包赋值中含 _ 的情况（排除 __ 之类双下划线）
        if unpack_pattern.match(line):
            # 确认 _ 是独立的（不是 __something__）
            # 在赋值左侧找 \b_\b（只含 _，前后不是字母数字下划线）
            lhs_match = re.match(r'^(\s*\$?\s*)([^=]+)=', line)
            if lhs_match:
                lhs = lhs_match.group(2)
                # _ 需作为独立标识符出现
                if re.search(r'(?<![_\w])_(?![_\w])', lhs):
                    # 作用域核实：局部作用域内若从未调用 _("...")，遮蔽无害
                    scope = find_enclosing_scope(lines, i - 1)
                    in_local_scope = scope != (0, len(lines))
                    if in_local_scope and not scope_uses_func(lines, scope, "_"):
                        continue
                    where = ("当前作用域" if in_local_scope else "store 全局")
                    findings.append(Finding(
                        filepath, i, line, "translation_shadow", "CRITICAL",
                        f"解包赋值中使用 '_' 作为占位符，遮蔽 Ren'Py 翻译函数，"
                        f"{where}的 _(\"...\") 调用将触发 TypeError: 'int' object is not callable",
                        "将 _ 改为 _patch、_unused 或其他不冲突的名称，例如: a, b, _patch = func()"
                    ))
    return findings


def check_map_misuse(filepath, lines):
    """检测 map() 返回迭代器后的误用模式"""
    findings = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue

        # map() 结果被多次消费：先 list() 再用原变量
        if "map(" in line:
            # 检查上下文：是否有同变量名的 list() 调用
            var_match = re.search(r'(\w+)\s*=\s*map\(', line)
            if var_match:
                var_name = var_match.group(1)
                # 向后看 10 行，检查是否再次使用该变量
                for j in range(i, min(i + 10, len(lines))):
                    if re.search(rf'\blist\s*\(\s*{re.escape(var_name)}\s*\)', lines[j]) and j > i - 1:
                        # 已经用 list() 包裹，安全
                        break
                    # 直接使用变量名于 join/sum/len 等
                    if re.search(rf'(join|sum|len|min|max|sorted)\s*\(\s*{re.escape(var_name)}\s*\)', lines[j]):
                        # join 可以接迭代器，安全
                        if "join" in lines[j]:
                            break

        # map() 结果直接解包后，原变量不能再 list()
        if re.search(r'\w+\s*,\s*\w+\s*,?\s*\w*\s*=\s*map\(', line):
            findings.append(Finding(
                filepath, i, line, "map_misuse", "WARNING",
                "map() 返回迭代器解包后不能再被消费；若后续代码尝试 list(var) 将得到空列表",
                "将 map() 改为 [x for x in ...] 或 list(map(...)) 以支持多次遍历"
            ))

        # map() 返回值直接传给需要多次迭代的函数
        if re.search(r'reduce\s*\(\s*\w+,\s*map\(', line):
            findings.append(Finding(
                filepath, i, line, "map_misuse", "WARNING",
                "map() 结果直接传给 reduce()，若 reduce 需要多次遍历将失败",
                "改为 reduce(func, list(map(...)))"
            ))
    return findings


def check_globals_access(filepath, lines):
    """检测 globals()["dynamic_key"] 动态访问缺少保护"""
    findings = []
    # 匹配 globals()["xxx"] 或 globals()[f"xxx"] 或 globals()[var]
    pattern = re.compile(r'globals\(\)\s*\[\s*')
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if pattern.search(line):
            # 检查是否在 try-except 块中（简单启发：往前 5 行找 try）
            in_try = False
            for j in range(max(0, i - 6), i - 1):
                if "try" in lines[j] and not lines[j].strip().startswith("#"):
                    in_try = True
                    break
            if not in_try:
                # 提取 key 信息
                key_match = re.search(r'globals\(\)\s*\[\s*([^]]+)\s*\]', line)
                key_desc = key_match.group(1) if key_match else "?"
                severity = "WARNING"
                findings.append(Finding(
                    filepath, i, line, "globals_access", severity,
                    f"globals()[{key_desc}] 动态访问无 try-except 保护，可能 KeyError",
                    "用 try-except 包裹或用 globals().get(key, default)"
                ))
    return findings


def check_unsafe_intconv(filepath, lines):
    """检测 int()/float() 转换无 try-except 保护（仅 Python 代码行）"""
    findings = []
    pattern = re.compile(r'\b(int|float)\s*\(')
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        # 只检查 $ 行或 python block 中的行
        if not (stripped.startswith("$") or stripped.startswith("return") or
                stripped.startswith("if ") or stripped.startswith("elif ") or
                stripped.startswith("else:") or "=" in stripped):
            continue
        # 跳过 define/screen/image/label 等声明行
        first_word = stripped.split()[0] if stripped.split() else ""
        if first_word in ("define", "screen", "image", "label", "transform", "style", "menu", "show", "play", "scene", "voice", "window"):
            continue
        # 跳过 def 行
        if re.match(r'\s*def\s+(int|float)\b', line):
            continue
        if re.search(r'=\s*(int|float)\s*$', line.strip()):
            continue

        matches = pattern.findall(line)
        if not matches:
            continue

        # 排除安全模式
        safe_patterns = [
            r'int\s*\(\s*\d+\s*\)',
            r'float\s*\(\s*[\d.]+\s*\)',
            r'int\s*\(\s*len\s*\(',
            r'int\s*\(\s*round\s*\(',
            r'int\s*\(\s*float\s*\(',
            r'int\s*\(\s*bool\s*\(',
            r'float\s*\(\s*int\s*\(',
            r'float\s*\(\s*\d',
        ]
        is_safe = False
        for sp in safe_patterns:
            if re.search(sp, line):
                is_safe = True
                break

        if is_safe:
            continue

        # 检查是否在 try-except 中
        in_try = False
        for j in range(max(0, i - 6), i - 1):
            stripped_j = lines[j].strip()
            if stripped_j.startswith("try") and not stripped_j.startswith("#"):
                in_try = True
                break

        if not in_try:
            fn = matches[0]
            findings.append(Finding(
                filepath, i, line, "unsafe_intconv", "WARNING",
                f"{fn}() 转换可能抛出 ValueError (非数字字符串) 或 TypeError (None/复杂对象)",
                f"用 try-except 包裹或验证输入类型后再转换"
            ))
    return findings


def check_div_zero(filepath, lines):
    """检测除法运算潜在除零（仅检查 Python 代码行）"""
    findings = []
    # Ren'Py 文本标签，不应误报为除法
    RENPY_TAGS = {
        "s", "i", "b", "u", "color", "size", "cps", "font", "a",
        "alpha", "w", "h", "vspace", "hspace", "p", "nw", "fast",
        "done", "art", "plain", "now", "k", "u", "strike",
    }
    # 文件路径片段
    PATH_KEYWORDS = {"chapters", "images", "game", "gui", "audio", "renpy", "common"}
    # 只匹配真正的 Python 除法: var / var 或 var // var
    # 必须是 $ 行或 python block 内的 return/赋值行
    div_pattern = re.compile(r'\b(\w+)\s*(?://|/)\s*(\w+)\b')

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        # 只检查 $ 开头的 Python 赋值行
        if not stripped.startswith("$"):
            continue
        # 跳过字符串内的内容（简单启发：如果行有引号，只检查引号外）
        code_part = re.sub(r'"[^"]*"|\'[^\']*\'', '', line)

        for m in div_pattern.finditer(code_part):
            divisor = m.group(2)
            # 跳过字面量数字
            if divisor.isdigit():
                continue
            # 跳过 Ren'Py 标签和路径关键词
            if divisor in RENPY_TAGS or divisor in PATH_KEYWORDS:
                continue
            # 跳过已知安全函数
            if divisor in ("len", "size", "count", "total", "float", "int"):
                continue
            # 检查是否前面有零值检查
            has_check = False
            for j in range(max(0, i - 5), i):
                if re.search(rf'\b{re.escape(divisor)}\s*(==|!=|<|>|<=|>=)\s*0', lines[j]):
                    has_check = True
                    break
                if re.search(rf'\bif\s+{re.escape(divisor)}\b', lines[j]):
                    has_check = True
                    break
            if not has_check:
                findings.append(Finding(
                    filepath, i, line, "div_zero", "WARNING",
                    f"除以变量 '{divisor}'，可能为零值导致 ZeroDivisionError",
                    f"在除法前检查 if {divisor} != 0"
                ))
                break  # 每行只报一次
    return findings


def check_none_concat(filepath, lines):
    """检测字符串拼接可能涉及 None（仅检查 Python 代码行）"""
    findings = []
    RENPY_TAGS = {"ascii_letters", "ascii_lowercase", "ascii_uppercase", "digits", "hexdigits"}
    # 匹配 "..." + var 或 var + "..." 模式（仅 $ 行）
    pattern = re.compile(r'"[^"]*"\s*\+\s*(\w+)|(\w+)\s*\+\s*"[^"]*"')
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        # 只检查 $ 开头的 Python 行
        if not stripped.startswith("$"):
            continue
        # 跳过 f-string 行
        if 'f"' in line or "f'" in line:
            continue
        for m in pattern.finditer(line):
            var = m.group(1) or m.group(2)
            if not var:
                continue
            # 跳过已知安全值
            if var in ("str", "int", "float") or var in RENPY_TAGS:
                continue
            # 跳过全大写常量
            if var.isupper():
                continue
            findings.append(Finding(
                filepath, i, line, "none_concat", "INFO",
                f"字符串拼接中变量 '{var}' 可能为 None，导致 TypeError",
                "用 str(var) 包裹或改用 f-string: f\"...{var}...\""
            ))
    return findings


def check_bare_except(filepath, lines):
    """检测裸 except 吞掉异常"""
    findings = []
    pattern = re.compile(r'^\s*except\s*:')

    # 更宽泛的裸 except（不含具体异常类型）
    pattern_bare = re.compile(r'^\s*except\s*:\s*$')
    pattern_bare_inline = re.compile(r'^\s*except\s*:\s*')

    for i, line in enumerate(lines, 1):
        if pattern_bare.match(line) or pattern_bare_inline.match(line):
            # 检查是否至少有 pass 或 log
            has_handling = False
            for j in range(i, min(i + 5, len(lines))):
                stripped_j = lines[j].strip()
                if "pass" in stripped_j or "log" in stripped_j or "print" in stripped_j:
                    has_handling = True
                    break
                if not stripped_j or stripped_j.startswith("#"):
                    continue
                break

            findings.append(Finding(
                filepath, i, line, "bare_except", "INFO",
                "裸 except: 会吞掉所有异常（包括 KeyboardInterrupt），可能隐藏 bug",
                "改为 except Exception: 或指定具体异常类型"
            ))
    return findings


# ═══════════════════════════════════════════════════════════════
#  主流程
# ═══════════════════════════════════════════════════════════════

ALL_CHECKERS = [
    ("builtin_shadow",      check_builtin_shadow),
    ("translation_shadow",  check_translation_shadow),
    ("map_misuse",          check_map_misuse),
    ("globals_access",      check_globals_access),
    ("unsafe_intconv",      check_unsafe_intconv),
    ("div_zero",            check_div_zero),
    ("none_concat",         check_none_concat),
    ("bare_except",         check_bare_except),
]


def main():
    ap = argparse.ArgumentParser(
        description="Ren'Py 运行时崩溃风险静态检测",
        usage="python check_crash_risks.py <项目目录> [选项]",
    )
    ap.add_argument("project", help="Ren'Py 项目 game 目录路径")
    ap.add_argument("--fix-suggestions", action="store_true", help="显示修复建议")
    ap.add_argument("--severity", choices=["CRITICAL", "WARNING", "INFO"],
                    help="只显示指定级别及更高")
    ap.add_argument("--no-tl", action="store_true", default=True,
                    help="跳过 tl/ 翻译目录 (默认跳过)")
    ap.add_argument("--include-tl", action="store_true",
                    help="包含 tl/ 翻译目录")
    ap.add_argument("--include-engine", action="store_true",
                    help="包含游戏自带引擎目录 renpy/、lib/ 等（默认跳过，引擎源码误报多）")
    # 统一 CLI 会把 -l/--language 原样转发给 all 中的每个检查器；崩溃检测
    # 默认跳过 tl，因此该参数仅用于保持命令兼容，不参与源码扫描。
    ap.add_argument("-l", "--language", default="schinese", help=argparse.SUPPRESS)
    args = ap.parse_args()

    if not os.path.isdir(args.project):
        print(f"错误: 目录不存在: {args.project}")
        sys.exit(1)

    skip_tl = args.no_tl and not args.include_tl
    files = find_rpy_files(args.project, skip_tl=skip_tl,
                           include_engine=args.include_engine)
    if not files:
        print(f"未找到 .rpy 文件: {args.project}")
        sys.exit(1)

    print(f"扫描 {len(files)} 个 .rpy 文件")
    print(f"目录: {args.project}")
    print(f"跳过翻译目录: {'是' if skip_tl else '否'}")
    print(f"跳过引擎目录: {'否' if args.include_engine else '是 (renpy/、lib/ 等)'}")
    print("=" * 60)

    all_findings = []
    for fpath in files:
        lines = read_lines(fpath)
        if not lines:
            continue
        rel_path = os.path.relpath(fpath, args.project)
        for name, checker in ALL_CHECKERS:
            findings = checker(fpath, lines)
            for f in findings:
                f.file = rel_path
                all_findings.append(f)

    # 按严重级别排序
    all_findings.sort()

    # 过滤严重级别
    if args.severity:
        max_order = SEVERITY_ORDER[args.severity]
        severity_filter = {s for s, o in SEVERITY_ORDER.items() if o <= max_order}
        all_findings = [f for f in all_findings if f.severity in severity_filter]

    # 按类别统计
    by_category = defaultdict(list)
    for f in all_findings:
        by_category[f.category].append(f)

    # 输出
    for f in all_findings:
        sym = SEVERITY_SYMBOL.get(f.severity, "?")
        print(f"\n[{f.severity}] {f.category} — {f.file}:{f.line_no}")
        print(f"  {f.line}")
        print(f"  >> {f.message}")
        if args.fix_suggestions and f.suggestion:
            print(f"  FIX: {f.suggestion}")

    # 汇总
    print("\n" + "=" * 60)
    print("汇总:")
    critical = sum(1 for f in all_findings if f.severity == "CRITICAL")
    warning = sum(1 for f in all_findings if f.severity == "WARNING")
    info = sum(1 for f in all_findings if f.severity == "INFO")
    print(f"  CRITICAL: {critical}")
    print(f"  WARNING:  {warning}")
    print(f"  INFO:     {info}")
    print(f"  总计:     {len(all_findings)}")

    if by_category:
        print("\n按类别:")
        for cat, items in sorted(by_category.items()):
            print(f"  {cat:20s} {len(items)}")

    # 退出码：有 CRITICAL 则返回 1
    if critical > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
