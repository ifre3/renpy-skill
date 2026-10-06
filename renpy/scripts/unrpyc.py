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
import hashlib
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
# 安全约定（2026-10-06 起）：固定下载 commit，不跟随 @master 浮动分支——
# 浮动分支意味着上游（或被劫持的镜像）推任何代码，本地下次运行就会执行。
# 升级方法：查上游 master 最新 SHA 并替换 UNRPYC_PINNED_COMMIT（api.github.com
# 直连不通，gh-proxy.com 放行 api 路径，ghproxy.net 不行）：
#   curl "https://gh-proxy.com/https://api.github.com/repos/CensoredUsername/unrpyc/commits/master"
# 残余风险：SHA 固定只保证"下次下载的内容 = 固定时审过的内容"，镜像本身仍不可信，
# 彻底收口需自带源码或加 zip 哈希校验。
#
# 镜像存活维护提示（2026-10-06 实测，拉固定 commit 的 unrpyc.py 与整包 zip，6 候选全通）：
# gh-proxy.com 1.2s / ghfast.top 1.4s / ghproxy.net 1.8s 最快，列前；jsDelivr 三条
# 4.8-6.4s，且 zip 路径 301 到 raw.githubusercontent.com（直连被墙的机器上等于死链，
# 仅 .py 单文件可直出），降到最后兜底；codeload 供 GitHub 可直连的环境。

UNRPYC_PINNED_COMMIT = "3ae8334ed71a05535927dcc559663d3aca51215b"  # 2026-02-23 master HEAD

DOWNLOAD_MIRRORS = [
    ("GitHub Proxy (gh-proxy)", f"https://gh-proxy.com/https://github.com/CensoredUsername/unrpyc/archive/{UNRPYC_PINNED_COMMIT}.zip"),
    ("GitHub Proxy (ghfast)",   f"https://ghfast.top/https://github.com/CensoredUsername/unrpyc/archive/{UNRPYC_PINNED_COMMIT}.zip"),
    ("GitHub Proxy (ghproxy)",  f"https://ghproxy.net/https://github.com/CensoredUsername/unrpyc/archive/{UNRPYC_PINNED_COMMIT}.zip"),
    ("GitHub CodeLoad",         f"https://codeload.github.com/CensoredUsername/unrpyc/zip/{UNRPYC_PINNED_COMMIT}"),
    ("jsDelivr (fastly)", f"https://fastly.jsdelivr.net/gh/CensoredUsername/unrpyc@{UNRPYC_PINNED_COMMIT}/unrpyc-master.zip"),
    ("jsDelivr (gcore)",  f"https://gcore.jsdelivr.net/gh/CensoredUsername/unrpyc@{UNRPYC_PINNED_COMMIT}/unrpyc-master.zip"),
    ("jsDelivr (cdn)",    f"https://cdn.jsdelivr.net/gh/CensoredUsername/unrpyc@{UNRPYC_PINNED_COMMIT}/unrpyc-master.zip"),
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

# 固定 commit 下每个文件的 sha256（2026-10-06 由 gh-proxy.com 整包与 jsDelivr
# 单文件两条独立线路交叉核实一致）。提取后逐文件校验：镜像被劫持或包被篡改
# 时在这里拦下，不让被改动的代码落地执行。升级 commit 时需同步重新生成此表。
EXPECTED_SHA256 = {
    "unrpyc.py": "b1b675eb1695783d610d6ed9206ff182b9a93730c07820206ce42bcdb20b2b71",
    "decompiler/__init__.py": "29a9f118e546759903d8298cbefa05ce2dcb0d56ae4988ca007dc47ce64b307f",
    "decompiler/astdump.py": "2eec53000a74694d69a0c743770c9c3fbfbde88b90c162167ad0061e3a5f31d3",
    "decompiler/atldecompiler.py": "af477495961bf966a0abfbd6260c75bd126db6e2fb560fcfd1936809c3061e06",
    "decompiler/magic.py": "358644232f0dfc37c8993135142019f734ddd6033bbdd5246d20575d71f14023",
    "decompiler/renpycompat.py": "7485333ca92e8025263dd7b8eac478d64c5a185f6327bf51a8968e64f5e005d6",
    "decompiler/sl2decompiler.py": "2ef32f573cce822ad20075f4a53d5a11d98acfd49a7c8ca8dd69629313524ed1",
    "decompiler/testcasedecompiler.py": "76672ad24bebfac5362ca3991b8c149e4672efeaae4019cb9b4a253446ee3490",
    "decompiler/translate.py": "b5678a0511179db901508bf4ae60d6086744e4b75143d074a688ee64a040bc58",
    "decompiler/util.py": "5762a72f26982ee1b6491b6b575e3bae839b08891623727f22cfd435461e2974",
    "deobfuscate.py": "eba39393bbebf73fccbbc6ab247b4c0b973fa399921a1f8233279e858e1c7a54",
    "LICENSE": "766c195777d0e687bc11ecb91a2fc8956f9dd65b804b93308684125cfe8ea5dd",
    "setup.py": "a3f8d087522bc40e3461ea79dd053a3658979189d66c08d8fe2ada9e8840535c",
}

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(TOOLS_DIR, "_unrpyc_src")


class HashMismatch(Exception):
    """提取的 unrpyc 源码与固定哈希不符——下载源不可信。"""


def _sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _verify_local():
    """校验本地缓存完整；不完整返回 False，被篡改抛 HashMismatch。"""
    for relpath, expected in EXPECTED_SHA256.items():
        target = os.path.join(SRC_DIR, relpath)
        if not os.path.isfile(target):
            return False
        digest = _sha256_of(target)
        if digest != expected:
            raise HashMismatch(
                f"{relpath} sha256 不匹配（期望 {expected[:12]}…，实际 {digest[:12]}…）"
            )
    return True


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
    if not _verify_local():
        raise HashMismatch("提取不完整（EXPECTED_SHA256 中有文件缺失）")
    return count


def _local_ok():
    for relpath in FILES_NEEDED:
        if not os.path.isfile(os.path.join(SRC_DIR, relpath)):
            return False
    return True


def download():
    for name, url in DOWNLOAD_MIRRORS:
        print(f"  ?? 尝试 {name} ...")
        data = _download_url(url)
        if data is None or len(data) < 2000:
            continue
        z, prefix = _get_zip(data)
        if z is None:
            continue
        try:
            count = _extract_files(z, prefix)
        except HashMismatch as e:
            print(red(f"    哈希校验失败，弃用该镜像并清空缓存: {e}"))
            shutil.rmtree(SRC_DIR, ignore_errors=True)
            continue
        finally:
            z.close()
        if count >= 6:
            print(green(f"  ? 成功! 从 {name} 解压 {count} 个文件（sha256 已校验）"))
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
    try:
        if not _local_ok() or args.redownload:
            if not download():
                print(red("? 所有镜像均失败（网络不通或哈希校验被拒），请检查网络或更新 UNRPYC_PINNED_COMMIT"))
                sys.exit(1)
        else:
            _verify_local()
    except HashMismatch as e:
        print(red(f"? unrpyc 源码哈希校验未通过: {e}\n  下载源不可信或缓存被改动，已拒绝执行；删除 {SRC_DIR} 后重试，或更新 UNRPYC_PINNED_COMMIT。"))
        shutil.rmtree(SRC_DIR, ignore_errors=True)
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
