# Ren'Py Tools — 翻译检查与修复工具集

> **已随 skill 内置**：本目录位于 skill 的 `scripts/`（历史版本曾置于 `tools/`），纯 Python 标准库、零 SDK 依赖、
> 零绝对路径，整体拷贝即可用。SDK 仅 `lint` 子命令需要（`--sdk` 参数或向上扫描 SDK 目录定位）。
>
> 去重说明：翻译文件静态质检用 `sdk/tl_check.py`（v3，问题分级，已取代旧 v2）；
> 多语言初始化统一用 `sdk/setup_i18n.py`（重构版，原始版已移除）；
> `checks/lint_rpy.py`（.rpy 格式错误码 E001–E005，不需 SDK）与 `checks/lint_report.py`
> （按文件汇总的 lint 报告）是独立小工具、未入 CLI，与 tl_check 定位不同、不互相取代。

> 工具定位是修补检测，不代替专门翻译打包软件。

## 快速开始

```bash
# 列出所有工具
python renpy-tools-cli.py list

# 一键检测：14 项只读检查（参数会原样传给每个子脚本）
python renpy-tools-cli.py all MyGame-1.0-pc -l schinese

# AI 翻译后核心检查：角色、变量、标签结构/参数、转义
python renpy-tools-cli.py integrity MyGame-1.0-pc -l schinese

# 空译文/原文=译文（吃 tl 目录，不是项目目录）
python renpy-tools-cli.py untranslated MyGame-1.0-pc/game/tl/schinese --all

# SDK lint（完整性检查会再调用一次）
python renpy-tools-cli.py lint MyGame-1.0-pc --sdk D:/renpy-sdk
```

`all` 覆盖：`ui` `misuse` `func` `auto` `charname` `crash` `fontcheck` `langcheck`
`integrity` `label` `type` `duplicate` `button` `untranslated`。

两点与直觉不同，按下面理解才不会误判：

- **`untranslated` 吃 tl 目录**，`all` 会自动把 `<项目>` 换算成
  `<项目>/game/tl/<lang>` 再传给它；单独调用时必须自己传 tl 目录。
- **`all` 的退出码 1 = 查出了问题**，不是脚本崩溃（崩溃会打印 traceback）。
  `integrity` / `untranslated` / `charname` / `duplicate` / `button` 需要
  `game/tl/<lang>` 存在；没有时 `all` 会明确列出跳过了哪些项并提示先跑
  `setup_i18n`，不会报一堆「目录不存在」。

`urm` 是写入类，不进 `all`。

## AI 翻译安全流程

