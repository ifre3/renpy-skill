# renpy-skill

给AI Agent 的 Ren'Py 技能包，既包含调试等功能也包含用户常需功能。目前包含功能：
错误与崩溃检测，tl质检等等
## 目录结构

| 路径 | 职责 |
|------|------|
| `renpy-dev/SKILL.md` | 工程技能入口：脚本速览、触发关键词、注意事项（含独有引擎版本边界） |
| `renpy-dev/scripts/` | SDK CLI 封装与独立脚本（lint / 编译 / 打包 / 结构分析 / 资源检查 / 字体 / i18n / tl 质检），依赖 `sdk_common.py` 做 SDK 探测 |
| `renpy-dev/references/` | SDK 配置速查、renpy-tools 工具包边界分级、剧本→脚本工作流 |
| `renpy-dev/tools/` | 独立工具包 renpy-tools：纯标准库、统一入口 `renpy-tools-cli.py`，含错误检测、翻译相关、线性模式、统一名称、设置五组工具及 140 用例回归测试 |
| `renpy-user/SKILL.md` | 参考技能入口：只收录模型记不全或易过时的内容，.rpy 源码由 AI 直接编写 |
| `renpy-user/references/` | gotchas 陷阱库、玩家侧工具地图、汉化工作流、画廊/养成、解锁补丁、排错指南、非显性技巧、字体/rpyc/rpa 速查 |





## 变更记录

### 2026-10-02

- 外部引用核对：补充 unrpyc 对 Ren'Py 8.5 的支持边界（PR #265）、rpycdec 对 8.4+ 的兼容问题、unrpa 对新 RPA-3.0 档案的解析问题；rpatool 规范源头迁移至 Codeberg；替换失效的 GitHub 加速镜像。
- 精简：tl_check 描述去重；`snippets.md` 重构为陷阱速查（405 行 → 78 行）；`debugging.md` 报错对照表与开发者菜单说明压缩。
- 隐私清理：SDK 本机路径、翻译服务端点、含用户名的示例路径全部移出仓库，改由环境变量与本地配置提供。

### 2026-09-30 整合

以本包为主体，从本地 SDK 工作区并入脚本（check_assets / setup_fonts / setup_i18n / optimize_assets）、参考文档（snippets / gallery_and_stats / debugging / advanced_tools）与工作流（text2script / translation workflow）。未并入：renpy-reply（发行后客服场景，与主线无关）。

## 进展

- 
