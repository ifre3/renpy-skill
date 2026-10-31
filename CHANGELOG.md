# CHANGELOG

本文件是评审与修复流水（按时间倒序）。技能能做什么看 [README.md](README.md)，
入口与命令看 [renpy/SKILL.md](renpy/SKILL.md)。

### 2026-10-31（第九批）：线性模式生成器——半自动范式 + 三处机制修复

**背景**：用 `linear add` 给 AfterDark 0.26 生成补丁后实测，暴露 4 个机制级问题，
并确立「半自动线性」设计原则（选项与分支保留、沙盒机制跳过）。

**修复**（生成器 `linear_mode.py` 模板同步）：

- **JumpException 被吞**：模板回调的 `except Exception` 把 `renpy.jump` 抛的
  `JumpException` 也吞了，导致「按钮 ON 但永不跳转」。改为 `except renpy.game.JumpException: raise`
  放行，由引擎主循环（execution.py）完成跳转。这是"按钮亮但不生效"的根因。
- **剧情性表外标签被误跳**：自动播放把不在 LM_STORY 的标签一律当导航跳过，但
  `actualintro`（开场独白）/`story1congun`（枪战戏）这类剧情标签在表外会被跳过断片。
  治理方向写进 docstring/README：**表外剧情性标签必须手工纳入 LM_STORY**（生成器无法判断叙事结构）。
- **FF 快进 day 计算非法值**：`(day%7)+1` 在 day=7 时产出 8（星期画面卡死）。改为
  `(day+1) % LM_DAY_MOD`，新增 `LM_DAY_MOD` 常量（AfterDark=8，其他游戏常见 7）由用户按游戏校准。

**新增能力**（生成器模板）：

- `LM_GATES` 好感/天数补偿表 + `lm_compensate`：进入门控事件前自动补齐 `totaldays`/`affection`，
  解决跳过日常导航导致的状态冻结（占事件表 60%+ 的门控事件条件永远不满足）。默认空表，按游戏调度链填。
- `lm_done` 进度标记：已播场景目录标灰删除线，重进线性可续播。
- 清理模板里 `lm_label_callback` 的残留死代码（重复的 `st.lm_pos = idx / return`）。

**文档**：

- `sandbox_linear_design.md` 新增「三·五、半自动线性范式（选项保留、沙盒跳过）」——
  含三路线对比表（全自动 LostInYou / call 链 Dissonance·FC / 半自动 AfterDark 补丁），
  明确 `menu` 在剧情标签内部、callback 不干预，是"选项保留"的实现基础。
- `scripts/README.md` linear 一节 + 行数声明（1003→1052）同步。

**验证**：`python -m unittest discover` 614 用例 OK（约 75s，含 `test_repo_consistency`
文档↔代码数字自洽）。

### 2026-10-27（第八批）：母语流畅档落地到 prompt 模板

**背景**：文档把默认档升为「母语流畅」（重构时只改了 translation_polish.md 与
SKILL.md），但 `plan_batches.py` 的 `render_prompt` 模板仍是旧「中文审稿人/
大部分保持原样」文案——标准没落到 AI 实际读到的指令里。

**改动**：`render_prompt` 升级为母语流畅档：角色=中文母语审稿人、目标=像简体
中文母语者写的、判据=读着不像母语者写的才改（语序重组/增删连接词/拆分长句均可，
通顺的保持原样）、只做一轮；新增 `context_hint` 参数，`<项目根>/.cache/polish/
context.md` 存在时自动带「全局上下文」段（先读章节核心再读剧本）。低扰动档
策略一B 未单独设模板，需要时手改「标准」段。文档第 4 步已标注落地。
验证：`test_polish_batches` 50 项 OK（新增 TestNativeFluencyPrompt 3 项：
母语/流畅字样、语序重组许可、context 提示开关）。

### 2026-10-27（第七批）：筛行/自动规则增补——全库自动改写 701 条

**来源**：抽查 fixes_003 实测，提炼 4 条机器可枚举的机翻残留模式。

**改动**：`screen_suspicious.py` +3 条规则（〔…〕角色标记残留 / 纯单英文词未译 /
拟声 hhh 残留）；`direct_polish.py` +1 条 SAFE 自动改写（删〔…〕角色标记）。
实测（Dissonance 44,387 条）：自动改写 701 条（占 1.6%，零 token）；可疑行 210 条
需 AI。已知边界：纯单英文词规则会误报人名（实测 'Sada'），暂无专名白名单。

### 2026-10-27（第六批）：长流程续跑契约 + 引号奇偶检查内建（E012）

**背景**：用户问「作为（半）自动化的 skill，为了长流程执行要不要做设计调整」。
评估结论：骨架（账本/幂等/安全网/终检门）已对，缺口在跨会话续跑契约不统一、
无人值守档的引号奇偶校验只有 PowerShell 一行命令（Linux/macOS 上是空的）。

**改动**：

- **续跑契约（唯一出处 = `translation_workflow.md` 第 0 节）**：所有长流程在
  `<项目根>/.cache/<flow>_state.json` 落账本（`phase / done / next / decisions`）；
  命名阶段 T0–T5（汉化）/ C0–C3（创作）；**用户门决定落 `decisions`，同一项目
  不重问**（答过一次记账本，后续会话只汇报沿用）；续跑仪式四步：读账本 →
  零 token 复查 → 从 `next` 继续 → `done` 不重做。`translation_polish.md` §3、
  `game_creation_workflow.md` 第 3 节、SKILL.md 主表/注意事项挂指针。
- **回滚单元文档化**：`batch_NNN.json` 存 plan 时点润色前译文 = 天然快照，
  回滚 = 对调新旧值重放 `apply --overwrite`，逐批互不牵连（`translation_polish.md` §3）。
- **并行扇出可选档**（`translation_polish.md` §9）：术语表冻结 + context.md 产出后
  批次独立，可交子代理并行，代价是丢「上一批已定术语」接缝（改全量前置替代）；
  仅用户嫌慢时启用，不做默认。
- **fmtlint 新增 E012 引号奇偶**：剥掉 `\"`/`\\` 转义后逐行数双引号，奇数即报
  （problem 级，进退出码）；`old`/`new` 行仍由 E001 精确判定不重复报。跨平台
  取代无人值守档的 PowerShell 一行命令（`translation_polish.md` §8 已改指 fmtlint）。
  已知边界：tl 内嵌 python 块单独成行的 `"""` docstring 会误报，tl 里极罕见。

**验证**：`test_fmtlint` 17→22 用例全绿（新增 TestQuoteParity 5 例：损伤两形态、
转义不误报、old/new 不双报、problem 级）；全量 606→611 用例（README /
SKILL.md / scripts/README.md 三处计数同步）。

### 2026-10-27（第五批）：批次大小实测——200 偏大，默认改 150

**背景**：用户问「200 句/批合理吗」。对 Dissonance 0.14 schinese（44,387 条）用
`plan_batches.py` 做 100/150/200/300 四档实测，按 `(file,line)→场景名` 映射统计
批大小与跨场景混合。

**实测结论**：

| batch-size | 批数 | 平均/批 | 跨 10+ 场景批占比 | 单场景批占比 |
|---|---|---|---|---|
| 100 | 574 | 77 | **10%** | 27% |
| 150 | 384 | 116 | **21%** | 19% |
| 200 | 263 | 172 | **37%** | 7% |
| 300 | 169 | 263 | **59%** | 1% |

- 200 虽然省 token（263 批），但 37% 的批跨 10+ 场景——AI 读的"一段戏"是碎片拼合，
  撞上 §7 批评过的跨场景问题；300 更差。
- 100 最健康（跨 10+ 仅 10%），150 是成本/质量平衡点；四档 split 均为 0（本库连续
  场景段最长 223 条 < 300）。

**改动**：`plan_batches.py` `DEFAULT_BATCH_SIZE` 200→150（docstring 同步）；
`translation_polish.md` 新增「批次大小实测」节 + 策略一B「约 200 句/批」改 150。
验证：`test_polish_batches` + `test_repo_consistency` 60 项 OK。

### 2026-10-27：润色体系重构（校对 vs 润色分层 + 母语流畅档）

**背景**：用户提出两点：① 策略零（`direct_polish.py` 规则层机械改写）应归类为
**校对工具**而非润色；② 明确质量标准 = **目标语言母语者读得流畅**（对文学性无规定），
必要时**略读全文 + 罗列章节核心**作辅助信息。

**做法**（`translation_polish.md` + SKILL.md）：
- 策略零改称「校对档（非润色）」，归入 `tl_check` / `screen_quality` 同族，只在
  机械硬伤（标点/高频翻译腔），不碰语义语气文风。
- 原「策略一（双角色两阶段审稿）」改名 **策略一B：低扰动审稿档**（默认大部分不改）；
  新设 **策略一：母语流畅档（默认）**：标准 = 母语者读得流畅、无文学性要求；流程 =
  校对前置 → 略读全文（约 5~10% 体量，落 `.cache/polish/context.md`）→ 罗列章节核心
  （每章 2~4 条：主线/情节/人物/专名/语气）→ 连续剧本块润色，判据放宽为「读着别扭/
  不像母语者就改、通顺保持原样」→ 仍只输出改动行 + 结构守恒门 + **只做一轮**（辅助
  信息让第一轮更准，不增轮数）。
- 修正文档历史遗留：第二个重复的「策略一」标题段（实为策略二/二B 内容）改名
  「策略二/二B 详情」。

**验证**：`test_repo_consistency` 回归（索引/数字守门）。

