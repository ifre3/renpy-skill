# Ren'Py Skills

Ren'Py 8.x 开发辅助 Skill 包。

## 包含

| Skill | 做什么 | 不做什么 |
|-------|--------|---------|
| `renpy-dev` | 工程工具链 — Lint、编译、打包、测试、诊断 | 不写剧情、不生成代码 |
| `renpy-user` | 参考手册 — Ren'Py 陷阱、最佳实践、源码路径索引 | 不输出模板、不代笔写代码 |

## 目录

```
renpy-dev/             # 工程工具链（Python 脚本）
├── SKILL.md
├── scripts/           sdk_common.py, cli.py, analyze.py, diagnose.py, export.py, test_runner.py
└── references/        sdk_config.md

renpy-user/            # 纯参考（无脚本）
├── SKILL.md
└── references/        renpy_gotchas.md
```

## 快速开始

内容创作 → AI 直接输出 `.rpy`，需要诊断/测试时加载 `renpy-dev`

```bash
# Lint
RenPyCLI().lint("D:/my_game")

# 诊断
diagnose_from_file("game/log.txt")

# 分析项目结构
Analyzer("D:/my_game").report()
```
