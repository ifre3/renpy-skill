# 人名翻译统一

| 脚本 | 用途 |
|------|------|
| `unify_name_translations.py` | **主力脚本** v6 三步流程：收集 → 分类 → 统一 |
| `unify_names_v2.py` | 旧版频率统计（已弃用，保留作 fallback） |

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
# Step 1: 收集（扫描文件，记录角色名引用）
python unify_name_translations.py -g glossary.json -t game/tl/schinese --step 1

# Step 2: 分类（严格模式：只保留英文原名变体，不猜测）
python unify_name_translations.py --step 2

# --- 人工审核：检查 omitted_refs，手动添加需要替换的中文变体到 variants ---

# Step 3: 预览替换
python unify_name_translations.py --step 3 --dry-run

# Step 3: 执行替换
python unify_name_translations.py --step 3 --apply

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
| `--step` / `-s` | 指定步骤 (1=收集, 2=分类, 3=统一)。不指定则运行全部 |
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

## v2 vs v5 vs v6 区别

| | v2 | v5 | v6 |
|---|---|---|---|
| 变体来源 | 硬编码 KNOWN_VARIANTS | 自动发现（滑动窗口 + 英文匹配） | 仅英文原名匹配，不猜测 |
| 误报率 | 低（人工维护） | ~70%（滑动窗口） | 0%（严格模式） |
| 通用性 | 仅适用于特定游戏 | 适用于任何 Ren'Py 游戏 | 适用于任何 Ren'Py 游戏 |
| 流程 | 一步到位 | 三步分离（收集→分类→统一） | 三步分离（收集→分类→统一） |
| 格式支持 | 仅 c_xxx | c_xxx + 纯叙述 + old/new | c_xxx + 纯叙述 + old/new |
| 审核 | 无 | 编辑 JSON（需过滤大量误报） | 编辑 JSON（只看 omitted_refs） |
| 安全 | 全行 replace | CJK 边界保护 + 首次匹配 | CJK 边界保护 + 首次匹配 |
| 备份 | 单文件 .bak | 整目录快照 + 单文件 .bak 双层 | 整目录快照 + 单文件 .bak 双层 |
| 回滚 | 无 | --rollback 一键恢复 | --rollback 一键恢复 |