### 2026-10-26（第三批）：社区资产分层（大工具 vs 个人脚本/经验）

**背景**：用户澄清「社区工具」指**个人脚本和社区经验**，而非 AiNiee/MTool 这类
大工具。此前工具地图未区分，会把两者混为一谈。

**做法**：`community_playbook.md`「四、社区工具生态地图」补分层说明——① 大工具
（面向人的成品软件，AI 驱动不了）；② 个人脚本+社区经验（skill 的**上游信号源**，
优先级高于①：skill 的价值 = 验证 → 沉淀 → 变成可重复工具）。

### 2026-10-26（第二批）：社区工具生态调查入账（工具地图 + 3 条新经验）

**背景**：用户问「skill 工具和社区工具一样高效好用吗」，检索 AiNiee / MTool /
unrpyc / rpycdec / unrpyc-pure / RenpyThief / LunaTranslator / GalTransl /
Ren'Py 官方 9 个生态点的发行页与讨论，核实维护状态与社区公认教训。

**结论（已写入台账）**：两类工具是不同定位——skill 面向 AI 无人值守全链路
（CLI + 606 测试守门）；社区工具面向人类玩家（GUI、跨引擎、更新卷、单点）。
翻译质量维度双方在卷同一痛点（长句重组/上下文/变量安全）：AiNiee 7.1.1 修复
「renpy 翻译后变量消失」、MTool 分句切割损害质量（LinguaGacha 文档），而 skill
润色管线本就「不截断长句、连续剧本块」——同一思路的不同实现。

**做法**：`community_playbook.md` 新增「四、社区工具生态地图」（9 行表：工具/
形态/定位/维护状态/与 skill 的关系 + 选谁判据）；已验证经验账追加第 9-12 条
（翻译破坏变量、MTool 分句、unrpyc 双分支与混淆边界、生态活跃度实测）。
文档数不变（20，未新增文件），测试守门要求满足。

### 2026-10-26：社区经验首批入库（沙盒/线性模式 + 学习台账）

**背景**：连续分析三个 Ren'Py 发行版（AfterDark 0.26 沙盒、Dissonance 0.14 线性、
Lessons in Love 汉化提示系统）并检索社区（Lemma Soft / F95 / itch），沉淀出
skill 此前没有的两类知识：沙盒/线性模式的**架构范式**与**社区验证经验**；以及
「不断学习社区经验、不脱节」的**机制**。此前 `linear` 工具只有工程实现
（analyze/add/modify），知识层无对应参考。

**做法**：新增两篇参考（18 → 20）：

| 文件 | 分区 | 内容 |
|------|------|------|
| `renpy/references/sandbox_linear_design.md` | 写游戏 / 引擎行为 | 双模式设计共识（Lost in You 作者原话）、沙盒分层范式（时间×地图×调度 label 条件链，AfterDark 脚本核实）、线性链模板（Dissonance linear.rpy 源码核实）、线性化避坑清单（LiL Linear Mode Mod 玩家实测 bug）、事件追踪器最小实现 |
| `renpy/references/community_playbook.md` | 排错 / 工程 | 社区渠道清单（学什么→去哪学）、已验证经验账（8 条首批，带来源 URL 与验证分级：源码核实/作者原话/玩家实测）、更新机制（触发时机/学习流程/验证纪律/定期复查） |

**同步**：SKILL.md「你说→它做」补 `linear add` 入口行 + 两个分区索引挂载；
根 README 与 references/README 的数字 18→20（共 21 个 md）；分区轴表格补
「沙盒/线性架构范式」与「维护 skill」场景。

**验证**：`scripts/tests` 回归（references 双向索引、命名、数字声明由
`test_repo_consistency.py` 自动校）。

### 2026-10-21：全库数字声明扫描（守门网从 3 份文档扩到全库 md）

**背景**：`test_repo_consistency.py` 原本只盯三份主文档（root README / SKILL.md /
scripts/README）的子命令数与用例总数，网外面的 md 照样会漂。这轮一扫抓到三处，
且都不是刚写下的：

| 文件 | 写的 | 实际 |
|------|------|------|
| `renpy/scripts/checks/README.md` | 不再手写 **34** 项表 | 35（`TOOL_SCRIPTS`） |
| `renpy/references/namebox_translation.md` | `test_namebox_shared.py` **22** 用例 | 28 |
| `README.md` | **16** 个分场景参考（且漏列 3 篇） | 18 |

**做法**：新增 `TestNoStaleNumbersInProse`（2 用例），把扫描面扩到全库 md 里所有
写死的数字声明，五条规则——子命令数、`all` 检查项数、references 数、总用例数、
单文件用例数。两处判据来自实际误判：「N 用例」按同行有无测试模块名分流归属（回归
命令里模块名不带 `.py`，第一版正则漏判了 8 行）；子命令数要求上下文出现入口/门面
字样，免得把「某脚本自身 N 个子命令」误判成顶层门面数。

**不扫**：`CHANGELOG.md`（按日期倒序的流水，历史条目保持当年口径）、`cache/`
`tmp/` `.zcode/`（本机留档区与过程文件，不是仓库结构）。

**反证用例**：`test_scanner_flags_a_wrong_number` 用合成文本五条规则各写错一处，
要求逐条报出——只有覆盖率断言时，「正则命中但比较逻辑写错」仍会假通过。

**已知未覆盖（记在案，本轮不建规则）**：`scripts/README.md` 的「零测试面」清单里
`check_label_issues`（613 行）、`linear_mode.py`（975 行），实测 635 / 1003（含空行）、
535 / 877（非空行）——**行数口径未定，差约 15%**。要建规则得先在文档里固定口径
（写明"含空行"或"非空行"），否则规则本身会成为下一个漂移源。

**验证**：`unittest discover` → **597 用例 OK**（595 + 2）；三处漂移已修，用例数在
三份文档同步 595 → 597。

### 2026-10-18 二十一轮：名字栏中文的假绿灯（裸 define 说话人 + 全串精确匹配）

**背景**：拿 `术语表.xlsx` 核 Dissonance_0.14 的名字栏，`sync_namebox_translation.py`
报「无需补充翻译，所有术语表中的角色名字均已翻译」，实际 47 个说话人**全部显示英文**。
两处缺陷叠在一起，方向相反：

1. **识别只认 `Character("Name")`**。该项目零个 `Character()`，人名是带颜色标签的裸
   define 变量（`define nih = "{color=#0f37f2}Niwa{/color}"`）直接当说话人。工具扫出
   0 个名字，然后在空集上断言「全部已翻译」——不是漏报，是**假绿灯**。
   `check_charname_translation.py` 同病，且两者都未察觉。
2. **匹配语义理解错了**。引擎查找是
   `renpy/translation/__init__.py:545-564` 的**全串精确匹配**，
   只剥离 `{#...}` 翻译注释，`{color=}` 一律不剥。所以 `old "Eri"` 命中不了
   `{color=#d599aa}Eri{/color}`。原先按裸名比对，误判出「16 个已翻译」——同样是假绿灯，
   只是方向相反。若照它去补条目，`new` 里漏掉标签还会让角色名掉色。

运行时链路已逐环核对：裸字符串说话人会**被包成 `Character`** 再查同一张翻译表
（`ast.py:583` → `sayexports.py:129-130` → `defaultstore.py:420-422` →
`character.py:1444,1454,1348-1349` → `substitutions.py:344-345`），
所以「裸 define 翻不了」是误判，正确做法是补整串条目。

**做法**：新增 `shared/namebox.py` 作为名字栏的唯一实现层（识别 + 引擎等价查找 +
标签保留拼接 + 条目渲染），两个名字栏工具改为共用它：

- `scan_namebox_names()` 认三类写法：`Character()` / 带标签裸 define / 内联说话人；
  裸 define 须**真被当说话人用过**才算，并跳过资源路径、含插值的动态名（`[pn]`）、
  纯符号悬念标记（`???`）。产出保留完整串与台词条数，用于排优先级。
- `lookup_translation()` 复刻引擎两段查找（全串 → 剥 `{#...}`），**不做**标签剥离。
- `splice_tags()` 把裸译名塞回标签骨架；多文本段语义歧义时返回 `None` 交人工，不猜。
- `sync_namebox_translation.py` 新增 `--stub <路径>`：写独立 `translate strings` 文件，
  避免依赖某个既有文件里已有 strings 块（原先 `--target-file` 的硬前提）。
- 新增 `references/namebox_translation.md`，SKILL.md 加一行入口与一条「你说→它做」。

**边界**：`append_translations()` 的签名与 `.bak`/原子写入契约未动；两个工具仍默认
试运行、`--apply` 才写盘；检查器仍无 `--fix`。新增 `tests/test_namebox_shared.py`
（529 → 560），锁住「裸名条目命中不了带标签串」这条核心回归。

**补记（同一轮，跑 lint 后才发现的第二处）**：`old` 重复对引擎是**致命**的——
`renpy/translation/__init__.py:534` 直接抛 "A translation for ... already exists"，
游戏启动即崩。Dissonance_0.14 的 `Cashier` 既是 `define c = "Cashier"`、
又被内联说过一次，两个工具都只按「缺失/命中」判断，**不会发现自己正产出重复条目**。
现按 `value` 合并同名来源（保留台词数最大者，其余记入 `notes` 的「同名来源」），
并在落盘前再拦一道（重复即拒绝写入）。这类问题只有引擎 lint 能暴露，
已写进 `references/namebox_translation.md` 的「坑 3」。

