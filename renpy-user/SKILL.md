---
name: renpy-user
description: "Ren'Py 游戏开发参考与玩家侧工具地图。当你需要写 Ren'Py 对话、调试中文显示（字体方块）、了解存档兼容性、做解包/存档/汉化或汉化质检时激活。不生成代码模板。"
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
- **汉化翻译工作流** → [references/translation_workflow.md](references/translation_workflow.md)（翻译 .rpy：文件校验 / `翻译结果.md` 术语表 / 意译原则 / 审查循环）
- **译文润色**（已翻完还要提质）→ renpy-dev 的 [references/translation_polish.md](../renpy-dev/references/translation_polish.md)（双角色两阶段润色 / LinguaGacha 路线，按预算自选）
- **非显性技巧陷阱速查** → [references/snippets.md](references/snippets.md)（F2 语言热键、Scroll 三参、拖放回调契约、历史屏/气泡/侧头像陷阱——只收模型容易写错的点，基础模板不收录）
- **画廊/养成/调试** → [references/gallery_and_stats.md](references/gallery_and_stats.md)（画廊 CG/Music Room、属性养成、金手指、性能预设）
- **一键解锁画廊/CG/回放**（别人的游戏）→ [references/unlock_patches.md](references/unlock_patches.md)（引擎判定链 + 投放式补丁全文 + 控制台一行 + 非标准画廊打法）
- **排错指南** → [references/debugging.md](references/debugging.md)（lint/Shift 键调试/控制台/断点/log/常见 bug 分类/二分法）
- **开发者侧工具** → [references/advanced_tools.md](references/advanced_tools.md)（字体修改 4 法、rpyc 反编译、rpa 解包、镜像加速）
- 本地 SDK 路径（见下表）

需要工程工具链（lint/打包/编译/翻译）→ 加载 **renpy-dev** Skill。

## SDK 路径（不写死）

SDK 根目录 `<SDK>` 按以下优先级解析：`--sdk` 参数 → 环境变量 `RENPY_SDK` → 向上查找 → `renpy-dev/scripts/sdk_common.py` 的 `_KNOWN_SDK_PATHS`（本机路径只在此一处维护）→ `~/renpy-sdk`。

| 用途 | 相对 `<SDK>` 的位置 |
|------|------|
| 启动器 / 可执行文件 | `renpy.exe`（Linux/macOS 用 `renpy.sh`） |
| 官方文档 | `doc/` |
| SDK 自带 Python 解释器 | `lib/py3-windows-x86_64/python.exe`（Windows x64） |
