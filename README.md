# Ren'Py 开发技能包

为 AI 辅助 Ren'Py 视觉小说创作提供工程支撑。

**基于 Ren'Py 8.5.3 官方 SDK 源码与文档实现。** 覆盖脚本生成、CLI 封装、项目骨架搭建、错误诊断、存档兼容全链路。

## 技能概览

| 技能 | 用途 | 核心能力 |
|------|------|---------|
| `renpy-dev` | 工程工具链 | CLI 封装、语法检查、项目分析、错误诊断、导出迁移、自动化测试 |
| `renpy-user` | 内容创作 | 脚本生成（28 种语句）、预制模式（12 种）、项目脚手架 |

### renpy-dev —— 工程工具链

基于 Ren'Py 8.5.3 官方 CLI（doc/cli.html）和错误处理机制（renpy/config.py）：

- **CLI 封装**：22 个命令全覆盖，参数签名与官方文档一致
- **代码检查**：封装 lint 命令，支持 --error-code / --by-character 等全部参数
- **项目分析**：扫描 labels / screens / images / 悬空引用
- **错误诊断**：19 种 Ren'Py 特有错误模式（LabelNotFound / ScreenNotFound / ImageNotFound / 存档不兼容等）
- **导出迁移**：.rpy ↔ JSON 双向转换

### renpy-user —— 内容创作

基于 Ren'Py 8.5.3 官方 AST（renpy/ast.py）和内置模式库：

- **脚本生成**：28 种 Ren'Py 语句，含 call / jump / if / while / define / default / play / pause 等
- **预制模式**：12 种开箱即用功能模块
- **项目脚手架**：从零生成完整项目骨架，内置容错性配置

## 快速开始

环境要求：Ren'Py SDK >= 8.0，Python 3.7+。

```bash
# 1. 设置 SDK 路径
set RENPY_SDK=D:/renpy-8.5.3-sdk

# 2. 执行 lint 检查
python cli.py /path/to/project lint --error-code

# 3. 生成游戏脚本
python -c "
from bridge import RenPyScript
s = RenPyScript()
s.character('e', 'Eileen', color='#c8ffc8')
s.label('start')
s.scene('bg cafe', with_='fade')
s.say('e', 'Hello!')
s.write('game/script.rpy')
"
```

## 预制模式一览

| 模式 | 用途 |
|------|------|
| `gallery` | 图片画廊 + 解锁系统 |
| `cjk_font` | 中/日/韩字体全局配置 |
| `splash` | 开场 logo 动画 |
| `nvl_mode` | NVL 模式适配 |
| `save_load` | 存档/读档增强 |
| `preferences` | 设置界面扩展 |
| `credit_roll` | 制作人员名单滚动 |
| `day_night` | 早晚切换系统 |
| `affection` | 好感度系统（多角色/多等级） |
| `choice_timer` | 菜单计时器 |
| `after_load_migration` | 存档版本迁移 |
| `layeredimage` | LayeredImage 立绘系统 |
| `fault_tolerance` | 容错性配置 |

## 更新日志

### v0.2.0 — 2026-06-21

核心代码全部基于 Ren'Py 8.5.3 官方 SDK 源码与文档重写。

**脚本生成器（bridge.py）**
- 语句类型从 6 种扩展至 28 种，覆盖 renpy/ast.py 全部核心 AST 节点
- 新增：call / jump / return / pass / if / elif / else / while / define / default / init / play / stop / queue / pause / window_show / window_hide / show_layer / camera / image / transform / screen / style
- 新增 BlockScope 块管理器（with 语句自动缩进控制）
- 新增 validate() 语法验证器（引号配对、重复 label、悬空引用检测）

**CLI 封装（cli.py）**
- 基于 doc/cli.html 从 8 个命令补齐至 22 个
- 新增：update / director / rmpersistent / add_from / generate_gui / gui_images / set_project / get_projects_directory / update_old_game / ios_create / ios_populate / extract_strings
- 所有命令参数签名与官方文档一致

**预制模式（patterns.py）**
- 新增 after_load_migration：存档版本迁移（基于 config.after_load_callbacks，renpy/common/00start.rpy）
- 新增 layeredimage：LayeredImage 立绘系统（基于 doc/layeredimage.html）
- 新增 fault_tolerance：容错性配置（基于 config.exception_handler / load_failed_label / missing_label_callback / missing_image_callback / save_dump）

**错误诊断（diagnose.py）**
- 错误模式从 6 种扩充至 19 种
- 新增 Ren'Py 特有错误：LabelNotFound / ScreenNotFound / ImageNotFound / ParserError / init offset / 存档不兼容
- 基于 renpy/config.py error_suggestion_handlers 实现

**项目脚手架（scaffold.py）**
- 新增 error_handling.rpy 容错性配置文件
- 自动生成：exception_handler / load_failed_label / missing_label_callback / missing_image_callback / after_load_callbacks / save_dump / after_warp 标签

**文档**
- 更新 SKILL.md 触发词表
- 更新 patterns_api.md（3 个新模式完整参数文档）
- 更新 renpy_gotchas.md（存档迁移注意事项）

### v0.1.0 — 2026-06-18

- 初始发布：项目骨架生成、基础脚本生成器、CLI 封装、10 种预制模式
- 基于 Ren'Py 8.0+ 语法实现

## 目录结构

```
renpy-skill/
├── renpy-dev/                    # 工程工具链
│   ├── SKILL.md
│   ├── scripts/                  # cli.py / analyze.py / diagnose.py / export.py / test_runner.py
│   └── references/               # sdk_config.md
├── renpy-user/                   # 内容创作
│   ├── SKILL.md
│   ├── scripts/                  # bridge.py / patterns.py / scaffold.py
│   └── references/               # patterns_api.md / renpy_gotchas.md
└── README.md
```

## 维护说明

- 每个技能是独立单元，不跨技能共享代码
- _version_guard.py 按设计重复置于两个技能目录中
- 修改技能后运行 hermes skill validate <name> 检查语法
- 本项目的代码基于 Ren'Py 8.5.3 SDK 编写，目标版本 Ren'Py >= 8.0
