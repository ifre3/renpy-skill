"""
Ren'"'"'Py Project Structure Scanner — lightweight regex-based scanner.

LIMITATIONS:
- This is a REGEX-BASED scanner, NOT a full Ren'"'"'Py parser.
- It WILL miss or misidentify constructs in complex scripts
  (e.g. if/menu blocks, show expression, python-generated labels).
- Use the SDK'"'"'s official lint command for authoritative analysis.

Scans for: labels, screens, images, transforms, characters, defines,
           styles, layeredimages, calls, jumps, orphan references.
"""

import os
import re


class Analyzer:
    """Ren'"'"'Py project structure scanner.

    Uses regex to identify common declarations across .rpy files.
    Results are best-effort — always verify with renpy lint.
    """

    # Built-in label names that are always valid targets
    BUILTIN_LABELS = {
        "start", "after_load", "splashscreen", "main_menu", "quit",
    }

    def __init__(self, project_dir: str):
        self.project_dir = os.path.abspath(project_dir)
        self.game_dir = os.path.join(self.project_dir, "game")
        self.results = {
            "labels": [],
            "screens": [],
            "images": [],
            "transforms": [],
            "styles": [],
            "layeredimages": [],
            "characters": [],
            "defines": [],
            "defaults": [],
            "init_blocks": [],
            "python_blocks": [],
            "calls": [],
            "jumps": [],
            "show_refs": [],
            "orphan_refs": [],
        }

    @property
    def rpy_files(self) -> list:
        """Collect all .rpy files under game/."""
        if not os.path.isdir(self.game_dir):
            return []
        files = []
        for root, _, names in os.walk(self.game_dir):
            for name in names:
                if name.endswith(".rpy"):
                    files.append(os.path.join(root, name))
        # 排除 cache/ __pycache__/ 等临时目录
        files = [f for f in files if not any(
            seg in f.replace("\\", "/").split("/")
            for seg in ("cache", "__pycache__", ".git")
        )]
        return sorted(files)

    def analyze(self) -> "Analyzer":
        """Run the full structure scan."""
        self.results = {k: [] for k in self.results}

        for fpath in self.rpy_files:
            rel = os.path.relpath(fpath, self.game_dir)
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            self._scan_labels(content, rel)
            self._scan_screens(content, rel)
            self._scan_images(content, rel)
            self._scan_transforms_styles(content, rel)
            self._scan_defines_defaults(content, rel)
            self._scan_init_python(content, rel)
            self._scan_calls_jumps(content, rel)
            self._scan_show_refs(content, rel)

        self._find_orphan_refs()
        return self

    def _scan_labels(self, content: str, rel: str):
        """Scan label definitions: label <name>[:] or label <name>(<params>):"""
        for m in re.finditer(
            r"^label\s+(\w[\w.]*)\s*(?:\([^)]*\))?\s*:", content, re.MULTILINE
        ):
            self.results["labels"].append((m.group(1), rel, m.start()))

    def _scan_screens(self, content: str, rel: str):
        """Scan screen definitions."""
        for m in re.finditer(r"^screen\s+(\w[\w.]*)\s*:", content, re.MULTILINE):
            self.results["screens"].append((m.group(1), rel, m.start()))

    def _scan_images(self, content: str, rel: str):
        """Scan image definitions.

        Matches:
          image <name> = <path>
          image <tag> <attribute>
          layeredimage <name>: (Ren'"'"'Py 8.5.3)
        """
        # image <name> = ...
        for m in re.finditer(r"^image\s+(\S+(?:\s+\S+)*?)\s*=", content, re.MULTILINE):
            self.results["images"].append((m.group(1).strip(), rel, m.start()))
        # image <tag> <attribute> (non-assignment form)
        for m in re.finditer(r"^image\s+(\w+)\s+(\w+)", content, re.MULTILINE):
            if "=" not in m.group(0):
                self.results["images"].append(
                    (f"{m.group(1)} {m.group(2)}", rel, m.start())
                )
        # layeredimage <name>:
        for m in re.finditer(
            r"^layeredimage\s+(\w[\w.]*)\s*:", content, re.MULTILINE
        ):
            self.results["layeredimages"].append((m.group(1), rel, m.start()))

    def _scan_transforms_styles(self, content: str, rel: str):
        """Scan transform and style definitions."""
        for m in re.finditer(
            r"^transform\s+(\w[\w.]*)\s*:", content, re.MULTILINE
        ):
            self.results["transforms"].append((m.group(1), rel, m.start()))
        for m in re.finditer(r"^style\s+(\w[\w.]*)\s*:", content, re.MULTILINE):
            self.results["styles"].append((m.group(1), rel, m.start()))

    def _scan_defines_defaults(self, content: str, rel: str):
        """Scan define and default statements."""
        # define <var> = Character(...)  — character registration
        for m in re.finditer(r"define\s+(\w+)\s*=\s*Character\s*\(", content):
            self.results["characters"].append((m.group(1), rel, m.start()))
        # define <var> = ... (non-Character)
        for m in re.finditer(r"define\s+(\w+(?:\.\w+)*)\s*=", content):
            if "Character(" not in m.group(0):
                self.results["defines"].append((m.group(1), rel, m.start()))
        # default <var> = ...
        for m in re.finditer(r"default\s+(\w[\w.]*)\s*=", content):
            self.results["defaults"].append((m.group(1), rel, m.start()))

    def _scan_init_python(self, content: str, rel: str):
        """Scan init blocks and python blocks."""
        for m in re.finditer(
            r"^init\s+(-?\d+)\s*(hide|python)?", content, re.MULTILINE
        ):
            prio = m.group(1)
            suffix = m.group(2) or ""
            self.results["init_blocks"].append(
                (f"init {prio} {suffix}".strip(), rel, m.start())
            )
        for m in re.finditer(r"^python\s+(?:early|hide)?\s*:", content, re.MULTILINE):
            self.results["python_blocks"].append(
                (m.group(0).strip(), rel, m.start())
            )

    def _scan_calls_jumps(self, content: str, rel: str):
        """Scan call and jump references."""
        for m in re.finditer(r"\bcall\s+(\w[\w.]*)", content):
            self.results["calls"].append((m.group(1), rel, m.start() + 1))
        for m in re.finditer(r"\bjump\s+(\w[\w.]*)", content):
            self.results["jumps"].append((m.group(1), rel, m.start() + 1))

    def _scan_show_refs(self, content: str, rel: str):
        """Scan show/scene/hide image references."""
        for m in re.finditer(
            r"\b(?:show|scene|hide)\s+(\w[\w.]*)", content
        ):
            self.results["show_refs"].append((m.group(1), rel, m.start() + 1))

    def _find_orphan_refs(self):
        """Find call/jump targets that don'"'"'t match any defined label."""
        defined_labels = {name for name, _, _ in self.results["labels"]}
        all_refs = self.results["calls"] + self.results["jumps"]

        for name, frel, pos in all_refs:
            if name in self.BUILTIN_LABELS:
                continue
            # Check exact match or sub-label (e.g. mylabel.sub)
            defined = any(
                name == dl or name.startswith(dl + ".") for dl in defined_labels
            )
            if not defined:
                self.results["orphan_refs"].append((name, frel, pos))

    def summary(self) -> dict:
        """Return a count summary."""
        return {k: len(v) for k, v in self.results.items()}

    def report(self, verbose: bool = False) -> str:
        """Generate a human-readable analysis report."""
        lines = []
        lines.append(f"[Ren'Py Project Scan] {self.project_dir}")
        lines.append("=" * 50)
        lines.append("")

        summary = self.summary()
        for k, v in summary.items():
            if v > 0 and k != "orphan_refs":
                lines.append(f"  {k}: {v}")

        if self.results["orphan_refs"]:
            lines.append(f"\n  [!] orphan_refs: {len(self.results['orphan_refs'])}")

        if verbose:
            lines.append("")
            lines.append("--- Detail ---")
            for category in (
                "labels",
                "screens",
                "images",
                "layeredimages",
                "transforms",
                "styles",
                "characters",
                "defines",
                "defaults",
                "init_blocks",
            ):
                items = self.results.get(category, [])
                if items:
                    lines.append(f"\n{category}:")
                    for name, frel, _ in sorted(items):
                        lines.append(f"  - {name}  ({frel})")

            if self.results["orphan_refs"]:
                lines.append("\n[!] Orphan references (call/jump to undefined label):")
                for name, frel, _ in self.results["orphan_refs"]:
                    lines.append(f"  - {name}  ({frel})")

        if not any(v > 0 for v in summary.values()):
            lines.append("[!] No .rpy files or declarations found.")

        lines.append("")
        lines.append("=" * 50)
        return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Ren'Py project structure scanner (regex-based)"
    )
    parser.add_argument("project_dir", help="Project directory")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show detailed information"
    )

    args = parser.parse_args()
    analyzer = Analyzer(args.project_dir)
    analyzer.analyze()
    print(analyzer.report(verbose=args.verbose))


if __name__ == "__main__":
    main()