```powershell
# 端点与 Key 都只放环境变量，不写入源码或 JSON（OpenAI 兼容端点）
$env:RENPY_TRANSLATE_API_URL = "https://你的端点/v1/chat/completions"

cd D:/path/to/scripts/translate
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
├── renpy-tools-cli.py                  🏠 统一 CLI 入口 (30 个子命令，双击或命令行运行)
├── unrpyc.py                           🔓 rpyc 反编译兜底 (下载固定 commit 的 unrpyc 源码后 import 执行)
├── README.md                           📄 本说明
├── sdk/                                🛠️ SDK CLI 封装（需 Ren'Py SDK，另见 references/sdk_config.md）
│   ├── sdk_common.py                   ── SDK 路径检测共用模块（本组依赖）
│   ├── cli.py                          ── SDK CLI 封装: Lint/编译/打包/运行/翻译
│   ├── analyze.py                      ── 项目结构分析 (labels/screens/悬空引用)
│   ├── check_assets.py                 ── 资源完整性检查 (缺失/孤设；引用会与 .rpa 归档名比对)
│   ├── check_fonts.py                  ── 字体接入测试 (引用存在性含 .rpa/引擎字体、CJK 语言接入)
│   ├── check_i18n.py                   ── 多语言链路测试 (Language 入口/默认语言/strings 覆盖)
│   ├── setup_fonts.py                  ── 字体适配 (detect/config/fallback/list)
│   ├── setup_i18n.py                   ── 多语言基础设施 (tl/ 目录、语言 Screen)
│   ├── optimize_assets.py              ── 批量压缩图片/音频 (缺压缩器时逐文件降级并如实报告，全量降级退出码 1)
│   └── tl_check.py                     ── tl 翻译文件质检 v3 (三级报告 + --fix)
├── checks/                            🔍 翻译质量检查与审计
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
│   ├── check_translation_integrity.py  ── 翻译完整性: 角色/任意表达式/标签结构/转义
│   ├── check_untranslated.py           ── 智能未翻译检测 (支持 --csv 导出)
│   ├── check_charname_translation.py   ── 角色名字框完整性审计 (可 --stub 生成骨架)
│   ├── renpy_screen_calls.json.example ── 自定义 screen 名清单模板 (改名成 .json 生效，见 references/tools_boundaries.md)
│   └── check_crash_risks_guide.md       ── 崩溃检测使用说明
├── translate/                            🌐 翻译写入类工具（只读检查器已全部归位到 checks/）
│   ├── README.md                       ── 本组用法与安全规则
│   ├── autotranslate.py                ── AI 翻译流水线 (扫描→翻译→应用)
│   ├── sync_namebox_translation.py     ── 角色名字框同步 (Character → translate strings)
│   ├── patch_renpy_say.py              🔧 修补 Python renpy.say() 硬编码英文
│   ├── renpy_say_replacements.csv      ── patch_renpy_say.py 外部替换表
│   ├── patch_renpy_say_guide.md         ── 上述工具用法说明
│   ├── fix_missing_tags.py             ── 修复翻译中丢失的文本标签
│   ├── fix_translation_comments.py     ── 修复翻译注释行
│   └── autotranslate_troubleshooting.md ── autotranslate 排错手册
├── polish/                                ✨ 译文润色原子化管线 (配合 references/translation_polish.md)
│   ├── README.md                       ── 管线图、AI 润色循环与实测注意
│   ├── _say_parse.py                   ── say 条目适配器 (解析统一走 shared/rpy_syntax.py)
│   ├── extract_say.py                  ── 抽取全量 say 条目 (锚点与 autotranslate 兼容)
│   ├── screen_suspicious.py            ── 翻译腔规则筛行 (规则在顶部 RULES)
│   ├── screen_quality.py              ── 硬性质校筛行 (外文残留/假名残片/半角标点/相似度漏翻；判定经验移植自 LinguaGacha)
│   └── merge_polish.py                 ── AI 润色稿合并成回填批次
├── names/                            🏷️ 人名翻译统一
│   ├── README.md                       ── 分工、v6 三步流程说明与术语表格式
│   ├── unify_name_translations.py      ── v6 主流程 (收集→分类→统一，含审核/回滚)
│   ├── apply_glossary_body.py          ── 批式正文人名统一 (glossary 直改，产出 apply 批次)
│   ├── make_glossary.py                ── 术语表草稿生成 (Character 定义 + strings 配对取证)
│   └── renpy_skip_files.json.example   ── 跳过文件名清单模板 (改名成 .json 生效)
├── linear/                            🎬 剧情线性模式
│   ├── linear_mode.py                  ── analyze 分析 / add 生成补丁 / modify 校验事件表
│   └── README.md                       ── 用法与边界说明
├── setup/                                ⚙️ 项目适配与打包环境
│   ├── README.md                       ── 本组用法
│   ├── switch_default_language.py      ── 切换默认语言
│   ├── fix_lang_button.py              ── 修语言按钮写死 / 缺目标语言项
│   ├── add_fonts.py                    ── 字体添加
│   ├── add_performance_panel.py        ── 性能面板
│   ├── remove_translated.py            🧹 移除文件名 _translated 重复后缀
│   ├── urm_install.py                 🧰 URM 安装/卸载/体检（不代下载，--apply 才落盘）
│   ├── remove_translated_guide.md       ── 上述工具用法说明
│   ├── patch_android_tablet.py         ── 安卓平板适配补丁 (需拷入 SDK 内运行)
│   └── patch_android_tablet.bat        ── 上述补丁的双击交互入口
├── shared/                                💾 共享模块
│   ├── backup.py                       ── 首次 .bak + 原子写入
│   ├── base_checker.py                 ── 检查器契约层（name/summary/takes/requires_tl/read_only + CheckContext）
│   ├── tool_registry.py                ── 门面注册表：子命令→路径 + 分组（检查器元数据读各脚本 CHECKER）
│   ├── rpa_index.py                    ── .rpa 归档文件名清单提取（只读索引，不碰数据）
│   └── rpy_syntax.py                   ── Ren'Py 翻译条目/字符串/插值解析
└── tests/                               🧪 单元测试
    ├── test_renpy_tools.py            ── 解析、回填安全、CLI 回归测试（176 用例）
    ├── test_say_parse_contract.py     ── say 解析器契约回归（9 用例，原差分验证的可复现版）
    ├── test_crash_risks.py            ── 崩溃检测器误报边界回归（23 用例）
    ├── test_config_loaders.py         ── 外置 JSON 配置加载器（13 用例）
    ├── test_cli_surface.py            ── CLI 门面 30 子命令 --help 契约（7 用例）
    ├── test_fonts_i18n.py             ── check_fonts/check_i18n/rpa_index 契约（22 用例）
    ├── test_urm_install.py            ── URM 安装门界/回滚/不越权（29 用例）
    ├── test_checks_zoo.py             ── checks/ 零覆盖检查器契约 + 重复函数形态 + 转义回归（37 用例）
    ├── test_screen_quality.py         ── 硬性质校筛行契约 + 误报边界回归（24 用例，含 2026-10-06 截图例句锚点）
    ├── test_checker_contract.py       ── 检查器契约层 + 只读红线 + CLI/run 退出码一致（27 用例）
    ├── test_tool_registry.py          ── 门面注册表自洽 + -l 透传防复发 + requires_tl 实测校验（25 用例）
    ├── test_repo_consistency.py       ── 文档 ↔ 代码自洽：链接 / 目录 / 脚本清单 / 数字（10 用例）
    └── test_count.py                  ── 用例总数自证：数自己，断言等于文档写的数（2 用例）
```

