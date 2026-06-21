---
name: renpy-dev
version: "0.2.2"
description: "Packaging, linting, testing, diagnostics, and export workflows for Ren'Py 8.5.3 projects. Use when the user needs to run SDK CLI commands, analyze project structure, diagnose errors, manage translations, or export/import project data as JSON."
compatibility: "renpy>=8.0"
agent_created: true
---

# Ren'Py Dev — SDK 工程工具

> 本 skill 提供 Ren'Py 8.5.3 SDK 的轻量封装工具。每个脚本独立且有明确的能力边界。

## 路由表 — 你说什么就用什么

| 用户说 | 路由到 | 脚本 |
|--------|--------|------|
| "检查代码有没有问题" / "lint" | `cli.lint()` → SDK 语法检查 | `scripts/cli.py` |
| "打包成 Windows 版 / APK / 网页" | `cli.distribute()` / `cli.android_build()` / `cli.web_build()` | `scripts/cli.py` |
| "跑测试 / 测试对话流程" | `cli.test()` / `cli.run_tests()` + `make_scene_test()` | `scripts/cli.py` |
| "编译 / 重新编译" | `cli.compile()` | `scripts/cli.py` |
| "添加翻译 / 导出对话" | `cli.translate()` / `cli.dialogue()` / `cli.merge_strings()` | `scripts/cli.py` |
| "分析项目结构 / 看看有多少 label" | `Analyzer(path).analyze().report()` → 正则扫描 | `scripts/analyze.py` |
| "报这个错怎么修 / 崩溃 / 报 LabelNotFound" | `diagnose_from_file(path)` → 已知错误模式匹配 | `scripts/diagnose.py` |
| "导出对话成 JSON / 从 JSON 恢复" | `Export(path).to_json(out)` / `Export(path).from_json(f)` | `scripts/export.py` |

## 脚本速览

| 文件 | 定位 | 一句话用法 | 与 Ren'Py 8.5.3 源码对应 |
|------|------|-----------|---------------------------|
| `scripts/cli.py` | SDK CLI 命令的 subprocess 封装（Lint/编译/打包/运行/翻译/测试） | `RenPyCLI().lint("path")` | `renpy/arguments.py` 命令注册表；`renpy.py` CLI 入口 |
| `scripts/analyze.py` | 轻量正则结构扫描器（labels/screens/images/悬空引用）— **不是完整解析器** | `Analyzer("path").analyze().report()` | `renpy/ast.py` 的 AST 节点名称作参考，但只做正则匹配 |
| `scripts/diagnose.py` | 已知错误日志模式匹配和修复建议 — **不是通用错误分析器** | `diagnose_from_file("log.txt")` | `renpy/config.py` 的 `error_suggestion_handlers`；`renpy/error.py` 异常格式化 |
| `scripts/export.py` | JSON ↔ .rpy 单向导出（版本控制/翻译迁移） | `Export("path").to_json("out.json")` | `arguments.py` 的 `--json-dump` 功能 |

## 快速入门

```python
# 1. Lint 检查
from cli import RenPyCLI
cli = RenPyCLI()
result = cli.lint("D:/my_game", error_code=True)

# 2. 打包分发
cli.distribute("D:/my_game", destination="D:/output")

# 3. 分析项目结构
from analyze import Analyzer
print(Analyzer("D:/my_game").analyze().report())

# 4. 诊断错误日志
from diagnose import diagnose_from_file
for issue in diagnose_from_file("game/log.txt"):
    print(issue["severity"], issue["fix"])

# 5. 注入测试并运行
from cli import make_scene_test, make_menu_test
test_code = make_scene_test([("start", "choice"), ("end", None)])
cli = RenPyCLI()
cli.inject_test(test_code, "test_flow.rpy")
result = cli.run_tests("D:/my_game")
```

## 注意事项

| 场景 | 说明 |
|------|------|
| SDK 路径 | 自动检测：环境变量 `RENPY_SDK` → 向上查找 → 常见路径 fallback；也可显式传入 `sdk_path=` |
| 错误诊断 | diagnose.py **只能识别已知错误模式**，复杂逻辑 bug 不会捕获 |
| 测试 | `inject_test()` 后调用 `remove_injected()` 清理测试文件 |
| 游戏内容 | 需要写剧情/设画面/加系统？→ 加载 **renpy-user** Skill |
| 导出限制 | export.py 忽略 python 块、menu/screen 定义内的文本；同一对话以最后一行行号标记 |
| analyze 限制 | 基于正则扫描，**不能完整理解 Ren'Py 语法**；对 if、menu、init python、show expression 等复杂写法可能漏判/误判 |


## 容错性说明

| 场景 | 行为 |
|------|------|
| SDK 版本低于 8.0 | 版本守卫打印警告，建议避免使用 8.x 特性（layeredimage 等）|
| SDK 未安装 | 允许脱机生成代码（仅 IDE 辅助场景），运行命令时报错 |
| CLI 命令执行失败 | CLIResult.returncode 非零，错误信息在 stderr |
| CLI 命令超时 | 超时后返回 returncode=-1 |
| 项目结构分析 | analyze.py 跳过 cache/、__pycache__/、.git/ 目录 |
| 导出文件不可写 | 通过子进程返回错误信息，不崩溃 |


## 进阶参考

- [SDK 配置 & CLI 命令速查](references/sdk_config.md) — 自动检测逻辑、全部 CLI 命令

## 版本边界

目标 SDK: Ren'Py ≥ 8.0。SDK 不可达时仅警告，不阻塞（可能脱机生成代码供其他环境使用）。
