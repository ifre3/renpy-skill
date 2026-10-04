"""
Ren'Py SDK CLI 封装（瘦身版）— 只保留高频工程操作

用法：
    cli = RenPyCLI(sdk_path="<SDK 根目录，留空自动检测>")
    cli.lint("D:/my_game")                    # 检查脚本
    cli.compile("D:/my_game")                 # 编译
    cli.distribute("D:/my_game")              # 桌面发布包
    cli.translate("D:/my_game", "chinese")    # 生成翻译
    cli.run("D:/my_game")                     # 运行

参考：Ren'Py 8.5.3 CLI (doc/cli.html)
"""

import os
import sys
import subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sdk_common import detect_sdk, find_platform_python


class RenPyCLI:
    """Ren'Py SDK 命令行封装（高频操作）。"""

    def __init__(self, sdk_path: str = None):
        self.sdk_path = detect_sdk(sdk_path)
        self.python_exe = find_platform_python(self.sdk_path)

    def _renpy_py(self) -> str:
        return os.path.join(self.sdk_path, "renpy.py")

    def _run(self, args: list, timeout: int = 300) -> subprocess.CompletedProcess:
        """执行 renpy.py 命令。"""
        cmd = [self.python_exe, self._renpy_py()] + args
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )

    # ── 运行 ────────────────────────────────────────────

    def run(self, project_dir: str) -> subprocess.CompletedProcess:
        """运行项目 (renpy.py <basedir>)。"""
        return self._run([project_dir])

    def quit(self, project_dir: str) -> subprocess.CompletedProcess:
        """退出 Ren'Py (renpy.py <basedir> quit)。"""
        return self._run([project_dir, "quit"])

    # ── 检查与编译 ──────────────────────────────────────

    def lint(self, project_dir: str, filename: str = None,
             error_code: bool = False, all_problems: bool = False) -> subprocess.CompletedProcess:
        """检查脚本 (Lint)。"""
        args = [project_dir, "lint"]
        if filename:
            args.append(filename)
        if error_code:
            args.append("--error-code")
        if all_problems:
            args.append("--all-problems")
        return self._run(args)

    def compile(self, project_dir: str, keep_orphan_rpyc: bool = False) -> subprocess.CompletedProcess:
        """编译 .rpy → .rpyc。"""
        args = [project_dir, "compile"]
        if keep_orphan_rpyc:
            args.append("--keep-orphan-rpyc")
        return self._run(args)

    def rmpersistent(self, project_dir: str) -> subprocess.CompletedProcess:
        """删除持久化数据（⚠️ 不可恢复）。"""
        return self._run([project_dir, "rmpersistent"])

    # ── 构建与分发 ──────────────────────────────────────

    def distribute(self, project_dir: str, package: list = None,
                   packagedest: str = None, no_update: bool = False) -> subprocess.CompletedProcess:
        """构建桌面发布包 (Windows/macOS/Linux)。"""
        args = [project_dir, "distribute"]
        for p in package or []:
            args.extend(["--package", p])
        if packagedest:
            args.extend(["--packagedest", packagedest])
        if no_update:
            args.append("--no-update")
        return self._run(args, timeout=600)

    def android_build(self, project_dir: str, destination: str = None,
                      bundle: bool = False, install: bool = False) -> subprocess.CompletedProcess:
        """构建 Android 发布包（耗时）。"""
        args = ["launcher", "android_build", project_dir]
        if destination:
            args.extend(["--destination", destination])
        if bundle:
            args.append("--bundle")
        if install:
            args.append("--install")
        return self._run(args, timeout=600)

    def web_build(self, project_dir: str, destination: str = None,
                  launch: bool = False) -> subprocess.CompletedProcess:
        """构建 Web (HTML5) 发布包。"""
        args = ["launcher", "web_build", project_dir]
        if destination:
            args.extend(["--destination", destination])
        if launch:
            args.append("--launch")
        return self._run(args, timeout=600)

    # ── 翻译与本地化 ────────────────────────────────────

    def translate(self, project_dir: str, language: str,
                  empty: bool = False, strings_only: bool = False) -> subprocess.CompletedProcess:
        """生成/更新翻译文件。"""
        args = [project_dir, "translate", language]
        if empty:
            args.append("--empty")
        if strings_only:
            args.append("--strings-only")
        return self._run(args)

    def extract_strings(self, project_dir: str, language: str,
                        destination: str, merge: bool = False) -> subprocess.CompletedProcess:
        """导出翻译为 JSON。"""
        args = [project_dir, "extract_strings", language, destination]
        if merge:
            args.append("--merge")
        return self._run(args)

    def merge_strings(self, project_dir: str, language: str,
                      source: str, replace: bool = False) -> subprocess.CompletedProcess:
        """从 JSON 导入翻译。"""
        args = [project_dir, "merge_strings", language, source]
        if replace:
            args.append("--replace")
        return self._run(args)

    # ── 工具方法 ────────────────────────────────────────

    def format_result(self, result: subprocess.CompletedProcess) -> str:
        """格式化命令执行结果。"""
        lines = [f"退出码: {result.returncode}"]
        if result.stdout.strip():
            out_lines = result.stdout.strip().split("\n")
            if len(out_lines) > 30:
                out_lines = out_lines[-30:]
                lines.append(f"--- stdout (末 {len(out_lines)} 行) ---")
            else:
                lines.append("--- stdout ---")
            lines.extend(out_lines)
        if result.stderr.strip():
            lines.append("--- stderr ---")
            lines.append(result.stderr.strip()[-2000:])
        return "\n".join(lines)


# ── CLI ─────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Ren'Py SDK CLI 封装")
    parser.add_argument("project_dir", help="项目目录")
    parser.add_argument("command", choices=[
        "run", "lint", "compile", "distribute",
        "translate", "android_build", "web_build",
    ], help="要执行的命令")
    parser.add_argument("extra", nargs="?", default=None,
                        help="translate 需要：目标语言（如 chinese）")
    parser.add_argument("--sdk", default=None, help="SDK 路径")

    args = parser.parse_args()
    try:
        cli = RenPyCLI(sdk_path=args.sdk)
    except RuntimeError as e:
        # SDK 缺失不打 traceback，直接给可执行的指引（选项说明见 sdk_common.detect_sdk）
        print(f"[SDK 缺失] {e}", file=sys.stderr)
        sys.exit(2)

    method = getattr(cli, args.command)
    if args.command == "translate":
        if not args.extra:
            parser.error("translate 需要 extra 参数指定语言，例如：python cli.py <项目> translate chinese")
        result = method(args.project_dir, args.extra)
    else:
        result = method(args.project_dir)
    print(cli.format_result(result))
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
