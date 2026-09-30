# renpy-skill

两个技能：`renpy-dev/`（工程工具链：lint/编译/打包/翻译/结构分析/资源检查/字体/多语言，脚本在 `scripts/`）、  
`renpy-user/`（参考手册：`renpy_gotchas.md` 经验陷阱、`player_tools.md` 玩家侧工具地图、UI 模式/画廊/排错/汉化工作流等 references）。

## 维护约定

1. **能跑的进 SDK 的 `tools/`（renpy-tools 工具包，路径经 `RENPY_SDK`/`detect_sdk()` 解析），skill 只放模型不知道的结论。**
2. **description 必须写全故障词**（崩溃/traceback、汉化质检、字体方块、存档…）——漏一个，技能等于不存在。
3. **每次项目收尾只追加 1 条 gotcha**（≤10 行 + 可复制命令），不写教程。
4. **一个知识只放一处**：`.rpyc` 反编译归已装的 `renpy-script-decompile` 技能，本包只留指针。

## 2026-09-30 整合记录

以本包为主，从本地 SDK 工作区（`renpy-8.5.3-sdk/skills/`，源目录保留，未删除）并入：

- **脚本**（renpy-development-skill-cn-master → `renpy-dev/scripts/`）：`check_assets.py`（资源完整性）、`setup_fonts.py`（字体适配）、`setup_i18n.py`（多语言基础设施）、`optimize_assets.py`（资源压缩，外部工具缺失自动降级）。已用 SDK Python 验证 `--help` 可运行。
- **参考**（→ `renpy-user/references/`）：`snippets.md`（16 类 UI/角色模式）、`gallery_and_stats.md`（画廊/养成）、`debugging.md`（排错）、`advanced_tools.md`（字体/rpyc/rpa/镜像）。
- **工作流**（提炼自 renpy-text2script / renpy-translate）：`renpy-dev/references/text2script_workflow.md`（剧本→脚本）、`renpy-user/references/translation_workflow.md`（汉化 .rpy 术语表+审查循环）。
- **未并入**：`renpy-reply`（玩家评论回复助手，定位为发行后客服场景，与开发/参考主线无关）。

## 已知边界

- 未注册进 `~/.workbuddy/skills/`，需要手动指定路径加载。
- 传统工具箱（解包/存档/汉化）以调度现成工具为主，不重写轮子；Ren'Py 自定义程度高，做不到一键脚本的部分靠 AI 直接读写源码。
