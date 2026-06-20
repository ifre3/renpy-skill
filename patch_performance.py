#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ren'Py Performance Mode Patcher
================================
Adds a 3-tier performance switcher (Original / Balanced / Performance)
to any Ren'Py project's Settings > Display screen.

Uses verified runtime config variables:
  - swdraw.py:791  -> renpy.config.framerate (per-frame)
  - execution.py:928 -> renpy.config.predict_statements (per-prediction)
  - screen.py:276  -> renpy.config.predict_screens (per-screen-prediction)

Usage:
    python patch_performance.py [project_dir]

    Without arguments, uses the current directory's game/ subdirectory.
    Automatically backs up original files -> .rpy.bak.
    Clears *.rpyc caches after patching.

Compatibility: Ren'Py 8.x (Windows / Linux / macOS)
"""

import os
import sys
import shutil
from pathlib import Path

VERBOSE = True


PERFORMANCE_DEFAULT = (
    "\ndefault persistent.performance_mode = 0"
    "  # 0=Original, 1=Balanced, 2=Performance\n"
)

PERFORMANCE_FUNC = (
    "\n  def apply_performance_mode():\n"
    "    mode = persistent.performance_mode\n"
    "    if mode == 2:\n"
    "      renpy.config.framerate = 30\n"
    "      renpy.config.predict_statements = 0\n"
    "      renpy.config.predict_screens = False\n"
    "    elif mode == 1:\n"
    "      renpy.config.framerate = 60\n"
    "      renpy.config.predict_statements = 16\n"
    "      renpy.config.predict_screens = True\n"
    "    else:\n"
    "      renpy.config.framerate = 100\n"
    "      renpy.config.predict_statements = 32\n"
    "      renpy.config.predict_screens = True\n"
)


def log(msg):
    if VERBOSE:
        print("  " + msg)


def success(msg):
    print("  " + msg)


def warn(msg):
    print("  " + msg)


def die(msg, code=1):
    print("  " + msg)
    sys.exit(code)


def patch_globals(globals_rpy):
    with open(str(globals_rpy), "r", encoding="utf-8") as f:
        g = f.read()

    if "persistent.performance_mode" not in g:
        last_default = g.rfind("\ndefault ")
        if last_default == -1:
            die("Cannot find any default statement in globals.rpy")
        insert_at = g.index("\n", last_default + 1)
        g = g[:insert_at] + PERFORMANCE_DEFAULT + g[insert_at:]
        log("persistent.performance_mode default added")
    else:
        log("persistent.performance_mode already exists, skipping")

    if "def apply_performance_mode" not in g:
        g = g.rstrip() + "\n\n" + PERFORMANCE_FUNC + "\n"
        log("apply_performance_mode() function added")
    else:
        log("apply_performance_mode() already exists, skipping")

    if "def game_init():" in g:
        after_game_init = g.split("def game_init():", 1)[1]
        next_def = after_game_init.find("\ndef ")
        game_init_body = after_game_init[:next_def] if next_def > 0 else after_game_init

        if "apply_performance_mode()" not in game_init_body:
            lines = g.split("\n")
            new_lines = []
            patched = False
            for i, line in enumerate(lines):
                new_lines.append(line)
                if line.strip() == "def game_init():" and not patched:
                    j = i + 1
                    while j < len(lines) and lines[j].strip() == "":
                        j += 1
                    if j < len(lines):
                        body_indent = len(lines[j]) - len(lines[j].lstrip())
                        new_lines.append(" " * body_indent + "apply_performance_mode()")
                        log("Call added in game_init()")
                        patched = True
            g = "\n".join(new_lines)
    else:
        warn("game_init() not found - call must be added manually")

    with open(str(globals_rpy), "w", encoding="utf-8", newline="\n") as f:
        f.write(g)
    success("globals.rpy patched")


def patch_screens(screens_rpy):
    with open(str(screens_rpy), "r", encoding="utf-8") as f:
        s = f.read()

    if 'settings_item("Performance")' in s:
        log("Performance UI already exists, skipping")
        return

    lines = s.split("\n")
    marker_idx = -1
    for i, line in enumerate(lines):
        if line.strip() == 'if tab == "gameplay":':
            marker_idx = i
            break

    if marker_idx == -1:
        warn("Cannot find gameplay tab marker - not injected")
        return

    perf_ui = [
        "",
        '                    use settings_item("Performance"):',
        '                            style_prefix "radio"',
        '                            textbutton _("Original") action [SetVariable("persistent.performance_mode", 0), Function(apply_performance_mode)]',
        '                            textbutton _("Balanced") action [SetVariable("persistent.performance_mode", 1), Function(apply_performance_mode)]',
        '                            textbutton _("Performance") action [SetVariable("persistent.performance_mode", 2), Function(apply_performance_mode)]',
    ]

    for idx, val in enumerate(perf_ui):
        lines.insert(marker_idx + idx, val)

    s = "\n".join(lines)

    with open(str(screens_rpy), "w", encoding="utf-8", newline="\n") as f:
        f.write(s)
    success("screens.rpy patched")


def clear_caches(game_dir):
    count = 0
    for f in game_dir.rglob("*.rpyc"):
        f.unlink()
        count += 1
    log("Cleared %d .rpyc cache files" % count)


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    project_dir = Path(target)
    game_dir = project_dir / "game" if project_dir.name != "game" else project_dir

    if not game_dir.exists():
        die("game/ directory not found: %s" % game_dir)

    globals_rpy = game_dir / "globals.rpy"
    screens_rpy = game_dir / "screens.rpy"

    print()
    print("=" * 60)
    print("  Ren'Py Performance Mode Patcher")
    print("  Target: %s" % game_dir)
    print("=" * 60)
    print()

    if not globals_rpy.exists():
        die("globals.rpy not found at %s" % globals_rpy)
    if not screens_rpy.exists():
        warn("screens.rpy not found - UI injection skipped")

    for fpath in [globals_rpy, screens_rpy]:
        if fpath.exists():
            bak = fpath.with_suffix(fpath.suffix + ".bak")
            if not bak.exists():
                shutil.copy2(str(fpath), str(bak))
                log("Backup: %s" % bak.name)

    patch_globals(globals_rpy)
    if screens_rpy.exists():
        patch_screens(screens_rpy)

    clear_caches(game_dir)

    print()
    print("=" * 60)
    print("  Done!")
    print("  Restart the game for changes to take effect.")
    print("  Settings > Display > Performance to switch modes.")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()
