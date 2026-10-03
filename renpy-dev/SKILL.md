---
name: renpy-dev
description: "Ren'Py 工程工具链：lint/编译/打包/翻译/结构分析，以及项目体检（崩溃排查、traceback 判读、汉化缺句与质检、字体方块）。当你需要跑 lint、打包发行版、做汉化或排查报错时激活。"
compatibility: "renpy>=8.0"
metadata:
  openclaw:
    emoji: 🛠️
    permissions: ["file.read", "file.write", "exec"]
    os: ["darwin", "linux", "windows"]
---

# Ren'Py Dev — 工程工具

## 脚本速览

| 文件 | 用途 | 一句话用法（CLI，在 skill 根目录执行） |
|------|------|-----------|
| `scripts/sdk_common.py` | SDK 路径检测共用模块（其余脚本的依赖） | 库用：`detect_sdk()`, `find_platform_python(sdk)` |
| `scripts/cli.py` | SDK CLI 封装：Lint/编译/打包/运行/翻译 | `python scripts/cli.py <项目> lint [--sdk <SDK>]` |
| `scripts/analyze.py` | 项目结构分析（labels/screens/悬空引用，带行号，离线可用） | `python scripts/analyze.py <项目路径> [-v]` |
| `scripts/check_assets.py` | 资源完整性检查（.rpy 引用 vs 实际文件，报缺失/孤设） | `python scripts/check_assets.py --path <项目路径>` |
| `scripts/setup_fonts.py` | 字体适配（detect 检测 / config 生成配置 / fallback 回退链 / list 推荐） | `python scripts/setup_fonts.py detect --path <项目路径>` |
| `scripts/setup_i18n.py` | 多语言基础设施（生成 tl/ 目录、语言 Screen、字体配置，不含翻译内容） | `python scripts/setup_i18n.py --path <项目路径> --lang zh en ja` |
| `scripts/optimize_assets.py` | 批量压缩图片/音频减小包体积（pngquant/jpegoptim/ffmpeg 缺失时自动降级为复制） | `python scripts/optimize_assets.py --input ./game/images --output ./out` |
| `scripts/tl_check.py` | tl 翻译文件质检 v3（三级报告 + `--fix`。分级细则与崩溃边界是独有知识，**唯一完整出处 = 下方注意事项 tl_check 行**，此处不重复） | `python scripts/tl_check.py <项目路径> --lang schinese [--fix] [--max-examples N]` |

## Trigger 关键词

| 你说 | 它做 |
|------|------|
| "检查代码有没有问题" | cli.lint 语法检查 |
| "打包成 Windows 版 / APK / Web 版" | cli.distribute / android_build / web_build |
| "分析项目结构"、"看看有多少 label" | analyze 结构分析 |
| "添加中文翻译"、"导出翻译" | cli.translate / extract_strings / merge_strings |

## 快速入门

```bash
python scripts/cli.py "D:/my_game" lint             # 语法检查（退出码透传 SDK）
python scripts/analyze.py "D:/my_game" -v           # 结构分析：labels/screens/悬空引用
python scripts/check_assets.py --path "D:/my_game"  # 资源缺失/孤设
```

需要库调用（批量场景、自定义编排）时再 import：`RenPyCLI().lint(path)`、`Analyzer(path).analyze().report()`，方法签名与返回值见 [references/sdk_config.md](references/sdk_config.md)。

## 注意事项

