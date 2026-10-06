# 人名翻译统一

| 脚本 | 用途 |
|------|------|
| `unify_name_translations.py` | **主力脚本** v6 三步流程：收集 → 分类 → 统一（含审核与 `--rollback`） |
| `apply_glossary_body.py` | 批式正文人名统一：glossary 直改（长名优先、CJK 紧排），产出 autotranslate apply 批次 JSON，走安全回填（原名 `unify_names.py`，因与主力脚本名过近易调错而更名） |
| `make_glossary.py` | 术语表草稿生成（生产端）：扫 tl strings 块自动产出 glossary.json 草稿 + 漂移/未翻译报告 |

分工：`make_glossary` 取证 → 快速批改用 `apply_glossary_body`（无审核需求）→ 需要逐条审核/中文变体/回滚时走 `unify_name_translations` v6。

## make_glossary.py — 术语表从哪来（v3 确定性取证端）

分工原则（学自 LinguaGacha glossary 技能）：**脚本只做确定性取证，资格判断交给 AI 略读全文**（旧词新用、info 描述、普通词判定不读原文不可能做，脚本不做）。`python make_glossary.py <项目> --lang schinese`（默认输出到项目根 `.cache/glossary_draft_<项目名>.json`，不散落项目根；`-o` 可指定路径）：AI 自己的中间产物（批次 JSON、状态账本、略读笔记）同样进 `<项目根>/.cache/`，判据见 [../../references/translation_workflow.md](../../references/translation_workflow.md) 2.5 第 1 步；

- **人名主来源 = game 源码 `Character("...")` 定义**（身份最明确、零误报；变量插值跳过；纯 .rpyc 发行版提示先反编译）。Character 人名 + strings 唯一译名 → 直接进草稿 JSON
- **tl strings 块配对**（逐行匹配，不假定 old/new 相邻）、**字面碰撞**（May/may 式包含关系）、**出现次数**（证据字段，不是门槛）作为报告与证据输出
- 草稿 JSON 扁平格式与两个消费端（本目录 v6 与 apply_glossary_body.py）直接兼容；**普通术语不自动进草稿**——进 `<output>.evidence.jsonl`，由 AI 按 translation_workflow.md「术语表精读」判定资格、补 info（如"A（lo 的姐姐）"）后合并

## v6 架构：收集 → 分类 → 统一

三步职责分离，每步只做一件事。

### 设计原则

**变体来源严格限制，不做滑动窗口猜测。**

变体只有两种来源：
1. **概率筛选**：英文原名出现在中文译文里 → 英文变体（大概率是漏翻）
2. **精确匹配**：译文含标准译名 → ok

两者都没有 → `omitted`（未翻译/遗漏），**不猜测**，留给人工或 LLM 处理。

### Step 1 — 收集

扫描翻译文件，解析所有翻译块（**必须有注释行作为英文原文**），记录角色名引用。
**不做任何分类判断**，只产出原始数据。

输出 `name_collection.json`：
```json
{
  "refs": [
    {"en_name": "Tomori", "standard": "灯里", "file": "...", "line": 42, "en_context": "...", "cn_text": "..."}
  ]
}
```

### Step 2 — 分类

读 Step 1 的原始数据，对每条引用进行分类：
- `ok` — 译文含标准译名
- `variant` — 译文含英文原名（漏翻）
- `omitted` — 译文中既没有标准译名也没有英文原名（未翻译/遗漏/使用了其他中文译名）

**omitted 条目会附带完整上下文**（文件、行号、英文原文、中文译文），方便人工或 LLM 审核。

输出 `name_classification.json`：
```json
{
  "names": {
    "Tomori": {
      "standard": "灯里",
      "ok_count": 441,
      "omitted_count": 9,
      "variants": {},
      "omitted_refs": [
        {"file": "chapters/ch3.rpy", "line": 8612, "en_context": "...", "cn_text": "朋莉的..."}
      ]
    }
  },
  "totals": {"ok": 3707, "variant_kinds": 0, "variant_occurrences": 0, "omitted": 43}
}
```

**审核方式**：
- `variants` 里的条目可以直接信任（英文原名漏翻，替换为标准译名即可）
- `omitted_refs` 里的条目需要人工或 LLM 判断：译文中是否使用了不同的中文译名？

### Step 3 — 统一

读取分类结果，对所有变体执行安全替换（替换为标准译名）。

