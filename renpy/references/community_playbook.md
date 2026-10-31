# community_playbook — 社区经验学习台账（保持不脱节）

> 用途：把 Ren'Py 社区已验证的经验沉淀成可复查的记录，并定义「何时去社区学什么、
> 怎么验证、怎么入账」。skill 每次吸收社区知识后在此追加，并同步 CHANGELOG。
> 与 [sandbox_linear_design.md](sandbox_linear_design.md) 的关系：本文件管**来源与更新机制**，
> 那篇管**已沉淀的设计知识本体**。

## 一、渠道清单（学什么 → 去哪学）

| 渠道 | 学什么 | 频率 |
|------|--------|------|
| Lemma Soft Forums（lemmasoft.renai.us） | 引擎机制答疑、沙盒/事件/时间系统经典帖（t=46258 沙盒事件判定、t=563074 迷你沙盒主循环） | 引擎大版本发布后 / 遇到机制疑问 |
| F95zone（pizzagonemad 等镜像） | mod 实测 bug 清单（LiL Linear Mode Mod 评论区 = 线性化避坑实录）、双模式玩家反馈、汉化/解锁工具生态 | 做线性化/追踪器/解锁前 |
| itch.io devlog + 评论区 | 官方设计决策（Lost in You 双模式原则、Destined Dreams 沙盒重构全过程） | 设计功能时 |
| itch.io 模板/资产市场 | 现成系统封装（Shark303 Sandbox Starter Kit：时间/NPC 调度/关系/手机 UI） | 评估「别人怎么封装」时 |
| Ren'Py 官方文档 / CHANGELOG / GitHub | 引擎能力边界与 8.x 新特性（如 SL2、新的持久化行为） | 每次 8.x 更新发布后 |
| VNDB / vndb 引擎标签 | 用 Ren'Py 的发行版分布（验证某做法是否普遍） | 低频 |

## 二、已验证经验账（按入库时间倒序）

> 每条约格式：经验 — 来源 — 验证方式 — 入库日期。
> 「验证方式」分三级：源码核实（读了实际脚本/源码）/ 作者原话（开发者直接声明）/
> 玩家实测（多人复现的 bug 或反馈）。引用必须可追溯，写进文档时保留来源 URL。

### 2026-10-26 批次（首批入库）

1. **双模式设计原则**（linear 全剧情、sandbox 自由+可重复/奖励；设置可随时切换；
   linear 更受欢迎）— Lost in You 作者 atrX 在 itch 评论区原话 — 作者原话 —
   https://atrx.itch.io/lost-in-you/comments?before=136
2. **线性链实现模板**（`label linear` + `renpy.set_return_stack([])` + 按完成 flag
   依次 call + 手动 `$ week = N` + "{i}Days pass...{/i}"）— Dissonance 0.14
   `game/linear.rpy` — 源码核实 — 本机已解包发行版
3. **线性化 bug 预警清单**（乱序触发、day 计数缺失 softlock、flag 漏设重复播放、
   好感门控需补偿、双模式切换状态错乱）— LiL Linear Mode Mod v0.3.1 评论区玩家实测 —
   玩家实测 — https://pizzagonemad.com/threads/lessons-in-love-linear-mode-mod-v0-3-1-crustlord12.215252/
4. **flag 命名规律**（「99% 场景 label 名 == 完成变量名」，可自动化枚举事件）— LiL
   mod 作者 crustlord12 评论区说明 — 作者原话 — 同上 URL
5. **沙盒主循环模式**（`call screen` → 按钮 SetVariable location + Return →
   `call expression "label_"+location` → jump 回循环）— Lemma Soft t=563074
   迷你沙盒示例 — 帖内代码 — https://lemmasoft.renai.us/forums/viewtopic.php?p=563074
6. **事件可玩性判断**（维护 available missions 列表；python 函数/类封装判定，避免
   散落 if/elif）— Lemma Soft t=46258 经典帖 — 帖内讨论 —
   https://lemmasoft.renai.us/forums/viewtopic.php?t=46258
7. **时间状态机封装**（`next_time() / new_day() / do_pass_time()` + 地图 token +
   NPC 调度 + 手机 UI 的完整沙盒模板）— Shark303 Sandbox & Life-Sim Starter Kit —
   模板文档 — https://shark303-studio.itch.io/renpy-sandbox-life-sim-starter-kit
8. **沙盒提示/追踪是玩家公认需求**（Holiday Island FAQ：无攻略、靠手机 hint + mod；
   LiL 需要线性 mod 因沙盒主线难挖）— Holiday Island 官方 FAQ PDF + LiL mod 简介 —
   作者原话/官方文档 — https://attachments.f95zone.com/2019/02/259496_Holiday_Island_Guide_FAQ_0.1.4.2.pdf
9. **翻译工具会破坏 renpy 脚本变量（社区已知 bug）**：AiNiee 7.1.1 专门修复
   「renpy 翻译后变量消失」；同步改进 renpy 人名剔除方法 — AiNiee 更新日志（3DM 转载）—
   作者原话 — https://github.com/NEKOparapa/AiNiee
10. **MTool 分句切割损害翻译质量（第三方文档实锤）**：LinguaGacha 项目文档记录
    MTool 把文本按分句/碎片导出影响译文连贯性，AiNiee 为此提供 MTool Optimizer
    长句重组；对照：skill 的润色管线本就「不截断长句、连续剧本块」 — RuneTranslate
    对比页 — 第三方文档 — https://runetranslate.com/es/compare/mtool
