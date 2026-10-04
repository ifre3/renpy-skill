#!/usr/bin/env python3
"""
Ren'Py 资源完整性检查工具
扫描 .rpy 中引用的图片/音频文件，与实际文件对比，报告缺失和未使用的资源
"""
import os
import re
import argparse
from pathlib import Path
from collections import defaultdict


ASSET_TYPES = {
    "image": {
        "exts": {".png", ".jpg", ".jpeg", ".webp", ".gif"},
        "patterns": [
            r'(?:scene|show|hide)\s+(\w+)',  # 显示命令后的图像名
            r'"((?:bg|chara|cg|ui)\w*\.(?:png|jpg|jpeg|webp|gif))"',
            r'"(images/[^"]+\.(?:png|jpg|jpeg|webp|gif))"',
            r'add\s+"([^"]+\.(?:png|jpg|jpeg|webp|gif))"',
        ],
    },
    "audio": {
        "exts": {".ogg", ".mp3", ".wav", ".m4a"},
        "patterns": [
            r'play\s+(?:music|sound|voice)\s+"([^"]+)"',
            r'stop\s+(?:music|sound|voice)',
            r"'(audio/[^']+\.(?:ogg|mp3|wav|m4a))'",
            r'"(audio/[^"]+\.(?:ogg|mp3|wav|m4a))"',
        ],
    },
    "font": {
        "exts": {".ttf", ".otf", ".ttc"},
        "patterns": [
            r'"(fonts/[^"]+\.(?:ttf|otf|ttc))"',
            r"'fonts/[^']+\.(?:ttf|otf|ttc)'",
        ],
    },
}


def scan_rpy_files(project_path):
    """扫描所有 .rpy 文件"""
    game_dir = Path(project_path) / "game"
    files = list(game_dir.rglob("*.rpy"))
    # 排除 tl/ 目录下的翻译文件（不检查引用）
    files = [f for f in files if "tl" not in f.parts]
    return files


def extract_references(rpy_files):
    """从 .rpy 文件中提取所有资源引用"""
    refs = defaultdict(set)

    for rpy_file in rpy_files:
        content = rpy_file.read_text(encoding="utf-8", errors="ignore")
        lines = content.split("\n")

        for lineno, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            # 跳过注释部分
            if "#" in stripped:
                line_before_comment = stripped.split("#")[0]
            else:
                line_before_comment = stripped

            for asset_type, info in ASSET_TYPES.items():
                for pattern in info["patterns"]:
                    for match in re.finditer(pattern, line_before_comment):
                        if not match.groups():
                            continue  # 无捕获组的模式（如 stop music）不产生引用
                        ref = match.group(1)
                        # 剥离 ATL 音频前缀，如 <from 0 to 129>song.mp3 / <loop 3.5>x.ogg
                        ref = re.sub(r"^<[^>]*>", "", ref)
                        if not ref:
                            continue
                        refs[asset_type].add((ref, str(rpy_file), lineno))

    return refs


def list_actual_files(project_path):
    """列出项目 game/ 下实际存在的资源文件"""
    actual = defaultdict(set)
    game_dir = Path(project_path) / "game"

    # 标准资源目录
    scan_dirs = {
        "image": ["images", "images/bg", "images/chara", "images/cg", "images/ui", "gui"],
        "audio": ["audio", "audio/bgm", "audio/sfx", "audio/voice"],
        "font": ["fonts"],
    }

    for asset_type, dirs in scan_dirs.items():
        for d in dirs:
            dir_path = game_dir / d
            if dir_path.exists():
                for f in dir_path.rglob("*"):
                    if f.is_file() and f.suffix.lower() in ASSET_TYPES[asset_type]["exts"]:
                        actual[asset_type].add(f.name)

    # 很多发行版把音频/字体直接放在 game/ 根目录，一并索引
    for f in game_dir.iterdir():
        if f.is_file():
            ext = f.suffix.lower()
            for at, info in ASSET_TYPES.items():
                if ext in info["exts"]:
                    actual[at].add(f.name)

    return actual


