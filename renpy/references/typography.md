# Ren'Py 字体大小与排版实战手册

> 只收"模型容易闭眼写错"的字号/行距/说框宽度结论。基础写法（style size N）模型直接写即可，不收模板。
> 字体文件/语言联动 → [advanced_tools.md](advanced_tools.md) 一节；字体接入自测 → [check_fonts.py](../scripts/checks/check_fonts.py)

---

## 一、中文字号推荐表（1920×1080 基准）

中文同号比拉丁字小一圈，英文默认 22 对应中文建议 24+。以下数值是"可直接落盘"的参考，不是硬性规定：

| 场景 | 推荐字号 | 最小不低于 | 备注 |
|------|---------|-----------|------|
| 对白正文 `gui.text_size` | 24–32 | 20 | 说框宽度足够时可取 28–32；老年友好建议 30+ |
| 角色名字 `gui.name_text_size` | 20–26 | 18 | 略小于正文，通常加粗或换色区分 |
| 选项按钮 `gui.choice_button_text_size` | 20–24 | 18 | 点击区域足够大时可取 20 |
| UI 按钮 `gui.button_text_size` | 20–24 | 18 | 偏好/存档/画廊菜单 |
| 标题/画廊标题 | 32–48 | 28 | 建议走 ATL 或 image-based，不依赖 style size |
| 提示/说明/注脚 | 18–22 | 16 | 不宜低于 16，否则小屏/投影难读 |
| 历史回放 `gui.history_text_size` | 20–24 | 18 | 长文本建议同步加大行距 |

**关键结论**：字号各处独立，**不联动**。用户说"字太小"时，先确认是哪一处（对白？名字？选项？UI？），不要全局盲目加大。

---

## 二、分辨率适配与字号缩放

Ren'Py 的 `size` 是固定像素，**不会随窗口/分辨率自动等比缩放**。720p / 1080p / 1440p / 4K 下同一字号视觉差异大。

推荐在 `gui.rpy`（或 `options.rpy`）里按 `config.screen_width` 分档定义：

```renpy
## 字号分档（按基准分辨率自动选档）
if config.screen_width <= 1280:      # 720p 及以下
    define gui.text_size        = 22
    define gui.name_text_size   = 18
    define gui.choice_button_text_size = 20
    define gui.button_text_size = 20
    define gui.history_text_size = 20
elif config.screen_width <= 1920:    # 1080p（默认）
    define gui.text_size        = 28
    define gui.name_text_size   = 22
    define gui.choice_button_text_size = 22
    define gui.button_text_size = 22
    define gui.history_text_size = 22
else:                                 # 1440p / 4K
    define gui.text_size        = 34
    define gui.name_text_size   = 28
    define gui.choice_button_text_size = 26
    define gui.button_text_size = 26
    define gui.history_text_size = 26
```

> 不要在 `default` 里定义字号——字号是界面常量，不该随存档改变；`default` 变量修改初始值也不影响已有存档，会导致新旧存档字号不一致。

---

## 三、行间距 `line_spacing` 与字号配比

中文密度高，笔画多，行距太小会粘连，太大会挤掉说框最后一行。

| 字号 | 推荐行间距 | 配比 |
|------|-----------|------|
| 20–24 | 3–5 | 约 15%–20% |
| 28–32 | 4–6 | 约 15%–20% |
| 34+   | 6–10 | 约 15%–25% |

```renpy
style say_dialogue:
    size gui.text_size
    line_spacing 5          # 字号 28 的常用值
```

**快速判断**：说框内每行建议不超过 30–38 个中文字符。字号增大但说框宽度不变，每行可容纳字符数会下降，容易撑破边框或产生奇怪断行——此时应同步加宽说框或减小字号。

---

## 四、粗斜体：不要依赖引擎合成，准备独立字体文件

Ren'Py 没有粗体/斜体字体文件时会在渲染期合成伪粗斜，中文合成效果通常很差（笔画变形、模糊、粘连）。

推荐为 CJK 字体准备四套文件，通过 `font_replacement_map` 的 `(fn, bold, italic)` 三元组分别映射：

