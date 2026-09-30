#!/usr/bin/env python3
import os
import argparse
from pathlib import Path
import subprocess
import shutil

def optimize_image(input_path, output_path, quality=85):
    """优化图片文件"""
    ext = input_path.suffix.lower()
    
    try:
        if ext in ['.png']:
            # 使用pngquant优化PNG
            subprocess.run([
                'pngquant', '--quality', f'0-{quality}', '--force',
                '--output', str(output_path), str(input_path)
            ], check=True, capture_output=True)
        elif ext in ['.jpg', '.jpeg']:
            # 使用jpegoptim优化JPG
            subprocess.run([
                'jpegoptim', '--max', str(quality), '--strip-all',
                '--dest', str(output_path.parent), str(input_path)
            ], check=True, capture_output=True)
        elif ext in ['.webp']:
            shutil.copy(input_path, output_path)
            
        original_size = os.path.getsize(input_path) / 1024
        optimized_size = os.path.getsize(output_path) / 1024
        ratio = (1 - optimized_size / original_size) * 100
        
        return True, f"优化成功：减小 {ratio:.1f}% ({original_size:.1f}KB → {optimized_size:.1f}KB)"
    except Exception as e:
        # 如果优化工具不存在，直接复制文件
        shutil.copy(input_path, output_path)
        return False, "跳过优化（未安装优化工具）：直接复制"

def optimize_audio(input_path, output_path, bitrate="128k"):
    """优化音频文件"""
    ext = input_path.suffix.lower()
    
    try:
        if ext in ['.mp3', '.ogg', '.wav']:
            # 使用ffmpeg压缩音频
            subprocess.run([
                'ffmpeg', '-i', str(input_path), '-b:a', bitrate,
                '-y', str(output_path)
            ], check=True, capture_output=True)
            
            original_size = os.path.getsize(input_path) / 1024
            optimized_size = os.path.getsize(output_path) / 1024
            ratio = (1 - optimized_size / original_size) * 100
            
            return True, f"优化成功：减小 {ratio:.1f}% ({original_size:.1f}KB → {optimized_size:.1f}KB)"
    except Exception as e:
        shutil.copy(input_path, output_path)
        return False, "跳过优化（未安装ffmpeg）：直接复制"

def optimize_assets(input_dir, output_dir, quality=85, audio_bitrate="128k"):
    """批量优化资源文件"""
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    
    os.makedirs(output_dir, exist_ok=True)
    
    image_exts = ['.png', '.jpg', '.jpeg', '.webp']
    audio_exts = ['.mp3', '.ogg', '.wav', '.m4a']
    
    total_saved = 0
    processed = 0
    skipped = 0
    
    # 遍历所有文件
    for root, _, files in os.walk(input_dir):
        rel_path = Path(root).relative_to(input_dir)
        output_root = output_dir / rel_path
        os.makedirs(output_root, exist_ok=True)
        
        for file in files:
            input_path = Path(root) / file
            output_path = output_root / file
            
            ext = input_path.suffix.lower()
            
            if ext in image_exts:
                print(f"🖼️  处理图片：{input_path.relative_to(input_dir)}")
                success, msg = optimize_image(input_path, output_path, quality)
                print(f"   {msg}")
                processed += 1
            elif ext in audio_exts:
                print(f"🎵 处理音频：{input_path.relative_to(input_dir)}")
                success, msg = optimize_audio(input_path, output_path, audio_bitrate)
                print(f"   {msg}")
                processed += 1
            else:
                # 其他文件直接复制
                shutil.copy(input_path, output_path)
                skipped += 1
    
    print(f"\n✅ 资源优化完成：")
    print(f"   处理文件：{processed} 个")
    print(f"   跳过文件：{skipped} 个")
    print(f"\n💡 提示：安装优化工具可获得更好的压缩效果：")
    print(f"   sudo apt install pngquant jpegoptim ffmpeg")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="批量优化Ren'Py项目资源文件")
    parser.add_argument("--input", required=True, help="输入资源目录")
    parser.add_argument("--output", required=True, help="输出优化后资源的目录")
    parser.add_argument("--quality", type=int, default=85, help="图片质量（1-100，默认85）")
    parser.add_argument("--audio-bitrate", default="128k", help="音频比特率，默认128k")
    
    args = parser.parse_args()
    optimize_assets(args.input, args.output, args.quality, args.audio_bitrate)
