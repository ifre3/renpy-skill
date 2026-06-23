"""
Ren'Py 错误日志解析器 — 读取 traceback 并给出修复建议
基于 Ren'Py 8.5.3 官方错误处理 (renpy/config.py error_suggestion_handlers,
renpy/error.py, renpy/lint.py) 和常见错误模式
"""
import os
import re
import glob
from datetime import datetime
ERROR_PATTERNS = [
    {
        "pattern": r"LabelNotFound",
        "advice": "label 未定义。检查 jump/call 的目标 label 名是否正确（区分大小写）。",
        "type": "label_not_found"
    },
    {
        "pattern": r"ScreenNotFound",
        "advice": "screen 未定义。检查 show screen / ShowMenu() 中的 screen 名是否存在。",
        "type": "screen_not_found"
    },
    {
        "pattern": r"ImageNotFound",
        "advice": "图片未找到。确认图片文件在 game/images/ 下，检查文件名大小写。",
        "type": "image_not_found"
    },
    {
        "pattern": r"can't set attribute",
        "advice": "存档不兼容。类定义已改变（新增 __slots__ / 只读属性），旧存档无法反序列化。",
        "type": "save_compat"
    },
    {
        "pattern": r"AttributeError",
        "advice": "属性错误。可能原因：角色变量未定义、对象没有该属性、存档版本不兼容。",
        "type": "attribute_error"
    },
    {
        "pattern": r"NameError",
        "advice": "变量未定义。检查 define/default 语句或 Python 块中的变量名是否拼写正确。",
        "type": "name_error"
    },
    {
        "pattern": r"SyntaxError",
        "advice": "Ren'Py/Python 语法错误。检查引号/括号/缩进是否匹配，特别注意多行字符串。",
        "type": "syntax_error"
    },
    {
        "pattern": r"IndentationError",
        "advice": "缩进错误。Ren'Py 使用 4 空格缩进，不要混用 tab 和空格。",
        "type": "indentation_error"
    },
    {
        "pattern": r"ParseError",
        "advice": "脚本解析错误。常见原因：未闭合的括号/引号、缩进不匹配、未终止的字符串字面量。",
        "type": "parser_error"
    },
    {
        "pattern": r"TypeError",
        "advice": "数据类型错误。检查函数参数类型、变量类型是否正确。",
        "type": "type_error"
    },
    {
        "pattern": r"UnicodeDecodeError",
        "advice": "文件编码错误。确保 .rpy 文件使用 UTF-8 编码保存（无 BOM）。",
        "type": "encoding_error"
    },
    {
        "pattern": r"Couldn't find file",
        "advice": "文件未找到。确认图片/音频/字体文件路径是否正确，注意大小写和扩展名。",
        "type": "file_not_found"
    },
    {
        "pattern": r"^Exception:",
        "advice": "未捕获异常。检查 Python 语法和 Ren'Py 语句格式。",
        "type": "exception"
    },
    {
        "pattern": r"KeyError",
        "advice": "字典键不存在。检查字典变量中是否包含该键。",
        "type": "key_error"
    },
    {
        "pattern": r"IndexError",
        "advice": "列表索引越界。检查列表长度和索引值。",
        "type": "index_error"
    },
    {
        "pattern": r"IOError|FileNotFoundError",
        "advice": "文件读写错误。检查文件路径是否存在、是否有读写权限。",
        "type": "io_error"
    },
    {
        "pattern": r"ScriptError",
        "advice": "Ren'Py 脚本错误。检查 init 优先级、变量重复定义等。",
        "type": "script_error"
    },

    {
        "pattern": r"RecursionError|maximum recursion depth exceeded",
        "advice": "递归深度超限。检查 screen/ATL transform 是否形成了无限递归调用（screen 反复调用自身，或 ATL contains 循环嵌套）。",
        "type": "recursion_error"
    },
    {
        "pattern": r"UnboundLocalError",
        "advice": "局部变量未绑定。python 块中如果对变量赋值，该变量被视为局部变量；如需修改全局变量请用 'global var_name' 或 'store.var_name = value'。",
        "type": "unbound_local_error"
    },
    {
        "pattern": r"ImportError|ModuleNotFoundError",
        "advice": "模块导入失败。检查 Python 模块路径是否正确，或模块是否已安装。",
        "type": "import_error"
    },
    {
        "pattern": r"UnpicklingError|pickle",
        "advice": "存档文件损坏或版本不兼容。存档可能由不同版本的 Ren'Py 或 Python 创建，建议删除旧存档。",
        "type": "unpickling_error"
    },
    {
        "pattern": r"ValueError",
        "advice": "值错误。检查变量值是否在有效范围内，如颜色值、数值参数等。",
        "type": "value_error"
    },]
