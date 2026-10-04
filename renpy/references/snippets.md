# Ren'Py 陷阱速查（仅非显性技巧）

> 定位（2026-10 重构）：**只收模型容易写错、或要翻文档才能发现的点**。
> 基础模板（ATL/NVL/输入/notify/悬停/抖动/倒计时等）模型直接写即可，不再收录；
> 画廊系统 → [gallery_and_stats.md](gallery_and_stats.md)，字体与语言联动 → [advanced_tools.md](advanced_tools.md) 方法 3/4，汉化陷阱 → [renpy_gotchas.md](renpy_gotchas.md)。
> 新增条目先问一句：模型会不会闭眼写对？会 → 不收录。

---

## 一、F2 快捷键切换语言

```renpy
init python:
    def toggle_lang():
        _preferences.language = "english" if _preferences.language == "english" else "schinese"
        renpy.restart_interaction()

    config.underlay.append(renpy.Keymap(toggle_language=toggle_lang))

define config.keymap["toggle_language"] = ["f2"]
```

坑：`config.keymap` 只是注册按键名，**必须自己往 `config.underlay` 挂 Keymap** 按键才有响应；改完 `_preferences.language` 要 `restart_interaction()`，否则界面文本不刷新。

---

## 二、Viewport 一键滚到顶/底（Scroll 三参形式）

```renpy
screen auto_scroll():
    viewport id "vp":
        draggable True
        vbox:
            for i in range(50):
                text "自动滚动文本行 [i]"
    textbutton "到底部":
        action Scroll("viewport", "maximum", "vp")
```

坑：第三参是 viewport 在 screen 内的 **id**，漏配或与 id 不一致就静默不滚；第二参 `"maximum"` 滚到底、`"minimum"` 滚到顶。

---

## 三、拖放回调契约

```renpy
screen drag_example():
    draggroup:
        drag:
            drag_name "item1"          # 回调靠它识别，必填
            child "icon_heart.png"
            draggable True
        drag:
            drag_name "target"
            child "icon_target.png"
            droppable True

init python:
    def drag_placed(drags, drop):
        if drop is None:               # 没放到任何目标上
            return False
        if drags[0].drag_name == "item1" and drop.drag_name == "target":
            renpy.notify("放置成功！")
            return True                # 返回 True 才算接受本次放置
        return False
```

坑：回调签名固定 `drag_placed(drags, drop)`（drags 是列表）；不设 `drag_name` 回调里无法区分对象。

---

## 四、历史屏（history）陷阱

```renpy
screen history():
    tag menu
    predict False                       # 条目多时必须关预测，否则卡顿/爆图缓
    viewport:
        vbox:
            for entry in _history_list:
                if entry.who:           # 旁白条目 who 为 None，必须判空
                    text entry.who: color gui.name_text_color
                text entry.what
```

坑：`entry.who` 可为 `None`（旁白）；`entry.what` 已是替换后的最终文本，不要再套 `_()`；对话开始前 `_history_list` 为空，界面做空态处理。

---

## 五、气泡（bubble）前置条件

```renpy
define e = Character("艾丽", kind=bubble)
```

坑：`kind=bubble` 依赖 `screens.rpy` 里的 `screen bubble(who, what)`——**新工程模板自带，老工程/精简工程没有会直接报错**，需从官方模板 screens.rpy 补齐；左右气泡用 `window_background` + 样式区分角色。

---

## 六、侧头像随状态切换

```renpy
define e = Character("艾丽", side_image=ConditionSwitch(
    "mood == 'happy'", "chara/eileen_happy.png",
    "mood == 'sad'",   "chara/eileen_sad.png",
    "True",            "chara/eileen_normal.png"))
```

坑：静态 `side_image="路径"` 谁都会写；随情绪/状态切换用 `ConditionSwitch`，条件串里引用的是 **store 变量**。

---

> 维护约定：本文件只收陷阱，不收模板；被删类别找 `gallery_and_stats.md` / `advanced_tools.md` / `debugging.md` / `renpy_gotchas.md`。