**落地结果**：`术语表.xlsx` 补入 16 条说话人（Nurse/Me/Maid/Cashier/Employee 等），
按约定 `NOT ME` / `NOT SAYURI` / `NOT MY CLASS` 保留英文（术语表备注标注「可保留英文」，
工具据此跳过、不生成 `new == old` 的空转条目）。生成
`game/tl/schinese/zz_namebox.rpy` 共 40 条，引擎 lint 通过；
`check_charname_translation --glossary` 现以退出码 0 收口，可当回归闸门用。

### 2026-10-18 二十轮：吸收 AiNiee 的校对/检查维度（术语一致性 + 语言分块判定 + 润色结构守恒门）

**背景**：`cache/AiNiee-Beta` 里躺着一套成熟的翻译质检实现，值得对照吸收。逐文件
核对后（`Service/TranslationChecker/{TerminologyChecker,RuleChecker,LanguageChecker}.py`、
`Domain/ResponseChecker/*`、`Service/TaskExecutor/PolisherTask.py`）结论是**大部分维度本
仓库已有等价物**——未翻译/重复/标签结构/转义走 `tl_check` 与 `integrity`，相似度漏翻、
外文残留、假名残片走 `polish/screen_quality.py`，占位符保留走 `autotranslate.validate_translation`。
只补三处真缺口，且按本仓库形态落地（只读检查器 + 纯标准库，不照搬其 GUI 流程内闭环）：

1. **术语一致性**（AiNiee `TerminologyChecker`）：此前术语表只有「造」（`make_glossary`）
   与「用」（`apply_glossary_body` / `unify_name_translations` / `autotranslate -g`），
   没有「事后核对 tl 里是否真用上了定稿译名」的检查。落地为 `tl_check --glossary`。
2. **语言不匹配分块判定**（AiNiee `LanguageChecker`）：`screen_quality` 的外文残留/假名是
   行级轻量近似，没有整块语言占比判定。落地为 `tl_check --lang-ratio`。
3. **润色阶段的结构守恒门**（AiNiee `PolisherTask` → `check_polish_response_content`）：
   值得注意的发现是它的润色检查**比翻译阶段更松**（只留行数/序号/空值/换行/占位符五条，
   刻意不做「返回原文」「残留原文」「回复格式」检查）。本仓库对应缺口在 `merge_polish.py`：
   它原本只核锚点存在性，`apply` 也只核锚点，于是「润色把 `{i}` 润丢了」要等回填完跑
   `tl_check` 才发现，损伤已经写进 tl。

**做法**（均为最小改动，不改既有默认行为）：

- `checks/tl_check.py`：新增 `--glossary`（`.xlsx` 三栏 / `.jsonl` / `.json`，xlsx 用
  `zipfile`+`ElementTree` **零依赖**读，不引入 openpyxl；ASCII 词条整词边界且大小写不敏感，
  单字母与 `dst` 空词条丢弃；新增 `[术语]` 级并计入退出码）与 `--lang-ratio`（20 行分块、
  启发式语言判定、只对 zh/ja/ko/latin 目标生效、样本不足 5 行不判）。两条**都不入 `all`**，
  默认关闭，既有输出与退出码不变。
- `polish/merge_polish.py`：合并时逐条拿润色稿与**润色前译文**比对标签 `{}`／插值 `[]`／`%`
  格式符多重集与换行数，对不上的条目不入批次、列原因、退出码 1。基线取润色前译文而不是英文
  原文（与 AiNiee `PolisherTask` 的 `translation_text_dict` 同口径）：判据收窄成「这次润色有
  没有引入新损伤」，历史遗留的结构损伤（该由 `tl_check --fix --settle` 修）不会卡住整批。
  判据与 `tl_check` 同口径（只拦丢/多结构 token 与换行数增加，润色前译文有换行而润色后合并
  断行不拦）。顺带修一处隐患：该脚本原先用 `sys.stdout = io.TextIOWrapper(sys.stdout.buffer, ...)`
  换流，被 import 时旧 wrapper 回收会连带关掉共享 buffer，把同进程后续的 stdout 弄坏（实测让
  `discover` 全量跑出 100 个 ERROR）。改为 `sys.stdout.reconfigure`，与 `autotranslate.py` 一致。
- 测试：`test_tl_check_crash.py` 9→27 用例（术语一致性含 xlsx 零依赖读取、整词边界、
  大小写、fail-closed、CLI 端到端；语言分块含稀释/短块/无语言信息行/语言族映射），
  `test_polish_batches.py` 21→31 用例（结构守恒门九个正反例 + 历史损伤不卡批 + 缺锚点
  行为不变）。

**未采纳**：AiNiee 的「检查失败自动重发」闭环——本仓库是 CLI + 缓存 `warn` +
`--retry-failed`，内联重试会放大 token 成本，也破坏润色管线「只做一轮、账本防重润」的设计；
`Resource/Regex/check_regex.json` 那套控制代码正则面向 RPG Maker/Mtool，对 Ren'Py 无意义。

**验证**：`unittest discover` → **528 用例 OK**；`--glossary`/`--lang-ratio` 默认关闭，
`all` 16 项检查的输出与退出码未变。

### 2026-10-14 十九轮：仓库根收口（打包链路恢复 + `cache/` 定性 + 反编译路由补齐）

**背景**：497 用例全绿，但分发链路是断的——`package.py` / `.gitignore` /
`.gitattributes` 被挪进了 `cache/`，而该脚本用自身所在目录当仓库根，于是从根目录跑
`python package.py --check` 直接 `缺少必需文件：README.md`。这条防线正是为「工作区躺着
一个下不来的假包」造的，自己被绕过时没有任何检查会报。连带两处失效：`.gitignore` 困在
`cache/` 使根目录 `__pycache__` 裸露；README 约定 #4 声称「反编译唯一说明处在 SKILL.md
注意事项"反编译"行」而那行不存在——AI 拿不到「外部技能优先」，会直接走内置 `unrpyc.py`
去下载执行第三方代码。

**做法**（最小必要，不动工具链本体）：三个文件归回仓库根（先确认无同名冲突）；
`cache/LICENSE` 与根 `LICENSE` **署名不同**（contributors vs ifre3），属同名冲突，
两份原地保留不覆盖。`cache/` 定性为本机留档区（AiNiee 等同类工具参考包 + 单次调研数据，
按要求保留），写进 `.gitignore` 并在 README 目录表补一行——它不在 `package.py` 白名单
`INCLUDE_DIRS=("renpy",)` 内，本就不进分发包。SKILL.md 注意事项补「反编译 `.rpyc`」一行：
首选仓库外的 `renpy-script-decompile`，内置脚本只是兜底并点明其下载执行行为，路由到
`player_tools.md`；README 约定 #4 的"唯一说明处"随之自洽。

**验证**：`package.py --check` → `[OK] 111 条目 / 75 .py / 9 分组目录`；
`unittest discover` → **497 用例 OK**。

### 2026-10-08 十八轮：`config.replace_text` 钩子独立成篇（无 `tl/` 机翻的识别与拆除）

**背景**：处理一份第三方汉化发行版（Dissonance 0.14）时发现，该游戏 `game/tl/`
**根本不存在**却在显示中文。载荷是 `game/audio/dl_failed.mp3`——6 KB 伪音频，
双层 zlib 解出 18.5 KB Python，由 `game/AtsukoEve.rpy:1411` 的 `init python` 块
`exec()` 执行，同一 blob 里既装 `config.replace_text`（机翻）又注册
`welcome_popup` 覆盖屏（站外引流）。`try/except: pass` 吞异常，仅凭 log 判断不出
它跑过。此前 skill 里 `config.replace_text` 只作为「翻译工作流第 7 节兜底」出现，
且描述为「只支持纯文本」——这句不准确（钩子作用在 tokenize **之后**的 TEXT token 上，
标签与插值天然不受影响），也没有反向视角：拆别人发行版时该钩子正是「无 tl 机翻」的判定特征。

**做法**：新增 `references/replace_text_hook.md` 作为该钩子的唯一完整出处——
引擎源码依据（`renpy/config.py:628`、`renpy/text/text.py:2320-2321` 与
`2881-2882`、`renpy/text/extras.py:191`）、第三方载荷形态特征表（无 tl / 伪音频 /
双层 zlib / `exec` / 吞异常 / 与引流同 blob）、4 步识别流程（grep `exec(zlib` 定位
执行点、验载荷非真音频、双层解压只读输出）、拆除原则（汉化与引流同 blob 时只删
`overlay_screens` 与网络/AES 部分，重写回 zlib，调用点不动）与桩环境对比验证法
（`replace_text` 是纯函数，stub `renpy.loader.load` 即可跑，无需启动游戏）、
以及质量判据（44917 条映射中 41868 整句 / 3049 单词，碎片输出来自单词兜底，
虚词映射 `'had' -> 不是` 本身有错且会漏进 blur shader 代码——补全整句是唯一出路）。

接入 4 处：SKILL.md 参考索引新增一行、触发关键词表新增「没有 tl 目录却是中文 /
汉化在哪 / 有个弹窗推网站」、注意事项新增「无 `tl/` 的中文」行（点明
`check_i18n` / `tl_check` 对该机制无感，避免误以为工具失灵）；
`translation_workflow.md` 第 7 节补源码依据与交叉引用；`hanization_manual.md`
第 10 章排查流程图首步插入「先反问 `game/tl/` 是否存在」。

**测试**：本次只加文档、不动 `scripts/`，全量 404 例仍全绿；
`test_repo_consistency.py` 的 references 索引互校（双向）与 .md 链接解析对新文件通过。

### 2026-10-07 十七轮：`--step` 名称别名（接十六轮挂账）+ `unify_names.py` 更名 + lint 三件套定位说明

