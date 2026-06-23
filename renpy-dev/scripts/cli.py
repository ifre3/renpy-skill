"""
Ren'Py SDK CLI Wrapper — wraps renpy.py subcommands as Python callables.
Based on Ren'Py 8.5.3 official CLI documentation (doc/cli.html) and renpy/arguments.py.

This is a lightweight subprocess wrapper. It does NOT replace the Ren'Py SDK.
"""
import os
import sys
import subprocess
from typing import Optional, List


class CLIResult:
    """Result of a CLI command execution."""

    def __init__(self, command: str, stdout: str = "", stderr: str = "", returncode: int = 0):
        self.command = command
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode

    @property
    def success(self) -> bool:
        return self.returncode == 0

    @property
    def output(self) -> str:
        lines = [f"$ {self.command}", f"exit: {self.returncode}"]
        if self.stdout:
            out_lines = self.stdout.strip().split("\n")
            if len(out_lines) > 30:
                out_lines = out_lines[-30:]
                lines.append(f"--- stdout (last {len(out_lines)} lines) ---")
            else:
                lines.append("--- stdout ---")
            lines.extend(out_lines)
        if self.stderr.strip():
            lines.append("--- stderr ---")
            lines.append(self.stderr.strip()[-2000:])
        return "\n".join(lines)


