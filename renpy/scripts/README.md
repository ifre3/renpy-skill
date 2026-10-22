# Ren'Py Tools — 翻译检查与修复工具集

> **已随 skill 内置**：位于 skill 的 `scripts/`，纯 Python 标准库、零 SDK 依赖、零绝对路径，整体拷贝即可用。
> SDK 仅 `lint` 子命令需要（`--sdk` 参数或向上扫描 SDK 目录定位）。
> 工具定位是修补检测，不代替专门的翻译打包软件。

## 快速开始

```bash
python renpy-tools-cli.py list                          # 列出所有工具
python renpy-tools-cli.py all MyGame-1.0-pc -l schinese # 一键检测（18 项只读检查）
python renpy-tools-cli.py integrity MyGame-1.0-pc -l schinese  # AI 翻译后核心检查
python renpy-tools-cli.py untranslated MyGame-1.0-pc/game/tl/schinese --all  # 空译文
python renpy-tools-cli.py lint MyGame-1.0-pc --sdk D:/renpy-sdk              # SDK lint
python checks/tl_check.py MyGame-1.0-pc --glossary 术语表.xlsx               # 术语一致性（可选）
python checks/tl_check.py MyGame-1.0-pc --lang-ratio 0.75                    # 语言分块判定（可选）
```

`all` 覆盖：`ui` `misuse` `func` `auto` `charname` `crash` `fontcheck` `langcheck`
`integrity` `label` `type` `duplicate` `button` `typography` `tlcheck` `fmtlint` `untranslated`。

两点与直觉不同，按下面理解才不会误判：

- **`untranslated` 吃 tl 目录**（不是项目目录），`all` 会自动换算；单独调用时必须自己传 tl 目录。
- **`all` 退出码 1 = 查出了问题**，不是脚本崩溃（崩溃会打印 traceback）。缺 `game/tl/<lang>` 时 `all` 会列明跳过哪些项并提示先跑 `setup_i18n`。

`urm` 是写入类，不进 `all`。

## 目录结构

