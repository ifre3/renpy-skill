"""
Ren'Py SDK 版本守卫 — 轻量无依赖

用法：
    from _version_guard import check, RENPY_MIN
    if not check():
        print(f"警告：当前 SDK 版本不满足最低要求 {RENPY_MIN}")
"""

import os
import sys
import re

# 本 Skill 要求的最低 Ren'Py SDK 版本
RENPY_MIN = (8, 0, 0)
RENPY_MIN_STR = "8.0.0"


def _find_sdk_root() -> str | None:
    """轻量 SDK 检测（不依赖 cli.py）。"""
    # 环境变量
    env = os.environ.get("RENPY_SDK", "")
    if env and os.path.isdir(env) and os.path.isfile(os.path.join(env, "renpy.py")):
        return os.path.abspath(env)

    # 向上查找
    cur = os.path.dirname(os.path.abspath(__file__))
    for _ in range(8):
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        if os.path.isfile(os.path.join(parent, "renpy.py")):
            return parent
        cur = parent

    # 常见路径
    fallbacks = [
        os.path.expanduser("~/renpy-sdk"),
    ]
    for p in fallbacks:
        if os.path.isdir(p) and os.path.isfile(os.path.join(p, "renpy.py")):
            return p

    return None


def _parse_version(ver_str: str) -> tuple[int, ...]:
    """从版本字符串解析 (major, minor, patch) 元组。
    支持: "Ren'Py 8.5.3.26051504", "8.5.3", "7.6.2" 等格式
    """
    m = re.search(r'(\d+)\.(\d+)\.(\d+)', ver_str)
    if not m:
        return (0, 0, 0)
    return tuple(int(x) for x in m.groups())


def _get_sdk_version() -> tuple[int, ...] | None:
    """获取当前 Ren'Py SDK 版本号，失败返回 None。"""
    sdk = _find_sdk_root()
    if not sdk:
        return None

    python_exe = None
    lib = os.path.join(sdk, "lib")
    candidates = []
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
            python_exe = c
            break
    if not python_exe:
        return None

    import subprocess
    try:
        proc = subprocess.run(
            [python_exe, os.path.join(sdk, "renpy.py"), "--version"],
            capture_output=True, text=True, timeout=10,
        )
        return _parse_version(proc.stdout)
    except Exception:
        return None


def check(quiet: bool = False) -> bool:
    """
    检查当前 SDK 是否满足最低版本要求。

    返回 True 表示满足（或未检测到 SDK — 允许脱机生成代码）。
    返回 False 表示 SDK 版本过低。
    """
    ver = _get_sdk_version()
    if ver is None:
        if not quiet:
            print("⚠️  未检测到 Ren'Py SDK。生成的代码目标版本为 Ren'Py 8.x，"
                  "请在目标环境确认兼容性。", file=sys.stderr)
        return True  # 不阻塞脱机使用

    if ver >= RENPY_MIN:
        return True

    if not quiet:
        print(f"⚠️  当前 Ren'Py SDK 版本: {'.'.join(map(str, ver))} < "
              f"最低要求 {RENPY_MIN_STR}", file=sys.stderr)
        print("   生成的 .rpy 代码使用 Ren'Py 8.x 语法（Python 3、tuple define 等），"
              "在旧版 SDK 中可能出错。", file=sys.stderr)
    return False


# 模块导入时自动静默检查一次（仅在有 SDK 且版本过低时打印）
_check_result = None

def _auto_check():
    global _check_result
    if _check_result is None:
        sdk = _find_sdk_root()
        if sdk:
            ver = _get_sdk_version()
            if ver is not None and ver < RENPY_MIN:
                print(f"⚠️  [version_guard] SDK {'.'.join(map(str, ver))} < "
                      f"最低要求 {RENPY_MIN_STR}，请升级 Ren'Py", file=sys.stderr)
                _check_result = False
            else:
                _check_result = True
        else:
            _check_result = True
    return _check_result

_auto_check()
