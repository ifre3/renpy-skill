# sandbox_linear_design — 沙盒与线性模式：架构范式与社区验证经验

> 场景：正在写 / 改一个带自由探索（沙盒）或主线自动推进（线性）的 Ren'Py 游戏。
> 本文件回答「沙盒怎么组织事件、线性怎么串剧情、两者怎么共存」。
> 社区经验台账（来源/渠道/更新机制）见 [community_playbook.md](community_playbook.md)。

## 一、两种模式的社区共识

社区（Lost in You 作者 atrX 原话 + F95/Discord 玩家反馈，2026-10 核实）对双模式设计
已有一致看法：

- **Linear 模式**：按顺序自动播放全部主线事件；砍掉「用于在沙盒里刷属性/解锁」的
  可重复场景。是多数玩家的首选（作者在 Discord 的反馈：线性更受欢迎）。
- **Sandbox 模式**：地图自由探索，事件由 时间 × 地点 × 条件 触发；保留可重复场景、
  奖励场景（如 Lost in You 房间里的 wordle 谜题只在 sandbox 解锁）。
- **双模式共存是成熟做法**：开局菜单二选一 + 设置菜单随时切换（Lost in You）；
  Dissonance 0.14 则直接默认线性、注释掉了进沙盒的入口（内容未做完时的做法）。
- 设计分工一句话：**linear 保证故事不 miss，sandbox 保证自由与奖励**。切换时应保留
  两边的完成 flag 互认，避免「切回 sandbox 后事件状态对不上」。

## 二、沙盒范式（AfterDark 0.26 脚本核实）

沙盒游戏的通用分层（多个发行版实测同一模式）：

```
时间状态机 → 地图层 screen → 地点层 screen → 调度 label → 事件 label
```

1. **时间状态机**：`day`（0=周日…6=周六）× 时段（morning/noon/evening/night 拆文件）+
   累计天数 `totaldays`；推进函数 `pass_time() / next_day()`。时段不只看一个变量时，
   以实际拆分的 screen 文件为准（AfterDark 的 `max_time=2` 与四段屏幕并存）。
2. **地图层**：每个时段一个 `*_screen`，地点用按钮对象注册，例如
   `class_click(name, image, action=Jump("mapweekdaynoon_park"), pos)`；
   未解锁地点直接提示 "unavailable right now" 并返回（**解锁靠故事 flag，不做就永远锁**）。
3. **地点层**：地点屏幕里角色同样注册成可点击按钮，`action=Jump("library1_yuki")`。
4. **调度 label**：角色入口 label 内是纯 `if/elif` 条件链，例如 `yukilibraryevents`：
   ```renpy
   label yukilibraryevents:
       if storydream1 == 1 and storydream2 == 0:   jump library_yuki      # 主线前置
       elif yukilibraryintro == 0:                  jump yuki_library_intro
       elif Yuki.affection >= 10 and yuki5event == 1 and yuki10event == 0:
           jump yuki_10_event                       # 好感 + 事件链
       else:                                        jump library_yuki
   ```
5. **事件层**：纯剧情 label，播完设完成 flag（`yuki5event = True` 等）。

**关键规律**：事件的「可玩性」= 时间 × 地点 × flag × 好感 全满足。调度 label 的
if/elif 链就是**事件依赖图的现成实现**——做事件追踪器/线性化排序都从这里读，不要
自己另造一份条件表。

## 三、线性模式实现模板（Dissonance 0.14 linear.rpy 源码核实）

给沙盒游戏加线性模式的最小完整骨架（社区多个游戏同款）：

