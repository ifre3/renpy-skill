# Ren'Py 玩家侧工具地图

> 原则：**不重写这些工具的功能**。它们是成熟的开源工程（反编译器几千行、存档签名有硬门槛），
> AI 的职责是判断场景 → 调度正确工具 → 处理工具输出。
> 本地工具缺失时先 `pip install`（装到隔离环境），不要现写解析脚本。

## 本地工具优先（renpy-tools 工具包，已内置本 skill：`scripts/`）

汉化质检和崩溃排查**先用本地这套**，再考虑 pip 工具。纯标准库实现，随 skill 携带，无需 SDK（仅 `lint` 子命令需要）。统一入口：

```bash
TOOLS=<skill目录>/renpy/scripts
python "$TOOLS/renpy-tools-cli.py" list            # 列出所有子工具

# 崩溃风险检测（已默认跳过引擎目录；上报前会做作用域核实，误报少）
python "$TOOLS/renpy-tools-cli.py" crash <项目路径>

# 翻译质检：角色/变量/标签/转义完整性
python "$TOOLS/renpy-tools-cli.py" integrity <项目路径> -l schinese
# 空译文/原文=译文 检测（纯标签+标点条目自动归为无需翻译）
python "$TOOLS/renpy-tools-cli.py" untranslated <项目路径>/game/tl/schinese

# 角色名字框完整性：Character("Name") 是否有 old "Name" 字符串翻译
# （名字框走 substitute(translate=True)，缺条目就显示英文；可 --stub 生成待填骨架）
python "$TOOLS/renpy-tools-cli.py" charname <项目路径> -l schinese

# AI 翻译回填（autotranslate.py，安全流程见 scripts/README.md）
```

适用场景对照：汉化后闪退 → `crash`；汉化缺句/质检 → `integrity` + `untranslated`；
字体方块 → renpy_gotchas.md 的 font_replacement_map 方案；rpyc 反编译/提台词 → 优先用已装的
**renpy-script-decompile** 技能（纯 Python，不装任何东西），批量处理或需要 RPA/存档时再用下面的 rpycdec。

## 工具总览

| 工具 | 能力 | 安装 |
|------|------|------|
| **rpycdec**（首选，一个顶五个） | rpyc 反编译、RPA 解包/打包、APK 提取游戏、存档↔JSON（含重签名）、翻译提取 | `pip install rpycdec`（Python ≥3.10，支持 7.x/8.x；⚠️ 8.4+ 编译的 .rpyc 有解析失败报告 cnfatal/rpycdec#15，失败回退 unrpyc 或 renpy-script-decompile 技能） |
| **unrpa** | 仅 RPA 解包（老牌、简单场景够用；⚠️ 新游戏 RPA-3.0 档案可能解析失败，见 Lattyware/unrpa#50） | `pip install unrpa` |
| **unrpyc** | 仅 rpyc 反编译（经典，兼容到 Ren'Py 6） | GitHub: CensoredUsername/unrpyc |
| **rpa-toolkit** | .rpa/.rpi 解包 + .rpyc/.rpymc 反编译（rpatool 停更后的现代替代） | GitHub: regiellis/rpa-toolkit |
| **Universal Ren'Py Mod (URM)** | 通用游戏内 Mod：变量查找/修改/冻结/监控、场景查找与重放、**查看并选择隐藏/锁定选项**、路径 / if 语句检测、存档管理（重命名/移动/删除）、**任意角色显示名重命名**、文本框自定义、quickmenu 自定义 | 0x52.dev（官方）https://0x52.dev/mods/Universal-Ren-Py-Mod-1000，v2.6.2 / 1.1 MB，**要求引擎 ≥6.99.14**；下载 Mod 文件放进游戏 `game/` 目录，不动原游戏文件（官方设计约定：删除即完全还原） |
| **SaveEditOnline / Griviewer** | 网页版存档编辑（无 Python 环境的玩家用） | 网页直接用 |
| **Game Mod Kit** | 在线全家桶：RPA 解包 + rpyc 反编译 + 存档编辑 + APK | gamemodkit.com |
| **Lunatranslator** | 游玩生肉时的 HOOK 提取文本 + 翻译 | GitHub: HIllya51/LunaTranslator（官网 lunatranslator.org），活跃维护 |

## 场景 → 命令速查（rpycdec）

