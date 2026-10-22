---
name: renpy
description: "Ren'Py 全栈技能：工程工具链（lint/编译/打包/翻译/结构分析）+ 开发参考（画廊/数值/陷阱库/字体与字号排版）+ 玩家侧（解包/存档/汉化/解锁补丁）+ 排错（崩溃排查、traceback 判读、汉化缺句与质检、字体方块、字号不联动）。写游戏、做汉化、跑 lint、打包发行版、解包别人的游戏、排查报错时激活。"
# 主线面向 ≥8.0。7.x 发行版也能用：旧引擎有专门路径（见「注意事项·旧引擎发行版」，
# references/tools_boundaries.md 的引擎版本经验整节是 7.4.8 实测结论），但 lint
# 结果不可信——新 SDK 会把 7.x 的非法 config 当合法掩盖崩溃。
compatibility: "renpy>=7.4（>=8.0 为完整验证范围；7.x 走发行版自带解释器验证）"
metadata:
  openclaw:
    emoji: 🛠️
    permissions: ["file.read", "file.write", "exec"]
    os: ["windows", "linux", "darwin"]
---

# Ren'Py — 全栈技能

统一 CLI 入口：`python scripts/renpy-tools-cli.py <子命令> <项目路径>`（`list` 看全部）。

## 你说 → 它做

| 你说 | 它做 |
|------|------|
| 检查代码有没有问题 | `cli.lint` 语法检查 |
| 项目体检 / 闪退 / 缺句 / 名字是英文 | `renpy-tools-cli.py all <项目> -l schinese`（18 项只读检查，退出码 1 = 查出问题而非崩溃）。详解见 [scripts/README.md](scripts/README.md) |
| 多语言链路 / 语言切换通不通 | `langcheck`（check_i18n 只读测试） |
| 字体接没接对 / 切语言会不会方块 | `fontcheck`（check_fonts 只读测试） |
| tl 翻译文件质检 / 译文插入变量导致崩溃 | `tlcheck`（`checks/tl_check.py`，三级报告 + `--fix`；**分级细则唯一完整出处** = [references/tl_check.md](references/tl_check.md)） |
| 打包 Windows / APK / Web | `scripts/sdk/cli.py` 的 Python 方法（`distribute` / `android_build` / `web_build`）——**不是** `renpy-tools-cli.py` 子命令 |
| 分析项目结构 / 有多少 label | `renpy-tools-cli.py linear analyze`（`analyze` 是 `linear` 的二级子命令，不是顶层子命令） |
| 添加中文翻译 / 导出翻译 | `scripts/sdk/cli.py` 的 Python 方法（`translate` / `extract_strings` / `merge_strings`）——**不是** `renpy-tools-cli.py` 子命令 |
| 写剧情 / 加画廊 / 养成数值 / 设置项 | AI 直接写 .rpy；陷阱见 [references/snippets.md](references/snippets.md)，画廊/数值见 [references/gallery_and_stats.md](references/gallery_and_stats.md) |
| 从零做一个游戏 | [references/game_creation_workflow.md](references/game_creation_workflow.md)（立项确认 → 骨架 → 剧本落盘 → 占位资产 → 逐章验证 → 打包；美术由用户出，skill 只管占位与接入） |
| 解包 / 反编译 / 改存档 / 一键解锁 CG | [references/player_tools.md](references/player_tools.md)、[references/unlock_patches.md](references/unlock_patches.md) |
| 想改数值 / 看隐藏选项 / 重放剧情 | URM（投放式不碰原文件，需引擎 ≥6.99.14）→ player_tools.md。**URM 解不了画廊**（判据是 `_seen_ever` 而非 `_seen_images`），开画廊用 unlock_patches.md |
| 名字栏显示英文 / 名字没汉化 | 先跑 `checks/check_charname_translation.py`（含裸 define + 内联说话人），缺译名的补进术语表，再 `sync_namebox_translation.py --stub game/tl/<lang>/zz_namebox.rpy --apply`；**带 `{color=}` 标签的名字必须整串匹配**，详见 [references/namebox_translation.md](references/namebox_translation.md) |
| 汉化这个游戏 | [references/translation_workflow.md](references/translation_workflow.md)（**术语表定稿前必须停下征求用户**；`make_glossary.py` 默认落游戏根目录 `术语表.xlsx`，AiNiee 三栏 原文\|译文\|备注，AI 定稿后 `--finalize` 出完整版） |
| 翻译腔太重 / 想润色 | 润色管线（**审稿**，不是机翻矫正）：`extract_say.py` → `screen_suspicious.py` + `screen_quality.py` 零 token 筛行 → [`direct_polish.py` 无 API 规则层矫正（机翻味/标点）] → `plan_batches.py` 按场景切批并生成**连续剧本块**提示词（不截断长句、明确允许「大部分不改」）→ AI 审稿只输出改动行 → `merge_polish.py`（结构守恒门 + 剔除未改动行）→ `autotranslate.py apply --overwrite`。**润色只做一轮**（越润越差），账本防重润；见 [references/translation_polish.md](references/translation_polish.md) |
| 没有 tl 目录却是中文 / 弹窗推网站 / 想拆引流 | `renpy-tools-cli.py payloadscan <项目>`（只读，列出载荷形态 + 引流/汉化证据行号）。**拆除前必读** [references/replace_text_hook.md](references/replace_text_hook.md) 第 4 节：二者同 blob 时**只删引流**（`overlay_screens`/`define_screen`/联网），**必须保留** `config.replace_text` 及其依赖（词表加载、匹配函数、`_b_*` 内建别名） |
| 中文显示不出来 / 切不到中文 | 按序：① `langbtn --apply` 修语言按钮写死 ② `lang` 设默认语言 ③ `fonts` 注入字体 ④ 仍无切换入口则 `setup_i18n` 生成。勿重复造轮子 |
| 崩溃 / traceback | 没有脚本——直接给 AI 判读，比正则准；系统性排查见 [references/debugging.md](references/debugging.md) |
| 旧引擎发行版（≥8.0 lint 不可信） | 用**游戏自带解释器**就地验证：`cd <游戏根> && ./lib/windows-x86_64/python.exe <启动>.py . lint`；跑 `test` 必须加 `SDL_VIDEODRIVER=windows`。版本坑见 [references/renpy_gotchas.md](references/renpy_gotchas.md) |