```
scripts/
├── renpy-tools-cli.py                  🏠 统一 CLI 入口 (35 个子命令，双击或命令行运行)
├── unrpyc.py                           🔓 rpyc 反编译兜底 (下载固定 commit 的 unrpyc 源码后 import 执行)
├── README.md                           📄 本说明
├── sdk/                                🛠️ SDK CLI 封装（需 Ren'Py SDK，另见 references/sdk_config.md）
│   ├── sdk_common.py                   ── SDK 路径检测共用模块（本组依赖）
│   ├── cli.py                          ── SDK CLI 封装: Lint/编译/打包/运行/翻译
│   ├── analyze.py                      ── 项目结构分析 (labels/screens/悬空引用)
│   ├── check_assets.py                 ── 资源完整性检查 (缺失/孤设；引用会与 .rpa 归档名比对)
│   └── optimize_assets.py              ── 批量压缩图片/音频 (缺压缩器时逐文件降级并如实报告，全量降级退出码 1)
├── checks/                            🔍 翻译质量检查与审计（均只读；`--fix` 者默认不写，见下方注）
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
│   ├── lint_report.py                  ── fmtlint 的人工深挖视图（old 上下文 + 分文件计数；不入 all）
│   ├── lint_rpy.py                     ── tl 格式层 lint（引号/块ID/行尾/缩进/超长行/长度比；CLI `fmtlint`，入 all）
│   ├── check_translation_integrity.py  ── 翻译完整性: 角色/任意表达式/标签结构/转义
│   ├── check_untranslated.py           ── 智能未翻译检测 (支持 --csv 导出)
│   ├── check_charname_translation.py   ── 角色名字框完整性审计 (可 --stub 生成骨架)
│   ├── tl_check.py                     ── tl 翻译文件质检 v3 (三级报告 + --fix；可选 --glossary 术语/--lang-ratio 语言；CLI `tlcheck`，入 all)
│   ├── tag_repair.py                   ── 标签/插值结构修复层 (供 tl_check --fix --settle 调用)
│   ├── check_fonts.py                  ── 字体接入测试 (CLI `fontcheck`，入 all)
│   ├── check_i18n.py                   ── 多语言链路测试 (CLI `langcheck`，入 all)
│   ├── check_typography.py             ── 字号与排版合理性 (CLI `typography`，入 all)
│   ├── check_payload.py                ── 混淆载荷体检：区分引流/汉化 (CLI `payloadscan`，入 all，只读)
│   ├── renpy_screen_calls.json.example ── 自定义 screen 名清单模板 (改名成 .json 生效，见 references/tools_boundaries.md)
│   └── check_crash_risks_guide.md      ── 崩溃检测使用说明
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
│   ├── plan_batches.py                 ── 批次规划：场景感知切批 + 连续剧本审稿提示词（不截断长句/只输出改动行）+ 批次账本（CLI `polish`）
│   ├── merge_polish.py                 ── AI 审稿稿合并成回填批次（结构守恒门 + 剔除「未改动」行）
│   ├── direct_polish.py                ── 无 API 基于规则的直接润色（半角/重复标点、连续的的、被动“将会”等；--apply 回填 tl）
├── names/                            🏷️ 人名翻译统一
│   ├── README.md                       ── 分工、v6 三步流程说明与术语表格式
│   ├── unify_name_translations.py      ── v6 主流程 (收集→分类→统一，含审核/回滚)
│   ├── apply_glossary_body.py          ── 批式正文人名统一 (glossary 直改，产出 apply 批次)
│   ├── make_glossary.py                ── 术语表草稿生成 (取证 + 默认落游戏根 AiNiee 三栏 xlsx)
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
│   ├── patch_android_tablet.bat        ── 上述补丁的双击交互入口
│   ├── setup_i18n.py                   ── 多语言基础设施 (tl/ 目录、语言 Screen；CLI `i18n`)
│   └── setup_fonts.py                  ── 字体适配 (detect/config/fallback/list)
├── shared/                                💾 共享模块
│   ├── backup.py                       ── 首次 .bak + 原子写入
│   ├── base_checker.py                 ── 检查器契约层（name/summary/takes/requires_tl/read_only + CheckContext）
│   ├── tool_registry.py                ── 门面注册表：子命令→路径 + 分组（检查器元数据读各脚本 CHECKER）
│   ├── rpa_index.py                    ── .rpa 归档文件名清单提取（只读索引，不碰数据）
│   ├── namebox.py                      ── 名字栏识别 + 引擎等价翻译查找（全串精确，见 references/namebox_translation.md）
│   └── rpy_syntax.py                   ── Ren'Py 翻译条目/字符串/插值解析
└── tests/                               🧪 单元测试
    ├── test_renpy_tools.py            ── 解析、回填安全、CLI 回归测试（179 用例）
    ├── test_say_parse_contract.py     ── say 解析器契约回归（9 用例，原差分验证的可复现版）
    ├── test_crash_risks.py            ── 崩溃检测器误报边界回归（23 用例）
    ├── test_config_loaders.py         ── 外置 JSON 配置加载器（13 用例）
    ├── test_cli_surface.py            ── CLI 门面 35 子命令 --help 契约（7 用例）
    ├── test_fonts_i18n.py             ── check_fonts/check_i18n/rpa_index 契约（31 用例）
    ├── test_urm_install.py            ── URM 安装门界/回滚/不越权（29 用例）
    ├── test_checks_zoo.py             ── checks/ 零覆盖检查器契约 + 重复函数形态 + 转义回归（37 用例）
    ├── test_write_tools_smoke.py      ── 零覆盖写工具冒烟：不写脏数据/不建目录/产物定位（14 用例）
    ├── test_polish_batches.py         ── 润色切批：场景不劈开/账本幂等/锚点齐全 + 剧本提示词契约 + Tier A/B 分层 + merge 结构守恒门与未改动行剔除（47 用例）
    ├── test_fmtlint.py              ── tl 格式层 lint：BOM/排版级/E009 误报边界 + 契约（17 用例）
    ├── test_screen_quality.py         ── 硬性质校筛行契约 + 误报边界回归（24 用例，含 2026-10-06 截图例句锚点）
    ├── test_checker_contract.py       ── 检查器契约层 + 只读红线 + CLI/run 退出码一致（27 用例）
    ├── test_tool_registry.py          ── 门面注册表自洽 + -l 透传防复发 + requires_tl 实测校验（25 用例）
    ├── test_repo_consistency.py       ── 文档 ↔ 代码自洽：链接 / 目录 / 脚本清单 / 全库数字声明（12 用例）
    ├── test_tag_repair.py             ── tag_repair 结构修复层：修复正确性 + 健康句不许改动（20 用例）
    ├── test_tl_check_crash.py         ── tl_check 崩溃级规则：裸 % 未转义 + 伪插值[非ASCII] + BOM/行尾不被改写 + 术语一致性/语言分块判定（27 用例）
    ├── test_typography.py             ── 字号与排版合理性：字号下限/outline 阈值/硬编码 size/--no-tl/--severity（20 用例）
    ├── test_names_glossary.py         ── 人名取证：define+颜色标签写法识别 + 动态名与 tl 侧不误收（6 用例）
    ├── test_namebox_shared.py        ── 名字栏共享层：三类说话人识别 + 全串精确匹配 + 标签保留拼接（28 用例）
    └── test_count.py                  ── 用例总数自证：数自己，断言等于文档写的数（2 用例）
```

