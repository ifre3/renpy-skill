# 🔍 check — 翻译质量检查与审计
涵盖方面:调用lint检测,其他问题
已常见的游戏问题优先:
lint检测,
lint无法捕获的问题:标签闭合,转义字符,%中文
翻译后译文不显示-check_button_missing_translation.py
## check_label_issues.py 判定规则与边界
- 报告顺序：先收集全项目标签，再判定 jump/call 引用（两遍扫描），跨文件跳转不会误判。
- jump/call/return 只认**语句位置**，对白文本里的 "jump you" "return the book" 已屏蔽。
- 不可达代码只统计与标签体同级的语句，且跳过声明类语句（init/image/define/screen/style...）与嵌套 if/menu 里的 return。
- 已知噪音（WARNING 级，可忽略）：MISSING_RETURN 会把"靠 jump 结束"的标签也算上；ORPHAN_LABEL 是没人跳转的标签。
- 大 tl 文件（3 万行级）曾因 O(n²) 扫描挂死，已改单遍（12s 级）；默认跳过 tl/ 目录（--include-tl 可开）。
