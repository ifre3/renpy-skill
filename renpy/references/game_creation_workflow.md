# 从零创作游戏工作流（用户出剧本/美术，AI 出工程）

> 定位：**skill 是游戏工程承包商，不是画室**。剧本、美术由用户提供（或外部 AI 画图工具产出），skill 负责其余一切：骨架、脚本、演出、占位、验证、打包。已有剧本的直接跳到第 3 步衔接 [text2script_workflow.md](text2script_workflow.md)。

## 1. 立项确认门（一轮问清，不连环追问）

摸清用户手里的材料后，一口气确认三件事：

| 问题 | 选项 | 默认 |
|------|------|------|
| 篇幅 | 短篇 demo（一个 label 可跑通）/ 章节化长篇 | 按剧本量定 |
| 类型 | 纯视觉小说 / 带养成数值 / 带画廊回放 | 纯视觉小说 |
| 美术来源 | 用户自备 / 外部 AI 画图（用户自己跑，提示词见资产文档）/ 先占位试玩 | **占位先行** |

- 美术来源选"外部 AI 画图"时，skill **不执行画图**——第 3 步产出的资产文档里 `AI提示词` 字段就是给那个工具的输入
- BGM/SFX 同理：用户自备或免版权库，skill 只管 `play music` 挂进去

## 2. 项目骨架

- **有 SDK（优先）**：用启动器新建项目取模板壳（完整 gui/screens/options），再叠加本 skill 的 `setup_fonts.py`（中文字体）按需配置
- **无 SDK**：手写最小可跑集——`game/script.rpy`（含 start label）+ 基础 say 屏幕；后续装上 SDK 再补全 GUI，不做阻塞
- 全程用 `python scripts/sdk/cli.py <项目> lint` 把关；版本坑查 [renpy_gotchas.md](renpy_gotchas.md)（define vs default 存档语义、缩进只数空格）

## 3. 剧本解析与章节落盘

按 [text2script_workflow.md](text2script_workflow.md) 执行（输出结构 / 命名 / 演出注释前缀 / 资产文档格式），此处只补主线相关的三点：

- **长篇按章交付**：每章落盘即验证一轮（见第 6 步），不要攒到最后
- **资产文档照常产出**：`game/assets/<剧幕名>_assets.md` 里的 AI 提示词 / 搜索关键词是给用户的美术生产输入
- **角色集中声明**：`Character.rpy` 唯一，新章先查已有角色再追加

## 4. 占位资产流水线（占位先行默认路线）

美术未到位时，用纯代码占位让游戏**先完整可玩**，美术后补零成本替换。

占位定义集中写在 `game/scripts/images_placeholder.rpy`（只此一处）：

```rpy
# 背景：全屏色块 + 名称标注
image bg room_dim = Fixed(
    Solid("#22304a"),
    Text("〔占位〕bg room_dim", size=48, color="#ffffff"),
    xysize=(1920, 1080),
)

# 立绘：竖长色块 + 名字/表情标注；表情差分 = 换色 + 换标注文字
image john neutral = Fixed(
    Solid("#2f4f2f", xysize=(420, 900)),
    Text("john / neutral", size=32, color="#ffffff", xalign=0.5, yalign=0.45),
    xysize=(420, 900),
)
image john angry = Fixed(
    Solid("#5f2f2f", xysize=(420, 900)),
    Text("john / angry", size=32, color="#ffffff", xalign=0.5, yalign=0.45),
    xysize=(420, 900),
)
```

- **差分占位即设计**：表情/服装差分在占位阶段就按 tag+attributes 建好（`john neutral` / `john angry`），`show john angry` 的切换逻辑先写对，真图来了行为不变
- CG / BGM / SFX 占位：CG 同背景；音频占位可先注释掉 `play` 语句（音频没有纯代码占位），在脚本行留 `# [音乐] TODO: mystery_theme` 标记，配合 `check_assets.py` 追踪
- 落盘后用 lint + 试跑验证占位显示正常，再继续写剧情

## 5. 美术资产接入规范（真图怎么进游戏）

| 资产 | 放置路径 | 自动 image 名 | 脚本用法 |
|------|----------|--------------|----------|
| 背景 / CG | `game/images/bg/room_dim.png` | `bg room_dim` | `scene bg room_dim with fade` |
| 立绘差分 | `game/images/john/neutral.png` | `john neutral` | `show john neutral at left` |
| BGM / SFX | `game/audio/mystery_theme.ogg` | —（文件名即引用） | `play music mystery_theme` |

- **目录名进 image 名**（Ren'Py 自动命名），脚本的 `scene`/`show` 语句与占位阶段完全一致
- **替换流程 = 删占位 + 图入目录两步**：从 `images_placeholder.rpy` 删掉同名占位定义，把真图放进上表路径，脚本零改动
- 尺寸规格告知用户：背景/CG 1920×1080，立绘透明 PNG（高约 1080~1500），BGM/SFX 用 ogg/mp3
- 入场/切换演出（`with dissolve`、`moveinleft` 等）按 text2script 的演出注释规范已写在脚本里，真图到位自动生效
- 资产缺失/孤设复核：`python scripts/sdk/check_assets.py --path <项目>`

## 6. 逐章验证（每章落盘后跑）

```bash
python scripts/sdk/cli.py <项目> lint              # 语法
python scripts/sdk/analyze.py <项目>               # label/悬空引用
python scripts/sdk/check_assets.py --path <项目>   # 引用了不存在的资产
```

- 关键分支用 testcase 走通（`run`/`click`/`assert eval` 写在 .rpy，`renpy.py <项目> test` 执行；跑 test 加 `SDL_VIDEODRIVER=windows`，见 SKILL.md 旧引擎条目）
- 章节间跳转（`call`/`jump`）对照 analyze 输出核对，悬空引用当章清零

## 7. 打包与交付

- `python scripts/sdk/cli.py <项目> distribute` 出 Windows zip；需要 mac/linux/web/android 时按 sdk_config.md 对应命令
- 交付前 checklist：lint 零错误 / analyze 零悬空 / check_assets 零缺失 / 中文字体已注入 / 默认语言正确
- 想出多语言版 → `scripts/sdk/setup_i18n.py` 生成 tl 骨架，翻译按 [translation_workflow.md](translation_workflow.md)（含开工确认门与术语表用户门）