### checks/ — 只读检查器（想"找出问题"来这）

全部只读，唯一例外是用户显式点名的导出：`check_untranslated --csv`、`check_charname_translation --stub`。会写文件的工具在 `translate/`。

- **检查器契约**：每个检查器声明模块级 `CHECKER`（`name` / `summary` / `takes` / `requires_tl`），门面的子命令→路径映射从这里派生，不再手写 35 项表。漏 `-l` 透传由 `test_tool_registry.py` 防复发；只读红线由 `test_checker_contract.py` 钉死。
- **`check_label_issues.py` 边界**：两遍扫描（先收集全项目标签再判引用），跨文件跳转不误判；只认**语句位置**的 jump/call（屏蔽对白里的 "jump you"）。已知噪音（WARNING 可忽略）：MISSING_RETURN 会把"靠 jump 结束"的标签算上、ORPHAN_LABEL 是没人跳转的标签。默认跳过 `tl/`（`--include-tl` 可开）。
- **名字框机制**：`who` 显示走 `substitute(translate=True)` → `translate_string`，所以名字框是否显示中文**取决于 tl 里有没有 `old "名字"` 完全匹配的条目**，与名字定义在哪无关。审计用 `check_charname_translation.py`（`--stub` 可导出待填骨架）——`check_auto_trans.py` 只覆盖 menu 等字符串，不覆盖仅出现在 `Character("Name")` 里的名字，这个缺口由它补。
- `checks/lint_rpy.py`（格式错误码 E001–E005，不需 SDK）与 `checks/lint_report.py`（按文件汇总）是独立小工具、未入 CLI，与 `tl_check` 定位不同、互不取代。
- **`tl_check` 的两条可选维度**（默认关闭，**不参与 `all`**，规则取自 AiNiee 的 TranslationChecker）：`--glossary <术语表>` 核对原文命中词条时译文有没有用上定稿译名（`.xlsx` 三栏 / `.jsonl` / `.json` 都吃，xlsx 用标准库 zipfile 读，不依赖 openpyxl）；`--lang-ratio <阈值>` 按 20 行分块统计目标语言占比，低于阈值报语言不匹配（启发式，只对 schinese/tchinese/japanese/korean/english 生效）。详见 [../references/tl_check.md](../references/tl_check.md)。

### translate/ — 写入与修补（想"修掉问题"来这）

```powershell
cd scripts/translate
$env:RENPY_TRANSLATE_API_URL = "https://你的端点/v1/chat/completions"
$env:RENPY_TRANSLATE_API_KEY = "你的密钥"          # 只放环境变量，不写入源码或 JSON

python autotranslate.py scan game/tl/schinese     # 1. 扫描空译文（不调 API）
python autotranslate.py translate game/tl/schinese --max-chars 1000   # 2. 翻译到缓存，可中断重跑
python autotranslate.py apply game/tl/schinese --dry-run              # 3. 先预览
python autotranslate.py apply game/tl/schinese                        # 4. 回填
```

安全规则（`#` 原文 / `new` 部分）：

- 回填前核对**行号处的原文、目标角色、目标为空**三者，不凭"附近几行"写入。
- 保护 `{tag}`、`[expression!t]`、`[[`/`{{` 与反斜杠转义；回填前校验数量、参数与嵌套结构。
- 默认禁止覆盖非空译文，确需覆盖显式 `--overwrite`；`status=warn` 默认不回填（`--include-warnings` 才用）。
- `.bak` + 原子替换；备份失败即停止（fail-closed）。
- 只有 `translate` 子命令需要 `requests`；`scan/apply/status` 无需第三方库。

回填 JSON 格式：`[{"file": "chapters/ch1.rpy", "line": 123, "type": "cd", "char": "c_mc", "orig": "Hello [name!t]", "trans": "你好 [name!t]"}]`——`line` 是 `# ...` 注释或 `old` 行的 1 基行号，`orig` 必须与当前文件完全一致。润色管线产出同样走这条通道。

### polish/ — 译文润色（trans 的下游）

