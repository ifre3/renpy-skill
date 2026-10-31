# renpy-skill polish 管线：值得批评的地方（2026-10-18）

本文件记录对 `renpy/scripts/polish/` 及相关文档的诚实批评，作为本次润色功能改动的出发点。

## 1. `screen_suspicious.py` 默认 `--min-score 3` 过高，会漏行

`RULES` 里每条规则有独立权重（1~3），`entry_score` 把命中规则的权重累加。默认 `--min-score 3` 意味着：
- 只命中一条权重 1 或 2 的规则（如单个“被动句”“是否”“英文词≥4”）的行会被漏掉；
- 需要两条低权重规则凑分才会入选。

文档（`translation_polish.md` 第 57 行）自己也承认：“默认 `--min-score 3` 会漏掉只命中一条低权重规则的行——专项排查夹生词时降阈值。” 既然已知会漏，默认值就不该是 3，应该下调到 2，由需要高精度的用户自己 `--min-score 3`。

## 2. 整个 polish 管线把“AI 润色”当必需环节，无零 API 成本入口

`plan_batches.py` 产出 `batch_NNN.prompt.md` 给 AI 看，AI 产出 `fixes.json`，再走 `merge_polish.py` + `autotranslate apply --overwrite`。这条链路上没有任何“不调大模型”的分支：
- 没有 API 密钥/端点的用户，只能停在筛行阶段，知道哪些行可疑，但改不了；
- 很多翻译腔问题（半角标点、重复“的”、被动直译“将会”、“如果…的话”）是**规则就能机械改**的，不值得花 token 让模型去改；
- 没有一个“先规则清洗、再交 AI 润残留”的预处理分支，导致 token 被简单问题浪费。

## 3. `plan_batches.py --candidates` 要求用户手动组合两个筛行器

用户必须先分别跑 `screen_suspicious.py`（出 `candidates.json`）和 `screen_quality.py`（出 `quality_candidates.json`），再把两个文件路径都传给 `--candidates`。没有“一键自动筛行+去重”的入口，新手容易漏跑其中一项，或者两份结果有重叠行却无去重统计。

## 4. `extract_say.py` 条目不带 `scene` 字段，plan_batches 要二次回扫

`plan_batches.load_scene_map()` 的注释已直言：“`extract_say.py` 的条目没有场景字段，这是当前数据结构唯一的硬缺口。” 代码因此要回扫 tl 目录、用正则找 `translate <label>_<hash>:` 再上溯匹配原文注释行，既慢又脆弱（行号漂移后场景绑定会错）。`scene` 理应在抽取时就带入条目。

## 5. 默认批次 200 固定，缺少更小批次的便捷入口

文档（`translation_polish.md` 第 20 条）说“批次过大会明显掉质量、术语不一致增多”，建议“一次只给润色者 2~3 批”，但默认 `--batch-size 200` 且没有更小批次的快捷方式，用户想按 80~120 条切批得手动传参，且文档没给推荐下限。

## 6. `merge_polish.py` 结构守恒门是“一票否决”且无弱模式回退

润色稿只要把 `{i}` 润丢、加了 `[插值]`、换行增加，就被整条剔除、退出码 1。对非技术用户来说，被剔除的条目只能手动修 `fixes.json` 再重跑 `merge_polish`，没有“保留文本、仅标记风险”的弱模式，容易卡住润色流程。

## 7. 文档与代码的“可执行性”有断层

`translation_polish.md` 策略一的流程（步骤 1~6）写得很详细，但直到 `plan_batches.py`（2026-10-11 新增）才有脚本产出切批和提示词；在此之前“切批与提示词生成已脚本化”只是文档承诺，代码跟不上。说明文档先行、代码补位的节奏不均匀。

---

## 本次改动针对上述问题

| 问题 | 改动 |
|------|------|
| 1 | `screen_suspicious.py` 默认 `--min-score` 3 → 2 |
| 2 | 新增 `polish/direct_polish.py`：基于规则的无 API 直接润色，产出 `direct_fixes.json`，可 `--apply` 回填，也可作为 `plan_batches --direct-fixes` 预处理 |
| 3 | 曾新增 `plan_batches.py --auto-screen`，后于 2026-10-21 删除（与显式 `--candidates` 二选一会造成两条易漂移的入口；筛选行为交给筛行器脚本本身更可测）。当前一键做法：依次跑两个筛行器后把两份 JSON 都传给 `--candidates` |
| 4 | 记录在案，本次不改 `extract_say.py` 数据结构（避免改动解析契约与测试）；场景回扫保留降级逻辑 |
| 5 | `plan_batches.py` `--batch-size` 保留 200（默认值未变；文档 `translation_polish.md` 现有表述仍为「约 200 句/批，一次只给 2~3 批」，未写入 80~120 的推荐下限——本条当时声称的文档补充实际未落地，如需更小批次手动传参即可） |
| 6 | 记录在案，本次不改 `merge_polish` 一票否决逻辑（结构安全优先）；被剔除条目已有清晰原因输出 |
| 7 | 文档同步更新 `polish/README.md`、`references/translation_polish.md`、`renpy/SKILL.md` |
