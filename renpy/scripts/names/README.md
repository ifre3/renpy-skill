# names/ — 人名翻译统一

> **要点已内联到 [../README.md](../README.md)「names/ — 人名翻译统一」一节**，本文件只留分工与命令。

| 脚本 | 用途 |
|------|------|
| `make_glossary.py` | 术语表草稿生成（生产端）：扫 tl strings 取证，产出 glossary.json 草稿 + 证据 JSONL（`.cache/`）+ 默认落**游戏根目录** `术语表.xlsx`（AiNiee 三栏 `原文|译文|备注`，按列序读取）；`--finalize <定稿>` 据 AI 定稿生成完整版，`--no-xlsx` 纯取证 |
| `apply_glossary_body.py` | 批式正文人名统一（无审核需求时用）：glossary 直改，产出 apply 批次 JSON |
| `unify_name_translations.py` | v6 主流程（需审核/回滚时用）：收集 → 分类 → 统一 |

```bash
python make_glossary.py <项目> --lang schinese -o glossary.json   # 草稿+证据+xlsx（默认 游戏根/术语表.xlsx）
python make_glossary.py <项目> --finalize glossary_full.jsonl     # AI 定稿 → 完整版 xlsx（备注=info）
python make_glossary.py <项目> --no-xlsx -o glossary.json         # 纯取证，不生成 xlsx
python unify_name_translations.py -g glossary.json -t game/tl/schinese --step collect
python unify_name_translations.py --step classify          # 人工审核 omitted_refs
python unify_name_translations.py --step unify --dry-run   # 预览
python unify_name_translations.py --step unify --apply     # 执行
python unify_name_translations.py --rollback -t game/tl/schinese
```

术语表格式：`{"Tomori": "灯里"}` 或 `[{"src": "Tomori", "dst": "灯里"}]`。
AiNiee 导入用 xlsx：表头 `原文|译文|备注`，跳过表头按列序读（第 1 列非空即收）；备注仅放极简消歧辅助（身份/简称/特指提示一句话），**不写备选译法**（模型约束只要唯一译文），无则留空。
资格判定见 [../../references/translation_workflow.md](../../references/translation_workflow.md)。
