# Ren'Py 翻译脚本工作流（汉化）

> 来源：SDK\skills\renpy-translate（已并入本 skill）。用于翻译 `game/tl/<lang>/` 下的翻译脚本 .rpy，保持术语一致 + 地道表达 + 全量审查。

## 0. 长流程状态账本（跨会话续跑契约，唯一出处）

汉化是跨会话/多天的长流程。上下文压缩、会话中断、换人接手后，模型最容易犯的错不是单批质量差，而是**从头重跑已完成的活**。约定：

**账本**：进度落 `<项目根>/.cache/translate_state.json`（润色用已脚本化的 `polish_state.json`，创作用 `creation_state.json`——语义一致，各流程自己落）。AI 维护，纯 JSON，字段：

```json
{
  "flow": "translate",
  "phase": "T2",
  "done": ["T0 摸底", "T1 术语表（AI 自行定稿）"],
  "next": "T2 第 7/22 批（.cache/batches/batch_007.md 起未翻）",
  "decisions": {"route": "① AI 直接翻", "scope": "全量", "glossary": "AI 自行定稿"},
  "updated": "2026-10-27"
}
```

**命名阶段**（进度播报与账本 `phase` 都用这套编号）：

| 阶段 | 内容 | 出口判据 |
|------|------|----------|
| T0 | 摸底：版本（`script_version.txt`）/ 规模 / 语言 / 有无已有译文 | 开工确认门问完 |
| T1 | 术语表：`make_glossary.py` 取证 → AI 精读定稿（**定稿门**） | `glossary.json` 落盘 |
| T2 | 分批翻译：按 3.1 切批，逐批落盘 | 全部批次翻完 |
| T3 | 质检修复：`tlcheck` / `integrity` / `fmtlint` / `untranslated` | 退出码 0 |
| T4 | 润色（可选）：转 [translation_polish.md](translation_polish.md) | 终检 0 异常 |
| T5 | 收尾：`tlcoverage` + 进游戏抽查主菜单/设置/存读档 | 交付结论 |

**decisions 落账本（半自动的关键）**：T0 开工确认门、T1 定稿门这类**必须问用户**的决策，用户答过一次就写进 `decisions`，后续会话读账本沿用，**不重问**，只在汇报里带一句「沿用上次决定：……」。「必须问」约束的是不静默替用户决定，不是每会话重问一遍。

**续跑仪式**（会话恢复时固定四步）：

1. `.cache/translate_state.json` 存在 → 先读账本，向用户汇报 `phase / done / next`，再动手
2. 零 token 复查现场与账本是否一致（`renpy-tools-cli.py all` 或对应检查器）；外部改动过文件时**以现场为准**并更新账本
3. 从 `next` 继续；`done` 里的活不重做
4. 每完成一个阶段/批次，**先落账本再继续**（账本随批次 JSON 一起放 `.cache/`，理由见 2.5 第 1 步）

账本不存在 = 新任务，走正常流程；不存在"先全项目重扫一遍再说"的续跑方式。

## 1. 文件校验（必做）

- 文件必须包含 `translate` 关键字（如 `translate schinese ...:` 或 `translate schinese strings:`）
- **不是翻译文件**（只有 label/say，无 translate 块）→ 跳过，并明确提示"文件格式不正确，已跳过"

## 2. 术语表机制（`翻译结果.md`）

翻译前先检查项目根目录是否存在 `翻译结果.md`，存在则读取构建术语表；翻译中持续追加，**不重复添加已有条目**。五章节：

| 章节 | 记录内容 |
|------|----------|
| 专有名词 | 人名/地名/特殊术语对照（读取时主要看这章，保证一致性） |
| 文化梗与背景 | 双关、梗、文化背景说明 |
| 不确定内容 | 拿不准的翻译，供人工复核 |
| 意译与润色 | 结构差异大的重大意译及理由 |
| 审查修正 | 修正前后对比 + 原因 |

> 机器可读的 `glossary.json`（供 `names/unify_name_translations.py` 与 `names/apply_glossary_body.py` 消费）不必手工从零写：先跑 `python scripts/names/make_glossary.py <项目> --lang schinese` 生成草稿（自动提取 Character 定义人名 + strings 块配对 + 碰撞/漂移报告），再按下节精读定稿。**草稿与证据默认写项目根 `.cache/` 目录，不散落项目根**（AI 自己的中间产物同此，判据见 2.5 第 1 步）。**默认交付物例外（用户约定）**：AiNiee 三栏 xlsx（`原文|译文|备注`）默认落**游戏根目录** `术语表.xlsx`——表头一行、跳过表头按列序读、第 1 列非空即收，可直接导入 AiNiee；备注极简仅翻译辅助（消歧/身份/简称提示），**不写备选译法**（模型约束只要唯一译文），无则留空。

