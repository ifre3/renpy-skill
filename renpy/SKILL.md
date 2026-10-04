---
name: renpy
description: "Ren'Py 全栈技能：工程工具链（lint/编译/打包/翻译/结构分析）+ 开发参考（画廊/数值/陷阱库）+ 玩家侧（解包/存档/汉化/解锁补丁）+ 排错（崩溃排查、traceback 判读、汉化缺句与质检、字体方块）。写游戏、做汉化、跑 lint、打包发行版、解包别人的游戏、排查报错时激活。"
compatibility: "renpy>=8.0"
metadata:
  openclaw:
    emoji: 🛠️
    permissions: ["file.read", "file.write", "exec"]
    os: ["windows", "linux"]
---

# Ren'Py — 全栈技能

## 脚本速览

| 文件 | 用途 | 一句话用法（CLI，在 skill 根目录执行） |
|------|------|-----------|
| `scripts/sdk/sdk_common.py` | SDK 路径检测共用模块（其余脚本的依赖） | 库用：`detect_sdk()`, `find_platform_python(sdk)` |
| `scripts/sdk/cli.py` | SDK CLI 封装：Lint/编译/打包/运行/翻译 | `python scripts/sdk/cli.py <项目> lint [--sdk <SDK>]` |
| `scripts/sdk/analyze.py` | 项目结构分析（labels/screens/悬空引用，带行号，离线可用） | `python scripts/sdk/analyze.py <项目路径> [-v]` |
| `scripts/sdk/check_assets.py` | 资源完整性检查（.rpy 引用 vs 实际文件，报缺失/孤设） | `python scripts/sdk/check_assets.py --path <项目路径>` |
| `scripts/sdk/setup_fonts.py` | 字体适配（detect 检测 / config 生成配置 / fallback 回退链 / list 推荐） | `python scripts/sdk/setup_fonts.py detect --path <项目路径>` |
| `scripts/sdk/setup_i18n.py` | 多语言基础设施（生成 tl/ 目录、语言 Screen、字体配置，不含翻译内容） | `python scripts/sdk/setup_i18n.py --path <项目路径> --lang zh en ja` |
| `scripts/sdk/optimize_assets.py` | 批量压缩图片/音频减小包体积（pngquant/jpegoptim/ffmpeg 缺失时自动降级为复制） | `python scripts/sdk/optimize_assets.py --input ./game/images --output ./out` |
| `scripts/sdk/tl_check.py` | tl 翻译文件质检 v3（三级报告 + `--fix`；分级细则与崩溃边界的唯一完整出处见 [references/tl_check.md](references/tl_check.md)） | `python scripts/sdk/tl_check.py <项目路径> --lang schinese [--fix] [--add-tflag] [--max-examples N]` |
| `scripts/设置/fix_lang_button.py` | 运行时 UI 修复：语言按钮写死/缺目标语言项（`Language("english")` 硬编码导致汉化后仍无法切中文；默认试运行，`--apply` 才落盘，自动 .bak） | `python scripts/设置/fix_lang_button.py <项目路径> [--apply] [-l schinese]` |

## Trigger 关键词

| 你说 | 它做 |
|------|------|
| "检查代码有没有问题" | cli.lint 语法检查 |
| "打包成 Windows 版 / APK / Web 版" | cli.distribute / android_build / web_build |
| "分析项目结构"、"看看有多少 label" | analyze 结构分析 |
| "添加中文翻译"、"导出翻译" | cli.translate / extract_strings / merge_strings |
| "写剧情 / 加画廊 / 加养成数值 / 加设置项" | AI 直接写 .rpy；陷阱查 references/snippets.md，画廊/数值/性能查 gallery_and_stats.md |
| "从零做一个游戏 / 我有剧本想做成游戏" | 从零创作主线：references/game_creation_workflow.md（立项确认 → 骨架 → 剧本落盘 → 占位资产 → 逐章验证 → 打包；美术用户出/外部画，skill 只管占位与接入） |
| "解包 / 反编译 / 改存档 / 一键解锁 CG" | 玩家侧工具调度：references/player_tools.md、unlock_patches.md |
| "汉化这个游戏" | translation_workflow.md 工作流 + scripts/ 工具链质检 |
| "中文显示不出来 / 语言按钮没反应 / 切不到中文" | 三件套：`fix_lang_button`（语言按钮写死，默认试运行 `--apply` 落盘）→ `switch_default_language`（默认语言）→ `add_fonts`/`setup_fonts`（字体注入），顺序见注意事项"运行时 UI 修复" |

## 快速入门

```bash
python scripts/sdk/cli.py "D:/my_game" lint             # 语法检查（退出码透传 SDK）
python scripts/sdk/analyze.py "D:/my_game" -v           # 结构分析：labels/screens/悬空引用
python scripts/sdk/check_assets.py --path "D:/my_game"  # 资源缺失/孤设
```

