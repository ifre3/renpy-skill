#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
URM（Universal Ren'Py Mod）安装 / 卸载 / 体检
==============================================
针对玩家的通用作弊 / 调试 Mod（https://0x52.dev/mods/Universal-Ren-Py-Mod-1000，
作者 0x52，当前 v2.6.2）。投放式：不改游戏任何原文件，删除即完全还原。

## 为什么需要脚本而不是让 AI 手搓

URM 以 **.rpa 文件**形式分发（`0x52_URM.rpa`），不是 .rpy。这个事实模型容易猜错，
猜错的代价是「下载了 .rpa 却按 .rpy 的方式去改文件」。脚本做三件模型不可靠的事：

  1. **引擎版本闸门**：URM 要求 ≥ 6.99.14，从游戏目录读版本并拦下不满足的
  2. **.rpyc 残留检测**：删除 .rpy 后同目录 .rpyc 会继续生效（Ren'Py 加载
     .rpyc 优先且不校验 .rpy），这是「删了补丁却还在」的头号原因
  3. **文件签名记录**：安装时写入 .urm_installed.json，卸载据此精确回滚，
     不靠猜文件名（避免误删游戏自带的同名 .rpy）

## 边界（重要）

- **不下载**。第三方 URL 会漂移，且「替用户决定往游戏目录放可执行代码」不是
  AI 该做的决定。请用户自己从官网下载，本脚本只处理已下载到本地的文件。
- **不碰 .rpa 加密游戏**。这类游戏需先解包才能投放补丁（unlock_patches.md 同样限制），
  本脚本检测到 .rpa 加密特征会明确拒绝，而不是投放后静默失效。
- **不动原文件**。只新增 `game/` 下的 URM 文件 + 一份签名文件。

## 用法

    # 体检：引擎版本 / 是否已装 / 能否投放 / 常见故障排查（只读）
    python urm_install.py <游戏目录>

    # 安装（默认试运行，加 --apply 才落盘）
    python urm_install.py <游戏目录> --rpa <下载的0x52_URM.rpa>
    python urm_install.py <游戏目录> --rpa <...> --apply

    # 卸载（默认试运行；--apply 才删）
    python urm_install.py <游戏目录> --uninstall
    python urm_install.py <游戏目录> --uninstall --apply

    # 连同 .rpyc 残留一起清（卸载时自动检测并询问式提示）
    python urm_install.py <游戏目录> --uninstall --purge-rpyc --apply

## 装上后怎么确认

URM 默认不出现在主菜单，需要在游戏内触发：
  - 主菜单 / 游戏内按 **空格** 或点 **quickmenu 的齿轮图标**（部分版本在右上角）
  - 首次触发会弹「风险警告」，点确认（可在 URM 设置里对全部游戏禁用再确认）

