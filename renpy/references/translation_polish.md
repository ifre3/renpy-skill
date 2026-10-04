# 译文润色方法（可选策略）

> 适用场景：`game/tl/<lang>/` 已有初翻（autotranslate.py 管线或 AI 直接翻译均可），需要二次提质。
> AI 根据用户预算、文本量、质量要求**自行选择或组合**下列策略，不必询问；默认推荐策略一（局部润色档），用户明确要求全文提质或预算充足时才上策略二/三。

## 选型速查

| 策略 | 机制 | Token 成本 | 适用 |
|------|------|-----------|------|
| **策略一**：双角色两阶段润色 | 初翻后由独立"润色者"角色再过一轮 | 局部档 ≈ 初翻的 25%~40%；全文档 ≈ 1.7~2 倍初翻 | 有明确质量 complaint，或用户要求"更地道" |
| **策略二**：LinguaGacha 风格前置 | 翻译时挂风格预设/自定义文风指令 | 0 额外（本就要翻） | 还没翻 / 愿意重翻 |
| **策略二B**：LinguaGacha Agent 审校 | agent 按指定范围逐条润改 | 按指定范围计 | 不想写脚本、范围可控 |

## 策略一：双角色两阶段润色（实测工作流）

来源：18 万字游戏对白实战（见文末来源①）。关键实测数据：初稿修改率约 75%（200 行改 150+），抽查 99% 的修改为正向改善；**润色只做一轮**——让润色者对自己再润一遍，好坏改动五五开，越润越差。

流程：

1. **切批**：按对话行分批（约 200 句/批），一次只给润色者 2~3 批；批次过大会明显掉质量、术语不一致增多。
2. **翻译者角色出初稿**：`autotranslate.py translate` 结果或 AI 直接翻译均可；初稿本来就会"一看就不行"，属正常现象，润色者第一遍会做大量优秀修改。
3. **校对润色者角色**（新会话/独立上下文，不与翻译者混用）prompt 要点：
   - 只做三件事：去翻译腔、按角色语气改口语、修正语法；**禁止增删剧情信息**
   - 对照 tl 文件里的原文注释（`# character "原文"`）核对语义；保护 `{tag}`、`[expression]`、`%%`、转义符不被改动
   - 只输出修改后的整行，不改行号、标签和文件结构
4. **术语一致性**：润色前先读项目根目录 `翻译结果.md` 的"专有名词"章；批次间把新术语回写进去（相当于实战文章里"让 Claude 自己做笔记"）。润色者改了很多人名/专名时会挤占其注意力，文风润色效果随之下降——此时拆小批或先统一术语。
5. **diff 回读**：初稿与润色稿逐行 diff，生成"行号｜原译文｜润色后"对照表供逐行接受/拒绝（VSCode diff 或脚本均可）。预期整行自动接受率约 60%，其余人工微调；被拒的行可选择性再丢给 AI 重润一次。
6. **记录**：重大意译写入 `翻译结果.md` 的"意译与润色"章。

回填沿用 `scripts/翻译相关/autotranslate.py apply` 的安全规则（.bak + 原子替换、标签/插值结构校验、`--overwrite` 才覆盖非空译文）。

## 策略一的可执行管线（脚本级，实测）

上文是流程逻辑；落地时用以下脚本组合，全程不需要新写回填代码：

### 1. 枚举条目

`autotranslate.py scan <tl_dir> --skip-same` 输出的条目结构即回填 JSON 的结构：
`{"file": 相对tl_dir的路径, "line": tl文件内行号, "type": "tb/on/cd", "orig": 原文, "char": 角色变量(cd才有), "trans": 译文}`。
润色场景把 `trans` 填当前译文、改后填润色稿，`file`/`line`/`orig` 原样保留。

### 2. 回填

```
python autotranslate.py apply <tl_dir> --input polish_batch01.json --overwrite --dry-run   # 先预览
python autotranslate.py apply <tl_dir> --input polish_batch01.json --overwrite             # 实写（自动 .bak）
```