```bash
pip install rpycdec

# 反编译整个游戏（rpyc → rpy）
rpycdec decompile /path/to/game/ -o out/

# 解包 RPA
rpycdec unrpa archive.rpa -o out/
rpycdec unrpa archive.rpa -s .rpy          # 只抽脚本

# 从 APK 提取游戏
rpycdec extract-game game.apk -o out/

# 存档编辑（核心链路，含重签名）
rpycdec save info slot1-1-save.save        # 看存档结构
rpycdec save extract slot1-1-save.save     # → JSON
# ... 编辑 JSON 里的变量（通常在 store 命名空间下）...
rpycdec save restore slot1-1-save.save     # JSON → .save 并重签名

# 提取翻译到 tl/ 目录
rpycdec extract-translate /path/to/game/ -l chinese
```

⚠️ rpyc/rpa/save 内部是 Python pickle，只处理可信来源的文件。

## 存档位置（按平台）

存档目录名 = 游戏内 `config.save_directory` 的值（不是游戏名）：

| 平台 | 路径 |
|------|------|
| Windows | `%APPDATA%\RenPy\<save_directory>\`（老游戏可能在 `游戏目录\game\saves\`） |
| macOS | `~/Library/RenPy/<save_directory>/` |
| Linux | `~/.renpy/<save_directory>/` |
| Android | `Android/data/<游戏包名>/files/saves/`（新版安卓需系统文件管理器或 ADB 访问） |
| iOS | 应用沙盒内，需越狱或应用内导出 |

目录内容：`<页码>-<槽位>-save.save`（存档）、`persistent`（全局解锁数据）、`quick-*.save`（快速存档）。

## 常见玩法链路

先判断需求属于哪一类，再选工具：**不碰文件**（投放式，删完即还原）→ **碰文件/存档**（改后不好回退）。

| 需求 | 首选 | 备注 |
|------|------|------|
| 解锁全 CG / 全结局 | **投放式补丁** → [unlock_patches.md](unlock_patches.md) | 不写 persistent，删文件即还原。**URM 替代不了**（判据不同，见下节） |
| 回看已过剧情 / 场景重放、选隐藏或锁定选项 | **URM** | 其场景重放基于看过的 **label**，不是看过的**图片** |
| 改变量 / 冻结数值 / 看隐藏 if 路径 | **URM** | 实时生效，不写文件 |
| 改角色**显示名**（不改资料库） | **URM** | 运行时生效 |
| 改角色**资料库译名**（全局永久，含 tl 文件） | `scripts/names/unify_name_translations.py` | 改文件，带三步审核 + 整目录回滚快照 |
| 修存档里的进度 | **URM** 存档管理，或编辑 `persistent`（同目录、无扩展名，rpycdec save extract 同样适用） | 文件级改动需重签名 |
| 汉化生肉 | 解包 → `rpycdec decompile` 拿到脚本 → 翻译 `.rpy` 的 `tl/` 目录 → 打包回 game/（或直接以 .rpy 散文件覆盖，Ren'Py 优先加载 .rpy） | 本 skill 的主场景，见 translation_workflow.md |
| 只有 APK 的游戏 | `rpycdec extract-game` | 比解压 APK 再找 assets 手动抽省事得多 |

### 为什么「全 CG 解锁」不用 URM

两者都是投放式、都不碰原文件，但判据走的是**不同的 persistent 字典**（官方 `persistentexports.py`）：

| persistent 键 | 记录什么 | 谁在读 |
|------|------|------|
| `_seen_images` | 看过的**图片** | `renpy.seen_image()` → 画廊解锁判定本体 |
| `_seen_ever` | 看过的 **label** | 场景重放（URM） |

URM 的「场景查找与重放」建立在 `_seen_ever` 上，**解不了画廊**。用 URM 往回放看过的剧情段，画廊里的 CG 仍然锁着。要开画廊必须走 unlock_patches.md 的旁路（`renpy.seen_image` 恒真 / 清空 Gallery conditions）。

反过来：若用户要的是「重看已看过的剧情」而不是「开没看过的」，那 URM 更方便——不要拿 unlock_patches 那套重东西。

## 开发者侧对应操作

玩家侧的"改游戏"若由开发者自己做，等价操作见本 skill SKILL.md 脚本速览：lint（改完校验）、compile（重新编译）、translate（官方翻译文件流程，比 extract-translate 更规范）。
