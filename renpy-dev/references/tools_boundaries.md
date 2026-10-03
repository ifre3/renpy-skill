# renpy-tools 工具包边界与通用性（保守使用经验）

> 位置：skill 内置 `renpy-dev/scripts/`（历史版本曾置于 `renpy-dev/tools/` 与 `<SDK>/tools/`）。结论基于 2026-10-02 全源码审读。
> 用法原则：**通用工具直接跑；半通用先看本页再调参；专用条目当经验用，不要当现成轮子。**

## 通用度分级

- 【通用 20】`renpy-tools-cli` `tl_check` `check_charname_translation` `check_translation_integrity` `check_untranslated` `fix_translation_comments` `patch_renpy_say`(机制) `add_performance_panel` `patch_android_tablet` `remove_translated` `setup_i18n` `unrpyc` `check_auto_trans` `check_crash_risks` `check_duplicate_translations` `check_label_issues` `check_translation_misuse` `check_type_safety` `check_ui_text` `lint_check` —— 直接用。
- 【半通用 10】`linear_mode` `unify_name_translations` `autotranslate` `sync_namebox_translation` `add_fonts` `switch_default_language` `check_func_text` `check_button_missing_translation` `lint_report` `lint_rpy`
- 【专用 2】`fix_missing_tags`
- 【基础设施】`公共/backup.py`(幂等 .bak+原子写, fail-closed) `公共/rpy_syntax.py` `错误检测/common.py`

## 半通用条目的保守经验

| 工具 | 边界 | 保守做法 |
|------|------|----------|
| `linear_mode.py` | **剧本门控（经验做法，未内置脚本）**：把路由标签 if/jump 链简化成「totaldays 达标 && 本天未播」写回剧本（FriendshipClub 式节点门控，需授权改原文件；条件简化会丢弃前置 flag → 剧情连续性可能有小跳跃）。**悬浮补丁（linear_mode.py add）**：单开关 + 回调顶层重定向；菜单仍需手点、repeatable 长对话场景不跳。**modify 专用**：只认 `get_event_list` + `Event(id=)` 事件表（LostInYou 自有机制）。add 的场景推导含 LostInYou 式桩标签与 `script.rpy` 命名假设（`--min-says/--include/--exclude/--list` 校正） | 先 `analyze` 再选方式；路由链集中在单标签 → 用剧本门控（自行改写剧本，不要找现成脚本）；不想改原文件 → 悬浮补丁；有事件表 → modify |
| `unify_name_translations.py` (v6) | 核心通用（不猜测变体，全靠外部 glossary）；残留 SKIP_FILES 四个文件名、`DEFAULT_TL_DIR=game/tl/schinese`。旧版 `unify_names_v2.py` 已移除 | 换游戏传 `--tl-dir`；SKIP_FILES 残留无害但注意 |
| `autotranslate.py` | DEFAULT_CONFIG 不内置端点（`--api-url` 或环境变量 `RENPY_TRANSLATE_API_URL` 提供 OpenAI 兼容端点），`target_language="Simplified Chinese"` 默认简中，提示词是 Galgame 中文化专用 | 换语言对先改 DEFAULT_CONFIG；端点与密钥都走环境变量（`RENPY_TRANSLATE_API_URL` / `RENPY_TRANSLATE_API_KEY`） |
| `sync_namebox_translation.py` | 默认目标 `script_translated.rpy`、术语表 `导出_术语表.xlsx` 是自家命名约定 | 永远先看试运行输出（默认不写，`--apply` 才落盘） |
| `add_fonts.py` | 只认 setup_i18n 生成的 `fonts_common.rpy` 与 4 个自家 define 变量名 | 先跑 `setup_i18n.py`，否则拒绝写入是预期行为 |
| `switch_default_language.py` | 依赖 setup_i18n 的 language_selector marker 注释格式 | 同上，配套使用 |
| `check_func_text.py` / `check_button_missing_translation.py` | `SCREEN_CALL_KW`（common.py）白名单含特定游戏 screen 名（`end_screen_text`/`reward_button`/`settings_item`/`tab_button`），换游戏漏报这些类目 | 新项目把该游戏的自定义 screen 名补进 `错误检测/common.py` 的 SCREEN_CALL_KW |
| `lint_report.py` / `lint_rpy.py` | 语言已参数化但仍默认 schinese | 非简中项目必须显式传 `-l <lang>`，否则检测不到条目 |

