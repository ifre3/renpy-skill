# Ren'Py Tools — 翻译检查与修复工具集

> **已随 skill 内置**：本目录位于 skill 的 `renpy-dev/tools/`，纯 Python 标准库、零 SDK 依赖、
> 零绝对路径，整体拷贝即可用。SDK 仅 `lint` 子命令需要（会经 `sdk_common.detect_sdk()` 定位）。
>
> 去重说明：翻译文件静态质检用 `../scripts/tl_check.py`（v3，问题分级，已取代本目录旧 v2）；
> `设置/setup_i18n.py` 是本套件的原始版本，`../scripts/setup_i18n.py` 是重构版，二选一即可。

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
$env:RENPY_TRANSLATE_API_KEY = "你的密钥"

cd D:/path/to/tools/翻译相关
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
tools/
├── renpy-tools-cli.py                  🏠 统一 CLI 入口 (双击或命令行运行)
├── patch_android_tablet.bat            🖥️ 安卓平板模式打包 (双击运行)
├── README.md / LICENSE                 📄 项目说明与许可
├── 错误检测/                            🔍 翻译质量检查与审计
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
│   ├── lint_check.py                   ── SDK lint + 翻译专项检查
│   ├── lint_report.py                  ── lint 结果分析报告
│   ├── lint_rpy.py                     ── .rpy 文件格式检查 (引号/编码/重复ID等)
│   └── check_crash_risks_说明.md       ── 崩溃检测使用说明
├── 文档/                                📚 开发文档与笔记
│   ├── RenPy汉化常见问题手册.md         ── 汉化常见问题完整手册
│   ├── RenPy_AI翻译常见问题诊断与解决方案.md ── AI 翻译问题诊断方案
│   ├── crash_detection_20260629.md      ── 崩溃检测脚本开发总结
│   ├── p3_split_and_cli_20260629.md     ── P3 任务报告：CLI 拆分
│   ├── tep技能设计.txt                  ── 技能流程设计笔记
│   └── 常见问题罗列.txt                 ── AI 翻译常见问题清单
├── 翻译相关/                            🌐 翻译操作与修补
│   ├── check_translation_integrity.py  ── 翻译完整性: 角色/任意表达式/标签结构/转义
│   ├── check_untranslated.py           ── 智能未翻译检测 (支持 --csv 导出)
│   ├── autotranslate.py                ── AI 翻译流水线 (扫描→翻译→应用)
│   ├── sync_namebox_translation.py     ── 角色名字框同步 (Character → translate strings)
│   ├── patch_renpy_say.py              🔧 修补 Python renpy.say() 硬编码英文
│   ├── fix_missing_tags.py             ── 修复翻译中丢失的文本标签
│   └── fix_translation_comments.py     ── 修复翻译注释行
├── 统一名称/                            🏷️ 人名翻译统一
│   ├── unify_name_translations.py      ── v6 主流程 (匹配→审核→统一)
│   ├── unify_names_v2.py               ── v2 频率统计 (deprecated)
│   └── deprecated/                     ── 已弃用脚本
├── 线性模式/                            🎬 剧情线性模式
│   ├── linear_mode.py                  ── analyze 分析 / add 生成补丁 / modify 校验事件表
│   └── README.md                       ── 用法与边界说明
├── 设置/                                ⚙️ 项目配置
│   ├── setup_i18n.py                   ── 多语言初始化
│   ├── switch_default_language.py      ── 切换默认语言
│   ├── add_fonts.py                    ── 字体添加
│   ├── add_performance_panel.py        ── 性能面板
│   ├── remove_translated.py            🧹 移除文件名 _translated 重复后缀
│   └── patch_android_tablet.py         ── 安卓平板适配补丁
├── 公共/                                💾 共享模块
│   ├── backup.py                       ── 首次 .bak + 原子写入
│   └── rpy_syntax.py                   ── Ren'Py 翻译条目/字符串/插值解析
├── 补丁集/                             📋 外部替换规则
│   └── renpy_say_replacements.csv      ── patch_renpy_say.py 替换表
└── 测试/                               🧪 单元测试
    └── test_renpy_tools.py             ── 解析、回填安全、CLI 回归测试
```

## 典型工作流

```
1. python 设置/setup_i18n.py ...                 → 初始化多语言
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