**背景**：十六轮明确记录「`unify_name_translations.py` 859 行用 `-s/--step 1|2|3`
而同类用 `add_parser`，本轮不动，仅记录」。本轮接账处理；另处理评审中发现的
`unify_names.py` 与 `unify_name_translations.py` 命名过近（只差两个词，AI 与人
都易调错脚本），及 `lint_report.py`/`lint_rpy.py` 与 `tl_check.py` v3 的关系无文档说明。

**做法**：
- `unify_name_translations.py`：`--step` 增加 `collect`/`classify`/`unify` 名称别名，
  编号 1/2/3 保留兼容旧命令行。新增模块级 `STEP_ALIASES` 与 `normalize_step()`
  （argparse `choices` 拦截非法值），docstring、argparse description、7 处
  「下一步」提示全部改用名称形式。`test_renpy_tools.py` 新增 `TestStepAliases`
  4 例（名称映射 / 编号兼容 / None=跑全部 / 别名表闭合断言）。
- **更名 `names/unify_names.py` → `names/apply_glossary_body.py`**：内容不变
  （78 行批式 glossary 直改），只改名字自述动作；脚本 docstring 记录更名原因
  与新旧分工。同步 6 处引用：`scripts/README.md` 目录树、`names/README.md`
  （分工表 ×2 + 草稿消费端）、`make_glossary.py`（docstring + 输出提示）、
  `polish/README.md`（管线图 + 归组说明）、`references/translation_workflow.md`。
  `tools_boundaries.md` 里的 `unify_names_v2.py` 是 2026-10-03 已移除的历史脚本，
  与本次无关，未动。
- `scripts/README.md` 去重说明补一句：`lint_rpy.py`（.rpy 格式错误码 E001–E005，
  不需 SDK）与 `lint_report.py`（按文件汇总报告）未入 CLI、与 `tl_check.py` v3
  定位不同、不互相取代——消除「质检该用哪个」的歧义。

**测试**：全量 400 → **404 例全绿**；用例数同步三份文档（root README /
SKILL.md / scripts/README.md）与目录树内 per-file 计数（172→176）。
实跑验证：`--step classify` 与 `--step 2` 行为一致，`--help` 展示名称形式。

### 2026-10-06 十六轮：检查器契约层（BaseChecker）+ 门面注册表 + checks/ 收全部只读检查器

**背景（读 AiNiee 源码后的结论）**：比对 `NEKOparapa/AINIEE`（经 gh-proxy 拉
tree 核实：`ModuleFolders/Domain/{FileReader,FileOutputer,PromptBuilder,...}` 按技术
角色分层，`BaseSourceReader` / `BaseTranslationWriter` 用抽象基类 + `pre_/on_/post_` 钩子
声明扩展点）。结论是**该学的是"契约前置"而不是目录树**：renpy-skill 的消费方是 agent，
导航面是 SKILL.md 的两张表，不是目录树；照搬 Domain/Infrastructure/Service 三层对 agent
消费无收益。但 AiNiee 那套"加新读写器不会漏生命周期"的**结构化保证**，正是本skill 缺的——
本 skill 靠文档表格保证，且已腐烂过（十五轮的 `check_i18n.py` 假阳性）。

**顺带查清的三处分类问题**（都有实测依据）：
- 同类检查器分居两地：`checks/` 放 11 个、tl 侧那 3 个落在 `translate/`（"本组的
  check_*.py 因此归这里"是历史理由）。→ 归位。
- 多入口脚本（`autotranslate.py` 4 子命令 / `linear_mode.py` 3 / `setup_fonts.py` 4）
  聚合的是"同一对象的不同动作"，且 `autotranslate` 的 `scan` 输出结构就是 `apply` 的输入
  结构（translation_polish.md:38）——**不是混装，不拆**，拆了断流水线契约。
- `unify_name_translations.py` 859 行用 `-s/--step 1|2|3` 而同类用 `add_parser`，
  同一仓库两套多入口风格。→ 本轮不动，仅记录。

**做法**：
- **新增 `shared/base_checker.py`**：`BaseChecker`（`name`/`summary`/`takes`/
  `requires_tl`/`read_only` + `applies_to()` + 可选 `run()`）与 `CheckContext`。
  缺 `name`/`summary`、`takes` 取值非法、`takes=tl_dir` 却没声明 `requires_tl`
  都在 `class` 语句处 `TypeError`——拖到运行期才发现的漂移从源头消除。
- **14 个检查器各声明 `CHECKER`**：`requires_tl` 按实测填（见下），不是照抄旧集合。
  `run()` 设为可选并默认抛 `NotImplementedError`——门面走子进程，只需三元元数据，
  14 个都去抽 argparse 逻辑是过度改动；目前只有 `check_crash_risks`（抽出 `run_scan()`）
  与 `check_untranslated` 实现了就地执行，CLI 行为逐字保留。
- **新增 `shared/tool_registry.py` 门面注册表**：门面那两张 33 项手写表
  （`TOOL_SCRIPTS`/`TOOL_DESC`）与两个硬编码集合（`NEEDS_TL_DIR`/`TL_DIR_TOOLS`）
  全部删除，改为从各脚本 `CHECKER` 派生。`list` 输出的分组展示逻辑同时简化
  （原先按 6 个集合反复过滤，末尾一个 `name not in ...` 长链，现按 `ALL_GROUP` /
  `FIX_GROUP+SETUP_GROUP` / 其余 三段走）。
- **归位 3 个检查器**：`check_translation_integrity.py` / `check_untranslated.py` /
  `check_charname_translation.py` 从 `translate/` 移到 `checks/`；连带修
  `lint_check.py` 与两个测试的 sys.path、门面路径映射、`scripts/README.md` 目录树、
  `translate/README.md`、`checks/README.md`（新增「检查器契约（CHECKER）」节）、
  `references/hanization_manual.md` 速查表（改走 CLI 入口）。
- **修正一处实测出的错误声明**：`button` 从 `requires_tl` 移出。门面的旧集合把
  `button` 算进 `NEEDS_TL_DIR`，但实测它判据在源码层（"按钮文本有没有进 translate
  strings 块"读 .rpy 不读 tl/），无 tl 时照样报 WARN——旧集合会让无 tl 项目白跳一项。
  `NEEDS_TL_DIR` 因此从 7 项缩到 6 项（tl 侧检查器 4 + 非检查器 2）。

**只读红线从口头约定变成断言**（`test_checker_contract.py`）：口径不是"零写操作"——
`check_untranslated --csv`、`check_charname_translation --stub` 这类**用户点名的导出**
是合法的。硬红线只挡备份/原子写原语（`atomic_write_text`/`ensure_bak`/`os.replace` 等）
与 `--fix`，并要求每个写调用可追溯到某个 argparse 开关、写辅助函数的路径必须来自参数。
另加一条反向断言：写入类工具（`fix_*`/`patch_*`/`sync_*`）必须保留显式写入开关且不得
改名成 `check_*.py`——防止有人为了让断言变绿把工具藏起来。

**防复发护栏**（`test_tool_registry.py`）：每个注册检查器都必须真吃下 `all` 的透传
参数 `-l <lang>`。行为层（实跑，看`unrecognized arguments`）+ 声明层（源码须有
`"-l"`）两层都验。当初 `check_i18n.py` 既没声明也没人测，两层都加上才不会再漏。
另钉：`requires_tl` 集合按**有无 tl 的输出差异**实测校验（不是照抄声明自证）、
门面各项（路径/描述/分组/tl 集合/ALL_GROUP）必须与注册表一致、`list` 输出须含每个工具。

**测试**：新增 `test_checker_contract.py`（27 例）+ `test_tool_registry.py`（25 例），
全量 348 → **400 例全绿**；用例数与目录树同步三份文档（348→400）。
`package.py --check` 通过（103 条目 / 67 .py）。门面实跑：有 tl 项目失败项仅
`fontcheck`+`langcheck`（真问题——schinese 未接 CJK 字体、无 Language() 入口），
无 tl 项目明确跳过 4 项且退 0。

### 2026-10-06 十五轮：统一中间产物落盘约定（`.cache/`）+ 修 `check_i18n.py` 缺 `-l` 致 `all` 假阳性

**背景（补挂账）**：十四轮末尾记下的存量项「`test_fonts_i18n` 1 个 `-l` 参数错误（测试
期望 check_i18n.py 支持 `-l`，脚本无此参数）」——当时只给 `check_fonts.py` 补了兼容参数，
漏了 `check_i18n.py`。而 `all` 走 `renpy-tools-cli.py:274` 把 `-l` 原样转发给 `ALL_GROUP`
每个检查器，故 `all <项目> -l schinese` 的 langcheck 撞 argparse rc=2，被门面归一成失败
项 → **在任何项目上都返回 1**，与 SKILL.md「`all` 退出码 1 = 查出了问题而非崩溃」的口径
冲突，用户看到的是恒定假阳性。

**做法**：
- `scripts/checks/check_i18n.py`：按 `check_fonts.py:158` 同款 no-op 兼容参数补
  `-l/--language/--lang`，注明「本检查按 `tl/` 全语言枚举，不依赖指定语言」。不改检查
  逻辑与报告口径（不选「只查指定语言」方案，避免 all 漏报其他语言）。
