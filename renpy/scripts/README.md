# Ren'Py Tools — 翻译检查与修复工具集

> **已随 skill 内置**：本目录位于 skill 的 `scripts/`（历史版本曾置于 `tools/`），纯 Python 标准库、零 SDK 依赖、
> 零绝对路径，整体拷贝即可用。SDK 仅 `lint` 子命令需要（`--sdk` 参数或向上扫描 SDK 目录定位）。
>
> 去重说明：翻译文件静态质检用 `sdk/tl_check.py`（v3，问题分级，已取代旧 v2）；
> 多语言初始化统一用 `sdk/setup_i18n.py`（重构版，原始版已移除）。

> 工具定位是修补检测，不代替专门翻译打包软件。

## 快速开始

```bash
# 列出所有工具
python renpy-tools-cli.py list

# 一键检测（参数会原样传给每个子脚本）
python renpy-tools-cli.py all MyGame-1.0-pc -l schinese

# AI 翻译后核心检查：角色、变量、标签结构/参数、转义
python renpy-tools-cli.py integrity MyGame-1.0-pc -l schinese

# 空译文/原文=译文
python renpy-tools-cli.py untranslated MyGame-1.0-pc/game/tl/schinese --all

# SDK lint（完整性检查会再调用一次）
python renpy-tools-cli.py lint MyGame-1.0-pc --sdk D:/renpy-sdk
```

## AI 翻译安全流程

```powershell
# 端点与 Key 都只放环境变量，不写入源码或 JSON（OpenAI 兼容端点）
$env:RENPY_TRANSLATE_API_URL = "https://你的端点/v1/chat/completions"

cd D:/path/to/scripts/翻译相关
python autotranslate.py scan game/tl/schinese
python autotranslate.py translate game/tl/schinese
python autotranslate.py apply game/tl/schinese --dry-run
python autotranslate.py apply game/tl/schinese
```

- 回填前会核对**行号、原文、目标角色和目标是否为空**，不会只凭“附近几行”写入。
- JSON 回填默认禁止覆盖非空译文；确需覆盖时显式使用 `--overwrite`。
- `status=warn` 的译文默认不回填；人工修正后使用 `--include-warnings`。
- 文件采用同目录临时文件 + `os.replace` 原子写入，并强制保留首次 `.bak`。
- 历史版本曾内置过 API Key；即使已删除，也应立即在服务商后台**撤销并轮换**。

## 目录结构

