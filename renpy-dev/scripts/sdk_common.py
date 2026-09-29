"""
Ren'Py SDK 路径检测 — 供 renpy-dev 各脚本共用

用法：
    from sdk_common import detect_sdk, find_platform_python
    sdk = detect_sdk()
    py = find_platform_python(sdk)
"""

import os
import sys


# 常见 SDK 安装路径（维护点：本机新装/升级 SDK 后在此追加一行即可）
_KNOWN_SDK_PATHS = [
    r"D:\workplace\renpy-8.5.3-sdk",
]


def _is_sdk(path: str) -> bool:
    return os.path.isdir(path) and os.path.isfile(os.path.join(path, "renpy.py"))


def detect_sdk(sdk_path: str = None) -> str:
    """按优先级检测 Ren'Py SDK 根目录，失败时抛 RuntimeError。

    优先级：显式参数 > 环境变量 RENPY_SDK > 向上查找 > _KNOWN_SDK_PATHS > ~/renpy-sdk
    """
    if sdk_path and _is_sdk(sdk_path):
        return os.path.abspath(sdk_path)

    env = os.environ.get("RENPY_SDK", "")
    if env and _is_sdk(env):
        return os.path.abspath(env)

    cur = os.path.dirname(os.path.abspath(__file__))
    for _ in range(8):
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        if _is_sdk(parent):
            return parent
        cur = parent

    for known in _KNOWN_SDK_PATHS:
        if _is_sdk(known):
            return os.path.abspath(known)

    fb = os.path.expanduser("~/renpy-sdk")
    if _is_sdk(fb):
        return fb

    raise RuntimeError(
        "未找到 Ren'Py SDK。请设置环境变量 RENPY_SDK、修改 sdk_common.py 顶部 "
        "_KNOWN_SDK_PATHS，或传 sdk_path= 参数"
    )


def find_platform_python(sdk_path: str) -> str:
    """定位 SDK 自带的 Python 解释器。"""
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
