"""
Ren'Py .rpy ↔ JSON 双向转换 — 版本控制 / 机器翻译 / 迁移
支持 Unicode（中文/日文/韩文）和复杂项目结构

用法：
    # .rpy → JSON
    exporter = Export("D:/projects/my_game")
    exporter.to_json("backup.json")

    # JSON → .rpy
    exporter.from_json("backup.json", output_dir="D:/projects/restored/game")

注意：本工具面向对话文本提取/翻译工作流，不适合含复杂 python 块的项目完整迁移。"""

import os
import json
import re
import glob


class ExportError(Exception):
    """导出/导入过程中的异常。"""
    pass


class Export:
    """Ren'Py .rpy ↔ JSON 双向转换。"""

    # 需要提取的 Ren'Py 语句类型（支持 Unicode）
    # 改进的正则表达式，支持中文/日文/韩文字符
    LINE_PATTERNS = {
        "say": re.compile(
            # 支持 Unicode 字符名：匹配任何非空白、非引号、非 # 的字符序列
            r'^\s*([^\s"#][^\s"#]*?)\s+"(?P<what>(?:[^"\\]|\\.)*)"\s*(?:#.*)?$'
        ),
        "narrator": re.compile(
            # 旁白：行首直接是引号
            r'^\s*"(?P<what>(?:[^"\\]|\\.)*)"\s*(?:#.*)?$'
        ),
        "comment": re.compile(r'^\s*#\s*(?P<text>.*)$'),
        "menu": re.compile(
            # menu 选项：包含引号的选项
            r'^\s*"((?:[^"\\]|\\.)*)"\s*:$'
        ),
    }

    def __init__(self, project_dir: str, game_dir: str = None):
        """
        初始化导出器。

        Args:
            project_dir: 项目根目录
            game_dir: game/ 目录路径（可选，自动检测）
        """
        self.project_dir = os.path.abspath(project_dir)
        self.game_dir = game_dir or self._detect_game_dir()
        self.errors = []  # 存储处理过程中的错误

    def _detect_game_dir(self) -> str:
        """自动检测 game/ 目录位置。"""
        candidates = [
            os.path.join(self.project_dir, "game"),
            os.path.join(self.project_dir, "mod_assets", "game"),
            os.path.join(self.project_dir, "submods", "game"),
        ]

        for path in candidates:
            if os.path.isdir(path):
                rpy_files = glob.glob(os.path.join(path, "**/*.rpy"), recursive=True)
                if rpy_files:
                    return path

        # 搜索项目目录
        for root, dirs, files in os.walk(self.project_dir):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('cache', '__pycache__')]
            if any(f.endswith('.rpy') for f in files):
                return root

        default = os.path.join(self.project_dir, "game")
        self.errors.append(f"⚠️  未找到 game/ 目录，使用默认位置：{default}")
        return default

    # ── 提取为 JSON ─────────────────────────────────────

    def to_json(self, output_path: str, include_all: bool = False) -> dict:
        """
        将项目中的 .rpy 对话/字符串提取为 JSON。
        include_all=True 时包含所有语句，否则只包含 say / narrator。

        返回解析后的 dict，同时写入 output_path。
        """
        data = {
            "meta": {
                "renpy_version": "8.5.3",
                "project": os.path.basename(self.project_dir),
                "exported_from": "rpy",
                "encoding": "utf-8",
                "supports_unicode": True,
            },
            "files": {},
            "errors": [],
        }

        rpy_files = self._rpy_files()
        if not rpy_files:
            data["errors"].append("未找到任何 .rpy 文件")
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return data

        for fpath in rpy_files:
            rel = os.path.relpath(fpath, self.game_dir)
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()

                entries = self._parse_file(content, include_all=include_all)
                if entries:
                    data["files"][rel] = entries

            except Exception as e:
                error_msg = f"读取文件失败：{rel} ({e})"
                data["errors"].append(error_msg)
                self.errors.append(error_msg)

        # 保存错误
        data["errors"].extend(self.errors)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return data

    def _join_continuation(self, lines: list, start: int) -> tuple:
        """
        将多行对话的续行合并为单行。
        Ren'Py 中续行以空白开头（非 python/menu/screen 块内）。
        返回 (joined_line, next_index)。
        """
        joined = [lines[start]]
        i = start + 1
        while i < len(lines):
            nxt = lines[i]
            if nxt and (nxt[0] in (' ', '\t')):
                # 空行或纯空白行结束续行
                if not nxt.strip():
                    break
                joined.append(nxt)
                i += 1
            else:
                # 检查是否是纯对话续行（不以关键字开头）
                s = nxt.strip()
                if s and not s[0].isalpha():
                    joined.append(nxt)
                    i += 1
                else:
                    break
        return '\n'.join(joined), i

    def _is_python_block(self, line: str) -> bool:
        """检测 python / init python 块开头（需要跳过内部内容）。"""
        s = line.strip()
        return s in ("python:", "python hide:") or s.startswith("init python")

    def _parse_file(self, content: str, include_all: bool = False) -> list:
        """解析一个 .rpy 文件内容为结构化条目。"""
        entries = []
        lines = content.split("\n")
        in_python = False
        python_depth = 0

        i = 0
        while i < len(lines):
            line = lines[i]
            lineno = i + 1
            stripped = line.strip()

            # 跳过空行
            if not stripped:
                i += 1
                continue

            # 跳过 python 块内的代码（含 init python）
            if self._is_python_block(stripped):
                in_python = True
                python_depth = len(line) - len(line.lstrip())
                i += 1
                continue
            if in_python:
                cur_depth = len(line) - len(line.lstrip()) if stripped else 0
                if cur_depth <= python_depth and stripped:
                    in_python = False
                else:
                    i += 1
                    continue

            # 尝试合并多行对话
            joined_line = line
            joined_lineno = lineno
            # 检测：有开头引号但没有闭合引号（排除已转义的引号）
            unescaped_quotes = [m.start() for m in re.finditer(r'(?<!\\)"', stripped)]
            if len(unescaped_quotes) % 2 == 1 and len(unescaped_quotes) > 0:
                joined_line, next_i = self._join_continuation(lines, i)
                joined_lineno = lineno
                # 用合并后的行重新匹配（去掉换行符）
                stripped = joined_line.replace('\n', ' ').strip()
                i = next_i
            else:
                i += 1

            entry = {"line": joined_lineno, "raw": stripped}

            # 注释
            cm = self.LINE_PATTERNS["comment"].match(stripped)
            if cm:
                entry["type"] = "comment"
                entry["text"] = cm.group("text")
                entries.append(entry)
                continue

            # 叙述 (narrator)
            nm = self.LINE_PATTERNS["narrator"].match(stripped)
            if nm and not stripped.startswith("define") and not stripped.startswith("default"):
                entry["type"] = "narrator"
                entry["text"] = nm.group("what")
                entries.append(entry)
                continue

            # 对话 (say "who" "what")
            # 使用改进的正则，支持 Unicode 字符名
            sm = self.LINE_PATTERNS["say"].match(stripped)
            if sm:
                # 提取字符名（第一个引号之前的部分）
                who_match = re.match(r'^\s*([^\s"#][^\s"#]*)', stripped)
                if who_match:
                    who = who_match.group(1)
                    # 提取对话文本（第一个引号之内的内容）
                    text_match = re.search(r'"(?P<text>(?:[^"\\]|\\.)*)"', stripped)
                    if text_match:
                        entry["type"] = "say"
                        entry["who"] = who
                        entry["text"] = text_match.group("text")
                        entries.append(entry)
                        continue

            # 其他语句（可选）
            if include_all:
                entry["type"] = "other"
                entries.append(entry)

        return entries

    # ── 从 JSON 恢复 ────────────────────────────────────

    def from_json(self, json_path: str, output_dir: str = None) -> int:
        """
        从 JSON 文件恢复 .rpy 文件。
        只恢复 say/narrator 行（保留原始结构）。
        返回处理文件数。
        """
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        output_base = output_dir or self.game_dir
        count = 0

        for rel, entries in data.get("files", {}).items():
            try:
                out_path = os.path.join(output_base, rel)
                os.makedirs(os.path.dirname(out_path), exist_ok=True)

                original_path = os.path.join(self.game_dir, rel)
                if os.path.isfile(original_path):
                    with open(original_path, "r", encoding="utf-8") as fo:
                        orig_lines = fo.readlines()
                    self._merge_into_original(orig_lines, entries, out_path)
                else:
                    self._rebuild_from_entries(entries, out_path)
            except Exception as e:
                self.errors.append(f"{rel}: {e}")
                continue
            count += 1

        return count

    def _merge_into_original(self, orig_lines: list, entries: list, out_path: str):
        """将 JSON 中的翻译合并到原始文件。"""
        entry_map = {}
        for e in entries:
            if e["type"] in ("say", "narrator"):
                entry_map[e["line"]] = e

        new_lines = []
        for i, line in enumerate(orig_lines, 1):
            stripped = line.rstrip("\n")
            if i in entry_map:
                e = entry_map[i]
                if e["type"] == "say":
                    # 保留原始缩进和字符名
                    indent = line[:len(line) - len(line.lstrip())]
                    who = e.get("who", "")
                    text = e.get("text", "")
                    # 转义引号
                    text_escaped = text.replace('"', '\\"')
                    new_lines.append(f'{indent}{who} "{text_escaped}"\n')
                elif e["type"] == "narrator":
                    indent = line[:len(line) - len(line.lstrip())]
                    text = e.get("text", "")
                    text_escaped = text.replace('"', '\\"')
                    new_lines.append(f'{indent}"{text_escaped}"\n')
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)

        with open(out_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

    def _rebuild_from_entries(self, entries: list, out_path: str):
        """从结构化条目重建 .rpy 文件。"""
        lines = []
        for e in entries:
            t = e.get("type", "other")
            if t == "say":
                who = e.get("who", "")
                text = e.get("text", "").replace('"', '\\"')
                lines.append(f'{who} "{text}"')
            elif t == "narrator":
                text = e.get("text", "").replace('"', '\\"')
                lines.append(f'"{text}"')
            elif t == "comment":
                lines.append(f"# {e.get('text', '')}")
            elif t == "other":
                lines.append(e.get("raw", ""))
            else:
                lines.append(e.get("raw", ""))

        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    def _rpy_files(self) -> list:
        """收集所有 .rpy 文件。"""
        files = []
        if not os.path.isdir(self.game_dir):
            self.errors.append(f"❌ game/ 目录不存在：{self.game_dir}")
            return files

        for root, _, names in os.walk(self.game_dir):
            if '__pycache__' in root:
                continue
            for name in names:
                if name.endswith(".rpy"):
                    files.append(os.path.join(root, name))

        return sorted(files)


# ── CLI ─────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Ren'Py .rpy ↔ JSON 转换（支持 Unicode）")
    parser.add_argument("project_dir", help="项目目录")
    parser.add_argument("action", choices=["to-json", "from-json"], help="操作方向")
    parser.add_argument("file", help="JSON 文件路径")
    parser.add_argument("--game-dir", help="game/ 目录路径（可选，自动检测）")
    parser.add_argument("--output-dir", default=None, help="from-json 时的输出目录")

    args = parser.parse_args()
    exporter = Export(args.project_dir, game_dir=args.game_dir)

    if args.action == "to-json":
        data = exporter.to_json(args.file)
        print(f"✅ 已导出: {args.file}")
        print(f"   文件数: {len(data.get('files', {}))}")
        if data.get("errors"):
            print(f"⚠️  处理过程中的错误：")
            for err in data["errors"]:
                print(f"   {err}")
    else:
        count = exporter.from_json(args.file, output_dir=args.output_dir)
        print(f"✅ 已恢复: {count} 个文件")
        if exporter.errors:
            print(f"⚠️  处理过程中的错误：")
            for err in exporter.errors:
                print(f"   {err}")


if __name__ == "__main__":
    main()