```
scripts/
├── renpy-tools-cli.py                  🏠 统一 CLI 入口 (26 个子命令，双击或命令行运行)
├── unrpyc.py                           🔓 rpyc 反编译兜底 (下载 unrpyc 源码后 import 执行)
├── README.md                           📄 本说明
├── sdk/                                🛠️ SDK CLI 封装（需 Ren'Py SDK，另见 references/sdk_config.md）
│   ├── sdk_common.py                   ── SDK 路径检测共用模块（本组依赖）
│   ├── cli.py                          ── SDK CLI 封装: Lint/编译/打包/运行/翻译
│   ├── analyze.py                      ── 项目结构分析 (labels/screens/悬空引用)
│   ├── check_assets.py                 ── 资源完整性检查 (缺失/孤设)
│   ├── setup_fonts.py                  ── 字体适配 (detect/config/fallback/list)
│   ├── setup_i18n.py                   ── 多语言基础设施 (tl/ 目录、语言 Screen)
│   ├── optimize_assets.py              ── 批量压缩图片/音频
│   └── tl_check.py                     ── tl 翻译文件质检 v3 (三级报告 + --fix)
├── 错误检测/                            🔍 翻译质量检查与审计
│   ├── README.md                       ── 本组用法速览
│   ├── common.py                       ── 共享模块 (编码/输出/翻译加载)
│   ├── check_ui_text.py                ── screen UI 文本缺少 _()
│   ├── check_translation_misuse.py     ── Bug: Character[var] 缺 !t / 翻译函数误用
│   ├── check_func_text.py              ── renpy.input/notify/自定义屏幕调用 缺少 _()
│   ├── check_auto_trans.py             ── 交叉引用 Character 名字框 / menu 选项
│   ├── check_duplicate_translations.py ── 检测重复 old 字符串
│   ├── check_button_missing_translation.py ── 检测按钮文本未被 strings 捕获
│   ├── check_crash_risks.py            ── 运行时崩溃风险检测 (内置遮蔽/map/除零等)
│   ├── check_label_issues.py           ── Ren'Py 标签问题 (未定义/重复/不可达)
│   ├── check_type_safety.py            ── Python 类型安全
│   ├── lint_check.py                   ── SDK lint + 翻译专项检查 (CLI `lint` 命令)
│   ├── lint_report.py                  ── lint 结果分析报告 (独立使用，未入 CLI)
│   ├── lint_rpy.py                     ── .rpy 文件格式检查 (独立使用，未入 CLI)
│   └── check_crash_risks_说明.md       ── 崩溃检测使用说明
├── 翻译相关/                            🌐 翻译操作与修补
│   ├── README.md                       ── 本组用法与安全规则
│   ├── check_translation_integrity.py  ── 翻译完整性: 角色/任意表达式/标签结构/转义
│   ├── check_untranslated.py           ── 智能未翻译检测 (支持 --csv 导出)
│   ├── check_charname_translation.py   ── 角色名字框完整性审计 (可 --stub 生成骨架)
│   ├── autotranslate.py                ── AI 翻译流水线 (扫描→翻译→应用)
│   ├── sync_namebox_translation.py     ── 角色名字框同步 (Character → translate strings)
│   ├── patch_renpy_say.py              🔧 修补 Python renpy.say() 硬编码英文
│   ├── renpy_say_replacements.csv      ── patch_renpy_say.py 外部替换表
│   ├── patch_renpy_say_说明.md         ── 上述工具用法说明
│   ├── fix_missing_tags.py             ── 修复翻译中丢失的文本标签
│   ├── fix_translation_comments.py     ── 修复翻译注释行
│   └── RenPy_AI翻译常见问题诊断与解决方案.md ── autotranslate 排错手册
├── 润色/                                ✨ 译文润色原子化管线 (配合 references/translation_polish.md)
│   ├── README.md                       ── 管线图、AI 润色循环与实测注意
│   ├── _say_parse.py                   ── say 条目适配器 (解析统一走 公共/rpy_syntax.py)
│   ├── extract_say.py                  ── 抽取全量 say 条目 (锚点与 autotranslate 兼容)
│   ├── screen_suspicious.py            ── 翻译腔规则筛行 (规则在顶部 RULES)
│   └── merge_polish.py                 ── AI 润色稿合并成回填批次
├── 统一名称/                            🏷️ 人名翻译统一
│   ├── README.md                       ── 分工、v6 三步流程说明与术语表格式
│   ├── unify_name_translations.py      ── v6 主流程 (收集→分类→统一，含审核/回滚)
│   ├── unify_names.py                  ── 批式正文人名统一 (glossary 直改，产出 apply 批次)
│   └── make_glossary.py                ── 术语表草稿生成 (Character 定义 + strings 配对取证)
├── 线性模式/                            🎬 剧情线性模式
│   ├── linear_mode.py                  ── analyze 分析 / add 生成补丁 / modify 校验事件表
│   └── README.md                       ── 用法与边界说明
├── 设置/                                ⚙️ 项目适配与打包环境
│   ├── README.md                       ── 本组用法
│   ├── switch_default_language.py      ── 切换默认语言
│   ├── add_fonts.py                    ── 字体添加
│   ├── add_performance_panel.py        ── 性能面板
│   ├── remove_translated.py            🧹 移除文件名 _translated 重复后缀
│   ├── remove_translated_说明.md       ── 上述工具用法说明
│   ├── patch_android_tablet.py         ── 安卓平板适配补丁 (需拷入 SDK 内运行)
│   └── patch_android_tablet.bat        ── 上述补丁的双击交互入口
├── 公共/                                💾 共享模块
│   ├── backup.py                       ── 首次 .bak + 原子写入
│   └── rpy_syntax.py                   ── Ren'Py 翻译条目/字符串/插值解析
└── 测试/                               🧪 单元测试
    ├── test_renpy_tools.py             ── 解析、回填安全、CLI 回归测试（168 用例）
    └── test_say_parse_contract.py      ── say 解析器契约回归（9 用例，原差分验证的可复现版）
```

## 典型工作流

```
1. python sdk/setup_i18n.py ...                  → 初始化多语言
2. python renpy-tools-cli.py all <项目>          → 一键检测
3. python 翻译相关/check_translation_integrity.py <项目>
4. python 翻译相关/check_untranslated.py <tl目录> --csv
5. python 统一名称/unify_name_translations.py ... → 统一角色名翻译
6. python 翻译相关/check_translation_integrity.py <项目> → 最终校验
```

## 线性模式（剧情自动串联）

```bash
# 分析游戏是否内置线性机制（如 LostInYou 的 game_mode / get_event_list）
python renpy-tools-cli.py linear analyze MyGame-1.0-pc

# 纯沙盒游戏 → 生成剧情目录补丁（悬浮按钮 + 顺序目录 + 自动跳过导航）
python renpy-tools-cli.py linear add MyGame-1.0-pc

# 自带事件表的游戏 → 校验完整性、导出顺序、追加新版本遗漏事件
python renpy-tools-cli.py linear modify MyGame-1.0-pc --csv events.csv --append-new
```

- `add` 只新增 `game/zzz_linear_mode.rpy`，不改原脚本，删除即还原
- 游戏自定义程度高（场景强依赖沙盒 flag）时，用补丁里的 Variable Helper 手动补变量；详见 `线性模式/README.md`

## 备份机制

所有会**修改已有文件**的工具在首次写入前，会将原始文件备份为同目录下的 `.bak`（例如 `script.rpy` → `script.rpy.bak`）。

- `.bak` 只在首次修改时生成，后续不会覆盖，以保留最原始版本
- 备份采用 **fail-closed**：备份创建失败会停止写入，不会“只警告后继续覆盖”
- AI 翻译回填和缓存写入使用原子替换，避免进程中断留下半个文件
- 如需恢复，可在 PowerShell 执行 `Copy-Item script.rpy.bak script.rpy -Force`
- `unify_name_translations.py` 仍保留整目录 `.fix_name_backup/` 快照和单文件 `.bak` 双层保障

## 许可证

MIT License — 可自由使用、修改、分发。
