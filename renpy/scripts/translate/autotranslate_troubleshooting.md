# Ren'Py AI 翻译常见问题诊断与解决方案

> 生成时间: 2026-06-29 | 数据来源: AnySearch + Ren'Py 官方文档 + GitHub Issues

---

## 1. 标签闭合不合法（Text Tags Broken）

### 根因
AI 翻译时可能：
- 漏掉闭合标签（`{b}text` 少了 `{/b}`）
- 标签嵌套顺序错乱（`{b}{i}text{/b}{/i}`）
- 误改标签名（`{/b}` 变成 `{/ b}` 多了空格）

### 影响
游戏运行时报错或文本显示异常（乱码、标签原样输出）。

### 解决方案
1. **翻译前**：用 [Ren'Py Analyzer](https://github.com/Wintersta7e/renpy-analyzer) 的 `texttags` 检查模块扫描，可检测 Unclosed / mismatched / unknown text tags
2. **翻译后**：正则校验——提取所有 `{...}` 标签，检查配对
3. **脚本自动化**：写脚本提取翻译文件中的所有 `{tag}` 和 `{/tag}`，用栈检查匹配

### 参考
- Ren'Py Analyzer 的 texttags check (HIGH severity): "Unclosed / mismatched / unknown text tags, unescaped [bracket] interpolation"

---

## 2. [变量名]被修改

### 根因
Ren'Py 翻译使用标识符（identifier）匹配原文，标识符由 `label + 语句内容` 哈希生成。原文任何改动都会生成新 ID，导致旧翻译失效。

> Ren'Py docs: "Every change to the original language's dialogue strings gives that string a new identifier when compiled."

AI 翻译时若修改了原文中的 `[variable_name]` 插值变量名，也会导致不匹配。

### 解决方案
1. **规范 prompt**：翻译 prompt 中明确 `[xxx]` 为变量，必须原样保留
2. **后处理校验**：用正则检查翻译前后的 `\[.*?\]` 是否一致
3. **用 `id` 子句锁定**：开发者可在原文 say 语句后面加 `id` 固定标识符（如 `e "text" id start_abc123`），这样改原文不会生成新 ID
4. 不要改动 `[c_mc_name]`、`[day]`、`![t]` 等 Ren'Py 插值语法

### 参考
- https://github.com/renpy/renpy/issues/6918 — Unstable dialogue IDs
- Ren'Py 官方翻译文档：`id` 子句 + `hide` 标签使用

---

## 3. 未翻译（Untranslated / Missing Translations）

### 根因（多种）
| 场景 | 根因 |
|------|------|
| 剧情对话未翻译 | 翻译文件缺少对应 translate 块 |
| 系统提示未翻译 | Python `renpy.say()` 动态字符串，不会被 `generate_translations` 扫描 |
| UI 按钮未翻译 | 字符串未被 `_()` 包裹 |
| 菜单项未翻译 | 同上 |

### 解决方案
1. **对话类**：确保翻译文件完整覆盖所有源文件
2. **Python 动态文本**（如本次 LostInYou 问题）：
   - 直接修改源码 `globals.rpy` 中的英文字符串（已用 `patch_renpy_say.py` 解决）
   - 或将动态文本改为 `__()` 包裹
3. **UI/菜单**：给字符串添加 `_()` 函数，或在 `translate xxx strings:` 块中声明
4. **未定义翻译**：用 Ren'Py Analyzer 的 `translations` 检查（MED severity: "incomplete coverage, translate-folder case mismatch"）

### 参考
- Ren'Py docs: String Translations — `_()` / `__()` 函数
- Ren'Py Analyzer: translations check module

---

## 4. 名字框等未翻译（_() 未包裹）

### 根因
Ren'Py 只会扫描 `_()` 包裹的字符串生成翻译模板。如果 `Character("Eileen")` 没写成 `Character(_("Eileen"))`，名字不会出现在翻译文件中。

### 解决方案
1. 搜索所有 `Character("英文字符串")` → 改为 `Character(_("英文字符串"))`
2. 或在 `translate xxx strings:` 中手动添加：
   ```renpy
   translate schinese strings:
       old "Eileen"
       new "艾琳"
   ```
3. 重新运行 "Generate Translations" 生成新条目

### 参考
- Ren'Py docs: "When generating translations, Ren'Py will scan the script files for menus, and for strings enclosed inside the _() function."

---

## 5. 译名前后不统一

### 根因
同一个原文（如 "Tomori"）被翻译成多个不同中文名（"友利"、"灯里"、"朋里"），原因：
- AI 不同批次翻译上下文不一致
- 角色名在不同文件中被不同方式翻译
- Ren'Py 同一个字符串可能在多处重复（用 `id` 共享同一翻译块）

### 解决方案
1. **翻译前**：建立术语表（glossary），在 AI prompt 中明确角色名-译名映射
2. **翻译后**：用脚本统计所有译文中高频人名/术语，找出不一致
3. **利用 `strings` 翻译**：Ren'Py 的 string translation 对相同的 `old "string"` 只翻译一次，全局生效——缺点是有歧义（同样 "Yes" 在不同语境下可能需要不同翻译）

### 参考
- Ren'Py docs: "Be very careful when changing dialogue that has been translated, especially when that dialogue is repeated in more than one place."
- `{#...}` 标签可区分同文字不同语境：`"New{#project}"` vs `"New{#game}"`

---

## 6. 浮点计算问题（Android 计算严格）

### 根因
Ren'Py Android 端 Python 浮点运算与 Windows 端可能产生精度差异：
- GPU shader 精度：Android OpenGL ES 的 `highp`/`mediump` 精度范围与桌面端不同
- Python float 跨平台差异：Android (ARM) 的浮点运算严格度可能与 x86 不同

> GitHub Issue #6384: "Android Shader Precision Issue — range of precision is different on Android than on Windows."

### 解决方案
1. **避免在关键逻辑中用浮点数做相等判断**：
   ```python
   # 坏的
   if value == 0.1:
   # 好的
   if abs(value - 0.1) < 0.0001:
   ```
2. **Android shader 问题**：降低 shader 中高精度常数值（如 `43758.5453` 改为较小值）
3. **用 `round()` 归一化**：关键比对前 round 到一致精度
4. 确保 `options.rpy` 中声明正确的渲染精度

### 参考
- GitHub: renpy/renpy#6384 — Android Shader Precision Issue
- GitHub: renpy/renpy#6080 — 相关 precision 问题

---

## 7. 显示为原文（Translation Not Applied）

### 根因（多种）
| 场景 | 根因 |
|------|------|
| 翻译块 ID 不匹配 | 原文被修改导致 ID 变化，旧翻译块找不到对应原文 |
| 翻译文件未加载 | 语言设置不正确，或 tl 目录结构有问题 |
| `config.language` 未设置 | 游戏启动未自动切换到目标语言 |
| 硬编码英文（Python 动态文本） | 不在翻译系统范围内 |

### 解决方案
1. **检查 ID 匹配**：用 Ren'Py 开发者菜单(Shift+D) → "Show Translation Info" 查看当前语句是否有翻译
2. **更新翻译文件**：用 Launcher 的 "Generate Translations" 重新生成，比对差异
3. **设置默认语言**：`define config.language = "schinese"` 或环境变量 `RENPY_LANGUAGE=schinese`
4. **Python 动态文本**：用脚本直接替换源码（见问题 3）
5. **字体问题**：中日文需要配置 `gui.text_font` / `gui.system_font`，否则显示空白（看起来像"未翻译"）

### 参考
- Ren'Py docs: Default Language — `config.language`, `RENPY_LANGUAGE`
- Ren'Py docs: Translation Info Screen (`show screen _translation_info`)

---

## 工具清单

| 问题 | 推荐工具/方法 |
|------|--------------|
| 标签闭合 | Ren'Py Analyzer (texttags check) |
| 变量名修改 | 正则后处理校验 `\[.*?\]` |
| 未翻译 | `patch_renpy_say.py` (Python动态文本) + `_()` 包裹 |
| 名字框 | grep `Character("` → 加 `_()` |
| 译名不一 | 术语表 + 统计后校验脚本 |
| 浮点精度 | `abs(a-b) < eps` 替代 `a==b` |
| 显示原文 | Translation Info Screen + ID 比对 |
