"""
Ren'Py 自动化测试执行器

用法：
    runner = TestRunner("D:/projects/my_game")
    runner.inject_test("test_my_story.rpy", "test_script.rpy")
    result = runner.run()
    print(result.report())

参考：Ren'Py 8.5.3 Automated Testing (doc/testcases.html)
"""

import os
import sys
import subprocess

from sdk_common import detect_sdk, find_platform_python


class TestResult:
    """测试结果封装。"""

    def __init__(self, stdout: str, stderr: str, returncode: int):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        self._parsed = None

    @property
    def passed(self) -> bool:
        return self.returncode == 0

    @property
    def failures(self) -> list:
        """解析测试输出中的失败项。"""
        if self._parsed is not None:
            return self._parsed
        failures = []
        for line in self.stdout.split("\n"):
            if "FAILED" in line or "failed" in line.lower():
                failures.append(line.strip())
        if self.stderr:
            for line in self.stderr.split("\n"):
                if line.strip():
                    failures.append(f"[stderr] {line.strip()}")
        self._parsed = failures
        return failures

    def report(self) -> str:
        """生成可读的测试报告。"""
        lines = []
        lines.append("=" * 50)
        lines.append(f"测试结果: {'✅ 通过' if self.passed else '❌ 失败'}")
        lines.append(f"退出码: {self.returncode}")
        lines.append("-" * 50)
        if self.failures:
            lines.append("失败详情:")
            for f in self.failures:
                lines.append(f"  • {f}")
        else:
            lines.append("所有测试通过。")
        lines.append("=" * 50)
        return "\n".join(lines)


class TestRunner:
    """Ren'Py 自动化测试执行器。

    通过 SDK 子进程执行 renpy.py <project_dir> test。
    """

    def __init__(self, project_dir: str, sdk_path: str = None):
        self.project_dir = os.path.abspath(project_dir)
        self.game_dir = os.path.join(self.project_dir, "game")
        self._injected_files = []
        self.sdk_path = detect_sdk(sdk_path)
        self.python_exe = find_platform_python(self.sdk_path)

    def inject_test(self, test_code: str, filename: str = "auto_test.rpy") -> str:
        """注入测试脚本到项目 game/ 目录。返回完整路径。"""
        os.makedirs(self.game_dir, exist_ok=True)
        path = os.path.join(self.game_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(test_code)
        self._injected_files.append(path)
        print(f"📄 已注入: {path}")
        return path

    def inject_from_bridge(self, script, filename: str = "auto_test.rpy") -> str:
        """通过 RenPyScript 生成测试代码并注入。"""
        return self.inject_test(script.render(), filename)

    def remove_injected(self):
        """清理注入的测试文件。"""
        for path in self._injected_files:
            if os.path.isfile(path):
                os.remove(path)
                print(f"🧹 已清理: {path}")
        self._injected_files.clear()

    def run(self, timeout: int = 120) -> TestResult:
        """
        运行测试。
        通过 SDK 子进程执行 renpy.py <project_dir> test。
        """
        cmd = [
            self.python_exe,
            os.path.join(self.sdk_path, "renpy.py"),
            self.project_dir,
            "test",
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
            return TestResult(
                stdout=proc.stdout,
                stderr=proc.stderr,
                returncode=proc.returncode,
            )
        except subprocess.TimeoutExpired:
            return TestResult(
                stdout="",
                stderr=f"测试超时（{timeout}s）",
                returncode=1,
            )
        except FileNotFoundError:
            return TestResult(
                stdout="",
                stderr=f"找不到 Python 解释器: {self.python_exe}",
                returncode=1,
            )


# ── 预置测试模式 ──────────────────────────────────────
# 语法依据 Ren'Py 8.5.3 renpy/test/testparser.py：
#   - testcase 内跳转用 `run <label>`（没有 `call` 语句）
#   - `assert` 只接受 selector/True/False/eval；任意 Python 表达式须用 `assert eval "..."`
#   - `advance` 支持 `until screen "..."` 后缀

def make_scene_test(scenes: list) -> str:
    """
    生成场景流程测试。
    scenes = [("start", "choice"), ("end", None), ...]
    每个元组: (label, expected_screen_or_None)
    """
    lines = ["# 场景流程测试 - 自动生成"]
    lines.append("")
    for label, expected in scenes:
        lines.append(f"testcase test_{label}:")
        lines.append(f"    run {label}")
        if expected:
            lines.append(f"    advance until screen \"{expected}\"")
        else:
            lines.append("    advance")
        lines.append("")
    return "\n".join(lines)


def make_menu_test(label: str, choices: list) -> str:
    """
    生成菜单选择测试 — 每个选项生成一个独立 testcase。
    choices = [("选项文本", "expected_label"), ...]
    """
    lines = ["# 菜单选择测试 - 自动生成"]
    for i, (text, expected) in enumerate(choices):
        lines.append(f"testcase test_menu_{label}_{i}:")
        lines.append(f"    run {label}")
        lines.append(f'    click "{text}"')
        if expected:
            lines.append(f'    assert eval \'" {expected} " in renpy.get_all_labels()\'')
        lines.append("")
    return "\n".join(lines)


# ── CLI ─────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Ren'Py 测试执行器")
    parser.add_argument("project_dir", help="项目目录")
    parser.add_argument("--inject", help="注入测试 .rpy 文件路径")
    parser.add_argument("--mode", choices=["run", "inject+run", "clean"],
                        default="run",
                        help="操作模式")

    args = parser.parse_args()
    runner = TestRunner(args.project_dir)
    result = None

    if args.mode == "inject+run":
        if not args.inject:
            print("❌ inject+run 模式需要 --inject <file>")
            sys.exit(1)
        with open(args.inject, "r", encoding="utf-8") as f:
            code = f.read()
        runner.inject_test(code)
        result = runner.run()
        print(result.report())
        runner.remove_injected()
    elif args.mode == "run":
        result = runner.run()
        print(result.report())
    elif args.mode == "clean":
        runner.remove_injected()
        sys.exit(0)

    sys.exit(0 if result.passed else 1)


if __name__ == "__main__":
    main()
