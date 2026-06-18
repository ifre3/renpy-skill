"""
Ren'Py SDK CLI 封装 — 封装 renpy.py CLI 子命令

用法：
    cli = RenPyCLI(sdk_path="D:/renpy-8.5.3-sdk")
    cli.lint("D:/projects/my_game")           # 检查脚本
    cli.compile("D:/projects/my_game")        # 编译
    cli.distribute("D:/projects/my_game")     # 构建发布包
    cli.translate("D:/projects/my_game", "chinese")
    cli.run("D:/projects/my_game")            # 运行
    cli.test("D:/projects/my_game")           # 运行测试

参考：Ren'Py 8.5.3 CLI (doc/cli.html)
"""

import os
import sys
import subprocess


class RenPyCLI:
    """Ren'Py SDK 命令行封装。"""

    def __init__(self, sdk_path: str = None):
        self.sdk_path = sdk_path or self._detect_sdk()
        self.python_exe = self._find_python()

    # ── SDK 路径探测 ────────────────────────────────────

    @staticmethod
    def _detect_sdk() -> str:
        env = os.environ.get("RENPY_SDK", "")
        if env and os.path.isdir(env) and os.path.isfile(os.path.join(env, "renpy.py")):
            return os.path.abspath(env)
        cur = os.path.dirname(os.path.abspath(__file__))
        for _ in range(8):
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            if os.path.isfile(os.path.join(parent, "renpy.py")):
                return parent
            cur = parent
        fb = os.path.expanduser("~/renpy-sdk")
        if os.path.isdir(fb) and os.path.isfile(os.path.join(fb, "renpy.py")):
            return fb
        raise RuntimeError(
            "未找到 Ren'Py SDK。请设置环境变量 RENPY_SDK 或传 sdk_path= 参数"
        )

    @staticmethod
    def _find_platform_python(sdk_path: str) -> str:
        lib = os.path.join(sdk_path, "lib")
        if sys.platform == "win32":
            candidates = [
                os.path.join(lib, "py3-windows-x86_64", "python.exe"),
                os.path.join(lib, "py3-windows-i686", "python.exe"),
            ]
        elif sys.platform == "darwin":
            candidates = [
                os.path.join(lib, "py3-mac-x86_64", "python"),
                os.path.join(lib, "py3-mac-arm64", "python"),
            ]
        else:
            candidates = [
                os.path.join(lib, "py3-linux-x86_64", "python"),
            ]
        for c in candidates:
            if os.path.isfile(c):
                return c
        raise RuntimeError(f"在 {lib} 中找不到 Ren'Py Python 解释器")

    def _find_python(self) -> str:
        return self._find_platform_python(self.sdk_path)

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

    # ── 核心工作流命令 ──────────────────────────────────

    def run(self, project_dir: str) -> subprocess.CompletedProcess:
        """运行项目 (renpy.py <basedir>)。"""
        return self._run([project_dir])

    def quit(self) -> subprocess.CompletedProcess:
        """退出 Ren'Py (renpy.py <basedir> quit)。"""
        return self._run(["quit"])

    def compile(self, project_dir: str, keep_orphan_rpyc: bool = False) -> subprocess.CompletedProcess:
        """编译 .rpy → .rpyc。"""
        args = [project_dir, "compile"]
        if keep_orphan_rpyc:
            args.append("--keep-orphan-rpyc")
        return self._run(args)

    def director(self, project_dir: str) -> subprocess.CompletedProcess:
        """启动交互式导演模式。"""
        return self._run([project_dir, "director"])

    def rmpersistent(self, project_dir: str) -> subprocess.CompletedProcess:
        """删除持久化数据。"""
        return self._run([project_dir, "rmpersistent"])

    # ── 验证与测试 ──────────────────────────────────────

    def lint(self, project_dir: str, filename: str = None,
             error_code: bool = False, no_orphan_tl: bool = False,
             by_character: bool = False, all_problems: bool = False) -> subprocess.CompletedProcess:
        """检查脚本 (Lint)。"""
        args = [project_dir, "lint"]
        if filename:
            args.append(filename)
        if error_code:
            args.append("--error-code")
        if no_orphan_tl:
            args.append("--no-orphan-tl")
        if by_character:
            args.append("--by-character")
        if all_problems:
            args.append("--all-problems")
        return self._run(args)

    def test(self, project_dir: str, testcase: str = None,
             enable_all: bool = False, junit_xml: str = None) -> subprocess.CompletedProcess:
        """运行测试用例。"""
        args = [project_dir, "test"]
        if testcase:
            args.append(testcase)
        if enable_all:
            args.append("--enable_all")
        if junit_xml:
            args.append(f"--junit-xml={junit_xml}")
        return self._run(args)

    # ── 构建与发布 ──────────────────────────────────────

    def distribute(self, project_dir: str, package: list = None,
                   packagedest: str = None, no_archive: bool = False,
                   no_update: bool = False, format_: str = None) -> subprocess.CompletedProcess:
        """构建发布包 (distribute)。"""
        args = [project_dir, "distribute"]
        if package:
            for p in package:
                args.extend(["--package", p])
        if packagedest:
            args.extend(["--packagedest", packagedest])
        if no_archive:
            args.append("--no-archive")
        if no_update:
            args.append("--no-update")
        if format_:
            args.extend(["--format", format_])
        return self._run(args, timeout=600)

    def android_build(self, project_dir: str, destination: str = None,
                      bundle: bool = False, install: bool = False,
                      launch: bool = False) -> subprocess.CompletedProcess:
        """构建 Android 发布包。"""
        args = ["launcher", "android_build", project_dir]
        if destination:
            args.extend(["--destination", destination])
        if bundle:
            args.append("--bundle")
        if install:
            args.append("--install")
        if launch:
            args.append("--launch")
        return self._run(args, timeout=600)

    def ios_create(self, project_dir: str, destination: str) -> subprocess.CompletedProcess:
        """创建 iOS Xcode 项目。"""
        return self._run(["launcher", "ios_create", project_dir, destination], timeout=600)

    def ios_populate(self, project_dir: str, destination: str) -> subprocess.CompletedProcess:
        """更新 iOS Xcode 项目内容。"""
        return self._run(["launcher", "ios_populate", project_dir, destination], timeout=600)

    def web_build(self, project_dir: str, destination: str = None,
                  launch: bool = False) -> subprocess.CompletedProcess:
        """构建 Web 发布包。"""
        args = ["launcher", "web_build", project_dir]
        if destination:
            args.extend(["--destination", destination])
        if launch:
            args.append("--launch")
        return self._run(args, timeout=600)

    # ── 翻译与本地化 ────────────────────────────────────

    def translate(self, project_dir: str, language: str,
                  count: bool = False, rot13: bool = False,
                  piglatin: bool = False, empty: bool = False,
                  strings_only: bool = False) -> subprocess.CompletedProcess:
        """生成/更新翻译文件。"""
        args = [project_dir, "translate", language]
        if count:
            args.append("--count")
        if rot13:
            args.append("--rot13")
        if piglatin:
            args.append("--piglatin")
        if empty:
            args.append("--empty")
        if strings_only:
            args.append("--strings-only")
        return self._run(args)

    def dialogue(self, project_dir: str, language: str) -> subprocess.CompletedProcess:
        """提取/管理对话翻译。"""
        return self._run([project_dir, "dialogue", language])

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

    # ── 启动器命令 ──────────────────────────────────────

    def generate_gui(self, project_dir: str, width: int = 1280,
                     height: int = 720, accent: str = None,
                     start: bool = False) -> subprocess.CompletedProcess:
        """生成 GUI。"""
        args = ["launcher", "generate_gui", project_dir,
                f"--width={width}", f"--height={height}"]
        if accent:
            args.append(f"--accent={accent}")
        if start:
            args.append("--start")
        return self._run(args)

    def gui_images(self, project_dir: str) -> subprocess.CompletedProcess:
        """生成 GUI 图片。"""
        return self._run(["launcher", "gui_images", project_dir])

    def get_projects_directory(self) -> subprocess.CompletedProcess:
        """获取项目目录。"""
        return self._run(["launcher", "get_projects_directory"])

    def set_projects_directory(self, directory: str) -> subprocess.CompletedProcess:
        """设置项目目录。"""
        return self._run(["launcher", "set_projects_directory", directory])

    def set_project(self, directory: str) -> subprocess.CompletedProcess:
        """设置当前项目。"""
        return self._run(["launcher", "set_project", directory])

    def add_from_to_calls(self, project_dir: str) -> subprocess.CompletedProcess:
        """为已有 call 添加 from 子句。"""
        return self._run([project_dir, "add_from_to_calls"])

    def update(self, project_dir: str, url: str, force: bool = False) -> subprocess.CompletedProcess:
        """从网络更新项目。"""
        args = [project_dir, "update", url]
        if force:
            args.append("--force")
        return self._run(args)

    # ── 工具方法 ────────────────────────────────────────

    def format_result(self, result: subprocess.CompletedProcess) -> str:
        """格式化命令执行结果。"""
        lines = []
        lines.append(f"退出码: {result.returncode}")
        if result.stdout.strip():
            # 只显示最后 30 行
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
        "run", "lint", "compile", "test", "distribute",
        "translate", "android_build", "web_build",
    ], help="要执行的命令")
    parser.add_argument("--sdk", default=None, help="SDK 路径")

    args = parser.parse_args()
    cli = RenPyCLI(sdk_path=args.sdk)

    method = getattr(cli, args.command.replace("-", "_"))
    result = method(args.project_dir)
    print(cli.format_result(result))
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()