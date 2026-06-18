"""
Ren'Py .rpy ↔ JSON 双向转换 — 版本控制 / 机器翻译 / 迁移

用法：
    # .rpy → JSON
    exporter = Export("D:/projects/my_game")
    exporter.to_json("backup.json")

    # JSON → .rpy
    exporter.from_json("backup.json", output_dir="D:/projects/restored/game")
"""

import os
import json
import re


class ExportError(Exception):
    """导出/导入过程中的异常。"""
    pass


class Export:
    """Ren'Py .rpy ↔ JSON 双向转换。"""

    # 需要提取的 Ren'Py 语句类型
    LINE_PATTERNS = {
        "say": re.compile(r'^\s*(?P<who>\w+)?\s*"(?P<what>[^"]*)"\s*$'),
        "narrator": re.compile(r'^\s*"(?P<what>[^"]*)"\s*$'),
        "comment": re.compile(r'^\s*#\s*(?P<text>.*)$'),
    }

    def __init__(self, project_dir: str):
        self.project_dir = os.path.abspath(project_dir)
        self.game_dir = os.path.join(self.project_dir, "game")

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
            },
            "files": {},
        }

        for fpath in self._rpy_files():
            rel = os.path.relpath(fpath, self.game_dir)
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            entries = self._parse_file(content, include_all=include_all)
            if entries:
                data["files"][rel] = entries

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return data

    def _parse_file(self, content: str, include_all: bool = False) -> list:
        """解析一个 .rpy 文件内容为结构化条目。"""
        entries = []
        lines = content.split("\n")
        in_python_block = False

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # 跳过空行
            if not stripped:
                continue

            # 跳过 python 块内内容
            if stripped.startswith("python") and stripped.endswith(":"):
                in_python_block = True
                continue
            if in_python_block:
                if stripped and not stripped.startswith((" ", "\t")):
                    in_python_block = False
                else:
                    continue

            entry = {"line": i, "raw": stripped}

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
            sm = self.LINE_PATTERNS["say"].match(stripped)
            if sm and sm.group("who") and not sm.group("who").startswith("$"):
                entry["type"] = "say"
                entry["who"] = sm.group("who")
                entry["text"] = sm.group("what")
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
            out_path = os.path.join(output_base, rel)
            os.makedirs(os.path.dirname(out_path), exist_ok=True)

            # 尝试读取原始 .rpy 保留框架
            original_path = os.path.join(self.game_dir, rel)
            if os.path.isfile(original_path):
                with open(original_path, "r", encoding="utf-8") as fo:
                    orig_lines = fo.readlines()
                # 替换对话行
                self._merge_into_original(orig_lines, entries, out_path)
            else:
                # 纯重建
                self._rebuild_from_entries(entries, out_path)
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
                    # 保留原始缩进
                    indent = line[:len(line) - len(line.lstrip())]
                    new_lines.append(f'{indent}{e["who"]} "{e["text"]}"\n')
                elif e["type"] == "narrator":
                    indent = line[:len(line) - len(line.lstrip())]
                    new_lines.append(f'{indent}"{e["text"]}"\n')
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
                lines.append(f'{e["who"]} "{e["text"]}"')
            elif t == "narrator":
                lines.append(f'"{e["text"]}"')
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
            return files
        for root, _, names in os.walk(self.game_dir):
            for name in names:
                if name.endswith(".rpy"):
                    files.append(os.path.join(root, name))
        return sorted(files)


# ── CLI ─────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Ren'Py .rpy ↔ JSON 转换")
    parser.add_argument("project_dir", help="项目目录")
    parser.add_argument("action", choices=["to-json", "from-json"], help="操作方向")
    parser.add_argument("file", help="JSON 文件路径")
    parser.add_argument("--output-dir", default=None, help="from-json 时的输出目录")

    args = parser.parse_args()
    exporter = Export(args.project_dir)

    if args.action == "to-json":
        data = exporter.to_json(args.file)
        print(f"✅ 已导出: {args.file}")
        print(f"   文件数: {len(data.get('files', {}))}")
    else:
        count = exporter.from_json(args.file, output_dir=args.output_dir)
        print(f"✅ 已恢复: {count} 个文件")


if __name__ == "__main__":
    main()