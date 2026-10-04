# 润色工具族（原子化）

> 单一职责的小工具，配合 `references/translation_polish.md` 的策略一（局部润色档）使用。
> 全部纯标准库。回填一律走 `翻译相关/autotranslate.py apply --input <batch> --overwrite`
> （先 `--dry-run`），安全网：orig 锚点必须匹配、标签结构校验、自动 .bak。

## 管线

```
extract_say.py ──► entries.json（全量条目+锚点）
       │
       ├─► screen_suspicious.py ──► candidates.json（可疑行）/ untranslated.json（疑似漏翻）
       │
       ├─► ../统一名称/unify_names.py + glossary.json ──► name_fix.json（人名统一，可直接回填）
       │
       └─► merge_polish.py + fixes.json ──► polish_batch.json（AI 润色稿回填）
```

## 工具

| 脚本 | 职责 | 用法 |
|------|------|------|
| `_say_parse.py` | say 条目适配器（解析统一走 `../公共/rpy_syntax.py`，与 autotranslate 同层） | 库用 |
| `extract_say.py` | 抽取全量 say 条目（锚点与 autotranslate scan 兼容） | `python extract_say.py <tl目录> -o entries.json [--skip-empty]` |
| `screen_suspicious.py` | 翻译腔规则筛行（规则在顶部 RULES 增删） | `python screen_suspicious.py <tl目录或entries.json> -o candidates.json [--min-score 3]` |
| `merge_polish.py` | 把 AI 的 `file:line → 新译文` 映射合并成回填批次（锚点缺失即报出） | `python merge_polish.py --pool entries.json --fixes fixes.json -o polish_batch.json` |

> 人名统一不属本管线：`unify_names.py` 已归入 `../统一名称/`（与 v6 三步流程、make_glossary 术语表生产同目录）。

## AI 润色循环（策略一局部档落地）

1. `screen_suspicious.py` 筛出可疑行 + `tl_check.py`（崩溃级先修）。
2. AI 以润色者角色分批（~200 行/批）读 `candidates.json`，产出 `fixes.json`（只写新译文）。
3. `merge_polish.py` 合并 → `apply --dry-run` 核对 → 实际回填。
4. 跨会话用 `polish_state.json` 记录已完成批次；68k 行级项目不要指望一轮跑完。
5. 收尾复跑 `tl_check.py` + 引擎 lint（用游戏自带 `lib/py3-windows-x86_64/python.exe <启动py> . lint`）。

## 实测注意（2026-10-03/04，FriendshipClub 0.18，68,601 条）

- strings 块（含角色名）全库扫描必须逐行匹配 `old "..."`，不能假定 old/new 相邻——
  否则会像第一次那样漏掉 Time.rpy 的占位条目，新增 strings 条目时引擎 lint 报
  `A translation for "..." already exists` 直接启动失败。
- 名字框翻译生效机制：`who` 显示时经 `substitute(translate=True)` →
  `translate_string`（renpy/substitutions.py:328），所以 tl 侧补 `translate schinese strings`
  条目即可，无需给 Character 定义加 `_()`。
- 原版源码自带的标签 bug（`{/f}` `{/o}` `{/s}` 收错）会在 tl_check 里以
  "新旧标签不一致"出现；若译文侧写对了，属引擎不会崩的假阳性，修 tl 侧即可、别改回错的。
- 译文裸 `%`（如 `100%`）在 `config.safe_text=False`（默认）下显示到该行直接崩溃，写 `%%`。