## 典型工作流

```
1. python sdk/setup_i18n.py ...                    → 初始化多语言（建 game/tl/）
2. python renpy-tools-cli.py all <项目> -l schinese → 一键检测（14 项）
3. python renpy-tools-cli.py integrity <项目>      → 变量/角色/标签结构与转义
4. python renpy-tools-cli.py untranslated <tl目录> --csv → 缺句清单
5. python names/unify_name_translations.py ...    → 统一角色名翻译
6. python renpy-tools-cli.py all <项目> -l schinese → 最终校验（退出码 0 才算收尾）
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
- 游戏自定义程度高（场景强依赖沙盒 flag）时，用补丁里的 Variable Helper 手动补变量；详见 `linear/README.md`

## 备份机制

所有会**修改已有文件**的工具在首次写入前，会将原始文件备份为同目录下的 `.bak`（例如 `script.rpy` → `script.rpy.bak`）。

- `.bak` 只在首次修改时生成，后续不会覆盖，以保留最原始版本
- 备份采用 **fail-closed**：备份创建失败会停止写入，不会“只警告后继续覆盖”
- AI 翻译回填和缓存写入使用原子替换，避免进程中断留下半个文件
- 如需恢复，可在 PowerShell 执行 `Copy-Item script.rpy.bak script.rpy -Force`
- `unify_name_translations.py` 仍保留整目录 `.fix_name_backup/` 快照和单文件 `.bak` 双层保障

## 回归测试

纯标准库 unittest，无需 pytest（装了也能用）：

```bash
cd tests
python -m unittest discover -v          # 全部（当前 404 用例，约 20s）
python -m unittest test_renpy_tools -v  # 解析/回填安全/CLI 批次（176）
python -m unittest test_crash_risks -v  # 崩溃检测器误报边界（23）
python -m unittest test_say_parse_contract -v  # say 解析契约（9）
python -m unittest test_config_loaders -v # 外置 JSON 配置加载器（13）
python -m unittest test_cli_surface -v  # CLI 门面：30 子命令 --help 全通（7）
python -m unittest test_fonts_i18n -v   # 字体/多语言链路测试 + rpa_index（22 用例）
python -m unittest test_urm_install -v  # URM 门界/回滚/不越权（29 用例）
python -m unittest test_checks_zoo -v   # checks/ 零覆盖检查器契约 + 转义回归（37 用例）
python -m unittest test_screen_quality -v # 硬性质校筛行：残留/假名/标点/相似度（24 用例）
python -m unittest test_repo_consistency -v # 文档 ↔ 代码自洽（10 用例）
python -m unittest test_count -v        # 用例总数自证（2 用例）
```

跑测试会生成 `__pycache__`。不想让它留在工作区：

```bash
# PowerShell
$env:PYTHONDONTWRITEBYTECODE = "1"
# 或 Linux/macOS
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover
```

（`.gitignore` 已忽略 `__pycache__/`，但打包/分发 skill 时记得先清一遍。）

## 覆盖范围与盲区

**有测试**：公共解析层（`shared/rpy_syntax.py`、`shared/backup.py`）、`tl_check`、
`autotranslate` 回填安全、`check_untranslated`、`check_translation_integrity`、
`unify_name_translations`、`fix_missing_tags`、`sync_namebox_translation`、
崩溃检测器 `check_crash_risks`（误报边界双向断言）、`renpy-tools-cli` 参数透传与
`all` 批次范围/tl_dir 换算、CLI 门面 30 子命令的 `--help` 契约、
字体接入测试 `check_fonts` / 多语言链路测试 `check_i18n` / 归档名提取 `rpa_index`、
外置 JSON 配置加载器（`checks/renpy_screen_calls.json`、`names/renpy_skip_files.json`）、
`urm_install` 的引擎版本闸门 / .rpa 加密闸门 / 安装回滚幂等 / 不越权删除、
`checks/` 中 `check_type_safety` / `check_duplicate_translations` / `check_func_text` / `check_ui_text`、
`check_translation_misuse` / `check_auto_trans` / `check_button_missing_translation` 的实际契约。

**零测试**（使用时留意）：`sdk/` 下 `analyze` / `check_assets` /
`setup_i18n` / `setup_fonts`、`setup/` 下 6 个写入类工具、
`checks/` 下 `check_label_issues`（613 行）与 `lint_check`、
`linear_mode.py`（975 行）、`make_glossary.py`。

`optimize_assets.py` 曾是真 bug 源（`.m4a` 未处理导致 `TypeError` 崩溃、
GBK 控制台 emoji `UnicodeEncodeError`、把全量降级说成「优化完成」）。已修，
但仍无自动化测试——它依赖外部二进制（pngquant/jpegoptim/ffmpeg），
没有这些工具的机器上只会走降级路径，测不出压缩逻辑本身。

写入类工具没有自动化测试的替代品：默认试运行 + `--apply` 才落盘 + 首次 `.bak`
是它们的实际安全网，改动后请在示例项目上跑一遍试运行/落盘/回滚三连。

## 目录名（2026-10-05 起全 ASCII）

原先 8 个分组目录是中文名，macOS 的 NFD 归一化会让跨系统 checkout 后
`import` 找不到模块。现已全部 ASCII 化；从老版本升级时按下表改名：

| 老目录 | 现目录 |
|--------|--------|
| `错误检测/` | `checks/` |
| `翻译相关/` | `translate/` |
| `润色/` | `polish/` |
| `统一名称/` | `names/` |
| `线性模式/` | `linear/` |
| `设置/` | `setup/` |
| `公共/` | `shared/` |
| `测试/` | `tests/` |

## 许可证

MIT License — 可自由使用、修改、分发。
