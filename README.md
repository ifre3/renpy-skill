# renpy-skill

面向 AI Agent 的 Ren'Py 双技能包：`renpy-dev/` 负责工程工具链，`renpy-user/` 负责参考知识与玩家侧工具调度。设计目标是让 AI 在无人工补位的情况下，独立完成 lint、编译打包、汉化、质检、解包、存档编辑等完整链路。

## 目录结构

| 路径 | 职责 |
|------|------|
| `renpy-dev/SKILL.md` | 工程技能入口：脚本速览、触发关键词、注意事项（含独有引擎版本边界） |
| `renpy-dev/scripts/` | SDK CLI 封装与独立脚本（lint / 编译 / 打包 / 结构分析 / 资源检查 / 字体 / i18n / tl 质检），依赖 `sdk_common.py` 做 SDK 探测 |
| `renpy-dev/references/` | SDK 配置速查、renpy-tools 工具包边界分级、剧本→脚本工作流 |
| `renpy-dev/tools/` | 独立工具包 renpy-tools：纯标准库、统一入口 `renpy-tools-cli.py`，含错误检测、翻译相关、线性模式、统一名称、设置五组工具及 140 用例回归测试 |
| `renpy-user/SKILL.md` | 参考技能入口：只收录模型记不全或易过时的内容，.rpy 源码由 AI 直接编写 |
| `renpy-user/references/` | gotchas 陷阱库、玩家侧工具地图、汉化工作流、画廊/养成、解锁补丁、排错指南、非显性技巧、字体/rpyc/rpa 速查 |

## 使用

- **加载**：向 Agent 显式指定 SKILL.md 路径（`renpy-dev/SKILL.md` 或 `renpy-user/SKILL.md`）。
- **SDK 探测**优先级：`--sdk` 参数 → 环境变量 `RENPY_SDK` → 向上查找 → `sdk_common.py` 的 `_KNOWN_SDK_PATHS` → `~/renpy-sdk`。本机路径不写入仓库，本地使用时设 `RENPY_SDK` 环境变量或在 `_KNOWN_SDK_PATHS` 追加。
- **AI 翻译**：服务端点与密钥均通过环境变量提供（`RENPY_TRANSLATE_API_URL` / `RENPY_TRANSLATE_API_KEY`），仓库不含任何服务地址或凭据。

## 维护约定

1. 可执行逻辑进 `tools/` 或 SDK，技能文档只保留模型不知道的结论。
2. SKILL.md 的 description 必须覆盖全部故障关键词（崩溃 / traceback、汉化质检、字体方块、存档等）。
3. 每次项目收尾最多追加 1 条 gotcha（不超过 10 行，附可复制命令），不写教程。
4. 一个知识只放一处：`.rpyc` 反编译归独立的 renpy-script-decompile 技能，本包只保留指针。

## 变更记录

### 2026-10-02

- 外部引用核对：补充 unrpyc 对 Ren'Py 8.5 的支持边界（PR #265）、rpycdec 对 8.4+ 的兼容问题、unrpa 对新 RPA-3.0 档案的解析问题；rpatool 规范源头迁移至 Codeberg；替换失效的 GitHub 加速镜像。
- 精简：tl_check 描述去重；`snippets.md` 重构为陷阱速查（405 行 → 78 行）；`debugging.md` 报错对照表与开发者菜单说明压缩。
- 隐私清理：SDK 本机路径、翻译服务端点、含用户名的示例路径全部移出仓库，改由环境变量与本地配置提供。

### 2026-09-30 整合

以本包为主体，从本地 SDK 工作区并入脚本（check_assets / setup_fonts / setup_i18n / optimize_assets）、参考文档（snippets / gallery_and_stats / debugging / advanced_tools）与工作流（text2script / translation workflow）。未并入：renpy-reply（发行后客服场景，与主线无关）。

## 已知边界

- 未注册进技能加载器，需手动指定路径加载。
- 解包 / 存档 / 汉化以调度成熟开源工具为主，不重写轮子；Ren'Py 自定义程度高，无法一键脚本化的部分由 AI 直接读写源码。
