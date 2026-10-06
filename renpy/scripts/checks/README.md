# 🔍 check — 翻译质量检查与审计
涵盖方面:调用lint检测,其他问题
已常见的游戏问题优先:
lint检测,
lint无法捕获的问题:标签闭合,转义字符,%中文
翻译后译文不显示-check_button_missing_translation.py

## 本组边界（与 translate/ 的分工）
本组全部是**只读审计**：只报告问题，不改任何文件（唯一例外是用户显式点名的导出：
`check_untranslated --csv`、`check_charname_translation --stub`）。会写文件的工具
（AI 回填、修补、名框同步）在 `../translate/`。想"找出问题"来本组（或直接
`renpy-tools-cli.py all`），想"修掉问题"去 translate/。

2026-10-06：`check_translation_integrity.py` / `check_untranslated.py` /
`check_charname_translation.py` 从 `../translate/` 归位到这里——它们判据都在只读审计上，
且需与门面 `all` 的其余检查器共享同一套 `CHECKER` 契约。现在 `checks/` 收全部只读检查器，
`translate/` 只留会改文件的工具。

## 检查器契约（CHECKER）
本组每个检查器都声明模块级 `CHECKER`，供门面 `renpy-tools-cli.py` 读取：

```python
class CrashRiskChecker(BaseChecker):
    name = "crash"                   # 门面子命令名
    summary = "检测运行时崩溃风险"    # list / all 里的描述
    takes = PROJECT                   # 位置参数吃 <项目> 还是 game/tl/<lang>
    requires_tl = False# 是否必须存在 game/tl/<lang> 才有意义
```

门面的子命令→路径映射、分组、以及"要不要 tl 目录"都从这里派生，不再有两张 33 项手写表。
漏声明 `-l/--language` 这类参数透传问题由 `tests/test_tool_registry.py` 的防复发断言兜住
（历史上 `check_i18n.py` 漏过，导致 `all` 在任何项目上恒定返回 1）；只读红线由
`tests/test_checker_contract.py` 钉死。

## check_label_issues.py 判定规则与边界
- 报告顺序：先收集全项目标签，再判定 jump/call 引用（两遍扫描），跨文件跳转不会误判。
- jump/call/return 只认**语句位置**，对白文本里的 "jump you" "return the book" 已屏蔽。
- 不可达代码只统计与标签体同级的语句，且跳过声明类语句（init/image/define/screen/style...）与嵌套 if/menu 里的 return。
- 已知噪音（WARNING 级，可忽略）：MISSING_RETURN 会把"靠 jump 结束"的标签也算上；ORPHAN_LABEL 是没人跳转的标签。
- 大 tl 文件（3 万行级）曾因 O(n²) 扫描挂死，已改单遍（12s 级）；默认跳过 tl/ 目录（--include-tl 可开）。
