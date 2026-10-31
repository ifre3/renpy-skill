# polish/ — 译文润色原子化管线

> **要点已内联到 [../README.md](../README.md)「polish/ — 译文润色」一节**，本文件只留管线图与两条设计说明。

```
extract_say.py ──► entries.json（全量条目+锚点）
        │
        ├─► screen_suspicious.py ──► candidates.json（翻译腔可疑行）
        ├─► screen_quality.py    ──► quality_candidates.json（硬性质可疑行）
        ├─► direct_polish.py     ──► direct_fixes.json / direct_report.json
        │                                 （无 API 规则层：机翻味/标点矫正，可 --apply 回填）
        └─► plan_batches.py      ──► batch_NNN.json / .prompt.md / polish_state.json
                                                └─► merge_polish.py + fixes.json ──► 回填批次
```

## 两层分工：机翻矫正 vs 审稿

这条管线做的是两件不同的事，分层是刻意的：

| | 机翻矫正层 | 审稿层 |
|---|---|---|
| 工具 | `screen_*`（筛行）+ `direct_polish.py`（规则改写） | `plan_batches.py` 的剧本提示词 + AI |
| 判定 | 关键词/正则，零 token | 通读整段戏后的判断 |
| 能修的 | 半角标点、重复「的」「的」、`将会`、`如果…的话`、连续标点 | 语序、语气、角色贴合、前后衔接 |
| 修不了的 | 「这句读着别扭」「和上一句接不上」 | 标点格式 |

**审稿层怎么才能真的审稿**（2026-10-18 按 Dissonance 0.14 实测改过一轮，详见
[../../references/translation_polish.md](../../references/translation_polish.md) §7）：

- **提示词渲染成连续剧本块**（`### 场景` + `` `file:line` 角色：`` + `原：`/`译：`），不是 `| file:line | 角色 | 原文 | 译文 |` 表格。表格把每行变成孤立四元组，模型看不到前后句。
- **按 Tier 分层给料**（`classify_entry`）：

  | Tier | 给什么 | 判据 | 实测占比 |
  |------|--------|------|---------|
  | **A** | 只给译文 | 语病 / 语序 / 冗余 / 语气——中文母语读译文就能判断 | ~99% |
  | **B** | 原文 + 译文，标 `⚠` | 外文残留、假名、译者疑虑标记 `(?)、`长度比 < 0.8`（疑似漏译） | ~0.8% |

  理由：Tier A 塞原文是纯浪费（一半 prompt 体积）；Tier B 不塞原文则必然瞎猜——实测
  教训是把 `私室` 猜成「包厢」。取向是**宁可漏标不可误标**：误标只是多看一眼原文，
  漏标会让审稿者在没有依据的情况下改写语义。`--tier-report PATH` 导出需对照的清单。

  分层立刻见效的实例：`Chap1:38862` 的 `(?)` 看着可疑，一对照原文就确认
  `masked man(?)` —— **原文自带，译者保留是对的**，不该改。

- **不截断长句**（上限 `SCRIPT_MAX_CHARS = 400`；实测该库最长 orig 200 余字，等于零截断）。旧版一律截到 90 字，39.4% 的行原文被砍半。
- **`--skip-placeholders`**：跳过 `...` 这类纯占位行（实测占 5.5%），无可审内容却白占批次与注意力。
- **角色是「中文审稿人」，不是「校对润色者」**：显式写「大部分句子是好的，保持原样」「拿不准就不改」「禁止为了改而改」。
- **只输出改动行**：判断为「不用改」的句子不进 `fixes.json`。`merge_polish.py` 另会把「值与旧译文相同」的条目归入 `[跳过]`——回填与否等价，留着只污染 diff 与统计。

## 零 API 直接润色：`direct_polish.py`

整条管线从 `plan_batches` 到 `merge_polish` 都把“AI 润色”当必需环节。没 API 密钥、或只想先做本地规则清洗再交 AI 润残留时，用 `direct_polish.py`（属机翻矫正层，不含审稿）：

```
python polish/direct_polish.py game/tl/schinese -o .cache/polish/direct_fixes.json
                                                  --report .cache/polish/direct_report.json
# 先干跑：看 direct_report.json 里每条改了什么规则、前后对比
# 满意后：
python polish/direct_polish.py game/tl/schinese --apply   # 自带 .bak + 原子写入
```

产出的 `direct_fixes.json`（`file:line → 新译文`）可直接进回填通道：

```
python translate/autotranslate.py apply game/tl/schinese \
    --input .cache/polish/direct_fixes.json --overwrite --dry-run
python translate/autotranslate.py apply game/tl/schinese \
    --input .cache/polish/direct_fixes.json --overwrite
```

也可把规则改完的译文先塞进条目池，再由 `plan_batches` 切批，让 AI 只润规则搞不定的残留：

```
# 1. 规则层先过一遍（默认只出 JSON，不碰 tl）
python polish/direct_polish.py game/tl/schinese -o .cache/polish/direct_fixes.json

# 2. 复核报告后写回 tl（--apply 自带 .bak + 原子写入，保留原文件 BOM）
python polish/direct_polish.py game/tl/schinese --apply

# 3. 重新抽条目（此时池里已是规则改过的译文）
python polish/extract_say.py game/tl/schinese -o .cache/polish/entries.json

# 4. 切批：AI 只润规则搞不定的残留
python renpy-tools-cli.py polish --pool .cache/polish/entries.json \
    --tl game/tl/schinese --candidates .cache/polish/candidates.json \
    -o .cache/polish/
```

> 不提供 `--direct-fixes` 这类「预载改写结果」的选项：多一次 `extract_say.py`
> 抽取（约 30s），换来切批器不必维护第二份改写状态。简洁优先。

## 结构守恒门

`merge_polish.py` 合并时带**结构守恒门**：逐条拿润色稿与**润色前译文**比对标签 `{}`／插值 `[]`／
`%` 格式符多重集与换行数，对不上的条目不入批次、单独列原因并以退出码 1 提示。
下游 merge 与 `apply` 都只核锚点，润色把 `{i}` 润丢了要等回填完跑 `tl_check` 才发现，
所以这道门放在合并这一步。基线取润色前译文而不是英文原文——判据收窄成「这次润色引入了什么」，
历史遗留的结构损伤（该由 `tl_check --fix --settle` 修）不会卡住整批。

全部不碰 tl 文件，直到 `translate/autotranslate.py apply --overwrite` 才落笔（先 `--dry-run`）。
策略选择、prompt 要点与 token 成本对照见 [../../references/translation_polish.md](../../references/translation_polish.md)。
