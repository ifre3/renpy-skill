# Ren'Py 硬编码英文文本中文化补丁 (patch_renpy_say.py)

## 功能

扫描 `.rpy` 文件中 `renpy.say()` 等 Python 动态生成的系统提示文本，这些文本因为：
1. 在 Python `init python:` 块中通过字符串拼接生成，Ren'Py 的 `generate_translations` 不会扫描到
2. 没有对应的翻译文件

工具会将这些硬编码英文文本替换为 `__()` 包裹的形式，使其可被翻译系统捕获。

## 用法

```bash
# 预览（dry-run，不修改文件）
python patch_renpy_say.py --project MyGame-1.0-pc --replacements 补丁集/renpy_say_replacements.csv

# 执行替换
python patch_renpy_say.py --project MyGame-1.0-pc --replacements 补丁集/renpy_say_replacements.csv --execute
```

## 替换表格式

替换规则在外部 CSV 文件中定义（`补丁集/renpy_say_replacements.csv`），格式：

```csv
old,new
"Your affection with X has increased to Y...","你对 X 的好感度提升至 Y..."
"Time to hit the hay...","该睡觉了……"
```

## 执行流程

1. 加载替换表 CSV
2. 扫描项目 `.rpy` 文件中的 `renpy.say()` 调用
3. Dry-run 预览所有匹配
4. 确认后 `--execute` 执行替换
5. 首次修改自动生成 `.bak` 备份