需要库调用（批量场景、自定义编排）时再 import：`RenPyCLI().lint(path)`、`Analyzer(path).analyze().report()`，方法签名与返回值见 [references/sdk_config.md](references/sdk_config.md)。

## 注意事项

| 场景 | 说明 |
|------|------|
| **运行时 UI 修复（中文不显示/切不到）** | 按序排查：① `renpy-tools-cli.py langbtn <项目> --apply` 修语言按钮写死/缺目标语言项（自动 .bak 可回滚，默认只试运行）；② `lang`（`switch_default_language.py`) 设默认语言；③ `fonts`（`add_fonts.py`）注入字体；④ 仍无语言切换入口先 `sdk/setup_i18n.py` 生成。四类修复中 config.language 与字体已有脚本，langbtn 只补语言按钮缺口，勿重复造轮 |
| **项目体检（优先用现成工具）** | renpy-tools 工具包（**已内置 skill：`scripts/`**，纯标准库零依赖）统一入口：`python <skill>/scripts/renpy-tools-cli.py all <项目> -l schinese`。子命令：`crash` 崩溃风险、`untranslated` 空译文、`charname` 名字框漏译、`integrity` 变量/标签完整性、`label` 标签问题、`all` 全跑；仅 `lint` 子命令需要 SDK（`--sdk` 参数或向上扫描 SDK 目录定位）。闪退/缺句/名字英文先跑这个；**工具侧全目录树、备份机制与 AI 翻译安全流程见 [scripts/README.md](scripts/README.md)** |
| **翻译文件质检（tl 侧唯一工具）** | 上面工具跳过 tl 目录；用**内置**的 `python scripts/sdk/tl_check.py <项目> --lang schinese [--fix]` 查翻译侧隐患。三级报告（崩溃级 / 显示级 / 提示级）、`[]` 插值改名按崩溃级处理、`--fix --add-tflag` 等细则的**唯一完整出处**见 [references/tl_check.md](references/tl_check.md) |
| 反编译 .rpyc / 提台词 / 剧情地图 | 优先用已装的 **renpy-script-decompile** 技能（纯 Python 解 slot + pickle stub）；该技能不可用时用内置兜底：`python scripts/renpy-tools-cli.py unrpyc <游戏目录>`（自动下载 unrpyc，多镜像切换） |
| SDK 路径 | 自动检测（`sdk_common.py`）：`sdk_path=` 参数 → 环境变量 `RENPY_SDK` → 向上查找 → 已知路径；本机新装 SDK 只需在 `_KNOWN_SDK_PATHS` 追加一行 |
| 错误诊断 | log.txt / traceback 判读**没有脚本**——直接给 AI 判读，比正则匹配准（项目体检类静态检查走上面"项目体检"行的 renpy-tools-cli，两者不冲突）；系统性排查见 [references/debugging.md](references/debugging.md) |
| **旧引擎发行版（装不了 SDK 时）** | 别用本 skill 的 SDK CLI 判版本兼容——≥8.0 的 lint 会把 `config.label_callbacks` 当合法，掩盖 7.x 崩溃。改用**游戏自带引擎**就地验证：`cd <游戏根目录> && ./lib/windows-x86_64/python.exe <启动脚本>.py . lint`（发行版 `lib/<平台>/python.exe` 就是完整解释器，还支持 `test <用例>` 跑界面；**跑 test 必须加 `SDL_VIDEODRIVER=windows`**，否则 dummy 驱动无 OpenGL 报错，属环境问题非游戏问题）。版本兼容坑见 [references/renpy_gotchas.md](references/renpy_gotchas.md) |
| 测试 | 没有测试脚本——Ren'Py testcase 语法（`run`/`click`/`advance until screen`/`assert eval`）AI 直接写在 .rpy 里，用 `renpy.py 项目 test` 执行 |
| 存档/解包/汉化补丁 | 解包/存档编辑/玩家侧补丁 → [references/player_tools.md](references/player_tools.md)；一键解锁画廊/CG/回放 → [references/unlock_patches.md](references/unlock_patches.md) |
| 导出 JSON | 已删除 export.py——官方 `translate` 命令生成标准翻译文件，够用 |
| 跨平台（darwin 已知限制） | scripts/ 下含中文目录名（错误检测 / 翻译相关 / 润色 / 统一名称 / 线性模式 / 设置 / 公共 / 测试），git 在 macOS 上会把路径归一化为 NFD，跨系统 checkout 后 import 可能找不到模块。darwin 上建议整体 clone 后 `git config core.precomposeunicode true` 再使用；linux/windows 无此问题 |

## 参考知识（按场景索引）

**写游戏 / 引擎行为**（AI 直接写 .rpy，不背模板；参考只收模型记不全、易过时的内容）：