| 场景 | 说明 |
|------|------|
| **项目体检（优先用现成工具）** | renpy-tools 工具包（**已内置 skill：`renpy-dev/scripts/`**，纯标准库零依赖）统一入口：`python <skill>/renpy-dev/scripts/renpy-tools-cli.py all <项目> -l schinese`。子命令：`crash` 崩溃风险、`untranslated` 空译文、`charname` 名字框漏译、`integrity` 变量/标签完整性、`label` 标签问题、`all` 全跑；仅 `lint` 子命令需要 SDK（`--sdk` 参数或向上扫描 SDK 目录定位）。闪退/缺句/名字英文先跑这个 |
| **翻译文件质检（tl 侧唯一工具）** | 上面工具跳过 tl 目录；用**内置**的 `python scripts/tl_check.py <项目> --lang schinese [--fix]` 查翻译侧隐患，按级别输出：**崩溃级**（未知文本标签、关闭无开放标签、不接受关闭的标签、未闭合大括号、`%(...)s` 丢类型字符——引擎在 `config.safe_text=False`（默认）时显示到该行直接 raise；工具会读取项目配置自动降级）、**显示级**（`{}` 标签新旧不一致、全角伪标签 `【i】`、空译文、`[]` 插值不匹配）、**提示级**（new==old 的未翻译行，不含在退出码里）。v3 按引擎源码模拟：标签大小写敏感、花括号内空格不剥离。`--fix` 自动修机械性问题（`%(变量名被翻)` 还原、`{ i }`/`{/B}` 规范化）；输出行号是**译文行**，直接定位要改的行。**⚠️ `[]插值不匹配` 虽归显示级，但"变量被改名/多出未定义变量"（`[totaldays]`→`[总天数]`、人名写成 `[Tora]`）引擎同样 KeyError 崩溃，按崩溃级处理：还原变量名或删掉方括号；译文裸 `%`（`50%都是油`）在 safe_text=False 下也崩，写 `%%`。另：发行版常把 .mp3/.ttf 直接放 game/ 根目录，check_assets 已扫描根目录 |
| 反编译 .rpyc / 提台词 / 剧情地图 | 用已装的 **renpy-script-decompile** 技能（无需 unrpyc，纯 Python 解 slot + pickle stub） |
| SDK 路径 | 自动检测（`sdk_common.py`）：`sdk_path=` 参数 → 环境变量 `RENPY_SDK` → 向上查找 → 已知路径；本机新装 SDK 只需在 `_KNOWN_SDK_PATHS` 追加一行 |
| 错误诊断 | **没有诊断脚本**——把 log.txt/traceback 直接给 AI 判读即可，比正则匹配准 |
| **旧引擎发行版（装不了 SDK 时）** | 别用本 skill 的 SDK CLI 判版本兼容——≥8.0 的 lint 会把 `config.label_callbacks` 当合法，掩盖 7.x 崩溃。改用**游戏自带引擎**就地验证：`cd <游戏根目录> && ./lib/windows-x86_64/python.exe <启动脚本>.py . lint`（发行版 `lib/<平台>/python.exe` 就是完整解释器，还支持 `test <用例>` 跑界面；**跑 test 必须加 `SDL_VIDEODRIVER=windows`**，否则 dummy 驱动无 OpenGL 报错，属环境问题非游戏问题）。版本兼容坑见 [renpy-user/references/renpy_gotchas.md](../renpy-user/references/renpy_gotchas.md) |
| 测试 | 没有测试脚本——Ren'Py testcase 语法（`run`/`click`/`advance until screen`/`assert eval`）AI 直接写在 .rpy 里，用 `renpy.py 项目 test` 执行 |
| 存档/解包/汉化补丁 | 玩家侧需求 → 加载 **renpy-user** 的 `references/player_tools.md` |
| 游戏内容 | 需要写剧情/设画面/加系统？→ 加载 **renpy-user** Skill |
| 导出 JSON | 已删除 export.py——官方 `translate` 命令生成标准翻译文件，够用 |

## 进阶参考

[SDK 配置 & CLI 命令速查](references/sdk_config.md) — 自动检测逻辑、全部 CLI 命令

[renpy-tools 工具包边界](references/tools_boundaries.md) — 各工具通用度分级（通用/半通用/专用）、写操作风险表、引擎版本经验；半通用工具换游戏前先看这页

[剧本 → 脚本工作流](references/text2script_workflow.md) — 原始剧本转 .rpy 的拆分/命名/演出注释规范，及资产文档格式

[译文润色方法](references/translation_polish.md) — 双角色两阶段润色工作流与 LinguaGacha 路线（风格前置/Agent 审校），含 token 成本对照；按预算与范围自选

## 版本边界

目标 SDK: Ren'Py ≥ 8.0。SDK 不可达时仅警告，不阻塞（可能脱机生成代码供其他环境使用）。
