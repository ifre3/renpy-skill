# translate/ — AI 翻译写入与修补

> **要点已内联到 [../README.md](../README.md)「translate/ — 写入与修补」一节**，本文件只留本组边界摘要。

本组只留**会改文件**的工具：回填、修补、名字框同步。只读检查器已全部归位 `../checks/`。
润色是本组下游：`../polish/` 的产出最终经本组 `autotranslate.py apply` 回填。

| 脚本 | 功能 |
|------|------|
| `autotranslate.py` | 统一翻译管线：扫描 → 分批 LLM 翻译 → 校验 → 安全回填 |
| `sync_namebox_translation.py` | 角色名字框同步：按术语表生成 `translate strings` 条目。三类说话人写法（`Character()` / 带标签裸 define / 内联），带 `{color=}` 的名字**整串匹配且译文保留标签**；`--stub <路径>` 写独立文件（默认试运行，`--apply` 才写） |
| `fix_translation_comments.py` | 翻译注释中的术语反向恢复 |
| `patch_renpy_say.py` | 修补 Python `renpy.say()` 硬编码英文 |
| `fix_missing_tags.py` | 修复丢失标签，低置信度项只生成人工清单 |

详见 [../README.md](../README.md)（推荐流程、安全规则、回填 JSON 格式、缓存说明）。