- **经验性陷阱** → [references/renpy_gotchas.md](references/renpy_gotchas.md)（字体静默回退、UI 微调陷阱：字号不联动/位置三套属性/文本框 override、缩进只数空格、define vs default 存档语义、SL2 坑、存档迁移幂等）
- **非显性技巧陷阱速查** → [references/snippets.md](references/snippets.md)（F2 语言热键、Scroll 三参、拖放回调契约、历史屏/气泡/侧头像陷阱——只收模型容易写错的点）
- **画廊/养成/性能预设** → [references/gallery_and_stats.md](references/gallery_and_stats.md)（画廊 CG/Music Room、属性养成、金手指、原版/平衡/流畅三档性能预设完整实现）
- **字体修改 / 语言联动** → [references/advanced_tools.md](references/advanced_tools.md)（4 法 + 语言切换字体联动；rpyc/rpa 工具细则在 player_tools.md）
- **汉化常见问题手册** → [references/hanization_manual.md](references/hanization_manual.md)（10 章节按"现象 → 原因（含 Ren'Py 8.5.3 源码依据）→ 发现 → 修复"组织：翻译完全不显示、部分不显示、运行时崩溃、UI 错乱、角色/名字、漏翻、译名不统一、工具相关、跨平台、疑难排查流程）
- **汉化翻译工作流** → [references/translation_workflow.md](references/translation_workflow.md)（开工先过确认门：翻译方式三选一；术语表脚本取证 `scripts/统一名称/make_glossary.py` + AI 精读判资格，**定稿前必须停下征求用户**；批次切分 ~1024 token 不截句、提示词以目的语言流畅为第一目标、`config.replace_text` 兜底、图片/视频/字体 tl 资源覆盖、script_version.txt 版本预判——细则全部见该文件）

**玩家侧 / 排错**：

- **玩家侧工具地图** → [references/player_tools.md](references/player_tools.md)（解包/存档编辑/汉化/重放，调度现成工具而非重造轮子，含工具版本坑）
- **一键解锁画廊/CG/回放**（别人的游戏）→ [references/unlock_patches.md](references/unlock_patches.md)（引擎判定链 + 投放式补丁全文 + 控制台一行 + 非标准画廊打法）
- **排错指南** → [references/debugging.md](references/debugging.md)（Shift 键调试/控制台语句/常见 bug 分类/二分法/发布版容错配置）

**进阶参考（工程侧）**：

- [SDK 配置 & CLI 命令速查](references/sdk_config.md) — 自动检测逻辑、全部 CLI 命令
- [renpy-tools 工具包边界](references/tools_boundaries.md) — 各工具通用度分级（通用/半通用/专用）、写操作风险表、引擎版本经验；半通用工具换游戏前先看这页
- [剧本 → 脚本工作流](references/text2script_workflow.md) — 原始剧本转 .rpy 的拆分/命名/演出注释规范，及资产文档格式
- [从零创作主线](references/game_creation_workflow.md) — 立项确认门（篇幅/类型/美术来源）、项目骨架、纯代码占位资产流水线、美术资产接入与替换（目录名即 image 名，删占位+图入目录两步）、逐章验证与打包 checklist；定位：skill 是工程承包商，不执行画图
- [译文润色方法](references/translation_polish.md) — 双角色两阶段润色工作流与 LinguaGacha 路线（风格前置/Agent 审校），含 token 成本对照；按预算与范围自选

## SDK 路径（不写死）

SDK 根目录 `<SDK>` 按以下优先级解析：`--sdk` 参数 → 环境变量 `RENPY_SDK` → 向上查找 → `scripts/sdk/sdk_common.py` 的 `_KNOWN_SDK_PATHS`（本机路径只在此一处维护）→ `~/renpy-sdk`。

| 用途 | 相对 `<SDK>` 的位置 |
|------|------|
| 启动器 / 可执行文件 | `renpy.exe`（Linux/macOS 用 `renpy.sh`） |
| 官方文档 | `doc/` |
| SDK 自带 Python 解释器 | `lib/py3-windows-x86_64/python.exe`（Windows x64） |

## 版本边界

目标 SDK: Ren'Py ≥ 8.0。SDK 不可达时仅警告，不阻塞（可能脱机生成代码供其他环境使用）。

**SDK 缺失时给用户判断，不替用户决定**：先说明当前任务是否真需要 SDK（结构分析/资源检查/tl_check/字体/多语言/renpy-tools 均不需要，照常执行）；确需 lint/编译/打包/运行/翻译 时，把选项摆给用户二选一——①下载 SDK（https://www.renpy.org/latest.html ，解压设 `RENPY_SDK`）；②跳过该步只做免 SDK 部分。旧引擎（7.x）发行版第三选项：用游戏自带解释器（见注意事项"旧引擎发行版"）。不要静默自动下载，也不要静默跳过。