## 分支判据（条件不满足就换路，别照抄上一行）

| 条件 | 判据 | 是 → | 否 → |
|------|------|------|------|
| 中文但 `game/tl/` 不存在 | 跑 `payloadscan` | 载荷路径：按第 4 节**只删引流**，保 `replace_text`（删错 = 汉化全没） | 正常 tl 路径：`tlcheck` / `untranslated` |
| 想改数值 / 开隐藏内容 | 画廊判定走 `_seen_ever`？ | 是 → [unlock_patches.md](references/unlock_patches.md) | 否（`_seen_images` 类）→ URM（≥6.99.14，不碰原文件） |
| lint 结果可不可信 | 游戏引擎版本 | 7.x → **只用**游戏自带 `lib/.../python.exe` 验证，SDK lint 不可信 | ≥8.0 → `cli.lint` |
| 中文显示不出来 | 已有语言切换入口？ | 有 → 只 `langbtn` / `fonts` 补漏 | 无 → ① `langbtn --apply` ② `lang` ③ `fonts` ④ `setup_i18n`，**按序，勿跳步重造** |
| 崩溃 / traceback | —— | 直接给 AI 判读（比正则准），系统性排查走 [debugging.md](references/debugging.md) | —— |

> **请求模糊时**（拿不准用户在问哪一类）：先跑 `renpy-tools-cli.py all <项目> -l schinese`——18 项全只读，退出码 1 表示**查出问题**而非崩溃；它会自己列明跳过哪些项并提示先补什么。先让它吐依据，比先猜快。