class Issue:
    """诊断结果。"""
    def __init__(self, issue_type, severity, message, advice, line=None, file=None):
        self.issue_type = issue_type
        self.severity = severity
        self.message = message
        self.advice = advice
        self.line = line
        self.file = file
    def __str__(self):
        return f"[{self.severity}] {self.issue_type}: {self.message}\n  -> {self.advice}"
class Diagnoser:
    """Ren'Py 错误日志解析器。"""
    def __init__(self, project_dir=None, log_path=None):
        self.project_dir = os.path.abspath(project_dir) if project_dir else None
        self.log_path = log_path
        self.raw_text = ""
        self.issues = []
    def _find_log(self):
        if self.log_path and os.path.isfile(self.log_path):
            return self.log_path
        if self.project_dir:
            for fname in ["traceback.txt", "errors.txt", "renpy.log", "log.txt"]:
                for root, _, files in os.walk(self.project_dir):
                    if fname in files:
                        return os.path.join(root, fname)
        return None
    def load_log(self, text=None):
        if text:
            self.raw_text = text
        else:
            path = self._find_log()
            if not path:
                raise FileNotFoundError(f"未找到错误日志文件")
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                self.raw_text = f.read()
            self.log_path = path
        return self
    def analyze(self):
        self.issues = []
        lines = self.raw_text.split("\n")
        for i, line in enumerate(lines, 1):
            for pattern in ERROR_PATTERNS:
                if re.search(pattern["pattern"], line):
                    severity = "ERROR" if pattern["type"] in (
                        "syntax_error", "label_not_found", "save_compat"
                    ) else "WARN"
                    self.issues.append(Issue(
                        issue_type=pattern["type"],
                        severity=severity,
                        message=line.strip()[:120],
                        advice=pattern["advice"],
                        line=i,
                        file=os.path.basename(self.log_path) if self.log_path else None,
                    ))
                    break
        if not self.issues:
            self.issues.append(Issue(
                "unknown", "INFO",
                "未匹配到已知错误模式",
                "建议手动查阅日志内容或在 Ren'Py 官方论坛/文档中搜索相关错误。"
            ))
        return self
    def report(self):
        lines = [f"Ren'Py 错误诊断报告", "=" * 50]
        if self.log_path:
            lines.append(f"来源: {self.log_path}")
        lines.append(f"问题数: {len(self.issues)}")
        lines.append("")
        for issue in self.issues:
            lines.append(str(issue))
            lines.append("")
        return "\n".join(lines)
def diagnose_from_file(path=None, text=None):
    """便捷函数：从文件或文本诊断。"""
    d = Diagnoser(log_path=path)
    d.load_log(text=text)
    d.analyze()
    return d.issues
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Ren'Py 错误日志解析器")
    parser.add_argument("path", nargs="?", help="项目目录或日志文件路径")
    parser.add_argument("--file", help="指定日志文件路径")
    args = parser.parse_args()
    target = args.file or args.path
    d = Diagnoser(project_dir=target if target and os.path.isdir(target) else None,
                   log_path=target if target and os.path.isfile(target) else None)
    if not d.log_path and not d.project_dir:
        d.log_path = "traceback.txt"
    try:
        d.load_log()
        d.analyze()
        print(d.report())
    except FileNotFoundError as e:
        print(f"❌ {e}")
        return 1
if __name__ == "__main__":
    main()
