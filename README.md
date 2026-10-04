# renpy-skill

面向 AI Agent 的 Ren'Py 单体技能包：`renpy/` 一个技能覆盖全链路——工程工具链（lint / 编译 / 打包 / 翻译 / 结构分析）、开发参考（陷阱库 / 画廊 / 数值）、玩家侧（解包 / 存档 / 汉化 / 解锁补丁）与排错。设计目标是让 AI 在无人工补位的情况下，独立完成 lint、编译打包、汉化、质检、解包、存档编辑等完整链路。

> 2026-10-03 起由 renpy-dev + renpy-user 双技能合并为单技能，消除触发词打架与双向指针；旧路径引用已全部修复。

## 目录结构

| 路径 | 职责 |
|------|------|
| `renpy/SKILL.md` | 唯一入口：脚本速览、触发关键词、注意事项（含独有引擎版本边界）、references 分场景索引 |
| `renpy/scripts/` | 顶层仅统一门面 `renpy-tools-cli.py`（27 子命令）与 rpyc 反编译兜底 `unrpyc.py`；分组：`sdk/`（SDK CLI 封装：lint / 编译 / 打包 / 结构分析 / 资源检查 / 字体 / i18n / tl 质检，依赖 `sdk_common.py`）、错误检测 / 翻译相关 / 润色 / 统一名称 / 线性模式 / 设置 / 公共 / 测试，及 168 用例回归测试 |
| `renpy/references/` | 15 个分场景参考：SDK 配置速查、工具包边界分级、剧本→脚本工作流、译文润色；gotchas 陷阱库、非显性技巧、画廊/养成/性能预设、字体/rpyc/rpa 速查、汉化工作流、汉化常见问题手册、tl 质检细则、玩家侧工具地图、解锁补丁、排错指南 |

## 使用

- **加载**：向 Agent 显式指定 SKILL.md 路径（`renpy/SKILL.md`）。
- **SDK 探测**优先级：`--sdk` 参数 → 环境变量 `RENPY_SDK` → 向上查找 → `sdk_common.py` 的 `_KNOWN_SDK_PATHS` → `~/renpy-sdk`。本机路径不写入仓库，本地使用时设 `RENPY_SDK` 环境变量或在 `_KNOWN_SDK_PATHS` 追加。
- **AI 翻译**：服务端点与密钥均通过环境变量提供（`RENPY_TRANSLATE_API_URL` / `RENPY_TRANSLATE_API_KEY`），仓库不含任何服务地址或凭据。

## 维护约定

1. 可执行逻辑进 `renpy/scripts/` 或 SDK，技能文档只保留模型不知道的结论。
2. SKILL.md 的 description 必须覆盖全部故障关键词（崩溃 / traceback、汉化质检、字体方块、存档等）。
3. 每次项目收尾最多追加 1 条 gotcha（不超过 10 行，附可复制命令），不写教程。
4. 一个知识只放一处：`.rpyc` 反编译入口优先用独立的 renpy-script-decompile 技能，内置 `unrpyc.py` 仅作兜底（唯一说明处在 SKILL.md 注意事项"反编译"行）；rpyc/rpa 工具选型与版本坑统一在 `references/player_tools.md`，`advanced_tools.md` 不再重复；tl_check 分级细则唯一出处为 `references/tl_check.md`，SKILL.md 只留路由。

## 变更记录

### 2026-10-05 二轮：分类收敛 / 模板瘦身 / 解析层归一