## 注意事项

| 场景 | 说明 |
|------|------|
| **工具回归测试** | 改完 `scripts/` 必跑：`cd scripts/tests && python -m unittest discover`（纯标准库，597 用例）。用例数/目录树/子命令数须与 [scripts/README.md](scripts/README.md) 一致，有测试在守 |
| **写入类工具安全网** | 首次写入自动 `.bak`（fail-closed，备份失败即停止）+ 原子替换；多数默认试运行，`--apply` 才落盘 |
| **无 `tl/` 的中文（第三方机翻）** | 显示中文但 `game/tl/` 不存在 → 走 `config.replace_text`；`langcheck` 会点名它并指向 [replace_text_hook.md](references/replace_text_hook.md)，`tl_check` 仍只认 tl 目录 |
| **跨平台** | `scripts/` 下 9 个分组目录全 ASCII（macOS NFD 归一化会让中文路径 import 失效），darwin 可直接用 |
| SDK 路径 | 自动检测（`sdk_common.py`）：`--sdk` → `$RENPY_SDK` → 向上查找 → `_KNOWN_SDK_PATHS`（本机路径只在此一处维护）。仅 `lint` 需要 SDK；其余免 SDK 可用 |
| **SDK 缺失时给用户判断** | 先说明当前任务是否真需 SDK（结构分析/资源检查/tl_check/字体/多语言/体检都不需要，照常执行）；确需 lint/编译/打包时让用户二选一：①下载 SDK ②跳过该步。**不要静默自动下载，也不要静默跳过** |
| 游戏内测试 | 没有脚本——Ren'Py testcase 语法（`run`/`click`/`advance until screen`/`assert eval`）AI 直接写进 .rpy，用 `renpy.py 项目 test` 执行 |
| **反编译 `.rpyc`** | 首选仓库外的 `renpy-script-decompile` 技能（纯 Python、不下载任何东西）；内置 `scripts/unrpyc.py` **只是兜底**，它会下载并执行第三方代码，别默认走它。工具选型与版本坑见 [references/player_tools.md](references/player_tools.md) |
| 导出 JSON | 已删 `export.py`——官方 `translate` 命令够用 |

## 参考知识（按场景索引）

**写游戏 / 引擎行为**（AI 直接写 .rpy，不背模板；只收模型记不全、易过时的内容）：

- [renpy_gotchas.md](references/renpy_gotchas.md) — 引擎陷阱（字体静默回退、缩进只数空格、define vs default、SL2 坑）
- [snippets.md](references/snippets.md) — 非显性技巧（F2 热键、Scroll 三参、拖放契约、历史屏/侧头像）
- [typography.md](references/typography.md) — 中文字号/行距/outline 数值表与可复制 gui.rpy
- [gallery_and_stats.md](references/gallery_and_stats.md) — 画廊、养成数值、性能预设
- [advanced_tools.md](references/advanced_tools.md) — 字体修改 4 法 + 语言联动
- [game_creation_workflow.md](references/game_creation_workflow.md) — 从零创作主线
- [text2script_workflow.md](references/text2script_workflow.md) — 剧本 → .rpy 规范

**汉化**：

- [translation_workflow.md](references/translation_workflow.md) — 翻译工作流（**术语表定稿前必须征求用户**）
- [hanization_manual.md](references/hanization_manual.md) — 汉化故障手册（现象→原因→修复，10 章）
- [replace_text_hook.md](references/replace_text_hook.md) — `config.replace_text` 载荷识别与**拆除**（唯一完整出处）
- [translation_polish.md](references/translation_polish.md) — 译文润色策略
- [tl_check.md](references/tl_check.md) — tl 质检分级细则（唯一完整出处）
- [namebox_translation.md](references/namebox_translation.md) — 名字栏：三类说话人 + **全串精确匹配**

**玩家侧 / 排错 / 工程**：

