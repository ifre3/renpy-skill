# Ren'Py 汉化常见问题手册

> 基于 Ren'Py 8.5.3 源码分析与实际汉化项目经验编写。
> 面向对象：正在进行或计划进行 Ren'Py 游戏汉化的译者/开发者。
>
> 每条问题包含：现象 → 原因（含源码依据） → 如何发现 → 修复方法

---

## 目录

1. [翻译完全不显示](#1-翻译完全不显示)
2. [部分文本翻译了但没显示](#2-部分文本翻译了但没显示)
3. [运行时崩溃](#3-运行时崩溃)
4. [翻译后 UI 错乱](#4-翻译后-ui-错乱)
5. [角色/名字问题](#5-角色名字问题)
6. [漏翻](#6-漏翻)
7. [译名不统一](#7-译名不统一)
8. [分析/生成工具相关](#8-分析生成工具相关)
9. [跨平台问题](#9-跨平台问题)
10. [疑难杂症排查流程](#10-疑难杂症排查流程)

---

## 1. 翻译完全不显示

### 1.1 游戏语言没设置为中文

**现象：** 翻译文件（`game/tl/schinese/`）存在，但游戏内全是原文。

**原因：** Ren'Py 的 `config.language` 未设置或设置错误。默认情况下 Ren'Py 不加载任何翻译。

**发现：** 检查 `options.rpy` 或 `screens.rpy` 中是否有 `$ config.language = "schinese"`。

**修复：**
```python
# 在 options.rpy 中
define config.language = "schinese"
```
或在启动器中选择语言。

---

### 1.2 翻译文件结构不对

**现象：** 设置了语言，翻译仍不显示。

**原因：** Ren'Py 只识别特定目录结构下的翻译文件：
- 正确的：`game/tl/schinese/script.rpy`
- 错误的：`game/script_tl.rpy` 或 `tl_chinese/script.rpy`

**源码依据：** `renpy/config.py` 中定义 `gamedir` 下的 `tl/<lang>/` 为翻译搜索路径。

**修复：** 将翻译文件放到 `game/tl/<语言代码>/` 目录下。

---

### 1.3 `_` 函数被遮蔽（translation_shadow）⭐ 高危

**现象：** 游戏运行时，所有 `_()` 包裹的文本显示为原文。日志无报错。

**原因：** 在 `init python:` 块或 RPY 脚本中，`_` 被赋值为其他值。Ren'Py 的翻译系统依赖 `_` 作为翻译函数，一旦被覆盖，后续所有 `_("text")` 调用静默失效。

```
# 典型肇事代码
init python:
    _ = renpy.store.store  # 或类似的赋值，仅做示例
```

```rpy
# 更常见的——在循环中
$ for _ in range(10):  ← 这一行！遮蔽了翻译函数
```

**源码依据：** `renpy/substitutions.py:282` — Ren'Py 字符串替换/插值系统调用 `_("text")` 进行翻译。如果 `_` 已经被 Python 层面的赋值替换成本地变量，翻译调用实际上执行的是那个新函数（或值）。

- 如果 `_` 被赋值为整数/字符串 → 调用 `_("text")` 时直接 TypeError 崩溃
- 如果 `_` 被赋值为其他函数 → "翻译"静默生效但不是真正的翻译
- `for _ in range(10)` 在 Ren'Py 中尤其危险，因为 `_` 在 Python 中被用作"不在意"变量名是惯用法

**发现：** 运行 `check_crash_risks.py`，检测 `builtin_shadow` 和 `translation_shadow` 规则。

**修复：** 找到给 `_` 赋值的代码，改为其他变量名：
```rpy
# 错误
$ for _ in range(10):
# 正确
$ for i in range(10):
```

---

## 2. 部分文本翻译了但没显示

### 2.1 漏写 `!t` 标记

**现象：** 角色名字框显示 "Hina" 而不是 "雏"；`[name]` 插值显示原文。

**原因：** Ren'Py 的字符串插值 `[变量名]` 默认**不翻译**插值结果。需要显式添加 `!t` 标记告诉引擎对结果进行翻译。

```
# screen 中
text "[name]"           # 不翻译 → 显示原文
text "[name!t]"         # 翻译 → 显示翻译后的名字

# Character 定义
define h = Character("Hina")
# 这里的 "Hina" 作为名字框文本，需要 translate strings 捕获
```

**源码依据：** `renpy/substitutions.py` 对插值标记的处理逻辑：`!t` 标记触发再次翻译（re-translate）插值得到的结果。

**常见陷阱：** 很多人以为 `__()` 包了角色名就万事大吉，但角色`[name]`显示在 `say` 窗口时是通过 `who` 变量插值显示的，如果 name 是变量（不是字面量），就需要 `!t`。

**发现：** **无法自动检测！** 运行时才出现，必须人工检查每个 `[...]` 插值是否需要翻译。

**修复：**
```rpy
# 对需要翻译的插值加 !t
text "[hero_name!t]"
```

---

### 2.2 翻译块中的 `old` 字符串有大小写或标点差异

**现象：** 翻译文件中有 `old "Hello"` 但原文是 `"hello."`，翻译不匹配。

**原因：** Ren'Py 的翻译匹配是**精确字符串匹配**（区分大小写和标点）。原文是 `"Hello!"`，翻译中写 `old "hello"` → 不匹配 → 不显示翻译。

**发现：** `check_duplicate_translations.py` 在扫描中会遍历所有 `old` 字符串，可用 grep 辅助对比。

**修复：** 确保 `old` 字符串与原文**逐字符一致**。建议：
1. 用 `generate_translations` 生成翻译模板，不要手写 `old` 字符串
2. 或用脚本从源文件中提取精确原文

---

### 2.3 `Character("name")` 和 `translate strings` 不匹配

**现象：** 名字框翻译了但在某些场景还是原文。

**原因：**
- Ren'Py Character 的 `name` 参数支持多种格式：字符串、变量、返回字符串的函数
- `Character("Hina")` → 字面量字符串 → `translate strings` 可捕获
- `Character(h_name)` → 变量 → 不走 `translate strings`，需要在变量定义处做翻译

**发现：** `check_auto_trans.py` 或 `sync_namebox_translation.py` 扫描。

**修复：** 对变量形式的名字，在变量赋值时使用 `__()`：
```rpy
define h_name = __("Hina")
define h = Character(h_name)
```

---

### 2.4 `screen` 中文已自动翻译但被 `_()` 包裹

**现象：** 某个按钮文本翻译错误：显示 `_("Play")` 的字面量而不是 "Play" 的中文。

**原因：** screen 中的纯文本会自动进入翻译系统，不需要 `_()` 包裹。如果加了 `_()`，在某些 Ren'Py 版本中会变成双重处理，极端情况下导致显示异常。
```rpy
# 正确——Ren'Py 会自动捕获
textbutton "Play":
    action Start()

# 多余——画蛇添足，可能产生副作用
textbutton _("Play"):
    action Start()
```

**发现：** `check_ui_text.py` 会报 `INFO` 级别的提示（`is_pure_literal()` 检测）。

**修复：** 移除 screen 中纯文本上的 `_()`。

---

## 3. 运行时崩溃

### 3.1 `int()`/`float()` 转换 None

**现象：** 修改存档/进入某场景时崩溃，`TypeError: int() argument must be a string... not NoneType`

**原因：** Ren'Py 动态语言特性导致有些变量在运行时为 `None`，`int(None)` 会崩溃。翻译过程中通常不直接导致此问题，但翻译带来的代码修改可能引入新变量赋值，间接导致。

```rpy
# 潜在崩盘
$ score = int(flag_hina_h)  # 若 flag_hina_h 未初始化或为 None → 崩溃
```

**发现：** `check_crash_risks.py` 中的 `unsafe_intconv` 检测。

**修复：**
```rpy
# 安全写法
$ score = int(flag_hina_h or 0)
```

---

### 3.2 `map()` 等迭代器一次性消费

**现象：** 某段 Python 逻辑在 Ren'Py 8（Python 3）上崩溃，Ren'Py 7（Python 2）却正常。

**原因：** Python 3 中 `map()`、`filter()`、`zip()` 现在返回**迭代器**（不是列表）。遍历一次后就"空"了。

```python
# Python 2 没问题，Python 3 出 bug
a, b, c = map(str, [1, 2, 3])
# 此后如果再 list(map_result) → 空列表
```

**源码依据：** `renpy/lint.py` 的兼容性检查中有类似检测。

**发现：** `check_crash_risks.py` — `map_misuse` 检测。

**修复：** 显式转换为列表：
```python
result = list(map(str, data))
```

---

### 3.3 `_()` 遮蔽后任意处崩溃

参见 [1.3 `_` 被遮蔽](#13-_-函数被遮蔽) ⬆️

**说明：** 这其实是 **最危险的崩溃类型之一**，因为一旦 `_` 被覆盖为非函数值，游戏会在任何一个调用了 `_()` 执行翻译的地方崩掉。

---

## 4. 翻译后 UI 错乱

### 4.1 `{tag}` 在翻译中被破坏

**现象：** 翻译后某句对话显示为纯文本，字体、颜色等样式丢失。或显示出类似 `{b}` 的标签原文。

**原因：** Ren'Py 文本标签 `{b}`、`{i}`、`{color=#fff}`、`{size=+5}` 等被翻译者不小心修改或删除。

```
原文: "Are you {b}sure{/b}?"
翻译: "你{b}确定{/b}吗？"    ✅ 正确
翻译: "你确定？"             ❌ 标签丢失
翻译: "你{b确定{/b}吗？"    ❌ 标签格式错误（多了一个 {）
```

**发现：** `check_translation_integrity.py` 检查标签完整性。

**修复：**
- 翻译前先扫描原文中所有 `{...}` 标签
- 翻译时保持标签原样
- 翻译后运行 `check_translation_integrity.py` 验证

---

### 4.2 `\n` 换行符不一致

**现象：** 翻译后对话或选择项排版错乱，重叠或间距异常。

**原因：** 原文中的 `\n` 换行符在翻译后被移动、增加或删除。中文句子通常比英文短，译者可能无意中减少或增加换行，导致 UI 布局变化。

**发现：** `check_translation_integrity.py` 扫描 `\n` 出现次数。

**修复：** `old` 和 `new` 中的 `\n` 数量保持一致。如果确实需要调整排版，在 `new` 中增加 `\n` 但确保不会破坏行间距。

---

### 4.3 `[[` 转义字符被破坏

**现象：** 某段文本中出现 `[` 字符，但 Ren'Py 试图将其解释为变量插值，出警告或空白。

**原因：** Ren'Py 中用 `[[` 显示字面量方括号 `[`。翻译中容易被误改为 `[`。

```
原文: "Press [[ESC] to continue"
被误译为: "按 [ESC] 继续"
   → Ren'Py 认为变量 ESC 插值 → 显示空
正确翻译: "按 [[ESC] 继续"
```

**发现：** `check_translation_integrity.py`。

**修复：** 保持 `[[` 不变。使用 `\` 转义或保留原文格式。

---

### 4.4 翻译后字符串超长/超短

**现象：** 翻译后文本框显示不全或有大片空白。

**原因：** 中英文长度差异。英文 `"Do you want to save your progress?"`（35字符）中文 `"要保存进度吗？"`（7字符）差异很大。Ren'Py 的文本框在旧版中依赖固定宽度。

**发现：** `lint_check.py` 的 E011 检测（ratio < 0.3 或 ratio > 3.5）。

**修复：** 对极端长度差异的翻译添加 `\n` 或调整文本框布局。可在 `gui.rpy` 中设置文本框可自适应。

---

## 5. 角色/名字问题

### 5.1 Character name 翻译不生效

**现象：** Character 的 `"Hina"` 在 `translate strings` 中已有翻译，但游戏不生效。

**可能原因：**

| 原因 | 特征 | 修复 |
|------|------|------|
| Character 定义了 `what_prefix`/`what_suffix`/`who_prefix`/`who_suffix` | 角色名带前后缀 → 与翻译不匹配 | `sync_namebox_translation.py` 可检测 |
| Character name 是变量 | 不经过 `translate strings` → 需要在变量定义处翻译 | 改用 `__()` |
| `translate strings` 中 `old` 字符不匹配 | 多空格/大小写差异 | 重新 `generate_translations` 精确提取 |
| 名字框在 screen 中用了独立 text 而不是 Character | 纯 `text "Hina"` 走 screen 翻译系统 | 看是哪个系统捕获，统一方法 |

**发现：** `sync_namebox_translation.py` 扫描 Character 定义 + 翻译文件对比。

---

### 5.2 角色名 v.s. 纯叙述中称呼不一致

**现象：** 对话中的 "Hina" 翻译为 "雏"，但叙述中的 "Hina" 没有被翻译或在不同文件中有不同译名。

**原因：**
- 角色名在 `translate strings` 块中只翻译了 Character `name` 相关的 old 字符串
- 同一人名在其他位置作为普通文本出现时，需要单独的翻译
- 不同译者或不同时间翻译了同一人名的不同版本

**发现：** `unify_name_translations.py` 跨文件匹配。

**修复：** 统一翻译术语表，用工具批量扫描修正。

---

### 5.3 `___()` 前缀/后缀的隐藏坑

**现象：** Character 定义正确，但名前/后缀显示异常。

**原因：** `Character("Hina", who_prefix="[", who_suffix="]")` — 这时候名字框显示 `[Hina]`。翻译文件中的 `old` 字符串必须是**包含前缀/后缀的完整文本**。

**源码依据：** `renpy/character.py` 中 Character 的 `prefix_suffix` 参数将 `who` 替换为 `who_prefix + name + who_suffix`。翻译系统看到的是最终的完整文本。

**发现：** 需手动查看 Character 定义参数。

**修复：** 翻译时注意 `old` 字符串是否包含前缀后缀。

---

## 6. 漏翻

### 6.1 Python 块中的文本被忽略

**现象：** `init python:` 中的 `renpy.say()` 文本在 `generate_translations` 中没有被提取。

**原因：** Ren'Py 的翻译提取器默认只扫描 RPY 标签体（对话、menu 选择项、screen 文本），**不扫描 Python 块**中的字符串字面量。`init python:` 中的 `renpy.say()` 调用参数不会被自动捕获。

**发现：** `patch_renpy_say.py` 专门处理此问题。

**修复：**
```rpy
# 方案一：用 __() 包裹
$ renpy.say("", __("Your affection with Hina has increased."))

# 方案二：在 Python 块外用对话形式写
# 某个 label 下：
#  "Your affection with Hina has increased."
```

---

### 6.2 `renpy.input()`/`renpy.notify()` 中的文本

**现象：** `renpy.notify("Text")` 的提示一直显示英文。

**原因：** 同上，Python 函数调用参数不进自动扫描。

**发现：** `check_func_text.py`。

**修复：** 手动添加 `_()`：
```rpy
$ renpy.notify(_("Achievement unlocked!"))
```

---

### 6.3 screen 中属性值文本

**现象：** `textbutton "Play"` 翻译了，但 `tooltip "Click to start"` 没翻译。

**原因：** 
- `text "Play"` 中的纯文本 → Ren'Py 自动捕获 ✅
- `tooltip "Click"` 作为属性值 → 可能被自动捕获也可能不，取决于 Ren'Py 版本和具体属性
- `textbutton "Play":` 的标签文本 → 自动捕获 ✅

**最佳实践：** 对所有人工可见的屏幕文本统一加 `_()` 是安全的，但需要对 Ren'Py 自动捕获机制有了解以避免双重翻译。

**发现：** `check_button_missing_translation.py`。

---

### 6.4 对话框边角料文本

**现象：** 一些边角文字始终是英文：
- "History" / "Save" / "Load" / "Preferences" / "Skip" / "Auto"
- "Page X of Y"
- "Are you sure you want to quit?"
- "Save slot X (empty)"
- 游戏主菜单 "Start" / "Continue" / "Load"

**原因：** 这些文本通常在 Ren'Py 默认的 GUI 系统文件中定义（`game/screens.rpy`、`game/options.rpy`），而译者有时只翻译了游戏自身的脚本，没碰 GUI 文件。

**发现：** 手动检查以下文件中的字面量：
- `game/screens.rpy` — 主菜单、游戏内菜单
- `game/options.rpy` — 窗口标题等
- `game/gui.rpy` — 通用 UI 参数
- Ren'Py 自带 `game/tl/` 中有默认翻译模板，复制需要的部分到你的翻译目录

**修复：** 从 `template.txt` 或 `generate_translations` 生成的模板中复制这些文本的翻译。

---

### 6.5 NVL 模式翻页提示

**现象：** NVL（小说模式）游戏，"... more" 翻页提示始终是英文。

**原因：** NVL 翻页提示字符串在 Ren'Py 内部模块中定义（`renpy/nvl_mode.py`），不走常规翻译路径。

**发现：** 需要手动添加翻译字符串。

**修复：** 在翻译文件中添加：
```rpy
translate schinese strings:
    old "page"
    new "翻页"
```

---

## 7. 译名不统一

### 7.1 同一人名在不同文件中有不同翻译

**现象：** 角色 "Hina" 在对话中是 "雏"，在菜单/屏幕中是 "希娜"，在英文剧情中是 "Hina"。

**原因：**
- 多人协作翻译，缺少统一术语表
- 新译者不知道已有译名
- 同一英文名对应不同角色或同一角色在不同语境下使用了不同原文写法
- 名字在 `translate strings` 中被翻译了一次，在 `translate dialogue` / `translate python` 中又被翻译了一次 → Ren'Py 选择哪个取决于匹配优先级

**发现：** `unify_name_translations.py` 跨文件分析。

**修复：** 建立统一术语表（`glossary.json`），运行 `unify_name_translations.py` 批量统一。

---

### 7.2 角色名变体未被识别

**现象：** "Hina"、"hina"、"Hina-chan"、"Hina-さん" 这些变体没有被统一。

**原因：** Ren'Py 的翻译是完全字符串匹配的，这些变体是不同的字符串，需要分别翻译。工具基于编辑距离或公共前缀来自动检测变体关系。

**发现：** `unify_name_translations.py` 的 v5/v6 变体发现逻辑。

**修复：** 在术语表中列出所有变体，或用工具自动发现后人工审核。

---

## 8. 分析/生成工具相关

### 8.1 `generate_translations` 生成的模板太多/太少

**现象：** 运行 `generate_translations` 后，生成的翻译文件中没有包含某些已翻译的文本。

**原因：**
- `generate_translations` 只扫描 `.rpy` 文件中的**可提取**文本。Python 块中文本、外部文件中的内容不包含
- 生成的翻译模板**覆盖**而不是合并翻译目录 → 如果你已有翻译，generation 会重新生成新模板，覆盖已有内容

**发现：** `lint_check.py --skip-sdk-lint` 进行翻译专项检查可发现差异。

**修复：** 
1. 运行 `generate_translations` 前备份已有翻译
2. 用 `merge` 功能合并新旧翻译
3. 对 Python 块中的文本用 `__()` 手动包裹，重新生成

---

### 8.2 `config.developer = True` 下的黄色下划线

**现象：** 翻译后文本下方出现黄色波浪下划线。

**原因：** `config.developer = True` 时，Ren'Py 对**已翻译**的文本加黄色下划线标记，表示 "这条文本有翻译，但翻译内容是否准确需要开发者确认"。这是开发辅助标记，**不是错误**。

**注意：** 
- **有黄色下划线 = 翻译已生效**，不是漏翻
- 无下划线 = 未找到翻译，显示原文
- 此功能仅在开发模式下生效，发布版本中不会显示

**发现：** 很多译者误以为黄色下划线 = 翻译出问题。

---

### 8.3 `TranslateString` v.s. `TranslateBlock`

**现象：** 偶尔遇到翻译格式混乱，不理解 `translate strings:` 和 `translate schinese:` 的区别。

**源码依据：** `renpy/ast.py`：

| 类型 | 语法 | 用途 |
|------|------|------|
| `TranslateString` | `translate schinese strings:` | 替换具体的字符串字面量，适用于角色名、按钮文本等独立字符串 |
| `TranslateBlock` | `translate schinese:` | 替换整段对话/屏幕，适用于完整语句替换 |

**核心区别：**
- **TranslateString**：精确匹配 `old` → 替换为 `new`
- **TranslateBlock**：替换整个标签/屏幕的内容

**错误示例：** 用 `translate strings` 写一段完整的对话 → 翻译不会生效，因为对话走的是 `TranslateBlock` 路径。

**修复：** 
- 单字符串 → `translate <lang> strings:`
- 完整语句/标签 → `translate <lang>:`

---

## 9. 跨平台问题

### 9.1 浮点数精度差异

**现象：** 安卓版游戏崩溃，PC 版正常。或者某个计算在 PC 上结果正常，安卓上结果不对。

**原因：**
- Android 平台使用 ARM 处理器，浮点运算精度与 x86 不同
- 特别是在触发条件的判定中：`if score >= 10.0` 在 ARM 上可能因为精度差异不满足条件
- Ren'Py 中动画过渡的时间计算也可能受此影响

**发现：** 无法静态检测，需要在目标平台测试。

**修复：** 使用整数运算代替浮点，或放宽精度判断条件：
```rpy
# 脆弱
if score >= 10.0:
# 健壮
if score >= 999:  # 用整数表示（乘以 100 或 1000）
```

---

### 9.2 字体文件缺失

**现象：** 中文显示为方框（□□□）或乱码。

**原因：**
- Ren'Py 默认不包含中文字体
- 即使游戏本身使用了英文字体，中文字符在该字体中不存在字型
- 部分版本 Ren'Py 在手机上字体内置处理与 PC 不同

**修复：**
```rpy
# 在 gui.rpy 中设置中文字体
define gui.text_font = "fonts/NotoSansSC-Regular.otf"
define gui.name_text_font = "fonts/NotoSansSC-Bold.otf"
define gui.interface_text_font = "fonts/NotoSansSC-Regular.otf"
```
- 将中文字体文件放入 `game/fonts/` 目录
- 推荐使用思源黑体 (Noto Sans SC) 或 思源宋体 (Noto Serif SC) — 开源可商用

---

### 9.3 文件编码

**现象：** 翻译文件中的中文显示为乱码，或 Ren'Py 加载翻译时报错。

**原因：**
- Ren'Py 期望 `.rpy` 文件是 UTF-8 编码（无 BOM）
- Windows 下的编辑器可能默认保存为 GBK 或带 BOM 的 UTF-8
- GitHub 上合并 PR 时混合了不同编码的文件

**发现：** 打开文件检查编码，或用工具检测。

**修复：**
1. 将所有翻译文件统一为 UTF-8 without BOM
2. 在编辑器中将默认编码设置为 UTF-8

---

## 10. 疑难杂症排查流程

当某个文本不显示翻译时，按以下链路排查：

```
文本不显示中文
│
├─ 检查翻译目录结构
│  └─ game/tl/schinese/ 存在否？ → 不存在 → 创建
│
├─ 检查 config.language
│  └─ 设置为 "schinese"？ → 否 → 设置
│
├─ 文本来源是什么？
│  ├─ 对话/选项 → 走 TranslateBlock
│  │  └─ 找到对应 translate schinese: 块了吗？
│  │     ├─ 有 → 检查块内内容与原文是否匹配
│  │     └─ 无 → 生成模板或手动添加
│  │
│  ├─ UI 文本/名字框 → 走 TranslateString
│  │  └─ 找到对应 old/new 了吗？
│  │     ├─ 有 → 检查 old 是否与原文精确匹配（大小写/标点）
│  │     └─ 无 → 添加 translate strings 块
│  │
│  └─ 动态文本（Python 块中） → 需要 _() 包裹
│     └─ 加了 _() 吗？
│        ├─ 有 → 检查 _ 是否被遮蔽（⚠️ 常见！）
│        └─ 未 → 加 _() 或 __()
│
├─ 是变量插值 [name]？
│  └─ 加了 !t 吗？ → 否 → 加 !t
│
├─ 是在 screen 中的纯文本 text "Play"？
│  └─ 此情况 Ren'Py 自动处理，检查翻译块即可
│
└─ 以上都检查了？
   └─ 开 config.developer = True，看文本是否有黄色下划线
      ├─ 有黄色下划线 → 翻译已生效，下划线是开发标记
      └─ 无下划线 → 翻译匹配失败，逐级回溯
```

---

## 附录：工具速查

| 问题 | 命令 | 工具 |
|------|------|------|
| `_` 被遮蔽/崩溃风险 | `python check_crash_risks.py <目录>` | 错误检测 |
| UI 文本漏翻 | `python renpy-tools-cli.py ui <项目>` | CLI 入口 |
| 翻译函数误用 (缺 !t 等) | `python renpy-tools-cli.py misuse <项目>` | CLI 入口 |
| Python 函数文本漏翻 | `python renpy-tools-cli.py func <项目>` | CLI 入口 |
| 交叉引用自动翻译 | `python renpy-tools-cli.py auto <项目>` | CLI 入口 |
| 翻译完整性（标签/变量/换行） | `python check_translation_integrity.py <项目> -l schinese` | 翻译相关 |
| 未翻译检测 | `python check_untranslated.py <项目> -l schinese --csv` | 翻译相关 |
| 角色名同步 | `python sync_namebox_translation.py --project <项目>` | 翻译相关 |
| 名字统一 | `python unify_name_translations.py` | 统一名称 |
| 硬编码英文修补 | `python patch_renpy_say.py --project <项目> --replacements 补丁集/renpy_say_replacements.csv` | 翻译相关 |
| SDK lint + 翻译专项 | `python lint_check.py <项目> --sdk <SDK路径>` | 错误检测 |
| 按钮文本遗漏 | `python check_button_missing_translation.py <项目>` | 错误检测 |
| 重复翻译 | `python check_duplicate_translations.py <项目>` | 错误检测 |
| .rpy 格式检查 | `python lint_rpy.py <翻译目录>` | 错误检测 |

---

> 版本：2026-07-27
> 基于 Ren'Py 8.5.3 源码分析。
> 对应工具集位于 `tools/` 目录，MIT 许可。
