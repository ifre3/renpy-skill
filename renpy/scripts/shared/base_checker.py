# -*- coding: utf-8 -*-
"""检查器契约层：把"有哪些检查器、各自吃什么、只读吗"从门面手写表搬进脚本自己。

## 为什么加这层（2026-10-06）

`renpy-tools-cli.py` 过去用两张手写表描述工具面：`TOOL_SCRIPTS`（33 项
子命令名 → 文件路径）与 `TOOL_DESC`（33 项描述），外加两个硬编码集合
`NEEDS_TL_DIR` / `TL_DIR_TOOLS` 表达"谁吃 tl 目录、谁的路径参数要换成 tl_dir"。
表和集合都会漂，而且漂了不报错：

- `check_i18n.py` 漏声明 `-l/--language`，而 `all` 把 `-l` 原样转发给每个检查器
  → argparse rc=2 被门面归一成失败项 → `all` 在**任何**项目上恒定返回 1，
  与 SKILL.md「退出码 1 = 查出了问题」的口径冲突（假阳性）。

契约层解决的是"分发靠人记"这件事：新增检查器只要在脚本里声明 `CHECKER`，
名字、描述、吃项目还是吃 tl 目录就不再需要去门面改两处表。

## 借鉴

分层与"扩展点用基类声明而非文档保证"的做法来自 AiNiee 的
`ModuleFolders/Domain/FileReader/BaseReader.py`（`BaseSourceReader` 抽象基类 +
`pre_/on_/post_` 生命周期钩子 + `can_read`/`support_file` 能力查询）。
只借鉴"契约前置"这一条，不搬它的目录结构——本skill 的消费方是 agent，
导航面是 SKILL.md 的两张表，不是目录树。

## 契约三条

1. `name` / `summary`：门面子命令名与一句描述。不许空——空即门面缺项。
2. `takes`：`PROJECT`（吃 `<项目>/game`）或 `TL_DIR`（吃 `game/tl/<lang>`）。
   这条替代 `NEEDS_TL_DIR` / `TL_DIR_TOOLS` 两个硬编码集合。
3. `read_only`：检查器契约，恒为 True。检查器不得写任何文件——需要写的是
   `fix_*` / `*_apply` 那一类，不该混进 `checks`。tests/test_checker_contract.py
   用源码扫描把这条钉死（当前 16 个 checks/ 文件实测零写操作）。

退出码沿用仓库惯例：0 = 无问题，1 = 查出了问题（不是崩溃）。
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

PROJECT = "project"
TL_DIR = "tl_dir"


@dataclass(frozen=True)
class CheckContext:
    """一次检查的输入：项目目录 + 翻译目录 + 语言。

    `tl_dir` 允许为 None——`tl_dir` 类检查器据此判定 `applies_to()` 为 False，
    对应门面过去"跳过：无 <lang> 翻译目录"那一支。
    """

    project: Path
    tl_dir: Optional[Path] = None
    lang: str = "schinese"

    @classmethod
    def from_project(cls, project, lang="schinese"):
        """从项目根或 game 目录反推 tl/<lang> 目录（找不到则为 None）。"""
        project = Path(project)
        game_dir = project / "game" if (project / "game").is_dir() else project
        tl_dir = game_dir / "tl" / lang
        return cls(project=game_dir, tl_dir=tl_dir if tl_dir.is_dir() else None, lang=lang)

    def has_project(self):
        return bool(self.project) and Path(self.project).is_dir()

    def has_tl_dir(self):
        return bool(self.tl_dir) and Path(self.tl_dir).is_dir()


class BaseChecker:
    """检查器基类。子类在模块级实例化一个 `CHECKER` 供门面发现。"""

    #: 门面子命令名（如 "crash"）
    name = ""
    #: 门面前缀的一句话描述（如 "检测运行时崩溃风险"）
    summary = ""
    #: 位置参数语义：PROJECT（吃 `<项目>`）或 TL_DIR（吃 `game/tl/<lang>`）
    takes = PROJECT
    #: 是否必须存在 game/tl/<lang> 才能给出有意义的报告。与 `takes` 正交：
    #: check_translation_integrity / check_charname_translation /
    #: check_duplicate_translations / check_button_missing_translation 都吃
    #: `<项目>`（takes=PROJECT），但缺 tl 目录时只会空转或报错
    #: （实测 rc=1/2/0/0），所以 requires_tl=True。门面据此跳过并提示先跑
    #: setup_i18n，替代旧的手写集合 NEEDS_TL_DIR。
    requires_tl = False
    #: 只读契约，见模块 docstring 第 3 条
    read_only = True

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        missing = [f for f in ("name", "summary") if not getattr(cls, f, "")]
        if missing:
            raise TypeError(f"{cls.__name__} 缺少契约字段：{missing}")
        if cls.takes not in (PROJECT, TL_DIR):
            raise TypeError(f"{cls.__name__}.takes 只能是 {PROJECT!r} 或 {TL_DIR!r}，"
                            f"实际 {cls.takes!r}")
        if cls.takes == TL_DIR and not cls.requires_tl:
            raise TypeError(f"{cls.__name__} 吃 tl_dir 却没声明 requires_tl=True，"
                            f"两者矛盾")

    def applies_to(self, ctx):
        """默认按 `requires_tl` / `takes` 判定；需要更细的条件可覆写。

        规则：
        - 没有项目目录 → 一律不适用（`takes` 两种都要求有东西可读）。
        - `requires_tl=True` 或 `takes=TL_DIR` → 还必须有 tl 目录。
        - `takes=TL_DIR` 时门面还要把位置参数从 `<项目>` 换成 tl_dir。
        """
        if not ctx.has_project():
            return False
        if self.takes == TL_DIR or self.requires_tl:
            return ctx.has_tl_dir()
        return True

    def run(self, ctx):
        """就地执行检查，返回退出码（0=无问题，1=查出了问题）。

        **可选**：门面 `renpy-tools-cli.py` 走子进程执行脚本，只需要 name/summary/
        takes 这三元元数据，不要求每个检查器都能就地跑。因此默认实现是「不支持
        就地执行」，需要它时才覆写（目前只有 check_crash_risks 与
        check_untranslated 把逻辑从 argparse 里拆了出来）。

        覆写它要求脚本把业务逻辑与 CLI 解耦（逻辑收进 `run_xxx()` 函数，main()
        只做参数解析）——这条要求是有意的：解耦了的脚本才能被复用和测。
        """
        raise NotImplementedError(
            f"{type(self).__name__} 未实现 run()：门面走子进程，不需要就地执行。"
            f"如需就地执行，先把逻辑从 main() 拆成 run_xxx() 函数再调它。"
        )


def find_game_dir(path):
    """`<项目>` 或 `<项目>/game` 都接受，返回 game 目录；都没有则返回 None。"""
    path = Path(path)
    if (path / "game").is_dir():
        return path / "game"
    if path.name == "game" and path.is_dir():
        return path
    return None


def skip_dirs(*extra):
    """遍历项目时的公共跳过目录：`renpy/`（引擎）、`lib/`、`cache/`、`saves/`。"""
    return ("renpy", "lib", "cache", "saves") + tuple(extra)


def iter_rpy(root, skip=None, include_tl=False, include_engine=False):
    """遍历项目 .rpy 源文件。

    默认行为对齐各检查器既有约定：跳过引擎目录（`renpy/`、`lib/`，误报多）与
    `cache/`、`saves/`；`skip_tl=False` 时才进 `tl/`。收进这里是为了让"扫哪些
    文件"在各检查器之间同源——各脚本自己那份 `find_rpy_files` 早晚会漂。
    """
    root = Path(root)
    skip_set = set(skip if skip is not None else skip_dirs())
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in skip_set and (include_engine or d != "renpy")]
        if not include_tl and os.path.basename(dirpath) == "tl":
            dirnames[:] = []
            continue
        for fn in filenames:
            if fn.endswith(".rpy"):
                out.append(Path(dirpath) / fn)
    return out


if __name__ == "__main__":  # 手动自检
    import argparse

    ap = argparse.ArgumentParser(description="检查器契约自检")
    ap.add_argument("--context", help="打印一个示例 CheckContext")
    args = ap.parse_args()
    ctx = CheckContext.from_project(args.context or ".", "schinese")
    print(f"project={ctx.project} tl_dir={ctx.tl_dir} "
          f"has_project={ctx.has_project()} has_tl_dir={ctx.has_tl_dir()}")