```renpy
# 1) 全局模式开关 + 开局/设置菜单（Lost in You 支持设置内随时切换）
default gamemode = "sandbox"
# 开局菜单里 "Linear" → $ gamemode = "linear" → jump start2 … → jump linear

# 2) 线性主入口：清返回栈，按章节完成 flag 依次 call
label linear:
    $ renpy.set_return_stack([])        # 防止事件 return 回错地方
    if pro_complete == False:  call linear_pro
    if ch1_complete == False:  call linear_ch1
    ...
    jump linear_end

# 3) 章节链：按事件完成 flag 顺序 call，手动设星期 + 时间跳跃文字
label linear_pro:
    if day_one == False:
        call day_one
        call day_one2
        "{i}A week passes...{/i}"
    if day_16 == False:
        $ week = 1
        call day_16
        "{i}Days pass...{/i}"
    ...
    return

# 4) 结束菜单
label linear_end:
    "You've reached the end of current content!"
    jump linear_menu
```

要点：
- **事件完成必须设 flag**，重进 linear 自动跳过已完成的（flag 名 == 事件 label 名的
  规律见下节，可自动化）。
- 时间由链手动推进（`$ week = N` / 赋值 `day/time`），玩家不再有「时间流逝」按钮。
- 好感/欲望型事件在无日常时不会自然达标，需要**补偿**：开局调满全角色，或链内补丁
  （Dissonance 实测写法：`if yoshie_lust >= 1: $ yoshiegrind = True`）。
- 补丁式落地：独立 `zzz_linear_mode.rpy`、不改原脚本、删除即还原（renpy-skill 已有
  `linear add` 工具自动生成，见 scripts/README「linear/ — 剧情线性模式」一节）。

## 三·五、半自动线性范式（选项保留、沙盒跳过）——2026-10-31 用户决策沉淀

AfterDark 0.26 线性模式改造（renpy-skill `linear add` 生成补丁）确立的第三条路线，
与 LostInYou 全自动（忽略事件要求）和 Dissonance call 链不同，社区同样有玩家偏好：

**设计原则一句话：选项与分支保留，沙盒机制跳过。**
- **保留**：剧情内的 `menu` 选择、分支路线、QTE 判定——玩家自己选，线性模式不剥夺选择权
- **跳过**：日常/地图/时间推进等沙盒机制（导航标签：class_scene、weekday_*、map*、睡眠过渡等）

**实现形态**（label callback 拦截，见 `linear add` 生成器）：
- 剧情标签（LM_STORY）播完 → 游戏跳向导航标签 → 回调拦截 → 自动跳到下一个剧情标签
- `menu` 语句在剧情标签**内部**，callback 不会干预（label 已进入表内）→ 菜单自然停住等玩家，
  选完继续自动播放——这是"选项保留"的实现基础，**不要用 mode_callbacks 自动选菜单破坏它**
- 表外标签分类是质量关键：剧情性标签（actualintro/story1congun 这类）必须纳入白名单，
  否则会被误当导航跳过导致断片；导航标签不能入表（否则自动播放会卡住不跳）

**状态补偿**：沙盒机制跳过 → `totaldays`/好感度冻结 → 门控事件前自动补齐（LM_GATES 表）。
**进度标记**：可选 `lm_done` 集合记录已播场景，目录标灰，重进线性可续播（对标 Dissonance
完成 flag 的 `if day_one == False` 模式）。

**与另两条路线的对比**：

| 路线 | 代表 | 选项/分支 | 沙盒机制 | 状态处理 |
|------|------|-----------|----------|----------|
| 全自动 | LostInYou | 事件内部分支保留，但调度忽略全部要求 | 跳过 | 固定星期（官方承认日期难维护） |
| call 链 | Dissonance / FriendshipClub | 线性链里手动 call 场景，选项跟随场景 | 跳过 | 每场景显式 `$ week = N` + 过渡文字 |
| **半自动** | **AfterDark 补丁（本范式）** | **剧情内 menu 保留，玩家自选** | **跳过导航标签** | **LM_GATES 自动补偿** |

**适用判断**：游戏剧情内选项影响分支/好感时用半自动（保留可玩性）；剧情纯粹线性只想
"看故事"时用全自动；作者自己维护用 call 链。第三方 mod 场景只能选半自动/全自动（不改原脚本）。

## 四、线性化社区预警（Lessons in Love Linear Mode Mod 玩家实测）



