# check_crash_risks.py — Ren'Py 运行时崩溃风险检测

## 功能

静态扫描 `.rpy` 文件中可能导致运行时崩溃的代码模式，覆盖 8 类风险：

### 检测类别

| 级别 | 类别 | 说明 | 示例 |
|------|------|------|------|
| CRITICAL | `builtin_shadow` | 内置函数名被赋值遮蔽 | `$ str = "hello"` → 后续 `str(42)` 崩溃 |
| CRITICAL | `translation_shadow` | Ren'Py 翻译函数 `_` 被赋值/解包遮蔽 | `$ a, b, _ = f()` → `_("...")` TypeError |
| WARNING | `map_misuse` | Python3 map() 迭代器误用 | `a, b, c = map(...)` 后再 `list(var)` 得空 |
| WARNING | `globals_access` | `globals()["key"]` 无 try-except | `globals()[f"c_{name}"]` 可能 KeyError |
| WARNING | `unsafe_intconv` | `int()`/`float()` 无异常保护 | `int(flag_hina_h)` 若值为 None 崩溃 |
| WARNING | `div_zero` | 除法潜在除零 | `$ ratio = x / count` 若 count=0 |
| INFO | `none_concat` | 字符串拼接可能涉及 None | `"hello" + name` 若 name=None |
| INFO | `bare_except` | 裸 except 吞掉异常 | `except:` 隐藏 bug |

### 用法

```powershell
# 基本扫描
python check_crash_risks.py "D:\path\to\game"

# 显示修复建议
python check_crash_risks.py "D:\path\to\game" --fix-suggestions

# 只看 CRITICAL 级别
python check_crash_risks.py "D:\path\to\game" --severity CRITICAL

# 包含翻译目录
python check_crash_risks.py "D:\path\to\game" --include-tl

# 包含引擎运行时目录 renpy/、lib/（默认跳过，引擎源码误报多）
python check_crash_risks.py "D:\path\to\game" --include-engine

# 通过统一入口调用
python renpy-tools-cli.py crash "D:\path\to\game"
```

### 默认跳过的目录

| 目录 | 原因 |
|------|------|
| `tl/` | 翻译目录（`--include-tl` 可包含） |
| `renpy/`、`lib/`、`cache/`、`saves/` | 游戏自带引擎运行时与存档，非游戏代码（`--include-engine` 可包含） |
| 以 `.` 开头的隐藏目录 | 备份目录如 `.fix_name_backup` |

### 误报抑制（v2 行为）

`translation_shadow` 与 `builtin_shadow` 在上报前会做**作用域核实**：

1. 定位被遮蔽赋值所在的最小作用域（`def` / `screen` / `python` 块 / `label`）；
2. 若为局部作用域（screen 内 `$` 赋值、python 函数内），检查该作用域内是否
   实际调用了被遮蔽的函数（`_("...")`、`str(...)` 等）；
3. 未调用则视为无害，不上报（screen 局部变量与 store 互不影响）；
4. store 全局作用域的遮蔽仍然一律上报（会全局覆盖 Ren'Py 内置名）。

实测案例（LostInYou 0.16.1）：旧版报 25 条 CRITICAL，其中引擎 22 条 +
游戏 3 条全部为误报（`end_screen.rpy` 的 `_` 解包、`text_tags.rpy` 的
`_, text = ...`、`wordle.rpy` 的 `$ str = ...` 均未在作用域内实际调用被遮蔽
函数）；v2 全部不再上报，CRITICAL 归零。

### 退出码

- `0`：无 CRITICAL 级别问题
- `1`：存在 CRITICAL 级别问题

### 实际检测结果示例（v2，LostInYou 0.16.1）

- 扫描 106 个 .rpy 文件（已跳过引擎与翻译目录）
- CRITICAL: 0
- WARNING: 66 — globals_access 56 + unsafe_intconv 9 + div_zero 1
- INFO: 1 — none_concat 1
