#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量压缩图片/音频，减小发行版包体积。

设计约定：
- 缺 pngquant / jpegoptim / ffmpeg 时逐文件降级为复制，但**必须如实报告**
  「跳过 N 个」，绝不把全部跳过说成「优化完成」。
- 输出目录始终与输入目录镜像；复制降级时不覆盖已优化的同名文件以外的内容。
- Windows GBK 控制台安全：stdout 强制 UTF-8，emoji 不会 UnicodeEncodeError。

退出码：
- 0：有文件成功优化（可能同时有跳过）
- 1：一个都没优化成功（全量降级为复制）
- 2：参数/IO 错误
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
AUDIO_EXTS = {".mp3", ".ogg", ".oga", ".wav", ".m4a", ".flac", ".aiff", ".aif", ".opus"}


def _size_kb(path):
    return os.path.getsize(path) / 1024


def _report(original, output, ok, skip_reason=""):
    original_size = _size_kb(original)
    output_size = _size_kb(output)
    ratio = (1 - output_size / original_size) * 100 if original_size else 0.0
    if ok:
        return True, f"优化成功：减小 {ratio:.1f}% ({original_size:.1f}KB → {output_size:.1f}KB)"
    # 复制降级：体积不变，如实说明，不谎报收益
    return False, f"跳过优化（{skip_reason}）：原样复制 {original_size:.1f}KB"


def _copy_fallback(input_path, output_path, reason):
    """复制降级。已存在且不更大时保留原产物，避免用未压缩副本覆盖压缩结果。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() and _size_kb(output_path) <= _size_kb(input_path):
        return False, f"跳过优化（{reason}）：已有不更大的产物，保留 {output_path.name}"
    shutil.copy(input_path, output_path)
    return _report(input_path, output_path, False, reason)


def optimize_image(input_path, output_path, quality=85):
    """优化图片。pngquant→PNG，jpegoptim→JPG/JPEG，webp 直接复制（无压缩器）。"""
    ext = input_path.suffix.lower()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if ext == ".webp":
        # webp 已压缩，pngquant/jpegoptim 都不吃它；复制并在 ratio 上如实反映 0
        return _copy_fallback(input_path, output_path, "webp 无可用压缩器")

    tool = "pngquant" if ext == ".png" else "jpegoptim"
    try:
        if ext == ".png":
            cmd = [
                "pngquant",
                "--quality",
                f"0-{quality}",
                "--force",
                "--output",
                str(output_path),
                str(input_path),
            ]
        else:
            cmd = [
                "jpegoptim",
                "--max",
                str(quality),
                "--strip-all",
                "--quiet",
                "--dest",
                str(output_path.parent),
                str(input_path),
            ]
        # 不 check=True：压缩器退出码非 0 常常仍写出了更小的文件，
        # 但产物必须真实存在且不比原件大，否则才算失败。
        subprocess.run(cmd, check=False, capture_output=True)
        if not output_path.exists():
            return _copy_fallback(input_path, output_path, f"{tool} 未产出文件")
        if _size_kb(output_path) >= _size_kb(input_path):
            # 没省下体积就是没优化成，留副本但按失败记账
            shutil.copy(input_path, output_path)
            return _report(input_path, output_path, False, f"{tool} 未减小体积")
        return _report(input_path, output_path, True)
    except FileNotFoundError:
        return _copy_fallback(input_path, output_path, f"未安装 {tool}")
    except OSError as exc:
        return _copy_fallback(input_path, output_path, f"{tool} 调用失败({exc.__class__.__name__})")


def optimize_audio(input_path, output_path, bitrate="128k"):
    """优化音频。ffmpeg 可用则按目标码率重压；.wav 走 PCM 保留（无损源不重压）。"""
    ext = input_path.suffix.lower()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if ext in {".wav", ".aiff", ".aif"}:
        # 无损源：ffmpeg 写 PCM 只会更大/持平，直接复制
        return _copy_fallback(input_path, output_path, "无损 PCM 不重压")

    try:
        subprocess.run(
            ["ffmpeg", "-i", str(input_path), "-b:a", bitrate, "-y", str(output_path)],
            check=False,
            capture_output=True,
        )
    except FileNotFoundError:
        return _copy_fallback(input_path, output_path, "未安装 ffmpeg")

    if not output_path.exists():
        return _copy_fallback(input_path, output_path, "ffmpeg 未产出文件")
    if _size_kb(output_path) >= _size_kb(input_path):
        shutil.copy(input_path, output_path)
        return _report(input_path, output_path, False, "ffmpeg 未减小体积")
    return _report(input_path, output_path, True)


def optimize_assets(input_dir, output_dir, quality=85, audio_bitrate="128k"):
    """批量优化资源目录。返回 (成功优化数, 降级复制数, 非目标文件直传数)。"""
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)

    if not input_dir.is_dir():
        raise NotADirectoryError(f"输入目录不存在：{input_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)

    optimized = 0
    skipped = 0
    copied = 0

    for root, _dirs, files in os.walk(input_dir):
        rel_path = Path(root).relative_to(input_dir)
        output_root = output_dir / rel_path
        output_root.mkdir(parents=True, exist_ok=True)

        for name in files:
            input_path = Path(root) / name
            output_path = output_root / name
            ext = input_path.suffix.lower()

            try:
                if ext in IMAGE_EXTS:
                    print(f"[图片] {input_path.relative_to(input_dir)}")
                    ok, msg = optimize_image(input_path, output_path, quality)
                elif ext in AUDIO_EXTS:
                    print(f"[音频] {input_path.relative_to(input_dir)}")
                    ok, msg = optimize_audio(input_path, output_path, audio_bitrate)
                else:
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy(input_path, output_path)
                    skipped += 1
                    continue
            except OSError as exc:
                print(f"  !! 处理失败：{exc}", file=sys.stderr)
                skipped += 1
                continue

            print(f"   {msg}")
            if ok:
                optimized += 1
            else:
                # _copy_fallback / 未减小体积 都归为「降级复制」：文件在、但没省体积
                copied += 1

    print()
    print("=" * 56)
    print(f"处理结束：成功优化 {optimized} 个 / 降级复制 {copied} 个 / 非目标文件直传 {skipped} 个")
    if optimized == 0:
        print()
        print("⚠ 一个文件都没能优化——通常是压缩器没装，不是包体本来就没水分。")
        print("  装好压缩器后重跑：")
        print("    Windows : winget install jpegoptim  /  choco install pngquant ffmpeg")
        print("    Linux   : sudo apt install pngquant jpegoptim ffmpeg")
        print("    macOS   : brew install pngquant jpegoptim ffmpeg")
    print("=" * 56)
    return optimized, copied, skipped


def main():
    parser = argparse.ArgumentParser(description="批量优化 Ren'Py 项目资源文件")
    parser.add_argument("--input", required=True, help="输入资源目录")
    parser.add_argument("--output", required=True, help="优化后资源的输出目录")
    parser.add_argument("--quality", type=int, default=85, help="图片质量（1-100，默认 85）")
    parser.add_argument("--audio-bitrate", default="128k", help="音频目标码率，默认 128k")
    args = parser.parse_args()

    try:
        optimized, _copied, _skipped = optimize_assets(
            args.input, args.output, args.quality, args.audio_bitrate
        )
    except NotADirectoryError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"[ERROR] IO 失败：{exc}", file=sys.stderr)
        return 2

    # 全量降级时退出码非 0：调用方（AI/人）能区分「压了」和「只是复制了一遍」
    return 0 if optimized else 1


if __name__ == "__main__":
    sys.exit(main())