---
name: renpy-user
description: "Ren'Py 游戏开发参考与玩家侧工具地图。当你需要写 Ren'Py 对话、调试中文显示、了解存档兼容性、或做解包/存档/汉化时激活。不生成代码模板。"
compatibility: "renpy>=8.0"
metadata:
  openclaw:
    emoji: 📖
    permissions: ["file.read", "exec"]
    os: ["darwin", "linux", "windows"]
---

# Ren'Py User — 参考

## 这个 Skill 做什么

**不生成代码，不输出模板。** AI 直接写 `.rpy` 源代码——对话、Character 参数、ATL、SL2 screen、LayeredImage 这些模型都会，不要背模板。

本 Skill 提供的是模型记不全、容易过时的东西：

- **经验性陷阱** → [references/renpy_gotchas.md](references/renpy_gotchas.md)（字体回退、存档语义、SL2 坑）
- **玩家侧工具地图** → [references/player_tools.md](references/player_tools.md)（解包/存档编辑/汉化/重放，调度现成工具而非重造轮子）
- 本地 SDK 路径（见下表）

需要工程工具链（lint/打包/编译/翻译）→ 加载 **renpy-dev** Skill。

## 本地 SDK

Ren'Py SDK 路径（已安装）：`D:\workplace\renpy-8.5.3-sdk`

| 用途 | 路径 |
|------|------|
| SDK 可执行文件 | `D:\workplace\renpy-8.5.3-sdk\renpy.exe` |
| 官方文档 | `D:\workplace\renpy-8.5.3-sdk\doc\` |
| SDK Python 解释器 | `D:\workplace\renpy-8.5.3-sdk\lib\py3-windows-x86_64\python.exe` |