- **人名统一工具归组**：`unify_names.py` 从 `润色/` 移入 `统一名称/`（与其 v6 主流程、make_glossary 术语表生产同目录），组 README 写明三者分工（取证 → 批式直改 → 三步审核/回滚）；`_say_parse` 导入改为跨组定位，8 处文档引用同步。`autotranslate.apply_glossary` 属回填管线内嵌步骤，保留不动。
- **gallery_and_stats.md 模板瘦身**：27.7KB → 6.1KB。砍掉性能预设完整实现/极简版/分页画廊/作弊面板/完整示例等约 400 行可粘贴模板（违反"参考只收模型记不全的内容"原则），保留配置对照表与生效时机、容错模式、8 条实测翻车场景、Gallery 自动解锁机制与引用名一致性、Replay/MusicRoom 非显性参数、screen action 速查表。
- **say 解析归一**：`润色/_say_parse.py` 44 行自备正则重写为 `公共/rpy_syntax.py` 适配器（autotranslate 早已在 rpy_syntax 层，本轮核实）；差分验证 3 处差异均为修正——旧正则把 `\"` 转义原样吐出（与 autotranslate 锚点解码不一致）、把 `old "..."` 误判为 char='old' 的对话条目，新版皆正确；输出契约（file/line/src_line/type/orig/trans/char）不变，消费方零改动。
- **SKILL.md 减负**：汉化工作流巨型单元格收缩为一行路由；"项目体检"行挂上 `scripts/README.md` 链接（此前该 10KB 工具侧文档仅 player_tools 一处顺带提及）。
- **延后**：autotranslate.py（1359 行）/ linear_mode.py（1003 行）/ unify_name_translations.py（824 行）原子化拆分仍不做——0 class 平铺但测试覆盖真实，拆分是维护性收益非缺陷修复；`__pycache__` 复发根因确认为跑测试时 Python 重写字节码，清理时需带 `PYTHONDONTWRITEBYTECODE=1`。
- 验证：168 用例回归通过；新旧解析器差分测试通过（合成样本覆盖 cd/tb/空译文/转义引号/old-new/multiple=2/尾部属性）。

### 2026-10-05 结构自查修复

- SKILL.md 减负：tl_check 千字细则单元格迁出为 `references/tl_check.md`（唯一完整出处），SKILL.md 脚本表与注意事项改为路由；不再出现"唯一出处 = 注意事项表格行"的自指。
- 修复孤儿文件：`references/hanization_manual.md`（10 章节汉化手册，合并时移入但从未入索引）挂入 SKILL.md"参考知识·汉化"。
- 收敛 unrpyc 三处矛盾说法为一条规则：renpy-script-decompile 技能优先，内置 `renpy-tools-cli unrpyc` 兜底（SKILL.md 与维护约定同步）。
- 修复"错误诊断：没有诊断脚本"与 renpy-tools-cli 体检子命令的措辞冲突，改为"log/traceback 判读没有脚本"。
- 卫生：删除 `.zwork/artifacts/`（4 份 skill 文档过期副本）与 5 处 `__pycache__`；`.gitignore` 补 `.zwork/`。
- 文档数字校正：回归测试 140 → 168 用例；references 计数 12 → 15。中文脚本目录名跨平台风险与 translation_workflow 单元格减负经评估本轮不改（重命名牵动 import 与 6 处文档引用，收益低）。
- 验证：168 用例回归通过、SKILL.md 新增链接落盘确认。

### 2026-10-04 运行时 UI 修复：语言按钮缺口补齐

- 新增 `scripts/设置/fix_lang_button.py`（CLI 子命令 `langbtn`，入 FIX_GROUP）：修复 screens.rpy 中语言按钮写死/缺目标语言项（`Language("english")` 硬编码、按钮列表无中文导致汉化后切不到），参照 renpy-translate-studio 四类自动修复中唯一缺口，config.language/字体/语言钩子已有脚本覆盖不重复实现。
- 设计遵守工具包惯例：默认试运行、`--apply` 才落盘、`atomic_write_text(backup=True)` 写前 .bak、幂等（目标语言已存在则跳过）；配套 SKILL.md 注意事项"运行时 UI 修复"、tools_boundaries 半通用登记与写操作风险表、设置/README。
- 验证：示例项目试运行/落盘/重复执行/回滚重修复/CLI 联动/无语言入口提示全链路通过。

### 2026-10-04 scripts 结构归位

