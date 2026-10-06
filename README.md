# renpy-skill

面向 AI Agent 的 Ren'Py 单体技能包：`renpy/` 一个技能覆盖全链路——工程工具链（lint / 编译 / 打包 / 翻译 / 结构分析）、开发参考（陷阱库 / 画廊 / 数值）、玩家侧（解包 / 存档 / 汉化 / 解锁补丁）与排错。设计目标是让 AI 在无人工补位的情况下，独立完成 lint、编译打包、汉化、质检、解包、存档编辑等完整链路。

> 2026-10-03 起由 renpy-dev + renpy-user 双技能合并为单技能，消除触发词打架与双向指针；旧路径引用已全部修复。
> 2026-10-05 `scripts/` 下 8 个分组目录与 4 个说明文件由中文名改为 ASCII，macOS 的 NFD 归一化问题根治。
> 2026-10-06 检查器契约层（`BaseChecker`）+ 门面注册表落地，只读检查器全部归位 `checks/`，同类多入口脚本经评估不拆。

## 目录结构

| 路径 | 职责 |
|------|------|
| `renpy/SKILL.md` | 唯一入口：脚本速览、触发关键词、注意事项（含独有引擎版本边界）、references 分场景索引 |
| `renpy/scripts/` | 顶层仅统一门面 `renpy-tools-cli.py`（30 子命令 + all/list）与 rpyc 反编译兜底 `unrpyc.py`；9 个分组目录全 ASCII（`sdk` `checks` `translate` `polish` `names` `linear` `setup` `shared` `tests`），404 用例回归测试。详见 `renpy/scripts/README.md` |
| `renpy/references/` | 15 个分场景参考：SDK 配置速查、工具包边界分级、剧本→脚本工作流、译文润色；gotchas 陷阱库、非显性技巧、画廊/养成/性能预设、字体/rpyc/rpa 速查、汉化工作流、汉化常见问题手册、tl 质检细则、玩家侧工具地图、解锁补丁、排错指南 |
| `package.py` | 分发打包（纯标准库）：显式白名单 + 产物结构自检 + 可复现 sha256。`python package.py` / `--check` |
| `LICENSE` | MIT。`renpy/scripts/README.md` 声称 MIT，仓库就得真有这个文件（由测试盯） |

## 使用

- **加载**：向 Agent 显式指定 SKILL.md 路径（`renpy/SKILL.md`）。
- **SDK 探测**优先级：`--sdk` 参数 → 环境变量 `RENPY_SDK` → 向上查找 → `sdk_common.py` 的 `_KNOWN_SDK_PATHS` → `~/renpy-sdk`。本机路径不写入仓库，本地使用时设 `RENPY_SDK` 环境变量或在 `_KNOWN_SDK_PATHS` 追加。
- **AI 翻译**：服务端点与密钥均通过环境变量提供（`RENPY_TRANSLATE_API_URL` / `RENPY_TRANSLATE_API_KEY`），仓库不含任何服务地址或凭据。
- **变更记录**：[CHANGELOG.md](CHANGELOG.md)（评审与修复流水，不在本文展开）。

## 维护约定

1. 可执行逻辑进 `renpy/scripts/` 或 SDK，技能文档只保留模型不知道的结论。
2. SKILL.md 的 description 必须覆盖全部故障关键词（崩溃 / traceback、汉化质检、字体方块、存档等）。
3. 每次项目收尾最多追加 1 条 gotcha（不超过 10 行，附可复制命令），不写教程。
4. 一个知识只放一处：`.rpyc` 反编译入口优先用独立的 renpy-script-decompile 技能，内置 `unrpyc.py` 仅作兜底（唯一说明处在 SKILL.md 注意事项"反编译"行）；rpyc/rpa 工具选型与版本坑统一在 `references/player_tools.md`，`advanced_tools.md` 不再重复；tl_check 分级细则唯一出处为 `references/tl_check.md`，SKILL.md 只留路由。
5. 目录名与文件名一律 ASCII（内容、注释、文档用中文不限）。macOS 的 NFD 归一化会让中文路径上的 `import` 在跨系统 checkout 后失效。
6. 改完 `scripts/` 必跑：`cd renpy/scripts/tests && python -m unittest discover`。**目录树、用例数、子命令数已由测试强制一致**，不用再靠人眼核对：`test_repo_consistency.py` 查文档内部自洽，`test_count.py` 查文档等于现实；新增/删除测试后这两处会一起失败并打印实际值。
7. 分发一律走 `python package.py`：显式白名单，产物必须恰好一个 `SKILL.md`、不含 `.git/` / `__pycache__` / `renpy-dev` / `renpy-user`，时间戳固定因而可复现（同样的源码打出同样的 sha256）。提交前可跑 `python package.py --check` 只体检不写文件。

## 已知边界

- 未注册进技能加载器，需手动指定路径加载。
- 解包 / 存档 / 汉化以调度成熟开源工具为主，不重写轮子；Ren'Py 自定义程度高，无法一键脚本化的部分由 AI 直接读写源码。
- `.rpyc` 反编译的首选路径指向**仓库外**的 `renpy-script-decompile` 技能；该技能不存在时会静默回落到内置 `unrpyc.py`。后者下载并执行第三方代码，现固定在上游 2026-02-23 的 commit `3ae8334e`（7 个镜像按实测延迟排序，见 `scripts/unrpyc.py` 顶部注释与升级方法）；镜像本身仍不可信，彻底收口（自带源码或 zip 哈希校验）列为后续项。