若没反应，按 `check` 的输出逐条排查（最常见是引擎版本过低或 .rpyc 冲突）。
"""

import argparse
import json
import os
import re
import shutil
import sys

# ── 引入 shared/ 公共模块 ──
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shared")
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── 常量 ──

# URM 要求 ≥ 6.99.14（0x52 官网明确声明）。这是引擎下限，不是 Mod 版本。
URM_MIN_ENGINE = (6, 99, 14)

# 安装签名文件：记录本次装了什么，卸载据此精确回滚
SIGNATURE_NAME = ".urm_installed.json"

# URM 官方分发文件名（不同版本可能是 0x52_URM.rpa / universal_renpy_mod.rpa 等）
URM_NAME_HINTS = ("0x52", "urm", "universal")

# Ren'Py 版本号，出现在游戏根的若干位置
_VERSION_PATTERNS = (
    re.compile(r"version\s*=\s*\((\d+)\s*,\s*(\d+)\s*,\s*(\d+)"),
    re.compile(r"renpy_version\s*=\s*\((\d+)\s*,\s*(\d+)\s*,\s*(\d+)"),
    re.compile(r"'version'\s*:\s*\[(\d+)\s*,\s*(\d+)\s*,\s*(\d+)"),
)


# ── 工具函数 ──


def parse_game_dir(path):
    """接受游戏根目录或其中的 game/ 目录，返回 game 目录路径。"""
    p = os.path.abspath(path)
    if not os.path.isdir(p):
        raise SystemExit(f"[ERROR] 目录不存在：{p}")
    if os.path.basename(p).lower() == "game" and os.path.isdir(p):
        return p
    inner = os.path.join(p, "game")
    if os.path.isdir(inner):
        return inner
    # 发行版里 game/ 是必须的；没有就说明这不是 Ren'Py 项目根
    raise SystemExit(
        f"[ERROR] {p} 下没有 game/ 目录，这不是 Ren'Py 游戏根目录。\n"
        "       请指向含 game/ 的那一层（发行版通常就是 exe 同级）。"
    )


def read_engine_version(game_dir):
    """尽力读取引擎版本。读不到返回 None——不猜。

    常见位置：游戏根的 <name>.py / .sh / .bat（发行版自带启动脚本），
    或 game/ 下的 config 脚本。
    """
    root = os.path.dirname(game_dir)
    candidates = []
    for name in sorted(os.listdir(root)):
        if name.endswith((".py", ".sh", ".bat", ".rpy")):
            candidates.append(os.path.join(root, name))
    candidates += [
        os.path.join(game_dir, "options.rpy"),
        os.path.join(game_dir, "gui.rpy"),
    ]

    for path in candidates:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                head = fh.read(200000)
        except OSError:
            continue
        for pat in _VERSION_PATTERNS:
            m = pat.search(head)
            if m:
                return tuple(int(x) for x in m.groups()), os.path.basename(path)
    return None, None


def version_ok(version):
    return version is not None and version >= URM_MIN_ENGINE


def version_str(v):
    return ".".join(str(x) for x in v) if v else "未知"


def find_rpa_encrypted(game_dir):
    """检测 .rpa 加密游戏。URM 投放式补丁在加密游戏里无法加载。"""
    # 加密 .rpa 的典型特征：同目录下有 rpa 密钥文件 / index 隐藏
    for name in os.listdir(game_dir):
        low = name.lower()
        if low.endswith(".rpy") and ("key" in low or "rsa" in low):
            return True, name
        # 部分加密器把 index 拆成同名 .rpa.indexr / .idx
        if low.endswith((".rpa.indexr", ".rpa.index", ".idx")):
            return True, name
    return False, None


def load_signature(game_dir):
    path = os.path.join(game_dir, SIGNATURE_NAME)
    if not os.path.isfile(path):
        return None, path
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh), path
    except (OSError, ValueError) as exc:
        print(f"[WARN] 签名文件损坏（{exc}），按未安装处理：{path}")
        return None, path


def write_signature(game_dir, payload):
    path = os.path.join(game_dir, SIGNATURE_NAME)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    return path


def looks_like_urm(filename):
    low = filename.lower()
    return any(h in low for h in URM_NAME_HINTS) and low.endswith((".rpa", ".rpy", ".rpyc", ".zip"))


def scan_existing(game_dir):
    """扫 game/ 下已存在的 URM 相关文件（用于体检与幂等判断）。"""
    hits = []
    for root, _dirs, files in os.walk(game_dir):
        for name in files:
            if looks_like_urm(name) and name != SIGNATURE_NAME:
                hits.append(os.path.join(root, name))
    return hits


def stale_rpyc(targets):
    """找出与 targets 同名不同扩展的编译残留（.rpyc / .rpymc / .bak）。

    Ren'Py 加载 .rpyc 优先于 .rpy，且不校验两者是否一致——所以删掉 .rpy
    补丁后同目录的 .rpyc 会继续生效。这是「删了补丁却还在」的头号原因。

    扫全部同名变体而不只是 .rpyc：URM 官方发 .rpa，但部分用户会解包成
    .rpy/.rpym 放进 game/，那些同样会编译出 .rpyc。
    """
    stale = []
    for t in targets:
        stem = os.path.splitext(t)[0]
        for ext in (".rpyc", ".rpymc", ".bak"):
            cand = stem + ext
            if os.path.isfile(cand) and cand not in targets:
                stale.append(cand)
    return stale


# ── 体检 ──


def do_check(game_dir):
    print("=" * 62)
    print("  URM 安装体检（只读）")
    print("=" * 62)

    version, src = read_engine_version(game_dir)
    if version_ok(version):
        print(f"[OK]   引擎版本 {version_str(version)}  ≥ {version_str(URM_MIN_ENGINE)}"
              f"（来源 {src}）")
    elif version is None:
        print(f"[?]    引擎版本未读到 → 无法确认是否 ≥ {version_str(URM_MIN_ENGINE)}")
        print("       装之前手动确认：游戏能跑的 Ren'Py 基本都够，但老游戏（6.99.12 及更早）不行。")
        print("       查法：启动游戏看 log.txt 顶部 'Ren'Py version:' 那行。")
    else:
        print(f"[FAIL] 引擎版本 {version_str(version)} < {version_str(URM_MIN_ENGINE)}"
              f"（来源 {src}）")
        print("       URM 官方声明不支持这个版本，装了也不会加载。")

    encrypted, enc_name = find_rpa_encrypted(game_dir)
    if encrypted:
        print(f"[WARN] 检测到 .rpa 加密特征（{enc_name}）")
        print("       投放式补丁在加密游戏里不生效。先解包再用，解包见 player_tools.md。")
    else:
        print("[OK]   未检测到 .rpa 加密特征")

    sig, sig_path = load_signature(game_dir)
    existing = scan_existing(game_dir)
    if sig:
        files = sig.get("files", [])
        print(f"[OK]   检测到本工具安装的 URM（签名 {os.path.basename(sig_path)}）")
        print(f"       记录文件：{', '.join(os.path.basename(f) for f in files) or '（空）'}")
        print(f"       卸载：python {os.path.basename(__file__)} <游戏目录> --uninstall --apply")
        # 已装状态下同样要报残留：用户可能手工塞过 .rpy，或解包过官方 .rpa
        existing = existing or []
    elif existing:
        print("[?]    game/ 下有疑似 URM 文件，但不是本工具安装的：")
        for f in existing:
            print(f"       - {os.path.relpath(f, game_dir)}")
        print("       可能是手工放的。若要升级/卸载，请自行确认后再删。")
    else:
        print("[OK]   未安装 URM")

    # 残留扫描：以「卸载会删哪些文件」为基准，算出卸载后仍会留下的同名编译产物。
    # 判据不能用 scan_existing 的结果做排除——那些残留本身就是不该留下的。
    signed = [
        os.path.join(game_dir, f) for f in (sig or {}).get("files", [])
        if os.path.isfile(os.path.join(game_dir, f))
    ]
    if sig or existing:
        stale = stale_rpyc(signed or existing)
        stale = [f for f in stale if f not in signed]
        if stale:
            print(f"[WARN] 存在编译残留（{len(stale)} 个）——删除 .rpy 后它们会继续生效：")
            for f in stale:
                print(f"       - {os.path.relpath(f, game_dir)}")
            print("       卸载时加 --purge-rpyc 一并清理。")

        # 未签名的 .rpy/.rpym：不是本工具装的（多半是用户手工解包过官方 .rpa），
        # 但它们同样会被 Ren'Py 编译并加载——只清 .rpyc 不够，.rpy 本身得处理。
        # 不自动删（用户自己放的），但必须报出来，否则「卸载了却还在生效」。
        signed_set = {os.path.normpath(p) for p in signed}
        unsigned_src = [
            f for f in existing
            if os.path.normpath(f) not in signed_set
            and f.lower().endswith((".rpy", ".rpym"))
        ]
        if unsigned_src:
            print(f"[WARN] 另有 {len(unsigned_src)} 个未签名的脚本（非本工具安装，"
                  f"通常是手工解包官方 .rpa 得到）：")
            for f in unsigned_src:
                print(f"       - {os.path.relpath(f, game_dir)}")
            print("       这些会被 Ren'Py 编译加载。想彻底卸载需自行删除它们"
                  "（删 .rpy 的同时删同目录 .rpyc）。")

    print()
    print("装上后怎么确认：游戏内按空格（或 quickmenu 齿轮图标）触发 URM 面板。")
    print("官方下载：https://0x52.dev/mods/Universal-Ren-Py-Mod-1000（本脚本不代下）")
    print("=" * 62)
    return 0


# ── 安装 ──


def do_install(game_dir, rpa_path, apply):
    src = os.path.abspath(rpa_path)
    if not os.path.isfile(src):
        raise SystemExit(f"[ERROR] 找不到文件：{src}")

    version, vsrc = read_engine_version(game_dir)
    if version is not None and not version_ok(version):
        print(f"[ERROR] 引擎 {version_str(version)}（{vsrc}）< URM 要求的 "
              f"{version_str(URM_MIN_ENGINE)}，不安装。")
        print("        URM 官方声明不支持该版本，装了也不加载。")
        return 2
    if version is None:
        print(f"[?]    引擎版本读不到，无法自动确认 ≥ {version_str(URM_MIN_ENGINE)}。")
        print("       继续安装，但请自行确认游戏 Ren'Py 版本。")

    encrypted, enc_name = find_rpa_encrypted(game_dir)
    if encrypted:
        print(f"[ERROR] 检测到 .rpa 加密特征（{enc_name}），拒绝投放。")
        print("        加密游戏的 .rpa 无法被 URM 正常加载，先解包：见 player_tools.md。")
        return 2

    sig, _ = load_signature(game_dir)
    if sig:
        print("[ERROR] 本工具已安装过 URM（签名文件存在）。")
        print("        升级请先 --uninstall --apply，再装新的。")
        return 2

    dest_name = os.path.basename(src)
    if not looks_like_urm(dest_name):
        print(f"[?]    文件名 {dest_name} 不含 URM 关键字（{'/'.join(URM_NAME_HINTS)}）。")
        print("       URM 官方文件名通常是 0x52_URM.rpa。确认这是 URM 再继续。")
    dest = os.path.join(game_dir, dest_name)

    if os.path.isfile(dest) and os.path.getsize(dest) == os.path.getsize(src):
        print(f"[SKIP] {dest_name} 已存在且大小一致，未改动。")
        return 0

    print()
    print("计划安装：")
    print(f"  源    : {src}  ({os.path.getsize(src)/1024:.1f} KB)")
    print(f"  目标  : {dest}")
    print(f"  签名  : {SIGNATURE_NAME}（供 --uninstall 精确回滚）")
    print(f"  引擎  : {version_str(version) if version else '未读到'}")
    print()
    print("不改游戏任何原有文件；卸载只需删除上述两项。")
    if not apply:
        print()
        print("试运行结束（未写入）。确认无误后加 --apply。")
        return 0

    # 备份同名文件（幂等保护：重复安装不静默覆盖）
    if os.path.isfile(dest):
        bak = dest + ".bak"
        if not os.path.isfile(bak):
            shutil.copy2(dest, bak)
            print(f"\n已备份同名文件 → {os.path.basename(bak)}")

    shutil.copy2(src, dest)
    print(f"\n[OK] 已安装 {dest_name}")

    write_signature(game_dir, {
        "mod": "Universal Ren'Py Mod",
        "source_url": "https://0x52.dev/mods/Universal-Ren-Py-Mod-1000",
        "installed_file": dest_name,
        "files": [dest_name, SIGNATURE_NAME],
        "engine_version": version_str(version) if version else None,
        "note": "删除本文件与签名文件即可完全还原游戏",
    })
    print(f"[OK] 已写入签名 {SIGNATURE_NAME}")

    print()
    print("验证：启动游戏 → 游戏内按空格，或点 quickmenu 的齿轮图标。")
    print("首次会弹风险警告，点确认。")
    return 0


# ── 卸载 ──


def do_uninstall(game_dir, apply, purge_rpyc):
    sig, sig_path = load_signature(game_dir)
    if not sig:
        print("[ERROR] 没有本工具的安装签名，无法安全卸载。")
        print("        签名是精确回滚的依据；没有它只能靠文件名猜，可能误删游戏自有文件。")
        loose = scan_existing(game_dir)
        if loose:
            print()
            print("        但 game/ 下确实有疑似 URM 文件，需你自行确认后删除：")
            for f in loose:
                print(f"          - {os.path.relpath(f, game_dir)}")
            print("        注意：.rpy 的同目录 .rpyc 也要一起删，否则补丁仍会生效。")
        else:
            print("        game/ 下未发现 URM 相关文件，可能本就未安装。")
        return 2

    targets = []
    for name in sig.get("files", []):
        p = os.path.join(game_dir, name)
        if os.path.isfile(p):
            targets.append(p)
        elif name != SIGNATURE_NAME:
            print(f"[WARN] 签名里记的文件已不在：{name}（跳过）")

    # 未签名的 .rpy/.rpym 不自动删（用户自己放的），但卸载前必须提示，
    # 否则「删了签名文件却依然生效」——Ren'Py 会把它们重新编译。
    signed_set = {os.path.normpath(p) for p in targets}
    unsigned = [
        f for f in scan_existing(game_dir)
        if os.path.normpath(f) not in signed_set
        and f.lower().endswith((".rpy", ".rpym"))
    ]
    if unsigned:
        print(f"[WARN] game/ 下另有 {len(unsigned)} 个未签名的 URM 脚本"
              f"（非本工具安装，本次不会删）：")
        for f in unsigned:
            print(f"       - {os.path.relpath(f, game_dir)}")
        print("       删掉它们才算彻底卸载（注意同目录 .rpyc 也要一起删）。")
        print()

    stale = stale_rpyc(targets)
    if stale and not purge_rpyc:
        print(f"[WARN] 检测到 {len(extra_rpyc)} 个 .rpyc 残留，删除 .rpy 后它们会继续生效：")
        for f in extra_rpyc:
            print(f"       - {os.path.relpath(f, game_dir)}")
        print("       要一并清理请加 --purge-rpyc。")

    if not targets:
        print("[SKIP] 签名记录的文件都不存在，游戏已是干净状态。")
        return 0

    print()
    print("计划卸载：")
    for t in targets:
        print(f"  删除  {os.path.relpath(t, game_dir)}  ({os.path.getsize(t)/1024:.1f} KB)")
    for f in stale:
        print(f"  删除  {os.path.relpath(f, game_dir)}  (.rpyc 残留)")
    print()
    print("卸载后游戏完全恢复原状（URM 不写存档、不改 persistent）。")

    if not apply:
        print()
        print("试运行结束（未删除）。确认无误后加 --apply。")
        return 0

    for t in targets + stale:
        try:
            os.remove(t)
            print(f"[OK] 已删除 {os.path.relpath(t, game_dir)}")
        except OSError as exc:
            print(f"[FAIL] 删除失败 {t}：{exc}", file=sys.stderr)
            return 1
    return 0


# ── 入口 ──


def main():
    parser = argparse.ArgumentParser(
        description="URM（Universal Ren'Py Mod）安装 / 卸载 / 体检",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("game_dir", help="游戏根目录（含 game/ 的那一层）")
    parser.add_argument("--rpa", help="已下载的 URM 文件路径（安装时用；本脚本不下载）")
    parser.add_argument("--uninstall", action="store_true", help="卸载已安装的 URM")
    parser.add_argument(
        "--purge-rpyc", action="store_true",
        help="卸载时一并清理 .rpyc 残留（不改这参数会导致补丁删了仍生效）",
    )
    parser.add_argument("--apply", action="store_true", help="实际写入/删除；不加则试运行")
    args = parser.parse_args()

    game_dir = parse_game_dir(args.game_dir)

    if args.uninstall:
        if args.rpa:
            print("[ERROR] --uninstall 与 --rpa 不能同时用。")
            return 2
        return do_uninstall(game_dir, args.apply, args.purge_rpyc)

    if args.rpa:
        return do_install(game_dir, args.rpa, args.apply)

    if args.apply:
        print("[?]    没有 --rpa 也没 --uninstall，按体检处理（--apply 无作用）。")
        print()
    return do_check(game_dir)


if __name__ == "__main__":
    sys.exit(main() or 0)