## 2.5 术语表精读（脚本取证 → AI 判资格）

`make_glossary.py` 只做确定性取证（Character 定义 / strings 配对 / 字面碰撞 / 出现次数）；**术语资格、info 描述、旧词新用识别由 AI 略读全文判定**——脚本不该也不能力化这一步。流程：

1. 读 `.cache/glossary_draft_<项目名>.json.evidence.jsonl`（全部候选含 count/collisions/where；脚本默认写项目根 `.cache/`，路径见运行输出），对 `kind=term` 的候选逐条判定。**你自己的中间产物也进 `<项目根>/.cache/`**——批次 JSON、状态账本、略读笔记这类跨会话/多天还要复用的必须落这里：系统临时目录会被清空，账本一丢就重复润色/重复处理。只有本次会话读完就扔的采样片段才进临时目录（`.cache/` 会随任务积累，交付前清一遍即可）。一次性辅助代码优先复用 scripts/ 现成脚本或单行命令，不为小事新造脚本。
2. 分批略读 tl 对白原文（~200 行/批、从多个不连续区域采样），像读轻小说一样读：
   - **资格判据**（学 LinguaGacha glossary/rule.md）：**只收专有名词 + 特指称谓**——人名/别名/称号/组织/作品特有概念/作品标题/指代唯一对象的称谓（`Suzu's Mama`、`Mr. Hirai` 这类）；**地名、系统词（好感度/属性/任务）、引擎 UI 词、普通职业、泛指称谓（Nurse、Maid、Cashier 这类）、描述性表达一律不收**，按语境翻即可。频率只是证据，不构成资格——低频但身份重要的照收。
   - **Character 提取的同判**：make_glossary 从 Character 定义直接进草稿的条目**不豁免**——职业/称谓/描述性标签（`Bartender`、`Waiter`、`Bird`、`A Student`、`Everyone`、`Ginger Cat`、`Crowd` 这类无专名价值的）即便进了草稿也必须在定稿时剔除，术语表只留专有词汇。
   - **旧词新用必抓**：普通词在这部作品里是专有概念（"星核"式）的，通用翻译模型必翻错，发现即收。这只有读了原文才看得出。
   - **复核人名译名**：Character 定义清单 vs 译文（`Saki→"Sunday"` 式张冠李戴只有读了才看得出）。
3. **定稿前征求用户意见（必做，不得静默定稿）**：AI 略读到能概括剧情时停下，先给用户一句话简介「此游戏讲……（简略）」，再问术语表怎么选，三选一：
   - **译名单独选择**：把候选清单列给用户（原文 + 出现次数 + AI 建议译名），由用户逐条或整表定夺；定稿只收用户点头的条目
   - **不翻译**：专有名词保留原文，跳过术语表收录与后续统一（`glossary.json` 不产出或为空，直接进正文翻译）
   - **AI 自行选择**：按下方资格判据由 AI 定稿（继续 4–6 步）
   - 用户回答前不要产出 `glossary.json`，也不要开始大规模正文翻译
4. 收录条目 `info` **极简**：一句话，只写身份/关系 + 必要消歧（如 `A（lo 的姐姐）`、`Parker（与 Park 消歧）`）；不写行号、出现次数、定义文件等取证细节。有 `collisions` 的条目写清"何时用本条译名、其它用法怎么翻"。**没有必要信息的条目 `info` 留空**——不填"角色名""某词的翻译"这类凑数描述。**不写备选译法**（"亦可作X"）——术语表是喂翻译模型的约束（glossary injection / 一致性检查），只给唯一确定译文；备选写法只进人工审校笔记（如 `.cache/` 的略读笔记），不进术语表与 xlsx。
5. `src` 取最短自然稳定边界；仅当大小写存在真实碰撞才标 `case_sensitive`。
6. 定稿合并：确定条目进 `glossary.json`（扁平 `{src: dst}`，喂 unify 统一）；带 info 的完整版存 `glossary_full.jsonl`（`{src, dst, info, case_sensitive}`，AI 翻译/polish时作为提示词注入）。随后跑 `python scripts/names/make_glossary.py <项目> --finalize glossary_full.jsonl` 生成**完整版 xlsx**（备注列取 info，极简仅翻译辅助，无则留空；`--xlsx PATH` 可改输出路径）。

## 3. 翻译规则

### 3.0 开工确认门（项目级翻译必经，一次问清，不连环追问）

摸底（行数规模 / 语言 / 有无已有译文）后一口气确认，**翻译方式三选一，默认推荐 ①**：

