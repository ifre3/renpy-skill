# translate — AI 翻译、导出与翻译后修补

这里的工具用于 Ren'Py 翻译生成后的**写入与修补**，不替代 Ren'Py SDK lint。

与 `../checks/` 的分工（2026-10-06 调整）：`checks/` 收**全部只读检查器**，本组
只留**会改文件**的工具——回填、修补、同步。原先放在本组的 3 个只读检查器
（`check_translation_integrity.py` / `check_untranslated.py` /
`check_charname_translation.py`）已归位到 `../checks/`，因为它们判据都在只读审计上，
且现在要和门面 `all` 的其余检查器共享同一套 `CHECKER` 契约（`../shared/base_checker.py`）。
润色是本组下游：`../polish/` 的产出最终经本组 `autotranslate.py apply` 回填。

## 工具一览

| 脚本 | 功能 |
|------|------|
| `autotranslate.py` | 统一翻译管线：扫描 → 分批 LLM 翻译 → 校验 → 安全回填 |
| `sync_namebox_translation.py` | 角色名字框同步（Character → translate strings，需术语表） |
| `fix_translation_comments.py` | 翻译注释中的术语反向恢复 |
| `patch_renpy_say.py` | 修补 Python `renpy.say()` 硬编码英文 |
| `fix_missing_tags.py` | 尝试修复丢失标签，低置信度项只生成人工清单 |

只读检查（`check_translation_integrity` / `check_untranslated` /
`check_charname_translation`）见 `../checks/README.md`，或直接用门面
`python ../renpy-tools-cli.py all <项目> -l schinese` 一次跑完。

## 推荐流程

```powershell
cd D:/path/to/tools/translate

# 1. 扫描空译文（不调用 API）
python autotranslate.py scan "game/tl/schinese"

# 2. 配置端点与密钥。均不写入源码或缓存（OpenAI 兼容端点）
$env:RENPY_TRANSLATE_API_URL = "https://你的端点/v1/chat/completions"
$env:RENPY_TRANSLATE_API_KEY = "你的密钥"

# 3. 翻译到缓存；可随时中断后重跑
python autotranslate.py translate "game/tl/schinese" --max-chars 1000

# 4. 先预览，再回填
python autotranslate.py apply "game/tl/schinese" --dry-run
python autotranslate.py apply "game/tl/schinese"

# 5. 最终检查（只读检查器已归位到 ../checks/；门面一次跑完全套）
python ../renpy-tools-cli.py all "../.." -l schinese
```

单个检查器则直接调 `../checks/` 下的脚本，例如
`python ../checks/check_untranslated.py "game/tl/schinese" --all`。

## 译文润色（二次提质）

初翻完成后需要对译文润色时，按预算与范围选用：双角色两阶段润色工作流（初翻=本管线输出，润色者独立会话逐批过）或 LinguaGacha 路线。策略选择、prompt 要点、token 成本对照见 [../../references/translation_polish.md](../../references/translation_polish.md)；回填沿用本管线 `apply` 的安全规则。

## 角色名字框审计（../checks/check_charname_translation.py）

Ren'Py 显示说话人名字时会走 `substitute(translate=True)`，所以**名字框是否显示中文，取决于 tl 里有没有 `old "名字"` 完全匹配的条目**——和名字定义在哪里无关。
`check_auto_trans.py` 只覆盖 menu 选项等字符串，不覆盖只出现在 `Character("Name")` 里的名字；`sync_namebox_translation.py`（本组，写入类）需要先有术语表。审计侧补这个缺口：

```bash
# 审计（项目根目录或 game 目录均可）
python ../checks/check_charname_translation.py "../../MyGame-1.0-pc" -l schinese

# 缺失项导出待填骨架，填完 new 后放进 tl/<lang>/
python ../checks/check_charname_translation.py "../../MyGame-1.0-pc" --stub game/tl/schinese/zz_charnames.rpy
```

输出会列出缺失名字及其实际台词条数（排优先级），退出码 1 表示有缺失/空译文。
译名务必与既有正文一致（例如正文里已把 Lilith 译作"莉莉丝"，名字框就沿用），可用 `grep` 在 tl 里核对。

也可临时使用 `--api-key`，但命令行参数可能进入 shell 历史，不推荐。

## 安全与校验规则

- 同时支持 `c_x`、`e`、`mmc` 等任意角色变量，以及普通旁白和 old/new。
- 插值支持任意 Python 表达式，例如 `[player.names[0]]`、`[score / max:.1%]`；不只检查简单变量名。
- 保护 `{tag}`、`[expression!t]`、`[[` / `{{` 和反斜杠转义；回填前检查数量、参数与嵌套结构。
- 回填必须同时匹配行号处的原文、目标角色和空目标；源文件变化后陈旧缓存会跳过。
- JSON 路径禁止越出翻译目录；默认不能覆盖非空译文，确需覆盖用 `--overwrite`。
- `status=warn` 默认不应用。人工修正缓存后，才使用 `--include-warnings`。
- 写回使用 `.bak` + 原子替换；备份失败会阻止写入。
- 只有 `translate` 子命令需要第三方 `requests`；`scan/apply/status` 可在未安装时使用。

## JSON 回填格式

```json
[
  {
    "file": "chapters/ch1.rpy",
    "line": 123,
    "type": "cd",
    "char": "c_mc",
    "orig": "Hello [name!t]",
    "trans": "你好 [name!t]"
  }
]
```

`line` 是 `# ...` 原文注释或 `old` 行的 1 基行号。`orig` 必须与当前文件完全一致；`trans` 是运行时文本，写回时会自动进行 `.rpy` 字符串转义。

## 缓存说明

缓存位于翻译目录的 `.autotranslate_cache.json`，通过原子写入保存。缓存键包含文件、行号、类型、角色和原文，源文本变化后不会被误用。`warn` 表示格式校验未通过，缓存会保留供人工检查，但默认不会回填。