`extract_say.py` 抽条目 → `screen_suspicious.py`（翻译腔）+ `screen_quality.py`（硬性质：外文残留/假名/半角标点/相似度漏翻）零 token 筛行 → `direct_polish.py`（可选，无 API 规则层先洗机翻味，--apply 回填） → `plan_batches.py` 按场景切批并生成每批**连续剧本块**提示词（不截断长句、角色为审稿人、只输出改动行） → AI 审稿产出 `fixes.json` → `merge_polish.py` → `translate/autotranslate.py apply --overwrite`。全部不碰 tl 直到回填那一步。**机翻矫正（规则层）与审稿（AI 层）是两层，不要混为一谈**——详见 polish/README.md 与 [../references/translation_polish.md](../references/translation_polish.md) §7。策略与 token 成本同见该文档。

`merge_polish.py` 合并时带**结构守恒门**（2026-10-18，规则取自 AiNiee 润色阶段的 ResponseChecker）：逐条拿润色稿与**润色前译文**比对标签 `{}`／插值 `[]`／`%` 格式符多重集与换行数，对不上的条目**不入批次**、单独列出原因并以退出码 1 提示。基线取「润色前译文」而不是英文原文，判据才收窄成「这次润色有没有引入新损伤」——历史遗留的结构损伤（该由 `tl_check --fix --settle` 修）不会卡住整批。理由：下游 merge 与 `apply` 都只核锚点，润色把 `{i}` 润丢了要等回填完跑 `tl_check` 才发现，那时损伤已经写进 tl 文件。判据与 `tl_check` 同口径——只拦「丢/多结构 token」与「换行数增加」，润色前译文有换行而润色后合并断行不拦。

### names/ — 人名翻译统一

分工：`make_glossary` 取证（**脚本只做确定性取证，资格判断交给 AI 略读全文**）→ 快速批改用 `apply_glossary_body` → 需逐条审核/中文变体/回滚时走 `unify_name_translations` v6（收集 → 分类 → 统一，`--rollback` 一键回滚）。

`make_glossary.py` 默认产出三件套：草稿 JSON + 证据 JSONL（项目根 `.cache/`，`-o` 指定时落指定路径）+ **AiNiee 三栏术语表 xlsx**（`原文|译文|备注`，按列序读取）→ 默认游戏根目录 `术语表.xlsx`，行 = 草稿确定条目（Character 人名，备注留空）。AI 精读证据判资格、定稿（写入 `glossary_full.jsonl`，每条 `{src,dst,info}`，info 为极简翻译辅助，无则留空）后跑 `make_glossary.py <项目> --finalize glossary_full.jsonl` 生成含备注的完整版；`--no-xlsx` 关掉 xlsx 走纯取证。

v6 严格模式**不做滑动窗口猜测**（v5 误报率 ~70%）：变体只有"译文含英文原名"这一种可靠来源，其余归为 `omitted` 交人工/LLM。**"零误报"只对"是人名"成立**——Character 里的 `Bartender`、`A Student` 等泛称会进草稿，定稿时须剔除只留专有词汇。术语表 `{"Tomori": "灯里"}` 或 `[{"src":..., "dst":...}]` 两种格式皆可。

### linear/ — 剧情线性模式

按顺序自动串剧情，跳过沙盒地图导航。`analyze` 检测是否内置线性机制 → `add` 生成 `game/zzz_linear_mode.rpy` 补丁（**不改原脚本，删文件即还原**）/ `modify` 校验自带事件表并用 `--append-new` 追加遗漏。边界：场景列表由"对话密度 + 桩标签过滤"推导，`--min-says` 调阈值、`--include/--exclude` 手工增删；跨场景变量用补丁里的 Variable Helper 手动补。只有 `.rpyc` 时先跑 `scripts/unrpyc.py`。

### setup/ — 写入类工具（无自动化测试）

安全网是「默认试运行 + `--apply` 落盘 + 首次 `.bak`」。改完任一写入类工具，在样例游戏上跑三连：**试运行**（核对改动清单）→ **落盘**（确认 `.bak` 生成）→ **回滚**（`Copy-Item <文件>.bak <文件> -Force`，再跑试运行确认行为一致）。

```bash
python setup_i18n.py <game>                              # 初始化多语言（建 game/tl/）
python add_fonts.py <game> --font path/to/font.ttf       # 添加字体
python switch_default_language.py <game> --lang schinese # 切换默认语言
python fix_lang_button.py <game> --apply                 # 修语言按钮写死（先试运行）
```

## 典型工作流