- **中间产物落盘约定统一到 `<项目根>/.cache/`**。原先两条并存规则互相冲突：
  `translation_workflow.md:22`（脚本草稿进项目根 `.cache/`）与 `:28`（AI 中间产物进系统
  临时目录）；而 `translation_polish.md` 要求跨会话/多天维护 `polish_state.json`
  （已完成批次号、行范围、待重润行）与种子账本——临时目录会被清空，账本一丢就重复润色，
  而防重复正是账本存在的唯一理由。判据收敛成单条：**跨会话/多天还要复用的 → `.cache/`；
  本次会话读完就扔的 → 系统临时目录**；定稿产物（`glossary.json` / `glossary_full.jsonl`）
  属交付物，仍只在用户要求落盘时才进项目。
- `make_glossary.py`：新建 `.cache/` 时打印一次提示（不参与 `game/` 打包、可随时删、git
  项目建议加 `.gitignore`）；`.cache` 不可写退回临时目录时打印 `[提示]` + 实际路径
  （原先 `except OSError` 静默吞掉，用户按文档去 `.cache/` 找不到文件）。
- 同步文档：`translation_workflow.md:22/28`、`translation_polish.md:45-46/53`
  （`polish_batch01.json` / `polish_state.json` 给出 `.cache/` 路径）、
  `scripts/names/README.md:13`。**不改名 `.cache/`**：与引擎的 `game/cache/` 混淆只存在
  于阅读时，改名要同步 3 处文档 + 代码，收益不抵成本。

**测试**：`cd scripts/tests && python -m unittest discover` → **348 用例全绿**（改前
347 通过 / 1 error，即十四轮挂账的那条）。`make_glossary.py` 冒烟：首次运行打印创建提示、
二次运行不重复提示、`.cache/` 内仅草稿 + `.evidence.jsonl` 两个文件。

### 2026-10-06 十四轮：新增 screen_quality.py 硬性质校筛行（LinguaGacha 判定经验移植）

**背景**：用户实测截图暴露盲区——整句已翻但夹生词（"诺拉开始 hysterical 地大笑"）
在默认 `--min-score 3` 下漏报：`screen_suspicious.py` 的 `[A-Za-z]{4,}` 规则权重
仅 1，`tl_check.py` 只查假名不查英文残留，lint 检查的英文占比>70% 也抓不到 95%
中文的句子。

**做法**：读 LinguaGacha（neavo/LinguaGacha）源码（经镜像代理拉取
`src/shared/text/translation-quality-rules.ts`、`src/domain/language.ts`、
`src/shared/prefilter/rule-prefilter.ts`、`builtin/skills/translation/references/item-review.md`
等），判定经验移植成新脚本 `scripts/polish/screen_quality.py`（纯标准库，
与 screen_suspicious 同输入输出约定，职责分界：suspicious 管翻译腔风格，
quality 管硬性质）：
- **外文残留**：连续拉丁段聚合报证据；豁免单字母（A 班）、2-4 字全大写缩写
  （HP/RPG/OK）、免翻短语（DejaVu Sans/Ren'Py，短语级剔除防拆词误报）与
  EV 事件号（LG rule-prefilter 清单）。豁免收窄后夹生词可给高信号直报。
- **假名残片**：与 tl_check 同区间（[ぁ-ヿ]+，汉字不算）；`--lang ja*` 跳过。
- **半角标点**：中文译文夹 `!?` 与非千分位 `,`；无中文正文不判。
- **相似度漏翻**：包含快判 + 字符集 Jaccard > 0.8（LG 同阈值），抓"原文照抄
  加点料"的局部漏翻；整句照抄不重复报（归 untranslated 专项通道）。
- CLI 退出码：有命中=1（renpy-tools 惯例）；输出锚点 JSON 直接进
  merge_polish → autotranslate apply 回填管线。

**方法论**：translation_polish.md 新增第 6 节"种子驱动探查"，吸收 LG
item-review 审校技能的自启发循环（种子提炼/三种探查方向/警告判断重点表），
并划清边界：种子循环扩大调查范围，不改变"润色只做一轮"实测结论。

**测试**：新增 `test_screen_quality.py` 24 用例（截图例句固化为端到端回归
锚点）；全量 348 用例，新脚本全绿。同轮发现两处**存量问题**（与本轮改动无关，
分发包上同样复现）：`test_cli_surface` 5 个 `--help` 子进程失败（本机环境）、
`test_fonts_i18n` 1 个 `-l` 参数错误（测试期望 check_i18n.py 支持 `-l` 但
该脚本无此参数）。
### 2026-10-06 十三轮：AfterDark 0.26 实测三连——资源误报清零、tl_check 递归+自定义标签、新增多语言/字体测试

**实战场**：AfterDark-0.26-pc（发行版 + 3GB archive.rpa + 70 文件 schinese 汉化）。

**check_assets 资源误报 1986→13**：音频/字体检查只比对完整路径，不做图片检查已有的
basename 回退，`play music "audio/Music/Cafe.mp3"`（文件就在磁盘上）全部误报；图片
则因打包在 .rpa 里被整批误判。修复：音频/字体补 basename 回退；新增
`shared/rpa_index.py` 只读提取 .rpa 归档名清单（RPA-3.0 XOR / RPA-2.0，坏包跳过），
并入三类资源索引。实测 420 图缺失→0、1566 音频缺失→13（与引擎 lint 的 13 处
not-loadable 完全一致）。

**tl_check 递归扫描 + 自定义标签识别**：原版只扫 `tl/<lang>/` 顶层（AfterDark 顶层
10 个文件，实际 70 个，`Girls Scripts/` 等子目录全盲，% 格式码炸弹都漏）；现 rglob
递归并改用相对路径做文件标识。`{chaos}`/`{bt}` 这类项目自定义动态标签原被误报
"未知标签/关闭无开放标签"，现从 `config.custom_text_tags` / `renpy.register_text_tag`
/ `config.self_closing_custom_text_tags` 收集后并入已知集合。实测最终报告仅剩
真问题（1 崩溃 + 5 标签丢失，全部人工修复后 tl_check 全绿）。

**新增两个只读测试器（进 `all`，12→14 项）**：
- `checks/check_fonts.py` 字体接入测试：引用存在性（磁盘 + .rpa + 引擎自带
  `renpy/common/`）、CJK 翻译语言是否接入 CJK 字体（防切语言后方块）、可选
  fontTools 字形级抽查、`tl/None` 垃圾语言目录点名。
- `checks/check_i18n.py` 多语言链路测试：`Language()` 目标存在性、每语言切换入口
  （无入口且有翻译→指向 fix_lang_button；有 `_preferences.language` 自定义切换则豁免）、
  `config.language` 默认语言合法性、strings 块覆盖。
- 门面 28→30 子命令；`test_fonts_i18n.py` 18 用例（含伪造 RPA-3.0 索引 fixture）；
  全量 302→320 用例。

**实战应用（游戏侧）**：修复 tl 崩溃级 4 处（未闭合 `[`、`{Kitsune}` 未知标签、
`{ i }` 坏标签）+ 7 处幽灵插值（`[I]`/`[K]`/`[ut]`/`[ye]`/`[mc]`/`[a]`）+ 3 处裸
`%`（改全角％）+ 若干 `{i}`/`{w}`/`{/cps}`/`\n` 标签与假名残片；接入手动验证过
的 5 处原版坏跳转系作者自带（RPA 内原始源码比对证实），按用户决定保留原样。
中文接入：`sdk-fonts/SourceHanSansLite.ttf` 复制入 `game/Fonts/`，按
advanced_tools.md 方法 2 投放 `translate schinese style/python` 字体补丁
（切回英文自动恢复原版美术字），preferences 屏插入 Language 区块
（screens.rpy 首改 .bak 备份）；lint 零新增问题。

**对白字体异常（十三轮追加）**：实机验证发现「按钮字体正常、对白异常」——该游戏
say 屏写死了 `font persistent.pref_text_font`（无障碍字体机制，显示时求值），
优先级高于 translate style/python 覆盖。修复：该行表达式改语言感知
（`"Fonts/SourceHanSansLite.ttf" if _preferences.language == "schinese" else persistent.pref_text_font`）。
skill 侧固化：`check_fonts.py` 新增屏幕层 `font persistent.*` 运行时机制检测
（已含 `_preferences.language` 适配的不报），advanced_tools.md 方法 2 补边界警告；
`test_fonts_i18n` 增至 20 用例，全量 322 用例。

### 2026-10-06 十二轮：SDK 自动探测补「项目嵌在 SDK 里」+ 一致性测试抗 __pycache__ 污染

**SDK 向上查找起点**：`sdk/detect_sdk` 的向上查找原来固定从 skill 脚本自身位置出发，
项目嵌在 SDK 根目录下（如 `D:\renpy-8.x-sdk\Game-1.0-pc`）时永远找不到上层 SDK。
现 `detect_sdk(sdk_path, start=...)` 支持传入查找起点，`sdk/cli.py` 把项目路径传进去
（不传保持原行为）。`checks/lint_check.py` 的兄弟目录推断同理补了一步：先看项目
父目录本身是不是 SDK（含 renpy.exe/renpy.sh），再扫 `renpy-*sdk*` 兄弟目录。
实测：游戏嵌在 SDK 内时 `cli.py <项目> lint` 与门面 `lint` 均免 `--sdk` 自动探测成功。

**test_group_dirs_are_ascii_and_complete 自污染**：跑过任意 CLI 脚本后 `scripts/` 下
会生成 `__pycache__`，再跑回归测试时该用例把缓存目录当成多余分组而误报。现排除
`__pycache__`（同文件 `test_scripts_are_documented_bidirectionally` 的 os.walk 早已
这么做）。实测：故意制造缓存后全量 302 用例通过。

