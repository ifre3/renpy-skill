---
name: renpy-dev
description: "This skill provides packaging, linting, testing, diagnostics, and export workflows for Ren'Py projects. It should be used when the user needs to run SDK CLI commands, analyze project structure, diagnose errors, or export project data."
compatibility: "renpy>=8.0"
agent_created: true
---

# Ren'Py Dev — 工程工具

## 脚本速览

| 文件 | 用途 | 一句话用法 |
|------|------|-----------|
| `scripts/cli.py` | SDK CLI 封装（Lint/编译/打包/运行/翻译） | `RenPyCLI().lint("path")` |
| `scripts/analyze.py` | 项目结构分析（labels/screens/images/悬空引用） | `Analyzer("path").analyze().report()` |
| `scripts/export.py` | JSON ↔ .rpy 双向转换（版本控制/迁移） | `Export("path").to_json("out.json")` |
| `scripts/test_runner.py` | 自动化测试注入和执行 | `TestRunner("path").inject_test(code).run()` |
| `scripts/diagnose.py` | 错误日志解析和项目诊断 | `diagnose_from_file("log.txt")` |

## Trigger 关键词

| 你说 | 它做 |
|------|------|
| "检查代码有没有问题" | cli.lint 语法检查 |
| "打包成 Windows 版 / APK" | cli.distribute 打包分发 |
| "测试对话流程" | test_runner 自动测试 |
| "报这个错怎么修"、"闪退" | diagnose 解析错误日志 |
| "分析项目结构"、"看看有多少 label" | analyze 结构分析 |
| "导出项目结构成 JSON" | export 导出迁移 |
| "添加中文翻译" | cli.translate 多语言 |

## 快速入门

```python
# 1. Lint 检查
from cli import RenPyCLI
cli = RenPyCLI()
result = cli.lint("D:/my_game", error_code=True)

# 2. 打包分发
cli.distribute("D:/my_game", "D:/output")

# 3. 分析项目结构
from analyze import Analyzer
print(Analyzer("D:/my_game").report())

# 4. 诊断错误日志
from diagnose import diagnose_from_file
for issue in diagnose_from_file("game/log.txt"):
    print(issue["severity"], issue["fix"])
```

## 注意事项

| 场景 | 说明 |
|------|------|
| SDK 路径 | 自动检测：环境变量 `RENPY_SDK` → 向上查找 → 常见路径 fallback；也可显式传入 `sdk_path=` |
| 错误诊断 | diagnose.py 只能识别已知错误模式，复杂逻辑 bug 不会捕获 |
| 测试清理 | `inject_test()` 后调用 `remove_injected()` 清理测试文件 |
| 游戏内容 | 需要写剧情/设画面/加系统？→ 加载 **renpy-user** Skill |
| 导出限制 | export.py 忽略 python 块、menu/screen 定义内的文本；同一条对话以最后一行行号标记 |

## 进阶参考

[SDK 配置 & CLI 命令速查](references/sdk_config.md) — 自动检测逻辑、全部 CLI 命令

## 版本边界

目标 SDK: Ren'Py ≥ 8.0。SDK 不可达时仅警告，不阻塞（可能脱机生成代码供其他环境使用）。
 
 ## 2026-06-21 改进记录
 
 基于 Ren'Py 8.5.3 官方 SDK 源码和文档的改进：
 
 ### cli.py
 - 新增命令: update, director, rmpersistent, add_from, generate_gui, gui_images, 
   set_project, get_projects_directory, update_old_game, ios_create, ios_populate
 - 官方依据: doc/cli.html (Ren'Py 8.5.3 CLI 全部命令)
 - 所有命令签名与官方文档一致
 
 ### diagnose.py
 - 新增 Ren'Py 特有错误模式: LabelNotFound, ScreenNotFound, ImageNotFound,
   ParserError, init offset, screen load error, save compat (can't set attribute)
 - 官方依据: renpy/config.py error_suggestion_handlers
 
 | 你说 | 它做 |
 |------|------|
 | "报 LabelNotFound 错" | diagnose 识别 label 未定义 |
 | "闪退 / can't set attribute" | diagnose 识别存档不兼容 |
 | "ScreenNotFound 报错" | diagnose 识别 screen 未定义 |