- [player_tools.md](references/player_tools.md) — 解包/存档/汉化/重放工具地图
- [unlock_patches.md](references/unlock_patches.md) — 解锁画廊/CG/回放（补丁全文）
- [debugging.md](references/debugging.md) — 排错指南
- [sdk_config.md](references/sdk_config.md) — SDK 配置与 CLI 速查
- [tools_boundaries.md](references/tools_boundaries.md) — 工具通用度分级与写操作风险表

---

## AI 使用快速参考卡（让模型无人工补位独立完成）

### 触发词 → 对应动作

| 用户说 | AI 应先做 | 再做 |
|--------|----------|------|
| "字太小/太大" / "对白看不清" | 确认是哪一处（对白/名字/选项/UI/历史）→ 对应 `gui.*_size` 变量 | 改 `gui.rpy` 变量（不是 style 里的写死数值），见 [typography.md](references/typography.md) |
| "中文显示方块" / "切语言方块" | 先检查字体文件是否存在，再看 `font_replacement_map` 是否三元组 | 跨 `check_fonts.py`；按 [advanced_tools.md](references/advanced_tools.md) 方法 2 补全局替换 |
| "字号不联动" / "放大后描边发毛" | outline 是写死像素，需同步调 | 改 `style say_dialogue` 的 `outlines`，见 [typography.md](references/typography.md) 六 |
| "汉化 / 缺句 / 质检" | 缺句走 `untranslated`（吃 tl 目录）；质检走 `tlcheck` | 先定术语表（`make_glossary.py`，定稿前征求用户） |
| "写游戏 / 画廊 / 数值 / 设置" | AI 直接写 .rpy，不背模板；陷阱见 snippets.md | 画廊/数值见 gallery_and_stats.md |

> 其余意图见上方「你说 → 它做」。本表只收主表未覆盖的**视觉类判据**；「崩溃」「从零做游戏」「解包」等在主表已有，此处不重复。

### 常见失败模式 → 修复（可直接复制）

| 现象 | 根因 | 一句修复 |
|------|------|----------|
| `font_replacement_map` 值是字符串 `"fonts/xx.ttf"` | 引擎做 `fn, bold, italics = ...get(t, t)`，字符串会被逐字符解包 | 改成三元组 `("fonts/xx.ttf", False, False)`，见 renpy_gotchas.md |
| `config.language = "schinese"` 锁死语言切换 | 优先级高于玩家偏好，下次启动仍是中文 | 改 `define config.default_language = "schinese"`，见 renpy_gotchas.md |
| 字号放大后 outline 发毛/缩圈 | outline 像素写死，不随字号缩放 | `outlines [(N, ...)]` 按字号取 1–4，见 typography.md 六 |
| 中文同号比英文小，默认 22 看起来不够大 | CJK 字形更密 | 中文建议 24+，对白取 28–32，见 typography.md 一 |
| 行距太小导致中文笔画粘连 | 中文密度高 | `line_spacing` 取字号 15%–20%，见 typography.md 三 |
| 分辨率变化后字号不缩放 | Ren'Py `size` 是固定像素 | 按 `config.screen_width` 分档定义 `gui.text_size` 等，见 typography.md 二 |

### 可直接复制的中文友好 gui.rpy 片段

```renpy
## 字号（1080p 基准，分辨率变化时同步分档）
define gui.text_size        = 28
define gui.name_text_size   = 22
define gui.choice_button_text_size = 22
define gui.button_text_size = 22
define gui.history_text_size = 22
define gui.text_line_spacing = 5

style say_dialogue:
    size gui.text_size
    line_spacing gui.text_line_spacing
    outlines [(2, "#000000", 0, 0)]   # 字号 28 对应 outline 2，放大字号时同步加大
```

> 约定：SKILL.md 的 description 必须覆盖全部故障关键词（崩溃 / traceback、汉化质检、字体方块、字号不联动、存档等）。每个知识只放一处，新增条目先问：模型会不会闭眼写对？会 → 不收录。