def check_assets(project_path):
    """执行完整性检查"""
    rpy_files = scan_rpy_files(project_path)

    if not rpy_files:
        print("❌ 未找到任何 .rpy 文件")
        return

    print(f"🔍 正在检查 {len(rpy_files)} 个 .rpy 文件...\n")

    refs = extract_references(rpy_files)
    actual = list_actual_files(project_path)

    # 用于匹配时忽略扩展名的引用名列表
    rpy_names = {}
    for asset_type, items in refs.items():
        for ref, fpath, lineno in items:
            name_no_ext = os.path.splitext(ref)[0]
            if name_no_ext not in rpy_names:
                rpy_names[name_no_ext] = []
            rpy_names[name_no_ext].append((asset_type, ref, fpath, lineno))

    total_issues = 0

    # 预建小写索引（文件名 / 去扩展名），避免 引用数×文件数 的 O(n²) 比对
    def _lower_index(names):
        s = set()
        for fname in names:
            s.add(fname.lower())
            s.add(os.path.splitext(fname)[0].lower())
        return s

    img_index = _lower_index(actual.get("image", set()))
    audio_index = _lower_index(actual.get("audio", set()))
    font_index = _lower_index(actual.get("font", set()))

    # ---- 检查图片资源 ----
    print("=" * 60)
    print("📷 图片资源检查")
    print("=" * 60)

    missing_images = []
    for ref, fpath, lineno in refs.get("image", set()):
        # 检查引用内容是否直接是文件名（引用可能带 gui/overlay/ 之类的路径前缀）
        rl = ref.lower()
        found = (
            rl in img_index
            or os.path.splitext(rl)[0] in img_index
            or os.path.basename(rl) in img_index
            or os.path.splitext(os.path.basename(rl))[0] in img_index
        )
        if not found:
            # 检查是不是 Ren'Py 定义的图像名（define image），那里不需要实际文件
            # 或者在 scene/show 里用的不是文件名而是标签
            has_ext = bool(os.path.splitext(ref)[1])
            if has_ext:
                missing_images.append((ref, fpath, lineno))
            # 没有扩展名的可能就是图像标签，跳过

    if missing_images:
        print(f"\n❌ 缺失 {len(missing_images)} 个图片文件:")
        for ref, fpath, lineno in sorted(missing_images, key=lambda x: x[0]):
            rel = Path(fpath).relative_to(Path(project_path) / "game")
            print(f"   {ref}")
            print(f"     → 引用位置: {rel}:{lineno}")
            total_issues += 1
    else:
        print("\n✅ 所有引用的图片文件都存在")

    # ---- 检查音频资源 ----
    print(f"\n{'=' * 60}")
    print("🎵 音频资源检查")
    print("=" * 60)

    missing_audio = []
    for ref, fpath, lineno in refs.get("audio", set()):
        if ref.lower() not in audio_index and os.path.splitext(ref)[0].lower() not in audio_index:
            missing_audio.append((ref, fpath, lineno))

    if missing_audio:
        print(f"\n❌ 缺失 {len(missing_audio)} 个音频文件:")
        for ref, fpath, lineno in sorted(missing_audio, key=lambda x: x[0]):
            rel = Path(fpath).relative_to(Path(project_path) / "game")
            print(f"   {ref}")
            print(f"     → 引用位置: {rel}:{lineno}")
            total_issues += 1
    else:
        print("\n✅ 所有引用的音频文件都存在")

    # ---- 检查字体资源 ----
    print(f"\n{'=' * 60}")
    print("🔤 字体资源检查")
    print("=" * 60)

    missing_fonts = []
    for ref, fpath, lineno in refs.get("font", set()):
        if ref.lower() not in font_index and os.path.splitext(ref)[0].lower() not in font_index:
            missing_fonts.append((ref, fpath, lineno))

    if missing_fonts:
        print(f"\n❌ 缺失 {len(missing_fonts)} 个字体文件:")
        for ref, fpath, lineno in sorted(missing_fonts, key=lambda x: x[0]):
            rel = Path(fpath).relative_to(Path(project_path) / "game")
            print(f"   {ref}")
            print(f"     → 引用位置: {rel}:{lineno}")
            total_issues += 1
    else:
        print("\n✅ 所有引用的字体文件都存在")

    # ---- 检查未使用资源 ----
    print(f"\n{'=' * 60}")
    print("📦 未使用资源检查")
    print("=" * 60)

    # 收集所有引用的文件名（不带路径）
    all_ref_names = set()
    for asset_type in ("image", "audio", "font"):
        for ref, _, _ in refs.get(asset_type, set()):
            all_ref_names.add(os.path.splitext(ref)[0].lower())
            all_ref_names.add(ref.lower())

    unused = []
    for asset_type in ("image", "audio", "font"):
        for fname in actual.get(asset_type, set()):
            name_no_ext = os.path.splitext(fname)[0].lower()
            if name_no_ext not in all_ref_names and fname.lower() not in all_ref_names:
                unused.append((asset_type, fname))

    if unused:
        print(f"\n⚠️  发现 {len(unused)} 个未被引用的资源文件:")
        for asset_type, fname in sorted(unused, key=lambda x: x[1]):
            print(f"   [{asset_type}] {fname}")
    else:
        print("\n✅ 所有资源文件都有被引用")

    # ---- 总览 ----
    print(f"\n{'=' * 60}")
    print(f"检查完成")
    ref_count = sum(len(v) for v in refs.values())
    actual_count = sum(len(v) for v in actual.values())
    print(f"   扫描 .rpy 文件: {len(rpy_files)} 个")
    print(f"   引用资源总数: {ref_count} 处")
    print(f"   实际资源文件: {actual_count} 个")
    print(f"   问题总数: {total_issues} 个")
    if total_issues == 0:
        print("🎉 资源完整性良好！")
    else:
        print(f"⚠️  请修复以上 {total_issues} 个问题")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Ren'Py 资源完整性检查工具"
    )
    parser.add_argument(
        "--path", required=True,
        help="Ren'Py 项目根目录（含 game/ 文件夹的路径）"
    )

    args = parser.parse_args()

    if not (Path(args.path) / "game").exists():
        print(f"❌ 未找到 Ren'Py 项目: {args.path}")
        print("   请确认路径指向含 game/ 文件夹的项目根目录")
    else:
        check_assets(args.path)
