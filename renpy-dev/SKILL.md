---
name: renpy-dev
description: "打包/Lint/编译/翻译。当你需要工程工具链时激活。"
compatibility: "renpy>=8.0"
metadata:
  openclaw:
    emoji: 🛠️
    permissions: ["file.read", "file.write", "exec"]
    os: ["darwin", "linux", "windows"]
---

# Ren'Py Dev — 工程工具

## 脚本速览

| 文件 | 用途 | 一句话用法 |
|------|------|-----------|
| `scripts/sdk_common.py` | SDK 路径检测共用模块（cli 依赖） | `detect_sdk()`, `find_platform_python(sdk)` |
| `scripts/cli.py` | SDK CLI 封装：Lint/编译/打包/运行/翻译 | `RenPyCLI().lint("path")` |
| `scripts/analyze.py` | 项目结构分析（labels/screens/悬空引用，带行号，离线可用） | `Analyzer("path").analyze().report()` |

## Trigger 关键词

| 你说 | 它做 |
|------|------|
| "检查代码有没有问题" | cli.lint 语法检查 |
| "打包成 Windows 版 / APK / Web 版" | cli.distribute / android_build / web_build |
| "分析项目结构"、"看看有多少 label" | analyze 结构分析 |
| "添加中文翻译"、"导出翻译" | cli.translate / extract_strings / merge_strings |

## 快速入门

```python
from cli import RenPyCLI
cli = RenPyCLI()
print(cli.format_result(cli.lint("D:/my_game", error_code=True)))

from analyze import Analyzer
print(Analyzer("D:/my_game").analyze().report(verbose=True))
```

## 注意事项

| 场景 | 说明 |
|------|------|
| SDK 路径 | 自动检测（`sdk_common.py`）：`sdk_path=` 参数 → 环境变量 `RENPY_SDK` → 向上查找 → 已知路径；本机新装 SDK 只需在 `_KNOWN_SDK_PATHS` 追加一行 |
| 错误诊断 | **没有诊断脚本**——把 log.txt/traceback 直接给 AI 判读即可，比正则匹配准 |
| 测试 | 没有测试脚本——Ren'Py testcase 语法（`run`/`click`/`advance until screen`/`assert eval`）AI 直接写在 .rpy 里，用 `renpy.py 项目 test` 执行 |
| 存档/解包/汉化补丁 | 玩家侧需求 → 加载 **renpy-user** 的 `references/player_tools.md` |
| 游戏内容 | 需要写剧情/设画面/加系统？→ 加载 **renpy-user** Skill |
| 导出 JSON | 已删除 export.py——官方 `translate` 命令生成标准翻译文件，够用 |

## 进阶参考

[SDK 配置 & CLI 命令速查](references/sdk_config.md) — 自动检测逻辑、全部 CLI 命令

## 版本边界

目标 SDK: Ren'Py ≥ 8.0。SDK 不可达时仅警告，不阻塞（可能脱机生成代码供其他环境使用）。