- scripts/ 顶层收敛为门面 + 分组：8 个 SDK 封装脚本（cli/analyze/check_assets/setup_fonts/setup_i18n/optimize_assets/tl_check/sdk_common）收入 `sdk/`，`renpy-tools-cli.py` 留根；修复其 `SCRIPTS_DIR` 原指向 `../scripts`（搬移前恰好自指）改指 `sdk/`，`unrpyc` 命令路径同步。
- 错位归位：`patch_android_tablet.bat` 移入 `设置/`（与其调用的 py 同目录）；`unrpyc.py` 出 `设置/` 到 scripts 根（rpyc 兕底工具不属于任何组）。
- 撤销两个单成员/零引用目录：`补丁集/`（csv 并入 `翻译相关/`，patch_renpy_say.py 默认路径同步）；`文档/`（汉化手册 → `references/hanization_manual.md`，AI 翻译诊断 → `翻译相关/`）。
- 修复 `sdk/cli.py` 裸 `import sdk_common` 在 safe-path 模式（本机 `sys.flags.safe_path=True`）下的 ModuleNotFoundError，改为显式 sys.path 自定位。
- 同步全部文档路径：SKILL.md 脚本速览/快速入门、sdk_config/debugging/gotchas 引用、scripts/README 目录树重写（含润色组补录）。
- 验证：140 用例 OK、CLI list 正常、sdk 四脚本 import 冒烟通过、全库 .md 链接 0 断链、旧路径零残留。原子化拆分（autotranslate/unify/crash 三大脚本）经确认本轮不做。

### 2026-10-03 合并为单技能

- renpy-dev + renpy-user 合并为 `renpy/`：双技能触发词互相打架（"字体方块""汉化质检"两边都认领）、边界互相穿破（user 声称不生成代码模板却收录 877 行模板集），合并后单一入口按场景索引。
- user 侧 8 个 reference 移入 `renpy/references/`，内容只去重不丢失：`debugging.md` 410 → 200 行（删 lint 教程与通用 Python 常识，保留 Shift 键位、调试语句、bug 分类、发布版容错配置）；`advanced_tools.md` 432 → 约 210 行（rpyc/rpa 工具细则并入 player_tools.md 指针，保留字体 4 法、RPA 优先级结论、镜像大全）。
- 全库引用修复：dev SKILL.md 3 处跨包指针改为技能内路径；player_tools / unlock_patches / tools_boundaries / translation_workflow / gotchas / sdk_common / scripts/README 内的 renpy-dev、renpy-user 字样清除；scripts/README 的 `文档/` 目录树同步实际文件（移除 2 个已删文件行）。
- 清理：删除 3 处 `__pycache__`（git 未跟踪的磁盘残留）；scripts/README 翻译示例中密钥占位赋值行改为注释说明（密钥只走环境变量）。
- 结构判断依据：原 user 侧 8 文件中 unlock_patches / player_tools / renpy_gotchas / snippets 为模型写不出的引擎级与工具生态知识，是合并保留的核心理由。

### 2026-10-02

- 外部引用核对：补充 unrpyc 对 Ren'Py 8.5 的支持边界（PR #265）、rpycdec 对 8.4+ 的兼容问题、unrpa 对新 RPA-3.0 档案的解析问题；rpatool 规范源头迁移至 Codeberg；替换失效的 GitHub 加速镜像。
- 精简：tl_check 描述去重；`snippets.md` 重构为陷阱速查（405 行 → 78 行）；`debugging.md` 报错对照表与开发者菜单说明压缩。
- 隐私清理：SDK 本机路径、翻译服务端点、含用户名的示例路径全部移出仓库，改由环境变量与本地配置提供。
- 收割 v0.3.2 旧架构线残值：analyze.py 新增 styles / layeredimages / defaults / show_refs 扫描类别与临时目录排除；debugging.md 补发布版容错配置清单；gotchas 补存档迁移回调与幂等要求。旧架构代码（bridge/scaffold/patterns/export/diagnose）经评估不合并，远端分支已删除。

### 2026-09-30 整合

以本包为主体，从本地 SDK 工作区并入脚本（check_assets / setup_fonts / setup_i18n / optimize_assets）、参考文档（snippets / gallery_and_stats / debugging / advanced_tools）与工作流（text2script / translation workflow）。未并入：renpy-reply（发行后客服场景，与主线无关）。

## 已知边界

- 未注册进技能加载器，需手动指定路径加载。
- 解包 / 存档 / 汉化以调度成熟开源工具为主，不重写轮子；Ren'Py 自定义程度高，无法一键脚本化的部分由 AI 直接读写源码。
