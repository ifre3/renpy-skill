#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
unrpyc 反编译 —— 下载 unrpyc 源码后直接 import 反编译 Ren'Py 游戏 .rpyc 文件。

用法:
  python scripts/unrpyc.py <项目目录>
  python scripts/unrpyc.py <项目目录> -c             # 覆盖已有 .rpy
  python scripts/unrpyc.py <项目目录> -t schinese    # 用中文翻译替换对话
  python scripts/unrpyc.py <项目目录> --try-harder   # 反混淆
  python scripts/unrpyc.py <项目目录> -p 4           # 4 线程并行
  python scripts/unrpyc.py --status                  # 查看本地状态
"""

import argparse
import io
import os
import shutil
import sys
import urllib.error
import urllib.request
import zipfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def green(s): return f"\033[92m{s}\033[0m" if sys.stdout.isatty() else s
def red(s):   return f"\033[91m{s}\033[0m" if sys.stdout.isatty() else s
def yellow(s):return f"\033[93m{s}\033[0m" if sys.stdout.isatty() else s
def dim(s):   return f"\033[2m{s}\033[0m" if sys.stdout.isatty() else s


# ─── 下载镜像（按优先级） ────────────────────────────────────────
# 维护提示（2026-10 核对）：免费镜像经常失效，顺序只影响首次命中率，
# 死链靠下载循环逐个 fallback，不影响功能。当前存活实例可查聚合页
# https://ghproxy.link。jsDelivr 三条与 ghproxy.net / gh-proxy.com 存活；
# ghfast.top 存活不确定，已降到 codeload 之后。

DOWNLOAD_MIRRORS = [
    ("jsDelivr (fastly)", "https://fastly.jsdelivr.net/gh/CensoredUsername/unrpyc@master/unrpyc-master.zip"),
    ("jsDelivr (gcore)",  "https://gcore.jsdelivr.net/gh/CensoredUsername/unrpyc@master/unrpyc-master.zip"),
    ("jsDelivr (cdn)",    "https://cdn.jsdelivr.net/gh/CensoredUsername/unrpyc@master/unrpyc-master.zip"),
    ("GitHub Proxy (ghproxy)",  "https://ghproxy.net/https://github.com/CensoredUsername/unrpyc/archive/refs/heads/master.zip"),
    ("GitHub CodeLoad",         "https://codeload.github.com/CensoredUsername/unrpyc/zip/refs/heads/master"),
    ("GitHub Proxy (ghfast)",   "https://ghfast.top/https://github.com/CensoredUsername/unrpyc/archive/refs/heads/master.zip"),
    ("GitHub Proxy (gh-proxy)", "https://gh-proxy.com/https://github.com/CensoredUsername/unrpyc/archive/refs/heads/master.zip"),
]

FILES_NEEDED = [
    "unrpyc.py",
    "decompiler/__init__.py",
    "decompiler/astdump.py",
    "decompiler/atldecompiler.py",
    "decompiler/magic.py",
    "decompiler/renpycompat.py",
    "decompiler/sl2decompiler.py",
    "decompiler/testcasedecompiler.py",
    "decompiler/translate.py",
    "decompiler/util.py",
    "deobfuscate.py",
    "LICENSE",
    "setup.py",
]

ZIP_PREFIX = "unrpyc-master/"

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(TOOLS_DIR, "_unrpyc_src")


# ─── 下载 ────────────────────────────────────────────────────────


def _download_url(url, timeout=120):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) unrpyc-downloader/1.0",
            "Accept": "*/*",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, TimeoutError) as e:
        print(f"    {dim(f'失败: {e}')}")
        return None


def _extract_zip_from_jsd(zip_bytes):
    """jsDelivr 返回的可能是外层 zip 内嵌内层 zip"""
    try:
        outer = zipfile.ZipFile(io.BytesIO(zip_bytes))
        inner_name = None
        for name in outer.namelist():
            if name.endswith(".zip") and "/" not in name.rstrip("/"):
                inner_name = name
                break
        if inner_name:
            inner_bytes = outer.read(inner_name)
            outer.close()
            return zipfile.ZipFile(io.BytesIO(inner_bytes))
        # 也有平铺的
        has_direct = any(fname.endswith(".py") and "/" not in fname for fname in outer.namelist())
        if has_direct:
            return outer
        outer.close()
    except zipfile.BadZipFile:
        pass
    return None


def _get_zip(data):
    """从 bytes 解析 zip，返回 (ZipFile, 前缀路径)"""
    # 常规解析
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
        names = z.namelist()
        prefixes = set()
        for n in names:
            parts = n.split("/")
            if len(parts) > 1 and parts[0]:
                prefixes.add(parts[0])
        for prefix in sorted(prefixes, key=lambda x: -len(x)):
            if any(f.startswith(prefix + "/") and f.endswith(".py") for f in names):
                return z, prefix + "/"
        return z, ""
    except zipfile.BadZipFile:
        pass
    # jsDelivr 嵌套格式
    z2 = _extract_zip_from_jsd(data)
    if z2:
        names = z2.namelist()
        prefixes = set()
        for n in names:
            parts = n.split("/")
            if len(parts) > 1 and parts[0]:
                prefixes.add(parts[0])
        for prefix in sorted(prefixes, key=lambda x: -len(x)):
            if any(f.startswith(prefix + "/") and f.endswith(".py") for f in names):
                return z2, prefix + "/"
        return z2, ""
    return None, None


def _extract_files(z, prefix):
    os.makedirs(SRC_DIR, exist_ok=True)
    count = 0
    for relpath in FILES_NEEDED:
        entry = prefix + relpath
        try:
            info = z.getinfo(entry)
        except KeyError:
            continue
        target = os.path.join(SRC_DIR, relpath)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with z.open(info) as src, open(target, "wb") as dst:
            shutil.copyfileobj(src, dst)
        count += 1
    return count


def _local_ok():
    for relpath in FILES_NEEDED:
        if not os.path.isfile(os.path.join(SRC_DIR, relpath)):
            return False
    return True


def download():
    err = None
    for name, url in DOWNLOAD_MIRRORS:
        print(f"  ?? 尝试 {name} ...")
        data = _download_url(url)
        if data is None or len(data) < 2000:
            continue
        z, prefix = _get_zip(data)
        if z is None:
            continue
        count = _extract_files(z, prefix)
        z.close()
        if count >= 6:
            print(green(f"  ? 成功! 从 {name} 解压 {count} 个文件"))
            return True
    return False


# ─── 反编译逻辑 ──────────────────────────────────────────────


def find_rpyc_files(game_dir):
    result = []
    for root, dirs, fnames in os.walk(game_dir):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in fnames:
            if f.endswith((".rpyc", ".rpymc")):
                result.append(os.path.join(root, f))
    return sorted(result)


def main():
    ap = argparse.ArgumentParser(
        description="unrpyc 反编译（自动下载 + 多镜像切换）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("project", nargs="?", help="Ren'Py 项目目录（含 game/）")
    ap.add_argument("-c", "--clobber", action="store_true", help="覆盖已存在的 .rpy")
    ap.add_argument("-t", "--translate", help="用翻译替换对话（如 schinese）")
    ap.add_argument("--try-harder", action="store_true", help="反混淆")
    ap.add_argument("-p", "--processes", type=int, choices=range(1, 12),
                    metavar="{1..11}", help="并行线程数")
    ap.add_argument("--no-init-offset", action="store_true",
                    help="禁用 init offset 猜测")
    ap.add_argument("--redownload", action="store_true",
                    help="强制重新下载")
    ap.add_argument("--status", action="store_true",
                    help="检查下载状态")
    args = ap.parse_args()

    # ── status ──
    if args.status:
        if _local_ok():
            version = "?"
            try:
                with open(os.path.join(SRC_DIR, "unrpyc.py"), encoding="utf-8") as f:
                    for line in f:
                        if "__version__" in line:
                            version = line.split("=")[-1].strip().strip("'\"")
                            break
            except Exception:
                pass
            print(green(f"? unrpyc 本地已就绪 ({version})"))
        else:
            print(yellow("? unrpyc 未下载，运行以下命令自动下载:\n    python scripts/unrpyc.py <项目目录>"))
        return

    # ── 确保源码 ──
    if not _local_ok() or args.redownload:
        if not download():
            print(red("? 所有镜像均失败，请检查网络连接"))
            sys.exit(1)
    print(dim(f"? 使用本地缓存: {SRC_DIR}"))

    # ── 仅下载 ──
    if not args.project:
        print(green("? unrpyc 源码下载完成"))
        return

    # ── 定位 game ──
    game_dir = args.project
    if os.path.isdir(os.path.join(game_dir, "game")):
        game_dir = os.path.join(game_dir, "game")
    if not os.path.isdir(game_dir):
        print(red(f"? 找不到目录: {args.project}（需包含 game/ 子目录）"))
        sys.exit(1)

    rpyc_files = find_rpyc_files(game_dir)
    if not rpyc_files:
        print(yellow(f"? {game_dir} 下未找到 .rpyc 文件"))
        return

    # ── 过滤已有 ──
    if not args.clobber:
        existing = [f for f in rpyc_files if os.path.isfile(f[:-1])]
        if existing:
            print(yellow(f"  ? {len(existing)} 个 .rpy 已存在（使用 -c 覆盖）"))
            rpyc_files = [f for f in rpyc_files if not os.path.isfile(f[:-1])]
            if not rpyc_files:
                print(green("? 所有文件均已反编译"))
                return

    # ── 构建参数 ──
    argv = ["unrpyc.py", *rpyc_files]
    if args.clobber:
        argv.append("-c")
    if args.translate:
        argv += ["-t", args.translate]
    if args.try_harder:
        argv.append("--try-harder")
    if args.processes:
        argv += ["-p", str(args.processes)]
    if args.no_init_offset:
        argv.append("--no-init-offset")

    # ── 直接 import 调用 ──
    sys.path.insert(0, SRC_DIR)
    import unrpyc as _unrpyc

    old_argv = sys.argv
    try:
        sys.argv = argv
        print(green(f"? 开始反编译 {len(rpyc_files)} 个文件..."))
        _unrpyc.main()
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        sys.argv = old_argv

    print(green(f"? 反编译完成! 处理了 {len(rpyc_files)} 个文件"))


if __name__ == "__main__":
    main()