| 路线 | 适用 | 现实约束（如实告知用户） |
|------|------|------|
| **① AI 直接翻（推荐）** | 默认路线；小中体量、需边翻边修 | 意译原则 / 术语表 / 审查循环全套生效；大体量多轮分批 |
| **② 机翻 API（Bing/百度等）** | 预算为零、只求先占位 | **skill 无内置机翻脚本**，AI 现场实现且免费无 key 接口不稳定；直译腔重、Ren'Py 标签保护差，产出必过 `tl_check` + 润色轮兜底，总成本未必省 |
| **③ 自有 API key** | 数万行级、想指定模型 / 风格前置重翻 | key 只进 LinguaGacha 应用配置或环境变量，不要求发在会话里；未装 LinguaGacha 时摆下载选项，不静默安装也不静默跳过（与 SDK 缺失同哲学） |

同一轮顺带确认：目标语言（默认按路径推断）＋ 范围（全量重翻 / 只补空缺）。用户丢单文件零散几句 → 直接翻，不走此门。开工后用户随时可改方式，不设第二道门。

### 3.1 批次切分（AI / API 翻译通用）

- **每批约 1024 token（按原文计）**，按翻译块 / 条目切批；**批次边界永远落在完整条目上，绝不截断句子**——被截的条目整条挪入下批，宁可本批不满也不截半句
- 相邻批重叠 2~3 行原文做上下文衔接，避免人称 / 语气 / 称谓跳变
- 每批随附该批命中的术语表条目；批间发现的新术语回写 `翻译结果.md`（新词新用不许凭空造译名）

### 3.2 提示词以目的语言流畅为第一目标

- 角色定位写明："你是目标语言的母语本地化译者，任务是**用目标语言自然的表达重写原意**，不是逐词对应"——流畅优先于字面还原
- 正面指令替代负面清单：短句化、口语贴合角色语气、语法服从目标语言习惯；不用"不要中式英语"式空泛禁令
- 结构保护照旧：`{tag}` / `[插值]` / `%%` / 转义符逐字保留；输出只含译文，不带解释、不改动行号与文件结构

### 3.3 基本规则

- **只填空位**：翻译占位符内容为空（`""`）的部分；已有译文自动跳过（除非用户要求审查）
- **原文来源**：行内注释 `# character "原文"` 是翻译依据
- **禁直译、禁中式英语**：意译优先，只要含义相同且更符合目标语言语境即可，不必机械还原句式
- **目标语言判定**：文件路径（`game/tl/english/...`）或 `translate english strings:` 推断；用户指定则优先

## 4. 审查循环（Review & Polish）

- 新翻译完成后，**必须**对全部已翻译内容（含旧译文）做第二轮扫描
- 检查：中式英语/生硬直译、语法、语气是否符合角色性格、是否地道
- 发现问题直接修正，并在 `翻译结果.md` 的"审查修正"章节记录对比
- 输出总结：成功翻译文件数、审查修正条目数、跳过文件数
- 用户仍不满意或要求系统性润色时 → 用同目录的[译文润色方法](translation_polish.md)（双角色两阶段 / LinguaGacha 路线，按预算自选）

## 5. 版本预判（解包 / 开工前）

- 解包后先看 `game/script_version.txt`，内容即构建该游戏的引擎版本（如 `8.3.7`）。**低于 7.5 的引擎对中文兼容差**（字体回退/编码问题多），评估是否值得接
- 本地 SDK 跑 lint / 重编译时，**SDK 版本应 ≥ script_version.txt**；旧引擎发行版别用 8.x 专属 API 与 8.0 lint（会漏报 7.x 崩溃，详见 [renpy_gotchas.md](renpy_gotchas.md) 版本兼容条目）
- 改完译文进游戏不生效 → 先清翻译缓存再排查（`del /s /q game\tl\*.rpyc` + 删 `game/cache`，见 gotchas 翻译缓存条目）

## 5b. 收尾红线：脚本全绿 ≠ 玩家看到的都是中文

`check_untranslated` 只扫 tl 目录**内部**（空译文/new==old），`check_auto_trans` 只对已捕获的字符串交叉核对——**源脚本根本没有译文文件时，两者都看不见**（AfterDark 实测：124 个源脚本只有 70 个 tl 文件，`check_untranslated` 报 OK，玩家照样满屏英文）。收尾必须跑：

```bash
python renpy-tools-cli.py tlcoverage <项目> -l schinese   # 源脚本↔tl 文件覆盖对照
```

它利用 Ren'Py 的 tl 文件镜像约定（`game/foo/bar.rpy` → `game/tl/<lang>/foo/bar_translated.rpy`）按路径求差集，不依赖游戏结构，自定义程度高的项目也适用。缺口补法：用 SDK 跑 `renpy.py <项目> translate <lang>` 生成缺失骨架再走管线，或让机翻工具补齐那几个文件。