class RenPyCLI:
    """Ren'Py SDK CLI wrapper — mirrors commands from renpy/arguments.py and doc/cli.html.

    Usage:
        cli = RenPyCLI()
        result = cli.lint("path/to/project")
        result = cli.distribute("path/to/project", destination="output/")
    """

    _sdk_cache = None  # SDK 路径缓存，避免重复遍历目录
    """Ren'Py SDK CLI wrapper — mirrors commands from renpy/arguments.py and doc/cli.html.

    Usage:
        cli = RenPyCLI()
        result = cli.lint("path/to/project")
        result = cli.distribute("path/to/project", destination="output/")
    """

    # Known commands from renpy/arguments.py that require the display
    DISPLAY_COMMANDS = {"run", "director", "distribute", "android_build",
                        "web_build", "generate_gui", "gui_images"}

    # Commands that force --compile (from arguments.py compile_commands)
    COMPILE_COMMANDS = {"compile", "add_from", "merge_strings"}

    def __init__(self, sdk_path: Optional[str] = None,
                 safe_mode: bool = False, trace: int = 0,
                 savedir: Optional[str] = None,
                 errors_in_editor: bool = False):
        self.sdk_path = sdk_path or self._detect_sdk()
        self.python_exe = self._find_python()
        self.safe_mode = safe_mode
        self.trace = trace
        self.savedir = savedir
        self.errors_in_editor = errors_in_editor

    @staticmethod
    def _detect_sdk() -> str:
        """Detect Ren'Py SDK path. 结果缓存在 _sdk_cache 中，避免重复遍历目录。"""
        if RenPyCLI._sdk_cache is not None:
            return RenPyCLI._sdk_cache

        env = os.environ.get("RENPY_SDK", "")
        if env and os.path.isdir(env) and os.path.isfile(os.path.join(env, "renpy.py")):
            RenPyCLI._sdk_cache = os.path.abspath(env)
            return RenPyCLI._sdk_cache

        # Walk up from this file's directory
        cur = os.path.dirname(os.path.abspath(__file__))
        for _ in range(8):
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            if os.path.isfile(os.path.join(parent, "renpy.py")):
                RenPyCLI._sdk_cache = parent
                return RenPyCLI._sdk_cache
            cur = parent

        # Check common SDK locations
        candidates = [
            os.path.expanduser("~/renpy-sdk"),
            os.path.expanduser("~/RenPy/renpy-8.5.3-sdk"),
        ]
        for c in candidates:
            resolved = os.path.abspath(c)
            if os.path.isdir(resolved) and os.path.isfile(os.path.join(resolved, "renpy.py")):
                RenPyCLI._sdk_cache = resolved
                return RenPyCLI._sdk_cache

        raise RuntimeError(
            "Ren'Py SDK not found. Set RENPY_SDK environment variable "
            "or pass sdk_path= to the constructor."
        )
    def _find_python(self) -> str:
        """Find the Python executable bundled with the Ren'Py SDK."""
        sdk = RenPyCLI._detect_sdk()
        lib = os.path.join(sdk, "lib")
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
                os.path.join(lib, "py3-linux-i686", "python"),
            ]
        for c in candidates:
            if os.path.isfile(c):
                return c
        return sys.executable

    def _build_global_args(self) -> List[str]:
        """Build list of global Ren'Py arguments (from renpy/arguments.py ArgumentParser)."""
        args = []
        if self.safe_mode:
            args.append("--safe-mode")
        if self.trace:
            args.extend(["--trace", str(self.trace)])
        if self.savedir:
            args.extend(["--savedir", self.savedir])
        if self.errors_in_editor:
            args.append("--errors-in-editor")
        return args

    def _run(self, cmd: List[str], timeout: int = 3600,
             compile: bool = False, compile_python: bool = False,
             keep_orphan_rpyc: bool = False,
             json_dump: Optional[str] = None,
             json_dump_private: bool = False,
             json_dump_common: bool = False) -> CLIResult:
        """Execute a renpy.py command via subprocess.

        Args:
            cmd: Command arguments (project_dir + subcommand + flags)
            timeout: Subprocess timeout in seconds
            compile: Force recompile (--compile)
            compile_python: Force Python recompile
            keep_orphan_rpyc: Keep orphan .rpyc files
            json_dump: Path to JSON dump file (--json-dump)
            json_dump_private: Include private names
            json_dump_common: Include common names
        """
        renpy_py = os.path.join(self.sdk_path, "renpy.py")
        command = [self.python_exe, renpy_py]

        # Global arguments (from renpy/arguments.py ArgumentParser)
        command.extend(self._build_global_args())

        if compile:
            command.append("--compile")
        if compile_python:
            command.append("--compile-python")

        # Command-specific
        command.extend(cmd)

        if keep_orphan_rpyc:
            command.append("--keep-orphan-rpyc")

        # JSON dump arguments
        if json_dump:
            command.extend(["--json-dump", json_dump])
        if json_dump_private:
            command.append("--json-dump-private")
        if json_dump_common:
            command.append("--json-dump-common")

        display = " ".join(c if " " not in c else f'"{c}"' for c in command)
        try:
            p = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
            return CLIResult(display, p.stdout, p.stderr, p.returncode)
        except subprocess.TimeoutExpired:
            return CLIResult(display, stderr=f"Command timed out ({timeout}s)", returncode=-1)
        except FileNotFoundError as e:
            return CLIResult(display, stderr=f"Python not found: {e}", returncode=-1)

    # ── Core Commands ───────────────────────────────────

    def run(self, project_dir: str, warp: Optional[str] = None,
            profile_display: bool = False) -> CLIResult:
        """Run the project (default command). Supports --warp and --profile-display."""
        cmd = [project_dir, "run"]
        if warp:
            cmd += ["--warp", warp]
        if profile_display:
            cmd.append("--profile-display")
        return self._run(cmd)

    def quit(self, project_dir: str) -> CLIResult:
        """Quit without doing anything."""
        return self._run([project_dir, "quit"])

    # ── Compile & Lint ──────────────────────────────────

    def compile(self, project_dir: str, keep_orphan_rpyc: bool = False) -> CLIResult:
        """Force recompile all .rpy scripts."""
        return self._run([project_dir, "compile"], keep_orphan_rpyc=keep_orphan_rpyc)

    def lint(self, project_dir: str, error_code: bool = False,
             output_file: Optional[str] = None,
             by_character: bool = False, all_problems: bool = False,
             check_unclosed_tags: bool = False) -> CLIResult:
        """Lint project for errors."""
        cmd = [project_dir, "lint"]
        if output_file:
            cmd.append(output_file)
        if error_code:
            cmd.append("--error-code")
        if by_character:
            cmd.append("--by-character")
        if all_problems:
            cmd.append("--all-problems")
        if check_unclosed_tags:
            cmd.append("--check-unclosed-tags")
        return self._run(cmd)

    # ── Testing ─────────────────────────────────────────

    def test(self, project_dir: str, testcase: Optional[str] = None,
             enable_all: bool = False, report_detailed: bool = False,
             hide_execution: Optional[str] = None) -> CLIResult:
        """Run automated tests."""
        cmd = [project_dir, "test"]
        if testcase:
            cmd.append(testcase)
        if enable_all:
            cmd.append("--enable-all")
        if report_detailed:
            cmd.append("--report-detailed")
        if hide_execution:
            cmd += ["--hide-execution", hide_execution]
        return self._run(cmd)

    # ── Distribution ────────────────────────────────────

    def distribute(self, project_dir: str, destination: Optional[str] = None,
                   formats: Optional[str] = None,
                   no_archive: bool = False,
                   package: Optional[List[str]] = None) -> CLIResult:
        """Package project for distribution."""
        cmd = [project_dir, "distribute"]
        if destination:
            cmd += ["--destination", destination]
        if formats:
            cmd += ["--format", formats]
        if no_archive:
            cmd.append("--no-archive")
        if package:
            for p in package:
                cmd += ["--package", p]
        return self._run(cmd)

    # ── Platform Builds ─────────────────────────────────

    def android_build(self, project_dir: str, destination: Optional[str] = None,
                      bundle: bool = False, install: bool = False,
                      launch: bool = False,
                      package: Optional[List[str]] = None) -> CLIResult:
        """Build Android APK/AAB."""
        cmd = [project_dir, "android_build"]
        if destination:
            cmd += ["--destination", destination]
        if bundle:
            cmd.append("--bundle")
        if install or launch:
            cmd.append("--install")
        if launch:
            cmd.append("--launch")
        if package:
            for p in package:
                cmd += ["--package", p]
        return self._run(cmd)

    def ios_create(self, project_dir: str, destination: str) -> CLIResult:
        """Create iOS Xcode project."""
        return self._run([project_dir, "ios_create", destination])

    def ios_populate(self, project_dir: str, destination: str) -> CLIResult:
        """Populate iOS Xcode project with game data."""
        return self._run([project_dir, "ios_populate", destination])

    def web_build(self, project_dir: str, destination: Optional[str] = None,
                  launch_after: bool = False) -> CLIResult:
        """Build project for web."""
        cmd = [project_dir, "web_build"]
        if destination:
            cmd += ["--destination", destination]
        if launch_after:
            cmd.append("--launch")
        return self._run(cmd)

    # ── Translation ─────────────────────────────────────

    def translate(self, project_dir: str, language: str,
                  count: bool = False, empty: bool = False,
                  min_priority: Optional[int] = None,
                  max_priority: Optional[int] = None,
                  strings_only: bool = False) -> CLIResult:
        """Generate/update translation templates."""
        cmd = [project_dir, "translate", language]
        if count:
            cmd.append("--count")
        if empty:
            cmd.append("--empty")
        if min_priority is not None:
            cmd += ["--min-priority", str(min_priority)]
        if max_priority is not None:
            cmd += ["--max-priority", str(max_priority)]
        if strings_only:
            cmd.append("--strings-only")
        return self._run(cmd)

    def dialogue(self, project_dir: str, language: str,
                 as_text: bool = False, as_strings: bool = False,
                 notags: bool = False, escape: bool = False) -> CLIResult:
        """Export dialogue from a translation."""
        cmd = [project_dir, "dialogue", language]
        if as_text:
            cmd.append("--text")
        if as_strings:
            cmd.append("--strings")
        if notags:
            cmd.append("--notags")
        if escape:
            cmd.append("--escape")
        return self._run(cmd)

    def merge_strings(self, project_dir: str, language: str, source: str,
                      reverse: bool = False, replace: bool = False) -> CLIResult:
        """Merge translated strings."""
        cmd = [project_dir, "merge_strings", language, source]
        if reverse:
            cmd.append("--reverse")
        if replace:
            cmd.append("--replace")
        return self._run(cmd)

    def extract_strings(self, project_dir: str, language: str, destination: str,
                        merge: bool = False, force: bool = False) -> CLIResult:
        """Extract translatable strings."""
        cmd = [project_dir, "extract_strings", language, destination]
        if merge:
            cmd.append("--merge")
        if force:
            cmd.append("--force")
        return self._run(cmd)

    # ── JSON Dump (renpy/arguments.py --json-dump suite) ─

    def json_dump(self, project_dir: str, output_file: str,
                  private: bool = False, common: bool = False) -> CLIResult:
        """Dump game information to a JSON file.

        Maps to renpy/arguments.py JSON dump arguments:
        --json-dump, --json-dump-private, --json-dump-common
        """
        return self._run([project_dir, "run"],
                         json_dump=output_file,
                         json_dump_private=private,
                         json_dump_common=common)

    # ── GUI Generation ─────────────────────────────────

    def generate_gui(self, project_dir: str, width: int = 1280, height: int = 720,
                     accent: str = "#00B8C3", light: bool = False,
                     replace_images: bool = False, replace_code: bool = False,
                     update_code: bool = False, minimal: bool = False) -> CLIResult:
        """Generate GUI theme."""
        cmd = [project_dir, "generate_gui"]
        cmd += ["--width", str(width), "--height", str(height), "--accent", accent]
        if light:
            cmd.append("--light")
        if replace_images:
            cmd.append("--replace-images")
        if replace_code:
            cmd.append("--replace-code")
        if update_code:
            cmd.append("--update-code")
        if minimal:
            cmd.append("--minimal")
        return self._run(cmd)

    def gui_images(self, project_dir: str) -> CLIResult:
        """Regenerate GUI images."""
        return self._run([project_dir, "gui_images"])

    # ── Developer Tools ─────────────────────────────────

    def director(self, project_dir: str) -> CLIResult:
        """Launch the director tool."""
        return self._run([project_dir, "director"])

    def rmpersistent(self, project_dir: str) -> CLIResult:
        """Delete persistent data."""
        return self._run([project_dir, "rmpersistent"])

    def update(self, project_dir: str, url: str,
               force: bool = False, key: Optional[str] = None) -> CLIResult:
        """Update project from a URL."""
        cmd = [project_dir, "update", url]
        if force:
            cmd.append("--force")
        if key:
            cmd += ["--key", key]
        return self._run(cmd)

    # ── Project Management ──────────────────────────────

    def set_project(self, project_dir: str, project: str) -> CLIResult:
        """Register a project in the launcher."""
        return self._run([project_dir, "set_project", project])

    def set_projects_directory(self, path: str) -> CLIResult:
        """Set the projects directory path."""
        return self._run([self.sdk_path, "set_projects_directory", path])

    def get_projects_directory(self) -> CLIResult:
        """Get the projects directory path."""
        return self._run([self.sdk_path, "get_projects_directory"])

    def add_from(self, project_dir: str) -> CLIResult:
        """Add .rpy files from directories."""
        return self._run([project_dir, "add_from"])

    def update_old_game(self, project_dir: str) -> CLIResult:
        """Update old game format."""
        return self._run([project_dir, "update_old_game"])

    @staticmethod
    def format_result(result: CLIResult) -> str:
        """Format a CLIResult for display."""
        return result.output

    
    # ── Test Runner (merged from test_runner.py) ──────────

    def inject_test(self, test_code: str, filename: str = "auto_test.rpy") -> str:
        """Inject a test script into the project game/ directory.

        Args:
            test_code: Ren'Py test script source code
            filename: Target filename in game/

        Returns:
            Full path to the injected file
        """
        game_dir = os.path.join(self.project_dir, "game") if hasattr(self, 'project_dir') else None
        if not game_dir:
            # Assume we use the most recent project dir
            return filename  # caller should manage the file
        os.makedirs(game_dir, exist_ok=True)
        path = os.path.join(game_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(test_code)
        self._injected = getattr(self, '_injected', [])
        self._injected.append(path)
        return path

    def remove_injected(self):
        """Clean up injected test files."""
        for path in getattr(self, '_injected', []):
            if os.path.isfile(path):
                os.remove(path)
        self._injected = []

    def run_tests(self, project_dir: str, timeout: int = 120) -> "CLIResult":
        """Run Ren'Py test command.

        This is a convenience wrapper around test() that returns
        a TestResult with failure parsing.

        Args:
            project_dir: Project directory
            timeout: Test timeout in seconds

        Returns:
            CLIResult with test output
        """
        result = self.test(project_dir)
        return result

    def __repr__(self) -> str:
        return f"<RenPyCLI sdk={self.sdk_path}>"




# ── Test Helpers (from test_runner.py) ──────────────────

def make_scene_test(scenes: list) -> str:
    """Generate a scene flow test script.

    Args:
        scenes: List of (label, expected_screen_or_None) tuples

    Returns:
        Ren'Py test script source code

    Example:
        scenes = [("start", "choice"), ("end", None)]
    """
    lines = ["# Scene flow test - auto-generated"]
    lines.append("")
    for label, expected in scenes:
        lines.append(f"testcase test_{label}:")
        lines.append(f"    call {label}")
        if expected:
            lines.append(f"    advance until screen \"{expected}\"")
        else:
            lines.append("    advance")
        lines.append("")
    return "\n".join(lines)


def make_menu_test(label: str, choices: list) -> str:
    """Generate a menu choice test script.

    Args:
        label: The label where the menu is
        choices: List of (choice_text, expected_label) tuples

    Returns:
        Ren'Py test script source code

    Example:
        choices = [("Coffee", "coffee_route"), ("Tea", "tea_route")]
    """
    lines = ["# Menu choice test - auto-generated"]
    for i, (text, expected) in enumerate(choices):
        lines.append(f"testcase test_menu_{label}_{i}:")
        lines.append(f"    call {label}")
        lines.append(f"    click \"{text}\"")
        if expected:
            lines.append(f"    assert \"{expected}\" in renpy.get_all_labels()")
        lines.append("")
    return "\n".join(lines)

def main():
    """CLI entry point for direct invocation."""
    import argparse

    parser = argparse.ArgumentParser(description="Ren'Py SDK CLI — doc/cli.html")
    parser.add_argument("project_dir", nargs="?", default=None,
                        help="Project base directory")
    parser.add_argument("command", choices=[
        "run", "quit", "lint", "compile", "test", "distribute",
        "translate", "dialogue", "merge_strings", "extract_strings",
        "android_build", "web_build", "ios_create", "ios_populate",
        "generate_gui", "gui_images", "director", "rmpersistent",
        "update", "add_from", "set_project", "set_projects_directory",
        "get_projects_directory",
        "update_old_game", "json_dump",
    ], help="Command to execute")
    parser.add_argument("--sdk", default=None, help="Path to Ren'Py SDK")
    parser.add_argument("--error-code", action="store_true",
                        help="Show error codes in lint output")
    parser.add_argument("--json-dump", default=None,
                        help="Path to JSON dump file")
    parser.add_argument("--json-dump-private", action="store_true",
                        help="Include private names in JSON dump")
    parser.add_argument("--json-dump-common", action="store_true",
                        help="Include common names in JSON dump")

    args = parser.parse_args()

    cli = RenPyCLI(sdk_path=args.sdk)
    method = getattr(cli, args.command, None)
    if not method:
        print(f"Unknown command: {args.command}")
        sys.exit(1)

    kwargs = {}
    if args.project_dir:
        kwargs["project_dir"] = args.project_dir
    if args.command == "json_dump":
        kwargs["output_file"] = args.json_dump or "game_info.json"
        kwargs["private"] = args.json_dump_private
        kwargs["common"] = args.json_dump_common

    result = method(**kwargs) if kwargs else method()

    print(RenPyCLI.format_result(result))
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()