11. **unrpyc 双分支维护与混淆边界**：master(v2, Py3, Ren'Py 8) / legacy(v1, Py2,
    Ren'Py 6-7)；作者明确不参与混淆军备竞赛（deobfuscation 仅基础框架，专游戏
    混淆不接 feature）— unrpyc README — 源码核实 —
    https://github.com/CensoredUsername/unrpyc
12. **社区工具生态持续活跃（2026 年下半年实测）**：AiNiee 6.4k★ 2026-10-26 更新、
    MTool 2026-10-22 发版（Ren'Py 支持插件 336MB）、RenpyThief v6.7.11 2026-10-04、
    rpycdec 0.2.0 2026-09-20、unrpyc-pure(npm, JS) 1.1.0 2026-03 —
    各发布页核实 — 发行页核实 — 见下节「工具生态地图」

## 三、更新机制（怎么保持不脱节）

- **触发时机**：① 用户问「社区怎么做 X」且当前无沉淀；② 引擎 8.x 新版本发布；
  ③ 要实现的机制存在已知社区先例（线性化/追踪器/沙盒重构/双模式）；④ 本机拿到新的
  解包发行版（Dissonance/AfterDark 这类）且脚本可读。
- **学习流程**：按渠道清单检索 → 优先找能读源码的（发行版脚本 > 帖内代码 > 二手描述）
  → 提取可验证事实 → 标注「源码核实/作者原话/玩家实测」→ 写入本台账 +
  需要的 references → 挂 SKILL.md 索引 → 更新 CHANGELOG → 跑 `scripts/tests` 回归。
- **验证纪律**：能读源码的不引二手；引用附来源 URL；入库日期必填；玩家实测类结论
  写「多人复现」而非「普遍现象」。
- **定期复查**：每次 Ren'Py 8.x 发布后，抽查本台账与 renpy_gotchas.md 是否仍成立
  （引擎行为可能变）；社区经验若被新版本推翻，在台账原条目上标注「已过期 + 日期」，
  不静默删除。

## 四、社区工具生态地图（2026-10-26 调查）

> 用途：知道社区有什么、何时用它们而不是 skill、以及 skill 的对应关系。
> 「选谁」的判据：**AI 无人值守全链路 → skill；人类玩家点 GUI/跨引擎/实时翻译 →
> 社区工具；反编译/逆向 → 社区标准工具（skill 只作兜底）**。

> **分层（2026-10-26 用户澄清）**：社区资产分两类，别混为一谈——
> ① **大工具**（AiNiee/MTool/unrpyc 这类面向人的成品软件，见下表）；
> ② **个人脚本 + 社区经验**（Lemma Soft 帖内脚本、Starter Kit 模板、玩家 mod、
>   开发者 devlog 经验、命名规律/bug 清单这类知识）——后者是 skill 的**上游信号源**：
>   个人脚本无需测试因为一次性使用，skill 的价值是把它们**验证 → 沉淀 → 变成可重复
>   工具**；对 skill 而言②的优先级高于①（①多是人用 GUI，AI 驱动不了）。

| 工具 | 形态 | 定位 | 维护状态 | 与 skill 的关系 |
|------|------|------|----------|----------------|
| unrpyc（CensoredUsername） | CLI（Py3/Py2 双分支） | .rpyc 反编译标准 | 活跃（2026-07 文档更新） | skill 首选仓库外 `renpy-script-decompile` 技能；内置 `unrpyc.py` 仅兜底（会下载执行第三方代码） |
| rpycdec（cnfatal） | PyPI 包 | .rpyc/.rpymc 反编译 | 活跃（0.2.0 2026-09） | 备选反编译；纯 Python 依赖 |
| unrpyc-pure（asakura-minami） | npm / 浏览器 | 反编译 + 生成翻译模板 + 解 rpa | 2026-03（1.1.0） | 跨语言参考；`--gen-translate text chinese` 思路与 skill translate 同构 |
| AiNiee（NEKOparapa） | GUI，6.4k★ | AI 翻译全流程（术语表/思维链/润色/增量） | 2026-10-26 仍在更新（7.x） | 术语表三栏格式（原文\|译文\|备注）已对齐；**其「renpy 变量消失」修复是 skill tl_check 可借鉴的检查维度** |
| AiNiee-Next（ShadowLoveElysia） | TUI/CLI，文件夹监听全自动 | 系列作品增量术语 + 防剧透术语注入 | 2026-05 | 与 skill「AI 无人工补位」同思路的社区实现 |
| MTool | GUI（付费订阅），跨 18 引擎 | 实时翻译/注入 + 变量编辑器 | 2026-10-22 发版（Ren'Py 插件先行版 336MB） | 玩家向；分句切割损害质量（LinguaGacha 文档），skill 润色管线不截断长句即针对同类问题 |
| RenpyThief / LunaTranslator / GalTransl / Sakura | GUI | OCR/注入式实时翻译、补丁制作、VN 专用 LLM | 均活跃（2026-09/10） | 外挂汉化生态，与内嵌补丁流程互补 |
| Ren'Py 官方（SDK） | CLI + Launcher | lint / translate / 打包 / Automated Testing（8.5 新特性） | 8.5.2（2026-03） | skill 的 lint/打包/翻译导出走官方能力；版本差异见 SKILL.md 判据表 |
