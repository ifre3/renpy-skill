---
name: renpy-user
description: "This skill provides content creation workflows for Ren'Py games, including script generation, project scaffolding, and pre-built patterns (affection systems, galleries, CJK font config, etc.). It should be used when the user needs to write dialogue, create scenes, build a new project, or add game systems."
compatibility: "renpy>=8.0"
agent_created: true
---

# Ren'Py User — 写游戏

## 脚本速览

| 文件 | 用途 | 一句话用法 |
|------|------|-----------|
| `scripts/scaffold.py` | 新建项目骨架 | `Scaffold("path").set_name("我的故事").build()` |
| `scripts/bridge.py` | Python 链式生成 .rpy 剧情 | `RenPyScript().say("e","你好")...write("s.rpy")` |
| `scripts/patterns.py` | 预制功能模块（好感度/画廊/字体等） | `apply("gallery", {...}).write("g.rpy")` |

## Trigger 关键词

| 你说 | 它做 |
|------|------|
| "新建一个 Ren'Py 项目" | scaffold 建项目骨架 |
| "写一段开场剧情"、"让艾琳说句话" | bridge 生成对话/场景 |
| "加个好感度系统"、"做个图片画廊" | patterns 一键生成 |
| "显示教室背景"、"立绘出现" | bridge 的 scene/show |
| "配置中文显示"、"加字体" | patterns 的 cjk_font |
| "加个开场 logo 动画" | patterns 的 splash |
| "做个存档/读档界面" | patterns 的 save_load |
| "加个设置界面" | patterns 的 preferences |

## 快速入门

```python
# 1. 新建项目
from scaffold import Scaffold
Scaffold("D:/my_game").set_name("我的故事").set_resolution(1280, 720).build()

# 2. 写剧情
from bridge import RenPyScript
s = RenPyScript()
s.character("e", "艾琳", color="#c8ffc8")
s.label("start")
s.scene("bg cafe", with_="fade")
s.say("e", "要喝什么？")
s.menu([("咖啡", "coffee"), ("茶", "tea")])
s.write("game/script.rpy")

# 3. 加好感度系统
from patterns import apply
apply("affection", {"characters": [
    {"var":"e", "name":"艾琳"},
    {"var":"l", "name":"陆辰"}
]}).write("game/affection.rpy")
```

## 注意事项

- bridge.py 不生成图片资源 — 图片需手动放入 `game/images/`
- patterns 生成后可能需要微调（如图片路径、字号）
- 需要打包/Lint/测试？→ 加载 **renpy-dev** Skill

## 进阶参考

- [Patterns 参数详情](references/patterns_api.md) — 所有预制模式完整参数
- [常见陷阱 & 最佳实践](references/renpy_gotchas.md) — 图片/字体/缩进/变量作用域

## 版本边界

目标 SDK: Ren'Py ≥ 8.0。SDK 不可达时不阻塞，仅生成代码供其他环境使用。
 
 ## 2026-06-21 改进记录
 
 基于 Ren'Py 8.5.3 官方 SDK 源码和文档的改进：
 
 ### bridge.py
 - 新增语句类型（基于 renpy/ast.py AST 节点）:
   call/call_expression, jump/jump_expression, return_, pass_,
   if_/elif_/else_, while_, init, define, default,
   play/stop/queue (音频), pause, window_show/hide,
   show_layer, camera, image, transform, screen, style
 - 官方依据: renpy/ast.py (Say, Label, Jump, Call, Return, Menu, 
   Python, If, While, Show, Scene, Hide, With, ShowLayer, Camera,
   Pass, Define, Default, Image, Transform, Screen, Style, Init)
 - Audio 语句依据: renpy/common/00action_audio.rpy
 
 ### patterns.py
 - 新增 `after_load_migration`: 存档兼容性迁移
   官方依据: config.after_load_callbacks (renpy/common/00start.rpy)
 - 新增 `layeredimage`: LayeredImage 立绘系统
   官方依据: doc/layeredimage.html, 00layeredimage.rpy
 
 | 你说 | 它做 |
 |------|------|
 | "存档不兼容/升级了存档坏了" | patterns 的 after_load_migration |
 | "加个立绘切换系统/多图层角色" | patterns 的 layeredimage |
 | "用 call 跳转子程序" | bridge 的 call() |
 | "用 if/else 做分支" | bridge 的 if_() / else_() |
 | "播放背景音乐" | bridge 的 play("music", ...) |
