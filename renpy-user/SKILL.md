---
name: renpy-user
version: "0.2.2"
description: "Content creation workflows for Ren'Py 8.5.3 games, including script generation, project scaffolding, and pre-built patterns (affection, gallery, CJK font, splash, layeredimage, save/load, etc.). Use when the user needs to write dialogue, create scenes, build a new project, or add game systems."
compatibility: "renpy>=8.0"
agent_created: true
---

# Ren'Py User — 内容创作工具

> 本 skill 生成的的是 **Ren'Py 脚本文本**，而非调用 Ren'Py 运行时 API。
> bridge.py 是 **文本生成器**，不是 Ren'Py AST 的完整实现。

## 路由表 — 你说什么就用什么

| 用户说 | 路由到 | 脚本 |
|--------|--------|------|
| "新建一个 Ren'Py 项目" | `Scaffold(path).set_name("...").build()` | `scripts/scaffold.py` |
| "写一段开头剧情 / 让艾琳说句话 / 显示背景" | `RenPyScript().say("e","...")...write("s.rpy")` | `scripts/bridge.py` |
| "加个好感度系统 / 做个图片画廊 / 加中文字体" | `apply("gallery", {...}).write("g.rpy")` | `scripts/patterns.py` |
| "配置立绘 / 加立绘切换系统" | `apply("layeredimage", {...}).write("li.rpy")` | `scripts/patterns.py` |
| "做存档/读档/设置界面" | `apply("save_load", {...})` / `apply("preferences", {...})` | `scripts/patterns.py` |
| "开场 logo 动画 / 制作人员名单滚动" | `apply("splash", {...})` / `apply("credit_roll", {...})` | `scripts/patterns.py` |

## 脚本速览

| 文件 | 定位 | 一句话用法 |
|------|------|-----------|
| `scripts/scaffold.py` | 新建项目骨架（含 options/characters/screens 等） | `Scaffold("path").set_name("我的故事").build()` |
| `scripts/bridge.py` | Python 链式生成 .rpy 脚本文本 — **不是 AST 实现** | `RenPyScript().say("e","你好")...write("s.rpy")` |
| `scripts/patterns.py` | 预制功能模块（好感度/画廊/字体/splash/立绘等） | `apply("gallery", {...}).write("g.rpy")` |

## 场景指引

### 场景 A：从零开始建项目 → scaffold.py
```python
from scaffold import Scaffold
Scaffold("D:/my_game").set_name("我的故事").set_resolution(1280, 720).build()
```

### 场景 B：写代码生成器 → bridge.py
```python
from bridge import RenPyScript
s = RenPyScript()
s.character("e", "艾琳", color="#c8ffc8")
s.label("start")
s.scene("bg cafe", with_="fade")
s.say("e", "要喝什么？")
s.menu([("咖啡", "coffee"), ("茶", "tea")])
s.write("game/script.rpy")
```

**bridge.py 支持的语句类型**（基于 `renpy/ast.py` 节点名称）：
- 流程：`label()` / `call()` / `jump()` / `return_()` / `pass_()`
- 内容：`say()` / `menu()` / `scene()` / `show()` / `hide()` / `with_()`
- 逻辑：`if_()` / `elif_()` / `else_()` / `while_()`
- 声明：`init()` / `define()` / `default()` / `character()` / `image()` / `transform()`
- 音频：`play()` / `stop()` / `queue()` / `pause()`
- 画面：`show_layer()` / `camera()` / `window_show()` / `window_hide()`
- 系统：`screen()` / `style()` / `python()` / `early_python()`

### 场景 C：加游戏功能 → patterns.py
```python
from patterns import apply

# 好感度系统
apply("affection", {"characters": [
    {"var": "e", "name": "艾琳"},
    {"var": "l", "name": "陆景"}
]}).write("game/affection.rpy")

# 立绘系统
apply("layeredimage", {
    "name": "eileen",
    "layers": [
        {"type": "group", "attribute": "face", "auto": True, "prefix": "eileen"},
        {"type": "group", "attribute": "clothes", "variants": [
            {"attribute": "default", "default": True},
            {"attribute": "casual"}
        ]}
    ],
    "image_format": "images/eileen/{image}.png"
}).write("game/layered_eileen.rpy")

# 存档兼容性迁移
apply("after_load_migration", {
    "version": "1.0",
    "migrations": [("0.5", "renpy.set_variable('gold', 100)")],
    "use_before": True
}).write("game/migration.rpy")
```

## 注意事项

| 场景 | 说明 |
|------|------|
| bridge 限制 | **文本生成器**，不是 Ren'Py AST 的真实实现；适合生成代码草稿，不适合控制 Ren'Py 底层行为 |
| 图片资源 | bridge.py 不生成图片资源 — 图片需手动放入 `game/images/` |
| patterns 生成 | 生成后可能需要微调（如图片路径、字号）|
| scaffold 生成 | 生成的是最小 demo 结构，不是完整 Ren'Py 项目范例 |
| 打包 / Lint / 测试 | → 加载 **renpy-dev** Skill |


## 容错性说明

| 场景 | 行为 |
|------|------|
| 覆盖已有 .rpy 文件 | write() 自动备份原文件为 .bak（可设置 exists_ok=True/False）|
| sdk 版本低于 8.0 | 版本守卫打印警告，建议避免 8.x 特性 |
| project 目录已存在 | Scaffold.build() 对每个文件做 .bak 备份再覆盖 |
| 非法参数 | apply() 校验 pattern 名称和参数类型，未知名称抛 ValueError |
| 输出目录不存在 | write() 自动 makedirs |


## 进阶参考
- [Patterns 参数详情](references/patterns_api.md) — 所有预制模式完整参数
- [常见陷阱 & 最佳实践](references/renpy_gotchas.md) — 图片/字体/缩进/变量作用域

## 版本边界

目标 SDK: Ren'Py ≥ 8.0。SDK 不可达时不阻塞，仅生成代码供其他环境使用。
