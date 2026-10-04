"""
Ren'Py SDK 路径检测 — 供本技能各脚本共用

用法：
    from sdk_common import detect_sdk, find_platform_python
    sdk = detect_sdk()
    py = find_platform_python(sdk)
"""

import os
import sys


# 常见 SDK 安装路径（维护点：本机路径在此追加或直接设 RENPY_SDK 环境变量，勿提交个人路径）
_KNOWN_SDK_PATHS = [
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
        "未找到 Ren'Py SDK。注意：只有 lint/编译/打包/运行/翻译 需要 SDK，"
        "结构分析/资源检查/翻译质检/字体与多语言配置等脚本无需 SDK，可照常使用。\n"
        "解决方案（按情况选择）：\n"
        "  ① 已装 SDK：设环境变量 RENPY_SDK 指向 SDK 根目录，或传 --sdk <路径> / sdk_path=<路径>；\n"
        "  ② 未装 SDK 且确需上述功能：从 https://www.renpy.org/latest.html 下载对应平台 SDK，"
        "解压后设 RENPY_SDK 即可，无需安装器；\n"
        "  ③ 目标是旧引擎（7.x）发行版：不必装 SDK，用游戏自带解释器就地执行，例如\n"
        "     cd <游戏根目录> && lib/windows-x86_64/python.exe <启动脚本>.py . lint\n"
        "  ④ 本机固定安装路径可在本文件顶部 _KNOWN_SDK_PATHS 追加一行"
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
