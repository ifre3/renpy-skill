# 移除 Ren'Py 文件名 _translated 后缀脚本

## 背景
Ren'Py 翻译目录中有大量文件名被多重叠加 `_translated` 后缀，如 `cheats_translated_translated_translated.rpy`，需要一次性清理。

## 功能
- 递归处理目录下所有文件的文件名
- 使用 `str.replace("_translated", "")` 一次性移除所有 `_translated` 重复叠加
- 支持 dry-run 预览模式（默认）和 `--execute` 实际执行模式
- 执行前检查目标文件是否已存在，避免覆盖

## 用法
```powershell
python remove_translated.py <路径>           # 预览
python remove_translated.py <路径> --execute  # 实际执行
```