**顺手**：`setup/fix_lang_button.py` 的相对路径展示原本把 `game/` 下的文件一路
relpath 到盘符根（丢 `D:\` 前缀显示成 `workplace\...`），修正为以项目根为基准
（显示成 `game\screens.rpy`）。

### 2026-10-06 十一轮：关掉 load_trans 转义 bug + unrpyc 哈希收口到底

**load_trans 转义 bug（九轮定位，本轮关闭）**：`checks/common.py:load_trans` 与六个
检查器源侧抽取各自手搓的 `old "(.*)"/[^"]+` 弱正则，全部换到 `shared/rpy_syntax.py`
（common.py 统一做 sys.path 引导并 re-export；新增公开助手 `decode_quoted_literal`）。
契约改为：**源侧抽取与翻译侧加载的键值都是解码后的运行时文本**——
`textbutton "He said \"stop\" loudly.":` 不再截断成 `He said \`，误报「未翻」随之消失。
改动面：common.py 的 load_trans 重写；check_ui_text / check_func_text /
check_auto_trans / check_translation_misuse / check_button_missing_translation /
check_duplicate_translations 的正则体改为转义感知（`(?:[^"\\]|\\.)*`）并对捕获结果
解码。行为兼容：普通不含转义的输入逐字节同结果（护栏用例钉住）。
test_checks_zoo 新增 10 个转义回归用例（27 → 37），总用例 292 → 302。

**unrpyc 哈希校验（十轮遗留的"彻底收口"，本轮完成）**：`scripts/unrpyc.py` 新增
`EXPECTED_SHA256`——固定 commit 下 13 个文件的 sha256，由 gh-proxy.com 整包与
jsDelivr 单文件两条独立线路交叉核实一致后写入。提取后逐文件校验：不匹配的镜像
被弃用并清空缓存，被篡改的代码不会落地执行；本地缓存复用前也校验（用旧版本或
被改动过的缓存会被拒绝并提示 `--redownload`）。双向实测：干净下载放行；
篡改缓存文件后运行被拒且缓存自动清除。上一轮写的"残余风险：镜像本身仍不可信"
就此关闭；剩余的唯一信任假设是"固定 commit 的哈希表本身没被改"——它随仓库走
git/分发校验。

### 2026-10-06 十轮：收口 unrpyc 浮动下载 + 外部评审消化 + 同类工具质量对表

**unrpyc 收口（上轮定位的最高优先级）**：`scripts/unrpyc.py` 的 7 个镜像原来全部指向
`@master` 浮动分支——上游或被劫持的镜像推任何代码，本地下次运行就会执行。现固定在上游
2026-02-23 的 master HEAD `3ae8334e`（经 gh-proxy.com 的 api 通道核实，api.github.com
直连不通），镜像列表按当日实测延迟重排（gh-proxy.com 1.2s / ghfast.top 1.4s /
ghproxy.net 1.8s 列前；jsDelivr 的 zip 路径会 301 到 raw.githubusercontent.com，直连
被墙的机器上等于死链，降为末位兜底）。固定后的整包下载已实测 200。残余风险与升级方法写在
unrpyc.py 顶部注释；彻底收口（自带源码或 zip 哈希校验）列为后续项。

**外部评审消化**：一份外部评审（已归档至仓库外）指出 checks/ 与 translate/ 边界模糊、
setup/ 主题过杂、polish 与 translate 关系不明。逐条核实后采纳其"文档化"部分、不采纳
"搬目录"部分（9 个分组目录受 test_repo_consistency 强制，搬目录收益配不上成本）：
checks/README 补"只读审计"边界声明，translate/README 补与 checks 的分工及 polish 上下游
关系，polish/README 补下游定位，setup/README 按主题分组并新增写入类工具"试运行→落盘→
回滚"人工实测清单。评审的事实性错误（"速览表列 10 个 sdk 脚本"实为 8+1、"建议加指引"
SKILL.md 早已有之）未采纳。顺带：.gitignore 补 `*.bak` 与 `.fix_name_backup/`；删除
checks/、shared/ 残留的 `__pycache__`（此前会让 test_group_dirs 断言失败）。

**同类工具质量对表（维护参考，非代码改动）**：拉取 unrpyc / LinguaGacha /
renpy-translator 源码抽样比对——unrpyc 自带 89 文件编译↔反编译对拍语料并在 CI 跑全量
（其领域金标准）；LinguaGacha（TypeScript，约 2.5k 星）498 个测试文件、模块 1:1 配测试；
renpy-translator（功能最接近的同类）零测试、限流器用分钟键/秒键混装的同一个字典、错误
静默吞成 None，且 `openai_translate.py:17` 注释里残留真实格式的 OpenAI key（应视为已
泄露，即使可能已失效）。结论：本技能的测试纪律与安全网（292 用例、fail-closed 备份、
密钥只走环境变量）在同类中处上游，工程强度不及 LinguaGacha 的产品级后端；
`references/translation_polish.md` 把它列为备选路线的判断成立。源码证据存仓库外
`_bench_src/` 目录。

### 2026-10-06 九轮：修分发产物 + 把「文档↔代码」的自检交给测试

上一轮的自批只盯着测试覆盖率，漏掉了更靠前的一类问题：**仓库里那个「能下下来的包」
本身是坏的，而且没有任何检查会发现**。

**分发产物是三天前的旧版，且是被否掉的旧版**。`renpy-skill.zip`（2.3MB）里顶层是
`renpy-dev/` + `renpy-user/` 双技能、脚本目录还是中文名、带 16 个 `__pycache__` 条目和
整个 `.git/`。也就是用户下载到的恰好是「2026-10-03 消除触发词打架」之前的那版、也是
「2026-10-05 全 ASCII 化」之前的那版，还带着会遮蔽 import 的陈旧 `.pyc`。已改名为
`renpy-skill.zip.stale`，并新增 `package.py` 重打：显式白名单、产物必须恰好一个
`SKILL.md`、禁含 `.git/` / `__pycache__` / `renpy-dev` / `renpy-user`、时间戳固定因而
可复现（两次构建 sha256 相同）。新包 92 条目 / 356KB，解开后 292 用例全通。
不依赖 `git archive`——本机没装 git。

**三处文档数字长期漂移**：`README.md:13` 与 `renpy/SKILL.md:68` 写「27 子命令 / 217 用例」，
实际 28 / 280；只有 `renpy/scripts/README.md` 写对了，而它是三份里 Agent 最少读的那份。
更根子上，这是维护约定 #6「用例数与 README 一致」靠人眼执行的结果。现已交给测试强制。

**新增 12 个用例**（280 → 292）：

- `test_repo_consistency.py`（10）文档内部自洽——三份文档的子命令数与用例总数一致、
  各测试文件用例数之和 == 声明总数（280 = 172+9+23+13+7+29+27 这个不变量不需要跑测试
  就能查，且能指出是哪个文件没更新）、`.md` 链接不失效、`references/` 双向索引 SKILL.md、
  9 个分组目录全 ASCII 且被目录树列出、**磁盘上每个 `.py` 都写进了目录树**、LICENSE 存在
  且确为 MIT（`renpy/scripts/README.md` 一直声称 MIT，仓库却没有许可证文件）
- `test_count.py`（2）用例总数自证：运行时 `discover()` 数自己，断言与三份文档一致。
  这是自指问题，只能这么解。附一条下限断言，防止 `discover` 静默返回空 suite 时
  以「0 == 0」假通过

**顺带纠正上一轮的一个错误结论**。上一轮说 `checks/common.py` 里有「一批未被调用的小
函数」待删。实测：9 个函数全是活的，`_load_screen_call_kw` 在 `L106` 模块加载时就被调用。
这条债不存在，别再花时间删。

**下一个真 bug 已定位，留给下一轮**：`checks/common.py:load_trans` 是 `ui` / `misuse` /
`func` / `auto` 四个检查器在用的翻译解析器，它不解 rpy 字符串转义。用最小工程跑真实命令
复现：`textbutton "He said \"stop\" loudly.":` 的文本被截断成 `"He said \"`，既污染报告
又误报「未翻」。「已翻/未翻」计数同样错。根子是 `shared/rpy_syntax.py` 明明有 23 个函数
（完整处理转义、未闭合字面量、`old`↔`new` 间最多 12 行间隔）且 15 个模块里 12 个已
import，唯独 `checks/` 那 9 个检查器自己在 `common.py` 里手搓了一套弱正则——上一轮怀疑
的「四份已分叉副本」根子在此。

### 2026-10-05 八轮：逆向补测（补零覆盖检查器）+ 修一处自引回归

上一轮自批说「投入方向反了」（给一个玩家侧偶发需求配 29 个测试，
"
"而 `checks/` 九个检查器零覆盖）。本轮补回去。

**修一处我自己引入的回归**：五轮把 `SCREEN_CALL_KKW` 外置 JSON 时把默认清单收窄到只剩
"
"`game_menu`，理由写的是「其余是他游戏自造的名字」——但它们和 `game_menu` 一样不是
"
"Ren'Py 标准组件，区别只是我没验证过。结果是 `heading` / `settings_item` / `tab_button`
"
"三类自定义 screen 调用**静默失效**，`func` 子命令对这类游戏报不出东西，且没有任何提示。
"
"已恢复内置 4 个名字，并把「清单只能增不能减」写进测试。项目侧增量仍走 JSON。
"
"同时补了两个已知契约：`check_screen_calls` 只认**带括号的调用**（`heading("…")`），
"
"字面量 `heading "…"` 不属于此规则；`type_safety` 只扫 `$` 行、`scan_file` 要 `Path` 而非 `str`（传 str 会静默 skip）。
"
"这两条写进 `tools_boundaries.md`，避免下次再把它们当异常。
"
"
"
"**新增 `test_checks_zoo.py`（27 用例）**，覆盖之前零测试的：`check_type_safety`（get_size → randint 真崩溃链、
"
"字面量不报、`$` 行边界、规则元组形状）、`check_duplicate_translations`（跨文件重复 old、
"
"大小写敏感、单引号 old、结果携带两处位置）、`check_func_text`（screen 调用、`use` 前缀、
"
"已翻译不报、已声明不报）、四个分叉副本的返回形态。回归 253 → 280。
"
"
"
"**意外发现：结构性重复比预估严重**。`check_button_missing_translation.py`（565 行）内含 9 个检测函数，
"
"而 `check_ui_text` / `check_translation_misuse` / `check_func_text` / `check_auto_trans` 四个模块各持一份**已分叉**的副本，
"
"行数不同（如 `check_interpolation_no_t` 23 vs 52）、返回容器不同（元组 vs 扁平 list）。体样采样下
"
"发现项目一致、但不能因此宣称行为已分歧。合并会改变用户拿到的报告内容，
"
"因此本轮**只钉契约不合并**——这 27 个断言是合并的前置条件。
"
"
"
"**未做**：本轮没有删任何工具。上一次评审里列的 `add_performance_panel` /
"
"`patch_android_tablet` / `remove_translated` 及字体两套工具合并都**未执行**——合并会改变
"
"用户可见行为，需先用本轮这批契约测试把其固定下来再做。先补测试、后合并。
"
"
### 2026-10-05 七轮：CLI 退出码归一 + SDK 版本边界提示

两个小切口，解决「调用方无法区分'发现 bug'与'脚本报错'」和「7.x 用户蒙头跑 lint 却拿无意义输出」的问题。

- **CLI 退出码归一**（`renpy-tools-cli.py`）：子脚本返回负值（被信号终止）归一化为 2（崩溃），大于 1 的退出码归一化为 1（发现问题）。0/1 原样透传。模块顶部 docstring 写明退出码约定（0=成功、1=发现问题、2=崩溃/参数错误）。此前子进程被 `SIGTERM` 终止时返回 -15，市面 CI 与 shell 脚本判 `>0` 当失败、判 `>1` 当「严重」时行为不稳定。
- **SDK 版本边界提示**（`checks/lint_check.py`）新增 `check_sdk_version()`：跑 `renpy --version` 解析主版本，<8 时明确拒绝并提示「本工具仅支持 Ren'Py 8.x，请使用 `--skip-sdk-lint` 只做翻译专项检查」，不再把 SDK 7.x 的无意义输出喂给解析器。不再让「lint 通过但报告为空」这种歧义状态出现。
- 回归：172 用例全部通过，两处改动 import 正常。

### 2026-10-05 六轮：URM 安装/卸载支持（`urm_install.py`）

五轮把 URM 的能力与画廊边界写清了，但用户拿到下载好的文件之后还要自己拉进 `game/`、自己判断版本是否匹配、被永久性残留时不知道怎么回收。本轮补上这一层。

新增 `scripts/setup/urm_install.py`（CLI `urm`），做三件模型不可靠的事：

- **引擎版本闸门**：URM 官网声明要求 ≥6.99.14。从游戏根的启动脚本 / `game/*.rpy` 读版本，
  低于门槛直接拒绝安装并返回退码 2（安装了也不加载，白白占地）。
  读不到版本时返回 `None` 而不猜，并告知用户去看 `log.txt` 顶部的版本行。
- **`.rpa` 加密闸门**：检测 `archive_key.rpy` / `.rpa.index` 等特征，命中则拒绝投放并指向解包文档——
  加密游戏里投放式补丁不会生效，不能让用户投放后再猜。
- **签名回滚**：安装写 `.urm_installed.json`（记录来源 URL / 文件 / 引擎版本），卸载据此精确删除，
  不靠猜文件名——避免误删游戏自带的同名 `.rpy`。重复安装被拒绝（升级需先卸载）。
- **编译残留提示**：卸载时扫 `.rpyc` / `.rpymc` / `.bak`。Ren'Py 加载 `.rpyc` 优先于 `.rpy` 且不校验一致性，
  所以删掉 `.rpy` 补丁后同目录 `.rpyc` 会继续生效——这是「删了补丁却还在」的头号原因。
  `--purge-rpyc` 一并清理。

**越权红线**：卸载**绝不删除未签名的文件**。用户手工解包过官方 `.rpa`（得到 `.rpy`）时，
脚本只提示「这些不会被删、但会被编译加载」，不自作主张删除。无签名时卸载直接拒绝，
只报告疑似文件。这条有回归测试锁定（`TestNotDeletingForeignFiles`）。

**其他**：安装前体检为默认行为（不带任何参数即体检）；所有写操作默认试运行、`--apply` 才落盘；
新增 `test_urm_install.py`（29 用例，覆盖版本门界 / 加密门界 / 回滚幂等 / 不越权删除 / CLI 参数组合）。
回归总数 224 → 253，CLI 子命令 27 → 28（`urm` 属写入类，不进 `all`）。

**不做的事**：不下载。第三方 URL 会漂移，且「替用户决定往游戏目录里放下可执行代码」不是 AI 应做的决定——
这与 SKILL.md 「SDK 缺失时给用户判断，不替用户决定」同一原则。

### 2026-10-05 五轮：URM 与画廊解锁的边界拆清

审问“要不要加 mod 相关功能”得出的结论是**不加新功能**（现有工具链够用，
且 skill 的既定原则是不重写轮子）。但审问暴露了一个真实的文档缺口，本轮补上：

- **URM 条目与官网不符**：written 的是「选项后果提示」（官网原文是
  **See and pick hidden/locked choices** = 查看并选择隐藏/锁定选项）；缺引擎下限（≥6.99.14）、
  文件大小（1.1 MB）、两项功能（路径/if 语句检测、任意角色显示名重命名）。
- **被忽略的关键边界：URM 替代不了 unlock_patches**。两者都是投放式、都不碰原文件，
  但判据走不同的 persistent 字典：URM 场景重放基于 `_seen_ever`（看过的 **label**），
  画廊判定走 `_seen_images`（看过的**图片**）。用 URM 回放已看剧情不会开画廊。
  原先两页各说各的，AI 看到「URM 场景重放」很可能误以为不需要 unlock_patches 了。
  现已在三处建立交叉引用：`player_tools.md` 新增「为什么全 CG 解锁不用 URM」子节（含两字典对照表），
  `unlock_patches.md` 头部加互排提示，SKILL.md 触发表加一行“想改数值/看隐藏选项”并标出画廊限制。
- **方向性区分**：「改角色**显示名**」用 URM（运行时生效），
  「改角色**资料库译名**」用 `names/unify_name_translations.py`（改文件、永久、含 tl）。
  原文两处都没写这个区刧。
- **「常见玩法链路」重写为需求表格**：原来 4 条纯脚本流程，现按「不碰文件 → 碰文件/存档」这一个真实分界重组，
  并在表头声明选工具前先判断属于哪一类。

### 2026-10-05 四轮：评审批评项逐条修复

针对「真缺陷 / 文档与实现不一致 / 设计取舍」三类问题的评审结论，逐条落地：

**真缺陷**

- **`optimize_assets.py` 修三处**（26KB 的 `check_crash_risks.py` 零覆盖时，同级别脚本也在裸奔）：
  1. `.m4a` 在 `audio_exts` 里但不在 `optimize_audio` 的分支表里 → 函数走完不 return → `TypeError: cannot unpack non-iterable NoneType` 崩溃。
  2. 打印 emoji 但无 `sys.stdout.reconfigure` → Windows GBK 控制台首个 emoji 即 `UnicodeEncodeError`。
  3. 全量降级为复制时仍打印「✅ 资源优化完成」。改为三段计数（成功优化 / 降级复制 / 非目标文件直传）+ 一个都没优化成功时退出码 1，并提示装压缩器的具体命令（win/linux/mac 三平台）。
- **`check_crash_risks.py` 的 `$ try:` 漏判**（新写 23 用例时发现）：`globals_access` / `unsafe_intconv` 靠 `startswith("try")` 找保护块，而 Ren'Py 里 `$ try:` 与顶格 `try:` 等价 → 所有 `$` 形式的 try 块被误判为「无保护」，全局刷误报。加 `_strip_stmt_marker()` 统一剥 `$ ` / `python:` 前缀。
- **`"try" in line` 误判**：`try_count` / `try_here` / `country` 等含 try 子串的标识符会让未保护代码被判为已保护（漏报）。改为 `re.match(r"try\s*:", …)`。
- **`int(3.5)` 被判不安全**：`safe_patterns` 里 `int` 只匹配整数字面量，浮点字面量落进「无 try 保护」告警。补 `int\s*\(\s*[\d.]+\s*\)`。

**文档与实现不一致**

- **`all` 跑的不是文档说的那几项**（最严重的一条）：SKILL.md 与 scripts/README 都承诺 `all` 覆盖 `crash`/`untranslated`/`charname`/`integrity`/`label`，实际 `CHECK_GROUP + CRASH_GROUP` 只有 `ui misuse func auto charname crash` —— 用户按文档「缺句先跑 all」拿不到 `untranslated` 报告。现 `all` 覆盖 12 项（新增 `integrity`/`label`/`type`/`duplicate`/`button`/`untranslated`），并处理两个非直觉点：`untranslated` 吃 tl 目录，`all` 自动把 `<项目>` 换算成 `<项目>/game/tl/<lang>`；无翻译目录时明确列出跳过项并提示先跑 `setup_i18n`，而不是刷一片「目录不存在」。
- **`tools_boundaries.md` 只覆盖 39/47 模块**：漏登 `check_assets` / `optimize_assets` / `setup_fonts` / `sdk_common` / `extract_say` / `merge_polish` / `screen_suspicious` / `_say_parse`。该页的核心用途正是「半通用工具换游戏前先看」，漏登记等于没有边界说明。现补齐 47/47，并为 7 个新登条目写清边界与保守做法。
- **CLI 门面把 `--help` 当错误处理**：`remove_translated` / `patch_android_tablet` 把它当「路径不存在 / 未知操作」并 exit 1。门面原样转发参数，使上层批量探测可用性时会把这两个正常工具误判为不可用。已改为查询返回 0，并用 `test_cli_surface.py` 把 27 个子命令的 `--help` 全通锁死。
- **测试运行方式两份 README 都没写**（写的是 `pytest`，实际环境未装）。改为标准库 `python -m unittest`，pytest 作为可选。
- **frontmatter `compatibility: renpy>=8.0` 与内容矛盾**：`tools_boundaries.md` 引擎版本经验整节是 7.4.8 实测结论，SKILL.md 也专门教「7.x 发行版用自带解释器验证」。改为 `renpy>=7.4（>=8.0 为完整验证范围；7.x 走发行版自带解释器验证）`，并在版本边界段说明 7.x 的免 SDK 工具照常可用。

**设计取舍**

- **中文目录名 ASCII 化，macOS 支持收回**（本轮最大改动）：8 个分组目录 + 4 个说明文件由中文名改 ASCII，`os` 元数据重新包含 `darwin`。原先的判断是「重命名牵动 import 与 6 处文档引用，收益低」——实测 152 处引用，但其中约九成是正文词汇（译文润色 / 设置默认语言 / 公共前缀 / 游戏自带线性模式），无脑替换会毁掉文档。因此写上下文感知的替换器：只在路径上下文（`DIR/`、`/DIR`、引号包裹、目录名链、独占表格单元）替换，正文词汇保留。`README` / `SKILL.md` / 4 份 references / 32 个文件同步完成。映射表写进 `scripts/README.md`。
- **项目绑定常量外置为 JSON**：`checks/common.py` 的 `SCREEN_CALL_KW` 含 4 个他游戏自造 screen 名，`names/unify_name_translations.py` 的 `SKIP_FILES` 含 4 个自家项目产物文件名。这些写在代码里会造成「换游戏时恰好同名 → 被静默跳过」这类难以察觉的漏处理。改为读项目侧 JSON（`renpy_screen_calls.json` / `renpy_skip_files.json`，支持 append 与 replace 两种写法），随仓库带 `.example` 模板；内置清单收敛到 Ren'Py 标准文件/标准组件。
- **测试补齐（172 → 224）**：新增三个测试文件：
  - `test_crash_risks.py`（23 例）——正反双向锁死误报边界。检测器跑在别人游戏上，误报比漏报更伤用户信任，所以每条规则都要正例（该报）与反例（不该报）成对出现。
  - `test_config_loaders.py`（13 例）——包含「配置在 `collect_files` 调用时求值而非 import 时固化」：用户在 v6 流程中途改配置正是常见用法，必须立刻生效而不必重启进程。
  - `test_cli_surface.py`（7 例）——门面子命令清单与代码一致性 + 27 个子命令的 `--help` 全通。

文档不再只报绿数：`scripts/README.md` 新增「覆盖范围与盲区」节，明确列出零测试模块（`checks/` 其余 9 个检查器、`sdk/` 4 个、`setup/` 6 个写入类、`linear_mode.py` 975 行、`make_glossary.py`），并写明写入类工具的真实安全网是「默认试运行 + `--apply` + 首次 `.bak`」。

**文档纪律**

- README 原有 40/68 行是变更流水，体量超过入口文档本身，且读者要滑过 40 行才看到「已知边界」。流水迁到独立 `CHANGELOG.md`，README 收到 35 行。
- 维护约定新增两条：目录名/文件名一律 ASCII；改完 `scripts/` 必跑回归 + 核对目录树/用例数/子命令数与实际一致。

**卫生**

- 8 个 `__pycache__` / 29 个 `.pyc` 清除（此前两轮都清过但复发，根因是跑测试重写字节码）；`scripts/README.md` 给出 `PYTHONDONTWRITEBYTECODE=1` 的用法。
- 新增一次性核查脚本（目录树 vs 磁盘双向、md 链接与 scripts/ 路径引用、CLI 子命令数、测试用例数、tools_boundaries 覆盖率、ASCII 目录名、`__pycache__`）——7 项全绿。

### 2026-10-05 三轮：评审修复（差分验证入库 / 计数校正 / 卫生清理）

- **差分验证固化为契约测试**：原"新旧解析器差分测试"只有结论无物证（旧正则实现从未入库，git 全历史不可查）。新增 `scripts/tests/test_say_parse_contract.py`（9 用例），把声明过的合成样本维度（cd / tb / 空译文 / 转义引号 / old-new / multiple=2 / 尾部属性）固化为可复现断言，并显式断言旧正则两处缺陷不再出现（`\"` 解码、`old` 行不误判为 cd）。回归测试总用例 168 → 177。
- **CLI 子命令计数校正**：`renpy-tools-cli.py` 实际 26 个子命令（TOOL_SCRIPTS），README 原先误写 27；已按 26 表述并注明 `all`/`list`。
- **卫生清理**：移除 9 个 .py 文件的 UTF-8 BOM（编码统一，git 换行警告消除）；`.gitignore` 删去 `my.zip`、`say.md` 个人临时产物条目。
- **跨平台声明如实化**：SKILL.md metadata 的 os 由 `darwin/linux/windows` 收敛为 `windows/linux`（中文脚本目录名未改——重命名牵动 import 与 6 处文档引用收益低，已在 SKILL.md 注意事项标注 darwin 上需 clone 后重命名或映射的已知限制）。
- **合并成果补提交**：2026-10-03 起的双技能合并、历轮修复一直停留在工作区未入库；本轮将结构迁移（renpy-dev + renpy-user → renpy/）与文档修复拆为两个规范提交。
- 验证：177 用例回归通过（168 + 9 契约）、全库 .md 链接 0 断链、CLI list 正常、BOM 清零。

### 2026-10-05 二轮：分类收敛 / 模板瘦身 / 解析层归一

- **人名统一工具归组**：`unify_names.py` 从 `polish/` 移入 `names/`（与其 v6 主流程、make_glossary 术语表生产同目录），组 README 写明三者分工（取证 → 批式直改 → 三步审核/回滚）；`_say_parse` 导入改为跨组定位，8 处文档引用同步。`autotranslate.apply_glossary` 属回填管线内嵌步骤，保留不动。
- **gallery_and_stats.md 模板瘦身**：27.7KB → 6.1KB。砍掉性能预设完整实现/极简版/分页画廊/作弊面板/完整示例等约 400 行可粘贴模板（违反"参考只收模型记不全的内容"原则），保留配置对照表与生效时机、容错模式、8 条实测翻车场景、Gallery 自动解锁机制与引用名一致性、Replay/MusicRoom 非显性参数、screen action 速查表。
- **say 解析归一**：`polish/_say_parse.py` 44 行自备正则重写为 `shared/rpy_syntax.py` 适配器（autotranslate 早已在 rpy_syntax 层，本轮核实）；差分验证 3 处差异均为修正——旧正则把 `\"` 转义原样吐出（与 autotranslate 锚点解码不一致）、把 `old "..."` 误判为 char='old' 的对话条目，新版皆正确；输出契约（file/line/src_line/type/orig/trans/char）不变，消费方零改动。
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

- 新增 `scripts/setup/fix_lang_button.py`（CLI 子命令 `langbtn`，入 FIX_GROUP）：修复 screens.rpy 中语言按钮写死/缺目标语言项（`Language("english")` 硬编码、按钮列表无中文导致汉化后切不到），参照 renpy-translate-studio 四类自动修复中唯一缺口，config.language/字体/语言钩子已有脚本覆盖不重复实现。
- 设计遵守工具包惯例：默认试运行、`--apply` 才落盘、`atomic_write_text(backup=True)` 写前 .bak、幂等（目标语言已存在则跳过）；配套 SKILL.md 注意事项"运行时 UI 修复"、tools_boundaries 半通用登记与写操作风险表、setup/README。
- 验证：示例项目试运行/落盘/重复执行/回滚重修复/CLI 联动/无语言入口提示全链路通过。

### 2026-10-04 scripts 结构归位

- scripts/ 顶层收敛为门面 + 分组：8 个 SDK 封装脚本（cli/analyze/check_assets/setup_fonts/setup_i18n/optimize_assets/tl_check/sdk_common）收入 `sdk/`，`renpy-tools-cli.py` 留根；修复其 `SCRIPTS_DIR` 原指向 `../scripts`（搬移前恰好自指）改指 `sdk/`，`unrpyc` 命令路径同步。
- 错位归位：`patch_android_tablet.bat` 移入 `setup/`（与其调用的 py 同目录）；`unrpyc.py` 出 `setup/` 到 scripts 根（rpyc 兕底工具不属于任何组）。
- 撤销两个单成员/零引用目录：`补丁集/`（csv 并入 `translate/`，patch_renpy_say.py 默认路径同步）；`文档/`（汉化手册 → `references/hanization_manual.md`，AI 翻译诊断 → `translate/`）。
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