## 专用条目（当经验，不当工具）

- `fix_missing_tags.py`：框架（丢失标签 A-F 分类 + manual_fixes.json 流程）可复用，但 MANUAL_OVERRIDES 49 条 (文件,行号)、ITALIC_MAP 全部绑定 Tomori 系项目。换游戏只把它当 dry-run 报告生成器，逐条人工处理。
- 历史脚本 `unify_names_v2.py`、`fix_name_inconsistencies.py`（deprecated）已于 2026-10-03 移除：均绑定特定游戏角色表，人名统一一律用 `unify_name_translations.py` (v6)。

## 写操作风险表（2026-10-02 P1 修补后）

| 操作 | 状态 |
|------|------|
| `tl_check.py --fix` | ✅ 已修：原子写 + 首次 .bak（fail-closed） |
| `add_performance_panel.py --remove` | ✅ 已修：删除前先 create_bak |
| `sync_namebox_translation.py` | ✅ 已修：默认试运行，`--apply` 才写 |
| `lint_report.py` / `lint_rpy.py` | ✅ 已修：`-l/--lang` 参数化（默认 schinese；换语言必须显式传） |
| `check_button_missing_translation.py` | ✅ 已修：复制函数改回 `from common import`，SCREEN_CALL_KW 单点维护 |
| 其余全部写路径 | 均有 .bak / 备份目录 / dry-run / fail-closed |

> 注意：`tl_check --fix` 回写会把 UTF-8 BOM 去掉（原行为即如此，Ren'Py 不受影响）。

## 引擎版本经验

- `config.label_callbacks`（列表）为 8.x 形态；7.x 只有单数 `config.label_callback`，旧版访问列表名直接抛 "not a known configuration variable"（7.4.8.1895 实测崩 init；官方 changelog 确认改名）。给不确定版本的游戏写补丁：先 try 列表再回退单数并链式调用。
- init 阶段也会触发 label 回调（如 `gui.init()` → `_style_reset`），此时 `default` 变量未建立，读 store 一律 `getattr` 兜底 + 整体 try。
- **屏幕体读 store 变量也必须走 getattr 助手**：7.4.8 的 `Default.set_default` 只对「不在存档 `_defaults_set`/`ever_been_changed` 里」的变量落地（ast.py 实证）；换补丁版本后读旧存档时，同名变量会被跳过 default 又不存在 → `NameError`。避免屏幕与 default 变量同名，读一律 `getattr(renpy.store, "x", fallback)`。
- **回调/兜底 except Exception 会吞 `renpy.jump`**：7.4.8 的 `renpy.jump()` 就是 `raise JumpException`（exports.py L1902 实证）；包裹 jump 的 try 必须先 `except JumpException: raise` 再 `except Exception`，否则自动跳转变「报 error 不跳转」（Sensei Overnight 实测）。
- **官方线性模式的另一种形态**：`gamemodelinear = True/False` 赋值 + 事件 junction 处 `if gamemodelinear == True:` 门控（FriendshipClub 式，170+ 处）。analyze 已加「linear 开关赋值/判定」两个通用标记检测它；这类游戏直接用自带线性模式（开局选 Linear），**不要叠我们的 add 补丁**。
- 旧引擎发行版验证优先用游戏自带解释器：`cd <游戏根> && lib/<平台>/python.exe <启动>.py . lint`（比本机新 SDK lint 更真实，新 SDK 会把 7.x 的非法 config 当合法）。
- Ren'Py `[]` 插值不支持算术（`[lm_pos+1]` NameError），先 `$` 算好再传。