`--overwrite` 是必须的（润色覆盖非空译文）；默认 `--dry-run` 先跑一遍核对 SKIP 数。安全网：`line` 处的原文注释必须与 `orig` 完全一致才落笔，不一致/标签结构损坏自动跳过——所以**批次 JSON 里必须带准确的 file+line+orig**，不能只给新旧译文对。

### 3. 批次状态

润色跨多个会话/多天时，在工作区维护 `polish_state.json`（已完成批次号、每批 file 范围与行数、待重润行列表），避免重复润色。68k 行级项目不要指望一轮跑完。

### 4. 本地筛行规则（局部润色档的"可疑行"定义）

零 token 先跑：`tl_check.py`（崩溃/显示级先修）→ `check_duplicate_translations.py`（同句异译=术语漂移）→ `check_untranslated.py`（空译文/new==old）。再按需加规则筛：连续多个"的"、`被` 字被动直译、英文单词残留（人名除外）、`是否/如果…的话` 翻译腔高频词、单句超长无标点。筛出来的行按 file 分组进批次。

### 5. 原子化工具族（已内置：`scripts/润色/`）

上述管线已拆成单一职责小工具，用法与实测注意（strings 冲突、名字框机制、原版标签 bug 假阳性、裸 `%`）详见 `scripts/润色/README.md`：`extract_say.py`（全量条目+锚点）→ `screen_suspicious.py`（规则筛行，规则在顶部 RULES 增删）→ `../统一名称/unify_names.py`（术语表人名统一，已归入统一名称组）→ `merge_polish.py`（AI 只写 `file:line → 新译文`，锚点自动补齐）→ `autotranslate.py apply --overwrite` 回填。

## 策略二：LinguaGacha 路线

本机已装 `D:\workplace\LinguaGacha_v0.124.1_Windows_x64`。注意：**LinguaGacha 没有"润色"功能**（已核实其 main 分支技能清单：translation/glossary/text-preserve/writing-guide 等，无 polish），替代做法两条：

1. **风格前置（0 额外 token）**：文本导入 → 翻译指令挂内置风格预设（"文言文风格""文学措辞风格"）或自定义文风 prompt → 重翻。效果等于"翻译时就润"，适合还没翻或愿意重翻的项目。
2. **Agent 审校当润色器（按范围耗 token）**：对其 `item-review` / `page-review` 审校技能下明确指令——"对指定范围按 XX 风格润色，保留术语表条目和占位符"。该技能默认原则是"程序化批量探查优先，仅在无法程序化探查时动用模型"，所以 token 只花在有疑点的条目上；配合其 glossary（术语表）保证一致性。
3. 辅助：其本地质量规则（行数对齐/外语残留/标点/术语命中）零 token，可先跑一遍把可疑行筛出来，再决定润色范围。

局限：Ren'Py tl 文件的支持情况以实际导入为准；`{w}`、`{nw}`、`[变量]` 等 Ren'Py 特有标记的保护必须在自定义指令里写明，不能依赖其通用规则。

## Token 成本对照

- 全文双角色润色 ≈ 1.7~2 倍初翻量（初稿输入 + 润色输出）
- 局部润色（先本地规则/人工筛出可疑行，只润这些）≈ 初翻量的 25%~40%
- 风格前置重翻 = 1 倍翻译量（本来就要翻，零额外）
- LinguaGacha Agent 审校 = 按指定范围，范围可控

## 来源

- ① [流程分享：18 万字游戏对白中译英，AI 辅助 5 天完成（indienova）](https://indienova.com/indie-game-development/180000-word-game-dialogue-translated-from-chinese-to-english-ai-assisted-completion-in-5-days/)
- ② [如何让小模型也能大幅提升翻译质量：拆分 Prompt 两轮翻译润色（宝玉）](https://baoyu.io/blog/prompt-engineering/divide-your-prompt-to-mutiple-prompts)
- ③ [LinguaGacha 仓库](https://github.com/neavo/LinguaGacha)（内置技能清单与审校文档已核实）