即使覆盖补满，Ren'Py 的译文骨架仍天然不全——以下几类**任何覆盖检查都看不见**，只能进游戏目验或读代码：

- 运行时构造的文本（init python 里 `Text()`、字符串拼接/插值变量）
- tl 生成之后才新增/改动的源文本（骨架是生成那天引擎所见的快照）
- `gui.rpy` 变量与 style 里烤死的字符串（部分进 `translate strings`，部分不进）

所以最终判据是「退出码 0 + 进游戏抽查主菜单/设置/存读档界面」，不要拿单次扫描输出当交付结论。

## 6. 图片 / 视频 / 字体的语言级资源覆盖

文本翻译之外，Ren'Py 支持把资源**按原路径同名**放进 `tl/<lang>/` 下，切换到该语言时引擎优先加载，原文件零改动：

```
game/tl/schinese/images/ui/title.png      # 覆盖 game/images/ui/title.png
game/tl/schinese/videos/op.webm           # 覆盖同名视频（须 webm/VP9）
game/tl/schinese/fonts/MiSans-Regular.ttf
```

- **图片烤字 / 图片 UI**：PS（或 AI 去字）抹掉原文后导出同名 png 放入对应路径，比 OCR 回贴图轻得多，优先用这条
- **视频内嵌字幕**：重压导出后转 webm（Ren'Py 只认 webm）；格式不对会静默不播
- **合成字体（保持原游戏字体风格）**：FontCreator 打开原英文字体 + 中文字体，把 CJK 字形按相同码点选择性粘贴进原字体，字形转换器调粗细，导出后**原名**放 `tl/schinese/fonts/`。常规字体注入用 `scripts/setup/setup_fonts.py` 即可，不必合成
- 语言切换按钮 / 默认语言：`scripts/setup/fix_lang_button.py` + `switch_default_language.py`（三件套排查顺序见 SKILL.md 注意事项）

## 7. 查缺补漏兜底：`config.replace_text`

官方 translate 机制收不进来的顽固文本（动态拼接、第三方 screen 硬编码），oldnew 和额外文本提取都失败后的**最后手段**——渲染期对文本做纯文本替换：

```rpy
init python:
    def replace_text(s):
        s = s.replace("Long fragment with context", "长串优先替换")
        s = s.replace("Short", "短串最后")
        return s
    config.replace_text = replace_text
```

- 只支持纯文本（不含 `{}`/`[]` 语法处理），多条规则时**长的放前面**（短串会先吃掉长串的子串）
- 兜底顺序：oldnew strings（新建 rpy，首行 `translate schinese strings:`）→ 额外文本提取（`check_untranslated.py` / 工具箱）→ `config.replace_text`
- 引擎源码依据（`text.py:2320` / `2881`、`extras.py:191`）、以及**第三方发行版用本钩子做机翻**（无 `tl/`、载荷伪装成音频）的识别与拆除 → [replace_text_hook.md](replace_text_hook.md)

## 8. 目标语言不是中文时（i18n 速查）

翻译链路按 Ren'Py 语言码工作（`game/tl/<码>`），中文只是默认值不是前提：

- **AI 翻译**：`autotranslate.py translate <tl目录> --target-language japanese`
  （语言码或语言名都行，`korean`、"Brazilian Portuguese" 均可；也可用环境变量
  `RENPY_TRANSLATE_TARGET_LANGUAGE`）。源语言同理 `--source-language`。
  语言码→英文展示名映射收在 `scripts/shared/lang_names.py`，prompt 里用的是语言名。
- **检查器**：所有 `-l` 参数照常传目标语言码，默认值统一出自
  `lang_names.DEFAULT_LANG`（现为 schinese）。
- **术语表**：`names/` 组（make_glossary / apply_glossary_body）对任意语言对工作，
  人名术语表结构与语言无关。
- **字体**：拉丁/西里尔目标语言通常无需换字体；RTL（阿拉伯语/希伯来语）需要
  引擎级支持，Ren'Py 原生不完善，不要向用户承诺。
- **润色启发式的边界**：`polish/` 管线的可疑行规则（被动句、英文词≥4、夹生词）
  是中文译文专用启发式，非中文目标不要跑 polish 中文规则，直接跳过该环节。

## 典型示例

```rpy
# game/scripts/ch1.rpy:15
translate schinese ch1_start_a1b2c3d5:

    # e "真是拿你没办法。"
    e ""
```
→ 意译为 `e "You're hopeless."`（不要直译 "Really can't do anything with you"）。
