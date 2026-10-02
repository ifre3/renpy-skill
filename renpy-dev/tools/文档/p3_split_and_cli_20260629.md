# P3 任务完成：check_button_missing_translation.py 拆分 + 统一 CLI 入口

**日期:** 2026-06-29

## 完成内容

### 1. 拆分 check_button_missing_translation.py (745行 → 4+1 个文件)

原文件 26KB/745 行，拆分后：

| 新文件 | 大小 | 职责 |
|---|---|---|
| `common.py` | 4.4KB | 共享模块（ANSI颜色、跳过规则、文件扫描、翻译加载、格式化输出） |
| `check_ui_text.py` | 4.3KB | WARN: textbutton/label/show text/text f-string 缺少 _() |
| `check_translation_misuse.py` | 4.4KB | BUG: Character[var] 缺 !t / _() 在 init 无效 / [变量] 缺 !t |
| `check_func_text.py` | 3.2KB | WARN: renpy.input/notify/自定义屏幕调用 缺少 _() |
| `check_auto_trans.py` | 3.4KB | INFO: Character 名字框 / menu 选项交叉引用 |

拆分原则：按严重程度 + 语义分组，3级（BUG/WARN/INFO）各一个脚本，共享代码抽到 common.py。

### 2. 创建 renpy-tools.py 统一 CLI 入口 (3.8KB)

```
renpy-tools.py ui/misuse/func/auto/lint/integrity/untranslated/duplicate/namebox <项目目录>
renpy-tools.py all <项目目录>    → 一键跑全部 4 个检测
renpy-tools.py list              → 列出所有工具
```

注册了全部 9 个工具的路径和描述。

### 3. 验证结果

- 每个子脚本在 LostInYou-0.15.1-pc 项目上独立运行通过 ✅
- `renpy-tools.py all` 退出码 0 ✅
- `renpy-tools.py list` 正常输出 ✅
- Windows GBK 编码问题已处理（PYTHONIOENCODING=utf-8）

### 4. 更新 README.md

- 准确反映当前目录结构和文件名
- 添加快速开始命令
- 添加典型工作流

## 相关文件

- `<skill>/renpy-dev/tools\错误检测\common.py` (新增)
- `<skill>/renpy-dev/tools\错误检测\check_ui_text.py` (新增)
- `<skill>/renpy-dev/tools\错误检测\check_translation_misuse.py` (新增)
- `<skill>/renpy-dev/tools\错误检测\check_func_text.py` (新增)
- `<skill>/renpy-dev/tools\错误检测\check_auto_trans.py` (新增)
- `<skill>/renpy-dev/tools\renpy-tools.py` (新增)
- `<skill>/renpy-dev/tools\README.md` (覆盖更新)
- `<skill>/renpy-dev/tools\错误检测\check-button-missing-translation.py` (保留原文件，可后续删除)
