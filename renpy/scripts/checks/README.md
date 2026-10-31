# checks/ — 只读检查器

> **要点已内联到 [../README.md](../README.md)「checks/ — 只读检查器」一节**，本文件只留本组边界摘要。

全部**只读审计**，只报告问题不改文件；唯一例外是用户显式点名的导出：`check_untranslated --csv`、`check_charname_translation --stub`。
会写文件的工具（AI 回填、修补、名框同步）在 `../translate/`。想"找出问题"来本组（或 `renpy-tools-cli.py all`），想"修掉问题"去 `translate/`。

每个检查器声明模块级 `CHECKER`（`name`/`summary`/`takes`/`requires_tl`），门面的子命令由此派生这四项；「子命令名→脚本路径」映射仍是手写的 `TOOL_SCRIPTS`。

详见 [../README.md](../README.md)（检查器契约、`check_label_issues` 误报边界、名字框机制、lint_rpy 定位）。

名字栏（`check_charname_translation`）另有专门文档：[../../references/namebox_translation.md](../../references/namebox_translation.md)
——讲清「三类说话人写法」与「`tl` 查找是**全串精确匹配**，带 `{color=}` 标签时 `old` 也必须带标签」，
这两个坑都会让只认 `Character("Name")` 的工具扫出 0 个名字并误报全绿。