F95zone 上 crustlord12 的 LiL 线性 mod（v0.3.1，2023-01）评论区是线性化的避坑实录。
以下 bug 全部是真实玩家报告，做线性化前先对照：

| 预警 | 后果 | 对策 |
|------|------|------|
| 事件乱序触发（"Reached Ayane's Prisoner before Backwards Spider Crawl"） | 剧情矛盾、支线永久缺失 | 排线前先梳理调度 label 的依赖链；主线依赖的支线前置必须先排 |
| 未维护 day/星期计数（"ERROR IN ADVANCING TO weekdays"） | 依赖星期的事件无限循环 → softlock | 链内每个节点明确赋值 day/week/time，事件播完递增 |
| 完成 flag 漏设 | 同一事件重复播放 | 每个被 call 的 label 播完必须设对应 flag |
| 好感/欲望门控事件无补偿 | "拒绝 Ami 却仍播放 Wake Up Call" | 门控类型（二进制 flag vs 数值）分开处理，数值型统一补偿 |
| 切回 sandbox 状态对不上 | 存档进度错乱 | 双模式共享同一套完成 flag；切换入口记录当前进度 |

**命名规律（LiL mod 作者的发现）**：这个系列的游戏「99% 的情况下，场景 label 名与
标记它已播的变量名完全相同」——因此线性化与事件追踪可以按 `label 名 → 同名变量`
自动化枚举，不必手工维护映射表。

## 五、事件追踪器 / 提示系统（LiL 官方 + 汉化组 + Holiday Island）

「沙盒没提示 = 乱逛」是玩家公认痛点（Holiday Island 官方 FAQ 直接写「没有攻略」，
靠游戏内手机提示 + 玩家 mod 的 hint 解决；LiL 需要线性 mod 就是因为沙盒主线太难挖）。
三种已验证实现：

1. **官方 Event Tracker**（LiL 原版）：读原生 flag，只显示事件的 已解锁/已完成 状态，
   不给攻略文字。技术上就是「遍历事件表 + 按 flag 变色」。
2. **汉化组 Hint 面板**（Brainos 版 LiL）：自定义 screen + 手写事件条件表，逐条显示
   触发条件文字（"等待直到 Saturday 下午"），可按角色分类、条件满足变绿。纯加屏幕，
   不改事件逻辑、不碰存档，安全可逆。
3. **available missions 清单**（Lemma Soft 经典帖 t=46258）：维护一个可做事件列表，
   每完成一件往里加新条目——即追踪器的雏形；社区标准做法是 python 函数/类封装事件
   判定，避免散落 if/elif 难维护。

最小实现（与 LiL 提示面板同构）：

```renpy
init python:
    hint_events = [
        # (id, 角色, 标题, 条件表达式字符串, 提示文字)
        (37, "Maya", "爱猫溺亡金鱼缸挽歌",
         "day_of_week == 6 and time == 'afternoon'",
         "等待直到 Saturday(下午)."),
    ]
    def hint_ready(cond_str):
        return eval(cond_str)          # 条件表来自人工整理，eval 前自行校验白名单

screen hint_screen():
    tag menu
    use game_menu(_("提示"), scroll="viewport"):
        vbox:
            for ev in hint_events:
                text ("[ev[2]]" if hint_ready(ev[3]) else "{color=#888}[ev[2]]{/color}")
```

## 六、给 AI 的落地顺序

1. 先跑 `renpy-tools-cli.py linear analyze <游戏>`：判断是否内置线性机制、统计场景候选。
2. 纯沙盒 → `linear add <游戏>` 生成补丁（骨架自动做）；事件依赖梳理仍要手动：
   读每个调度 label 的 if/elif 链，排出主线顺序。
3. **先排主线最小链跑通**（mainquest + 1~2 个角色完整链），再逐角色扩展；不要一次性
   全量排线（LiL mod 作者同样选择分步修 bug）。
4. 时间变量适配：AfterDark 用 `day/time/totaldays`，Dissonance 用 `day/week/seg`，
   链内统一赋值，别混。