```
1. python setup/setup_i18n.py ...                    → 初始化多语言（建 game/tl/）
2. python renpy-tools-cli.py all <项目> -l schinese → 一键检测（18 项）
3. python renpy-tools-cli.py integrity <项目>      → 变量/角色/标签结构与转义
4. python renpy-tools-cli.py untranslated <tl目录> --csv → 缺句清单
5. python names/unify_name_translations.py ...    → 统一角色名翻译
6. python renpy-tools-cli.py all <项目> -l schinese → 最终校验（退出码 0 才算收尾）
```

## 备份机制

所有会**修改已有文件**的工具在首次写入前，把原文件备份为同目录 `.bak`（`script.rpy` → `script.rpy.bak`）。

- `.bak` 只在首次生成，后续不覆盖，保留最原始版本
- **fail-closed**：备份创建失败会停止写入，不会"只警告后继续覆盖"
- 回填与缓存写入用原子替换，避免中断留下半个文件
- 恢复：`Copy-Item script.rpy.bak script.rpy -Force`
- `unify_name_translations.py` 另有整目录 `.fix_name_backup/` 快照，双层保障

## 回归测试

纯标准库 unittest，无需 pytest：

```bash
cd tests
python -m unittest discover -v          # 全部（当前 597 用例，约 60s）
python -m unittest test_renpy_tools -v  # 解析/回填安全/CLI 批次（176）
python -m unittest test_crash_risks -v  # 崩溃检测器误报边界（23）
python -m unittest test_say_parse_contract -v  # say 解析契约（9）
python -m unittest test_config_loaders -v # 外置 JSON 配置加载器（13）
python -m unittest test_cli_surface -v  # CLI 门面：35 子命令 --help 全通（7）
python -m unittest test_fonts_i18n -v   # 字体/多语言链路测试 + rpa_index（31 用例）
python -m unittest test_urm_install -v  # URM 门界/回滚/不越权（29 用例）
python -m unittest test_checks_zoo -v   # checks/ 零覆盖检查器契约 + 转义回归（37 用例）
python -m unittest test_screen_quality -v # 硬性质校筛行：残留/假名/标点/相似度（24 用例）
python -m unittest test_tl_check_crash -v # tl 崩溃级规则 + 术语一致性/语言分块判定（27 用例）
python -m unittest test_polish_batches -v # 润色切批 + 剧本提示词与 Tier 分层 + merge 结构守恒门（47 用例）
python -m unittest test_repo_consistency -v # 文档 ↔ 代码自洽 + 全库数字声明（12 用例）
python -m unittest test_count -v        # 用例总数自证（2 用例）
```

跑测试会生成 `__pycache__`（`.gitignore` 已忽略；分发前请清理），可用 `PYTHONDONTWRITEBYTECODE=1` 禁止生成。

## 覆盖范围与盲区

**有测试**：公共解析层（`shared/rpy_syntax.py`、`shared/backup.py`）、`tl_check`、`autotranslate` 回填安全、`check_untranslated`、`check_translation_integrity`、`unify_name_translations`、`fix_missing_tags`、`sync_namebox_translation`、`check_crash_risks`（误报边界双向断言）、CLI 参数透传与 `all` 批次/tl_dir 换算、门面 35 子命令 `--help` 契约、`check_fonts` / `check_i18n` / `rpa_index`、外置 JSON 配置加载器、`urm_install` 的引擎与 .rpa 闸门 / 回滚幂等 / 不越权删除、`checks/` 中 `check_type_safety` / `check_duplicate_translations` / `check_func_text` / `check_ui_text` / `check_translation_misuse` / `check_auto_trans` / `check_button_missing_translation`。

**零测试**（使用时留意）：`sdk/` 下 `analyze` / `check_assets` / `setup_i18n` / `setup_fonts`、`setup/` 下 6 个写入类工具、`checks/` 下 `check_label_issues`（613 行）与 `lint_check`、`linear_mode.py`（975 行）。

`optimize_assets.py` 曾是真 bug 源（`.m4a` 未处理导致 `TypeError`、GBK 控制台 emoji `UnicodeEncodeError`、把全量降级说成「优化完成」）。已修但仍无自动化测试——它依赖外部二进制（pngquant/jpegoptim/ffmpeg），没有这些工具的机器上只会走降级路径，测不出压缩逻辑本身。

## 目录名（2026-10-05 起全 ASCII）

原先 8 个分组目录是中文名，macOS 的 NFD 归一化会让跨系统 checkout 后 `import` 找不到模块。现已全部 ASCII 化；从老版本升级时按下表改名：

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
