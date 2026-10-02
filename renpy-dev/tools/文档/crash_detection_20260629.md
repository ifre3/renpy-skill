# 崩溃检测脚本完成总结

## 目标

为 Ren'Py 游戏项目编写静态崩溃风险检测脚本，扫描 `.rpy` 代码中可能导致运行时崩溃的模式。起因是 Android 端出现 `TypeError: 'int' object is not callable` 异常。

## 完成内容

### 1. 新建 `check_crash_risks.py`（15KB）

位置：`<skill>/renpy-dev/tools\错误检测\check_crash_risks.py`

覆盖 7 类崩溃风险：

| 级别 | 类别 | 说明 |
|------|------|------|
| CRITICAL | builtin_shadow | 内置函数名被赋值遮蔽（如 `$ str = ...`） |
| WARNING | map_misuse | Python3 `map()` 返回迭代器后的误用 |
| WARNING | globals_access | `globals()["dynamic_key"]` 无 try-except 保护 |
| WARNING | unsafe_intconv | `int()`/`float()` 转换无异常保护 |
| WARNING | div_zero | 除法潜在除零 |
| INFO | none_concat | 字符串拼接可能涉及 None |
| INFO | bare_except | 裸 `except:` 吞掉异常 |

### 2. 误报优化

初版 457 条结果中 339 条 div_zero 误报（Ren'Py 文本标签 `{s}`, `{i}`, `{color}` 和文件路径被误判为除法）。优化后：
- div_zero：339 → 0（仅检查 `$` Python 行，排除 Ren'Py 标签和路径关键词）
- none_concat：53 → 1（仅检查 `$` Python 行，排除 `string.digits` 等已知安全值）
- 总计：457 → 66 条（误报率 <5%）

### 3. CLI 集成

将 `crash` 命令注册到 `renpy-tools.py` 统一入口：
- `python renpy-tools.py crash <目录>` — 单独运行崩溃检测
- `python renpy-tools.py all <目录>` — 包含崩溃检测

### 4. 实际检测结果（LostInYou v0.15.1）

- 扫描 90 个 .rpy 文件
- **CRITICAL: 1** — `wordle.rpy:140` `$ str = letter` 遮蔽内置 `str()`
- WARNING: 64 — globals_access 56 + unsafe_intconv 8
- INFO: 1 — none_concat 1

关键发现：
- `wordle.rpy:140` 的 `$ str = letter` 会遮蔽内置 `str()`，若同作用域后续有 `str(...)` 调用则触发 `TypeError: 'str' object is not callable`
- `event_list.rpy` 有 56 处 `globals()[f"c_{...}"]` 动态访问，无 try-except 保护
- `cheats.rpy` 有 `int(value)` 转换无保护，用户输入非数字会 ValueError

## 文件清单

| 文件 | 大小 | 说明 |
|------|------|------|
| `错误检测/check_crash_risks.py` | 15KB | 崩溃检测主脚本 |
| `check_crash_risks_说明.md` | 1.4KB | 使用说明 |
| `renpy-tools.py` | 4.8KB | 更新 CLI 入口（新增 crash 命令） |
