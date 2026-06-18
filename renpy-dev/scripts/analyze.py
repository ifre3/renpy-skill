"""
Ren'Py 项目结构分析器 — 扫描 labels / screens / images / 悬空引用

用法：
    analyzer = Analyzer("D:/projects/my_game")
    analyzer.analyze()
    print(analyzer.report())
"""

import os
import re


class Analyzer:
    """Ren'Py 项目结构分析器。"""

    def __init__(self, project_dir: str):
        self.project_dir = os.path.abspath(project_dir)
        self.game_dir = os.path.join(self.project_dir, "game")
        self.results = {
            "labels": [],
            "screens": [],
            "images": [],
            "transforms": [],
            "characters": [],
            "defines": [],
            "calls": [],
            "jumps": [],
            "orphan_refs": [],
        }

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

    def analyze(self) -> "Analyzer":
        """执行全面分析。"""
        self.results = {k: [] for k in self.results}

        for fpath in self.rpy_files:
            rel = os.path.relpath(fpath, self.game_dir)
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            # label 定义: label <name>:
            for m in re.finditer(r'^label\s+(\w[\w.]*)\s*(?=:|$)', content, re.MULTILINE):
                self.results["labels"].append((m.group(1), rel, m.start()))

            # screen 定义: screen <name>:
            for m in re.finditer(r'^screen\s+(\w[\w.]*)\s*:', content, re.MULTILINE):
                self.results["screens"].append((m.group(1), rel, m.start()))

            # image 定义: image <name> = 或 image <tag> <attribute>
            for m in re.finditer(r'^image\s+(\S+(?:\s+\S+)*?)\s*=', content, re.MULTILINE):
                self.results["images"].append((m.group(1).strip(), rel, m.start()))
            for m in re.finditer(r'^image\s+(\w+)\s+(\w+)', content, re.MULTILINE):
                if "=" not in m.group(0):
                    self.results["images"].append((f"{m.group(1)} {m.group(2)}", rel, m.start()))

            # transform 定义: transform <name>:
            for m in re.finditer(r'^transform\s+(\w[\w.]*)\s*:', content, re.MULTILINE):
                self.results["transforms"].append((m.group(1), rel, m.start()))

            # character 定义: define <var> = Character(...)
            for m in re.finditer(r'define\s+(\w+)\s*=\s*Character\(', content):
                self.results["characters"].append((m.group(1), rel, m.start()))

            # define 语句（不含 Character）
            for m in re.finditer(r'define\s+(\w+(?:\.\w+)*)\s*=', content):
                if "Character(" not in m.group(0):
                    self.results["defines"].append((m.group(1), rel, m.start()))

            # call 目标
            for m in re.finditer(r'call\s+(\w[\w.]*)', content):
                self.results["calls"].append((m.group(1), rel, m.start() + 1))

            # jump 目标
            for m in re.finditer(r'jump\s+(\w[\w.]*)', content):
                self.results["jumps"].append((m.group(1), rel, m.start() + 1))

        # 检查悬空引用
        self._find_orphan_refs()

        return self

    @property
    def rpy_files(self) -> list:
        """获取所有 .rpy 文件。"""
        return self._rpy_files()

    def _find_orphan_refs(self):
        """查找悬空引用（call/jump 到不存在的 label）。"""
        defined_labels = {name for name, _, _ in self.results["labels"]}
        for name, frel, pos in self.results["calls"] + self.results["jumps"]:
            # 只检查本项目的 label（排除 renpy 内置如 start）
            is_internal = True
            for dl in defined_labels:
                if name == dl or name.startswith(dl + "."):
                    is_internal = False
                    break
            if is_internal:
                # 再查一次——可能 label 确实不存在
                if name not in defined_labels:
                    # 跳过常见内置 label
                    if name not in ("start", "after_load", "splashscreen"):
                        self.results["orphan_refs"].append((name, frel, pos))

    def summary(self) -> dict:
        """返回统计摘要。"""
        return {k: len(v) for k, v in self.results.items()}

    def report(self, verbose: bool = False) -> str:
        """生成可读分析报告。"""
        lines = []
        lines.append(f"📊 Ren'Py 项目分析: {self.project_dir}")
        lines.append("=" * 50)
        lines.append("")

        summary = self.summary()
        for k, v in summary.items():
            if v > 0:
                lines.append(f"  {k}: {v}")

        if verbose:
            lines.append("")
            lines.append("─" * 40)
            for category in ("labels", "screens", "characters", "transforms"):
                items = self.results.get(category, [])
                if items:
                    lines.append(f"\n{category}:")
                    for name, frel, _ in sorted(items):
                        lines.append(f"  • {name}  ({frel})")

            if self.results["orphan_refs"]:
                lines.append("\n⚠️  悬空引用:")
                for name, frel, _ in self.results["orphan_refs"]:
                    lines.append(f"  • {name}  ({frel}) — 目标 label 不存在")

        if not any(v > 0 for v in summary.values()):
            lines.append("⚠️  未找到任何 .rpy 文件或结构定义。")

        lines.append("")
        lines.append("=" * 50)
        return "\n".join(lines)


# ── CLI ─────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Ren'Py 项目结构分析器")
    parser.add_argument("project_dir", help="项目目录")
    parser.add_argument("--verbose", "-v", action="store_true", help="显示详细信息")

    args = parser.parse_args()
    analyzer = Analyzer(args.project_dir)
    analyzer.analyze()
    print(analyzer.report(verbose=args.verbose))


if __name__ == "__main__":
    main()