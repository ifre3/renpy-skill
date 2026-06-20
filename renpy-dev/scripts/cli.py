"""
Ren'Py SDK CLI 封装 — 封装 renpy.py CLI 子命令
基于 Ren'Py 8.5.3 官方 CLI 文档 (doc/cli.html) 和 renpy/arguments.py
"""
import os
import sys
import subprocess
from typing import Optional, List
class CLIResult:
    """CLI 命令执行结果"""
    def __init__(self, command, stdout="", stderr="", returncode=0):
        self.command = command
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
    @property
    def success(self):
        return self.returncode == 0
    @property
    def output(self):
        lines = [f"$ {self.command}", f"exit: {self.returncode}"]
        if self.stdout:
            out_lines = self.stdout.strip().split("\n")
            if len(out_lines) > 30:
                out_lines = out_lines[-30:]
                lines.append(f"--- stdout (末 {len(out_lines)} 行) ---")
            else:
                lines.append("--- stdout ---")
            lines.extend(out_lines)
        if self.stderr.strip():
            lines.append("--- stderr ---")
            lines.append(self.stderr.strip()[-2000:])
        return "\n".join(lines)
class RenPyCLI:
    """Ren'Py SDK 命令行封装 — 参考 doc/cli.html 全部命令"""
    def __init__(self, sdk_path=None):
        self.sdk_path = sdk_path or self._detect_sdk()
        self.python_exe = self._find_python()
    @staticmethod
    def _detect_sdk():
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
        raise RuntimeError("未找到 Ren'Py SDK。请设置环境变量 RENPY_SDK 或传 sdk_path= 参数")
    @staticmethod
    def _find_python():
        sdk = RenPyCLI._detect_sdk()
        lib = os.path.join(sdk, "lib")
        if sys.platform == "win32":
            candidates = [os.path.join(lib, "py3-windows-x86_64", "python.exe"), os.path.join(lib, "py3-windows-i686", "python.exe")]
        elif sys.platform == "darwin":
            candidates = [os.path.join(lib, "py3-mac-x86_64", "python"), os.path.join(lib, "py3-mac-arm64", "python")]
        else:
            candidates = [os.path.join(lib, "py3-linux-x86_64", "python"), os.path.join(lib, "py3-linux-i686", "python")]
        for c in candidates:
            if os.path.isfile(c):
                return c
        return sys.executable
    def _run(self, cmd):
        command = [self.python_exe, os.path.join(self.sdk_path, "renpy.py")] + cmd
        display = " ".join(c if " " not in c else f'"{c}"' for c in command)
        try:
            p = subprocess.run(command, capture_output=True, text=True, timeout=3600)
            return CLIResult(display, p.stdout, p.stderr, p.returncode)
        except subprocess.TimeoutExpired:
            return CLIResult(display, stderr="命令超时(3600s)", returncode=-1)
        except FileNotFoundError as e:
            return CLIResult(display, stderr=f"Python 未找到: {e}", returncode=-1)
    def run(self, project_dir, warp=None, profile_display=False):
        cmd = [project_dir, "run"]
        if warp: cmd += ["--warp", warp]
        if profile_display: cmd.append("--profile-display")
        return self._run(cmd)
    def quit(self, project_dir):
        return self._run([project_dir, "quit"])
    def compile(self, project_dir, keep_orphan_rpyc=False):
        cmd = [project_dir, "compile"]
        if keep_orphan_rpyc: cmd.append("--keep-orphan-rpyc")
        return self._run(cmd)
    def director(self, project_dir):
        return self._run([project_dir, "director"])
    def rmpersistent(self, project_dir):
        return self._run([project_dir, "rmpersistent"])
    def update(self, project_dir, url, force=False, key=None):
        cmd = [project_dir, "update", url]
        if force: cmd.append("--force")
        if key: cmd += ["--key", key]
        return self._run(cmd)
    def lint(self, project_dir, error_code=False, output_file=None, by_character=False, all_problems=False, check_unclosed_tags=False):
        cmd = [project_dir, "lint"]
        if output_file: cmd.append(output_file)
        if error_code: cmd.append("--error-code")
        if by_character: cmd.append("--by-character")
        if all_problems: cmd.append("--all-problems")
        if check_unclosed_tags: cmd.append("--check-unclosed-tags")
        return self._run(cmd)
    def test(self, project_dir, testcase=None, enable_all=False, report_detailed=False, hide_execution=None):
        cmd = [project_dir, "test"]
        if testcase: cmd.append(testcase)
        if enable_all: cmd.append("--enable_all")
        if report_detailed: cmd.append("--report-detailed")
        if hide_execution: cmd += ["--hide-execution", hide_execution]
        return self._run(cmd)
    def distribute(self, project_dir, destination=None, formats=None, no_archive=False, package=None):
        cmd = [project_dir, "launcher", "distribute"]
        if destination: cmd += ["--destination", destination]
        if formats:
            for f in formats: cmd += ["--format", f]
        if no_archive: cmd.append("--no-archive")
        if package:
            for p in package: cmd += ["--package", p]
        return self._run(cmd)
    def android_build(self, project_dir, destination=None, bundle=False, install=False, launch=False, package=None):
        cmd = [project_dir, "launcher", "android_build"]
        if destination: cmd += ["--destination", destination]
        if bundle: cmd.append("--bundle")
        if install or launch: cmd.append("--install")
        if launch: cmd.append("--launch")
        if package: cmd += ["--package", package]
        return self._run(cmd)
    def ios_create(self, project_dir, destination):
        return self._run([project_dir, "launcher", "ios_create", destination])
    def ios_populate(self, project_dir, destination):
        return self._run([project_dir, "launcher", "ios_populate", destination])
    def web_build(self, project_dir, destination=None, launch_after=False):
        cmd = [project_dir, "launcher", "web_build"]
        if destination: cmd += ["--destination", destination]
        if launch_after: cmd.append("--launch")
        return self._run(cmd)
    def translate(self, project_dir, language, count=False, empty=False, min_priority=None, max_priority=None, strings_only=False):
        cmd = [project_dir, "translate", language]
        if count: cmd.append("--count")
        if empty: cmd.append("--empty")
        if min_priority is not None: cmd += ["--min-priority", str(min_priority)]
        if max_priority is not None: cmd += ["--max-priority", str(max_priority)]
        if strings_only: cmd.append("--strings-only")
        return self._run(cmd)
    def dialogue(self, project_dir, language, as_text=False, as_strings=False, notags=False, escape=False):
        cmd = [project_dir, "dialogue", language]
        if as_text: cmd.append("--text")
        if as_strings: cmd.append("--strings")
        if notags: cmd.append("--notags")
        if escape: cmd.append("--escape")
        return self._run(cmd)
    def merge_strings(self, project_dir, language, source, reverse=False, replace=False):
        cmd = [project_dir, "merge_strings", language, source]
        if reverse: cmd.append("--reverse")
        if replace: cmd.append("--replace")
        return self._run(cmd)
    def extract_strings(self, project_dir, output=None):
        cmd = [project_dir, "translate", "extract"]
        if output: cmd += ["--output", output]
        return self._run(cmd)
    def generate_gui(self, project_dir, width=1280, height=720, accent="#00B8C3", light=False, replace_images=False, replace_code=False, update_code=False, minimal=False):
        cmd = [project_dir, "launcher", "generate_gui"]
        cmd += ["--width", str(width), "--height", str(height), "--accent", accent]
        if light: cmd.append("--light")
        if replace_images: cmd.append("--replace-images")
        if replace_code: cmd.append("--replace-code")
        if update_code: cmd.append("--update-code")
        if minimal: cmd.append("--minimal")
        return self._run(cmd)
    def gui_images(self, project_dir):
        return self._run([project_dir, "launcher", "gui_images"])
    def set_project(self, project_dir, project):
        return self._run([project_dir, "launcher", "set_project", project])
    def get_projects_directory(self):
        return self._run(["launcher", "get_projects_directory"])
    def add_from(self, project_dir):
        return self._run([project_dir, "add_from"])
    def update_old_game(self, project_dir):
        return self._run([project_dir, "launcher", "update_old_game"])
    @staticmethod
    def format_result(result):
        return result.output
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Ren'Py SDK CLI — doc/cli.html")
    parser.add_argument("project_dir", nargs="?", default=None)
    parser.add_argument("command", choices=[
        "run","quit","lint","compile","test","distribute",
        "translate","dialogue","merge_strings","extract_strings",
        "android_build","web_build","ios_create","ios_populate",
        "generate_gui","gui_images","director","rmpersistent",
        "update","add_from","set_project","get_projects_directory",
        "update_old_game",
    ])
    parser.add_argument("--sdk", default=None)
    parser.add_argument("--error-code", action="store_true")
    args = parser.parse_args()
    cli = RenPyCLI(sdk_path=args.sdk)
    method = getattr(cli, args.command, None)
    if not method:
        print(f"未知命令: {args.command}"); sys.exit(1)
    result = method(args.project_dir) if args.project_dir else method()
    print(RenPyCLI.format_result(result))
    sys.exit(result.returncode)
if __name__ == "__main__":
    main()