```
game/fonts/
├── NotoSansSC-Regular.otf
├── NotoSansSC-Bold.otf
├── NotoSansSC-Italic.otf   # 真斜体，无则留空/走 Regular 回退
└── NotoSansSC-BoldItalic.otf
```

对应 `advanced_tools.md` 方法 2 的三元组写法（值必须是三元组，裸字符串会在首次渲染时抛 `ValueError`，lint 查不出）：

```renpy
init python:
    config.font_replacement_map[("NotoSansSC-Regular.otf", False, False)] = ("fonts/NotoSansSC-Regular.otf", False, False)
    config.font_replacement_map[("NotoSansSC-Regular.otf", True,  False)] = ("fonts/NotoSansSC-Bold.otf", True,  False)
    config.font_replacement_map[("NotoSansSC-Regular.otf", False, True)]  = ("fonts/NotoSansSC-Italic.otf", False, True)
```

---

## 五、多语言切换时的字号联动

中/日/韩同号下视觉大小不同（日文假名通常比同号汉字“小”）。切语言时若只换字体不换字号，部分语言会显得过小或过大。

推荐在语言切换动作里联动字号：

```renpy
screen language_picker():
    vbox:
        textbutton "简体中文":
            action [
                Language("schinese"),
                gui.SetPreference("font_size", 28),      # 需自行在 preferences 持久化 font_size
                gui.SetPreference("font", "fonts/NotoSansSC-Regular.otf")
            ]
        textbutton "English":
            action [
                Language(None),
                gui.SetPreference("font_size", 22),
                gui.SetPreference("font", None)
            ]
```

若不想持久化字号偏好，至少在 `init python` 里按语言给 `gui.text_size` 等变量重赋值（见 [advanced_tools.md](advanced_tools.md) 方法 4）。

---

## 六、outline 描边不随字号缩放

`gui.rpy` 里 `say_dialogue` 的 `outlines [(2, "#000", 0, 0)]` 是写死像素。字号放大后描边比例会失衡（看起来像"发毛"或"缩圈"），需同步调整：

| 字号 | 建议 outline 像素 |
|------|-----------------|
| 20–24 | 1–2 |
| 28–32 | 2–3 |
| 34+   | 3–4 |

```renpy
style say_dialogue:
    size 28
    outlines [(2, "#000000", 0, 0)]   # 字号 28 对应 outline 2
```

小字号（≤20）下 outline 建议关掉或取 1，否则笔画会粘成块。

---

## 七、可直接复制的 gui.rpy 片段（中文友好默认）

```renpy
## ---- 字号（1080p 基准，按实际分辨率微调）----
define gui.text_size        = 28
define gui.name_text_size   = 22
define gui.choice_button_text_size = 22
define gui.button_text_size = 22
define gui.history_text_size = 22

## ---- 行间距 ---- 
define gui.text_line_spacing = 5

## ---- 对白样式 ----
style say_dialogue:
    size gui.text_size
    line_spacing gui.text_line_spacing
    xalign 0.5
    yalign 0.5

style say_name:
    size gui.name_text_size
    xalign 0.0
    yalign 0.5

## ---- outline 不随字号缩放，需同步改 ----
style say_window:
    xpadding 40
    ypadding 20
    background Frame("gui/textbox.png", 40, 40)
```

---

## 八、快速自检清单（发行前）

- [ ] 对白字号 ≥ 20（中文），名字/选项/UI ≥ 18
- [ ] 粗斜体有独立字体文件，未依赖引擎伪合成
- [ ] `font_replacement_map` 值全是三元组 `(font, bold, italic)`，无裸字符串
- [ ] outline 像素与字号成正比（≤20 取 1，28–32 取 2–3）
- [ ] 行间距约占字号 15%–20%
- [ ] 说框每行中文字符 ≤ 38，字号大时同步加宽说框
- [ ] 不同分辨率下字号有分档（或至少在 1080p 可读）
- [ ] 切语言时字体与字号联动（避免某语言过小）

---

> 维护约定：本文件只收结论与数值，不收基础 style/screen 模板。被删条目找 `advanced_tools.md`（字体接入）/`renpy_gotchas.md`（UI 微调陷阱）/`check_fonts.py`（静态自测）。
