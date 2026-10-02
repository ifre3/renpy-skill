"""
remove_translated.py - 移除文件名中所有叠加的 _translated 后缀

用法:
    python remove_translated.py <目录或文件路径>            (预览)
    python remove_translated.py <目录或文件路径> --execute   (实际执行)

示例:
    python remove_translated.py "D:/Games/MyGame"
    python remove_translated.py "D:/Games/MyGame/cheats_translated_translated_translated.rpy" --execute
"""
import os
import sys


def remove_translated(name: str) -> str:
    """移除 stem 中所有的 _translated"""
    return name.replace("_translated", "")


def process_file(filepath: str, dry_run: bool = True) -> bool:
    """处理单个文件，返回是否发生了重命名"""
    dirpath = os.path.dirname(filepath)
    filename = os.path.basename(filepath)
    stem, ext = os.path.splitext(filename)

    new_stem = remove_translated(stem)
    if new_stem == stem:
        return False

    new_path = os.path.join(dirpath, new_stem + ext)
    prefix = "[DRY RUN]" if dry_run else "[RENAME]"
    print(f"{prefix}  {filepath}")
    print(f"       ->  {new_path}")

    if not dry_run:
        if os.path.exists(new_path):
            print(f"       !!!  目标已存在，跳过")
            return False
        os.rename(filepath, new_path)

    return True


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    target = sys.argv[1]
    execute = "--execute" in sys.argv or "-x" in sys.argv

    if not os.path.exists(target):
        print(f"错误: 路径不存在 - {target}")
        sys.exit(1)

    count = 0

    if os.path.isfile(target):
        if process_file(target, dry_run=not execute):
            count = 1
    else:
        for root, _, files in os.walk(target):
            for f in files:
                filepath = os.path.join(root, f)
                if process_file(filepath, dry_run=not execute):
                    count += 1

    print()
    if count == 0:
        print("没有找到需要重命名的文件。")
    elif not execute:
        print(f"将重命名 {count} 个文件。加上 --execute 参数以实际执行。")
    else:
        print(f"已重命名 {count} 个文件。")


if __name__ == "__main__":
    main()
