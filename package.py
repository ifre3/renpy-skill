#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""打包 renpy-skill 为可分发 zip（纯标准库）。

为什么需要这个脚本
------------------
2026-10-06 发现：工作区里躺着的 `renpy-skill.zip` 是 2026-10-03 打的旧版——
顶层还是 `renpy-dev/` + `renpy-user/` 双技能、脚本目录还是中文名、还带着
16 个 `__pycache__` 条目和整个 `.git/`。也就是说「仓库里有一个能下下来的包」
这件事本身当时是**假的**，而没有任何检查能发现它。

这里做三件事：
1. 显式白名单打包（不靠「排除掉坏东西」，而是「只放该放的」）；
2. 打包后自检产物结构，违规直接失败；
3. 输出可复现的 sha256——时间戳固定、条目排序，所以同样的源码打出同样的包。

用法::

    python package.py            # 打包并自检，输出 sha256
    python package.py --check    # 只体检当前工作区，不写文件（适合提交前/CI）
    python package.py --out D:/x.zip

不依赖 git：本机没装 git，`git archive` 这条路走不通。
"""

import argparse
import hashlib
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))

# 消费者真正需要的：技能本体 + 三份仓库级文档
INCLUDE_DIRS = ("renpy",)
INCLUDE_FILES = ("README.md", "LICENSE", "CHANGELOG.md", ".gitignore")

EXCLUDE_DIRS = {".git", "__pycache__", ".zwork", ".pytest_cache", ".mypy_cache"}
EXCLUDE_SUFFIXES = (".pyc", ".pyo", ".bak", ".orig", ".rej")

# 固定时间戳 → 同样的源码打出字节相同的包
FIXED_DATE = (1980, 1, 1, 0, 0, 0)

# ── 自检规则 ────────────────────────────────────────────────
FORBIDDEN_SUBSTRINGS = (
    "__pycache__",
    ".git/",
    "renpy-dev/",
    "renpy-user/",          # 2026-10-03 之前的双技能布局
    "/tools/",              # 同上，脚本曾挂在 renpy-*/tools/
)
REQUIRED_ENTRIES = (
    "renpy/SKILL.md",
    "renpy/scripts/README.md",
    "renpy/scripts/renpy-tools-cli.py",
)


class PackageError(Exception):
    """产物结构不合法——宁可打包失败，也不要发一个坏包出去。"""


def _norm_rel(path):
    return os.path.relpath(path, ROOT).replace(os.sep, "/")


def collect():
    """按白名单收集要打包的条目，返回排序后的相对路径列表。"""
    found = []
    for name in INCLUDE_FILES:
        p = os.path.join(ROOT, name)
        if not os.path.isfile(p):
            raise PackageError(f"缺少必需文件：{name}")
        found.append(name)

    for top in INCLUDE_DIRS:
        top_path = os.path.join(ROOT, top)
        if not os.path.isdir(top_path):
            raise PackageError(f"缺少必需目录：{top}")
        for dirpath, dirnames, filenames in os.walk(top_path):
            dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDE_DIRS)
            for fn in sorted(filenames):
                if fn.endswith(EXCLUDE_SUFFIXES):
                    continue
                found.append(_norm_rel(os.path.join(dirpath, fn)))
    return sorted(found)


def verify(names):
    """对条目清单做结构自检。不合格抛 PackageError。"""
    nameset = set(names)

    for required in REQUIRED_ENTRIES:
        if required not in nameset:
            raise PackageError(f"产物缺少必需条目：{required}")

    skills = [n for n in nameset if n.endswith("SKILL.md")]
    if len(skills) != 1:
        raise PackageError(
            f"应当恰好一个 SKILL.md，实际 {len(skills)} 个：{sorted(skills)}"
            "（多技能布局会让 Agent 的触发词互相打架）"
        )

    bad = sorted(n for n in nameset for f in FORBIDDEN_SUBSTRINGS if f in n)
    if bad:
        raise PackageError(f"产物含禁止条目：{bad}")

    # scripts/ 下的分组目录必须全 ASCII（macOS NFD 归一化会打穿 import）
    scripts_prefix = "renpy/scripts/"
    groups = {
        n[len(scripts_prefix):].split("/", 1)[0]
        for n in nameset
        if n.startswith(scripts_prefix) and "/" in n[len(scripts_prefix):]
    }
    non_ascii = sorted(g for g in groups if not g.isascii())
    if non_ascii:
        raise PackageError(f"分组目录名非 ASCII：{non_ascii}")

    return sorted(groups)


def check_tree():
    """只体检工作区：跑一遍收集 + 自检，不写任何文件。"""
    names = collect()
    groups = verify(names)
    py = [n for n in names if n.endswith(".py")]
    print(f"[OK] 工作区可打包：{len(names)} 个条目，{len(py)} 个 .py")
    print(f"     分组目录（{len(groups)}）：{' '.join(groups)}")
    return names


def build(out_path):
    names = collect()
    groups = verify(names)

    tmp = out_path + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for rel in names:
            src = os.path.join(ROOT, *rel.split("/"))
            with open(src, "rb") as fh:
                data = fh.read()
            info = zipfile.ZipInfo(rel, date_time=FIXED_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            info.create_system = 3  # Unix，保证跨平台权限一致
            zf.writestr(info, data)
    os.replace(tmp, out_path)

    # 产物回读自检：确认真的能打开，且内容与清单一致
    with zipfile.ZipFile(out_path) as zf:
        bad = zf.testzip()
        if bad is not None:
            raise PackageError(f"zip 损坏，首个坏条目：{bad}")
        got = sorted(i.filename for i in zf.infolist())
    if got != names:
        only_zip = set(got) - set(names)
        only_list = set(names) - set(got)
        raise PackageError(f"产物与清单不一致：多出 {sorted(only_zip)}，缺少 {sorted(only_list)}")

    size = os.path.getsize(out_path)
    with open(out_path, "rb") as fh:
        digest = hashlib.sha256(fh.read()).hexdigest()

    print(f"[OK] 已打包 {out_path}")
    print(f"     条目 {len(names)}（.py {len([n for n in names if n.endswith('.py')])}）"
          f"，分组目录 {len(groups)}")
    print(f"     体积 {size:,} 字节")
    print(f"     sha256 {digest}")
    return out_path


def main(argv=None):
    ap = argparse.ArgumentParser(description="打包 renpy-skill（显式白名单 + 产物自检）")
    ap.add_argument("--out", default=os.path.join(ROOT, "renpy-skill.zip"),
                    help="输出路径，默认仓库根下的 renpy-skill.zip")
    ap.add_argument("--check", action="store_true",
                    help="只体检当前工作区，不写文件")
    args = ap.parse_args(argv)

    try:
        if args.check:
            check_tree()
        else:
            build(args.out)
    except PackageError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