安全机制：
- CJK 边界保护：短名（≤2字）前后紧邻 CJK 字符时跳过
- 首次匹配：只替换引号内首次出现，避免一行内多次误替换
- 双层备份：整目录快照 + 单文件 .bak
- 拒绝覆盖：备份目录已存在时拒绝执行，保护原始数据
- 一键回滚：`--rollback` 恢复全部文件

## 典型工作流

```bash
# Step 0: 生成术语表草稿（还没有 glossary.json 时；报告里的漂移/未翻译项先定稿）
python make_glossary.py <项目> --lang schinese -o glossary.json

# Step 1: 收集（扫描文件，记录角色名引用）
python unify_name_translations.py -g glossary.json -t game/tl/schinese --step collect

# Step 2: 分类（严格模式：只保留英文原名变体，不猜测）
python unify_name_translations.py --step classify

# --- 人工审核：检查 omitted_refs，手动添加需要替换的中文变体到 variants ---

# Step 3: 预览替换
python unify_name_translations.py --step unify --dry-run

# Step 3: 执行替换
python unify_name_translations.py --step unify --apply

# 回滚
python unify_name_translations.py --rollback -t game/tl/schinese
```

## 如何处理 omitted 条目

`omitted_refs` 中的条目是"译文中既没有标准译名也没有英文原名"的情况。
可能的原因：
1. **使用了不同的中文译名**（如标准是"灯里"但译文用了"智"、"友利"等）
2. **翻译时省略了角色名**（如英文"Right, Yui?" → 中文"咲，你说呢？"完全改写了句子）
3. **角色名在原文中但译文没有对应**（如叙述行中省略了主语）

处理方式：
- **原因 1**：在 `name_classification.json` 的 `variants` 中手动添加变体条目
- **原因 2/3**：不需要处理（翻译本身没错，只是没有用人名）

建议使用 LLM 辅助审核 omitted 条目，判断译文中是否使用了不同的中文译名。

## CLI 参数

| 参数 | 说明 |
|------|------|
| `--step` / `-s` | 指定步骤：1/collect=收集，2/classify=分类，3/unify=统一（编号与名称等价）。不指定则运行全部 |
| `--glossary` / `-g` | 术语表 JSON 文件路径 |
| `--tl-dir` / `-t` | 翻译文件目录 |
| `--collection` / `-a` | Step 1 收集结果文件路径 |
| `--classification` / `-c` | Step 2 分类结果文件路径 |
| `--dry-run` / `-n` | Step 3: 预览模式，不实际修改 |
| `--apply` | Step 3: 执行替换 |
| `--rollback` | 从备份恢复所有文件 |

## 术语表格式

```json
{
  "Tomori": "灯里",
  "Nami": "奈美",
  "Saki": "咲"
}
```

或列表格式：
```json
[
  {"src": "Tomori", "dst": "灯里"},
  {"src": "Nami", "dst": "奈美"}
]
```

## 为什么不自动猜测中文变体？

v5 版本使用滑动窗口从 CJK 文本中提取候选变体，但误报率高达 ~70%：
- "我听说"、"你确定"、"看好了" 等正文短语被误识别为人名变体
- 单字标准译名（如"咲""莉"）的变体发现不稳定

v6 严格模式**只保留可信赖的变体来源**（英文原名匹配），将无法自动判断的条目归为 `omitted`，交给人工或 LLM 处理。这样：
- **零误报**：不会把正文短语误替换为人名
- **审核友好**：omitted 条目附带完整上下文，一目了然
- **可扩展**：未来可接入 LLM 审核 omitted 条目，自动提取中文变体

## v5 vs v6 区别

| | v5 | v6 |
|---|---|---|
| 变体来源 | 自动发现（滑动窗口 + 英文匹配） | 仅英文原名匹配，不猜测 |
| 误报率 | ~70%（滑动窗口） | 0%（严格模式） |
| 通用性 | 适用于任何 Ren'Py 游戏 | 适用于任何 Ren'Py 游戏 |
| 流程 | 一步到位 | 三步分离（收集→分类→统一） | 三步分离（收集→分类→统一） |
| 格式支持 | 仅 c_xxx | c_xxx + 纯叙述 + old/new | c_xxx + 纯叙述 + old/new |
| 审核 | 无 | 编辑 JSON（需过滤大量误报） | 编辑 JSON（只看 omitted_refs） |
| 安全 | 全行 replace | CJK 边界保护 + 首次匹配 | CJK 边界保护 + 首次匹配 |
| 备份 | 单文件 .bak | 整目录快照 + 单文件 .bak 双层 | 整目录快照 + 单文件 .bak 双层 |
| 回滚 | 无 | --rollback 一键恢复 | --rollback 一键恢复 |
