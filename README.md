# renpy-skill

给AI Agent 的 Ren'Py 技能包覆盖常见功能：
工具链（lint / 编译 / 打包 / 翻译 / 结构分析）
玩家侧（解包 / 解锁画廊 / 汉化 / 作弊补丁）与排错等等。

> 2026-10-03 起由 renpy-dev + renpy-user 双技能合并为单技能，消除触发词打架与双向指针；旧路径引用已全部修复。
> 2026-10-05 `scripts/` 下 8 个分组目录与 4 个说明文件由中文名改为 ASCII，macOS 的 NFD 归一化问题根治。
> 2026-10-06 检查器契约层（`BaseChecker`）+ 门面注册表落地，只读检查器全部归位 `checks/`，同类多入口脚本经评估不拆。

## 目录结构

| 路径 | 职责 |
|------|------|
| `renpy/SKILL.md` | 唯一入口：脚本速览、触发关键词、注意事项（含独有引擎版本边界）、references 分场景索引 |
| `renpy/scripts/` | 顶层仅统一门面 `renpy-tools-cli.py`（30 子命令 + all/list）与 rpyc 反编译兜底 `unrpyc.py`；9 个分组目录全 ASCII（`sdk` `checks` `translate` `polish` `names` `linear` `setup` `shared` `tests`），404 用例回归测试。详见 `renpy/scripts/README.md` |
| `renpy/references/` | 15 个分场景参考：SDK 配置速查、工具包边界分级、剧本→脚本工作流、译文润色；gotchas 陷阱库、非显性技巧、画廊/养成/性能预设、字体/rpyc/rpa 速查、汉化工作流、汉化常见问题手册、tl 质检细则、玩家侧工具地图、解锁补丁、排错指南 |
