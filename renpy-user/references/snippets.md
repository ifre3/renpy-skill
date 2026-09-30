# Ren'Py 常用代码模式速查

> 按功能域归类，开发时快速参考

---

## 一、ATL 动画

### 基础变换
```renpy
# 位移动画
show eileen at Move((0.0, 1.0), (0.5, 0.5), 2.0)
# 从屏幕外移动到中央，耗时 2 秒

# 自定义 ATL 变换
transform bounce_in:
    xalign 0.5 yalign 1.5
    easein 0.5 yalign 0.5
    # easein: 先快后慢; easeout: 先慢后快; ease: 平滑; linear: 匀速
```

### 循环动画
```renpy
transform float_loop:
    yoffset 0
    ease 1.0 yoffset -20
    ease 1.0 yoffset 0
    repeat

# 使用
show eileen at float_loop
```

### 组合动画（并行 + 串行）
```renpy
transform complex_appear:
    # 并行: 同时做缩放和淡入
    parallel:
        zoom 0.5
        ease 0.8 zoom 1.0
    parallel:
        alpha 0.0
        ease 0.8 alpha 1.0

# 串行: 先做一步再做下一步
transform step_by_step:
    pause 0.5
    ease 0.3 xalign 0.3
    pause 0.2
    ease 0.3 xalign 0.7
```

### 事件驱动动画
```renpy
# 点击后触发动画
show eileen:
    xalign 0.5 yalign 0.5
    on show:
        alpha 0.0
        linear 0.5 alpha 1.0
    on click:
        linear 0.3 zoom 1.2
        linear 0.3 zoom 1.0
```

---

## 二、NVL 模式

### 启用 NVL 模式
```renpy
define narrator = nvl_narrator
define e = Character("艾丽", kind=nvl)

label start:
    nvl clear  # 清除前页
    e "这是一段 NVL 模式的对话。"
    e "NVL 模式下文本会像书页一样显示。"
    nvl clear
    "翻页继续阅读下一段..."
```

### 混合 ADV + NVL
```renpy
# 定义两种角色
define adv_e = Character("艾丽")
define nvl_e = Character("艾丽", kind=nvl)

label start:
    adv_e "这段用 ADV 模式显示。"
    nvl clear
    nvl_e "这段用 NVL 模式显示。"
```

---

## 三、气泡台词

### 基础气泡
```renpy
define e = Character("艾丽", kind=bubble)

label start:
    e "这段话会出现在气泡里！"
```

### 气泡位置控制
```renpy
define e = Character("艾丽", kind=bubble, window_background="bubble_left.png")
define y = Character("百合", kind=bubble, window_background="bubble_right.png")

# 需要在 gui.rpy 或 screens.rpy 中配置气泡样式
```

---

## 四、画廊系统

### 基础画廊
```renpy
# 定义画廊
init python:
    gallery = Gallery()
    gallery.locked_button = "gallery_locked.png"
    gallery.unlocked_button = "gallery_unlocked.png"
    gallery.background = "bg_gallery.png"
    
    gallery.button("cg1_btn")
    gallery.image("cg1_1.png")
    gallery.image("cg1_2.png")
    gallery.unlock("cg1_1")
    
    gallery.button("cg2_btn")
    gallery.image("cg2_1.png")
    gallery.image("cg2_2.png")

# 画廊界面
screen gallery_screen():
    tag menu
    add "bg_gallery.png"
    grid 2 2:
        xalign 0.5 yalign 0.5
        spacing 20
        for i in range(4):
            add gallery.make_button(f"cg{i+1}_btn", f"cg_thumb_{i+1}.png", xalign=0.5, yalign=0.5)

# 游戏中解锁
$ renpy.show("cg1_1")   # 首次显示时自动解锁
# 或手动解锁
$ gallery.unlock("cg1_1")
```

---

## 五、文本输入

### 玩家名字输入
```renpy
define pov = Character("[povname]")

label start:
    $ povname = renpy.input("请输入你的名字:", length=12)
    $ povname = povname.strip() or "无名氏"
    pov "我的名字是 [povname]。"
```

### 文本输入组件（Screen）
```renpy
screen ask_name():
    frame:
        xalign 0.5 yalign 0.5
        vbox:
            spacing 10
            text "请输入你的名字:" xalign 0.5
            input:
                id "name_input"
                length 12
            textbutton "确定":
                action Return(gui.GetInputValue("name_input"))

label start:
    call screen ask_name
    $ povname = _return.strip() or "无名氏"
    "你好，[povname]！"
```

---

## 六、拖放组件

### 简单拖放
```renpy
screen drag_example():
    draggroup:
        drag:
            drag_name "item1"
            child "icon_heart.png"
            xpos 100 ypos 200
            draggable True
        drag:
            drag_name "target"
            child "icon_target.png"
            xpos 500 ypos 300
            droppable True

# 处理拖放结果
init python:
    def drag_placed(drags, drop):
        if drop is None:
            return False
        if drags[0].drag_name == "item1" and drop.drag_name == "target":
            renpy.notify("放置成功！")
            return True
        return False
```

---

## 七、侧头像

### 对话侧头像
```renpy
define e = Character("艾丽", side_image="chara/eileen_mutter.png")

# 随情绪自动切换
define e_happy = Character("艾丽", side_image="chara/eileen_happy.png")
define e_sad = Character("艾丽", side_image="chara/eileen_sad.png")
```

---

## 八、历史对话 / Log

### 自定义历史
```renpy
screen history():
    tag menu
    predict False
    
    frame:
        xalign 0.5 yalign 0.5
        viewport:
            vbox:
                for entry in _history_list:
                    if entry.who:
                        text entry.who:
                            color gui.name_text_color
                    text entry.what
                    null height 5
        textbutton "返回":
            action Return()
            xalign 0.5
```

---

## 九、语言切换 Screen

### 基础语言选择
```renpy
screen language_picker():
    frame:
        xalign 0.5 yalign 0.5
        vbox:
            spacing 10
            text "选择语言" xalign 0.5 size 28 bold True
            textbutton "简体中文" action Language("schinese")
            textbutton "English" action Language("english")
            textbutton "日本語" action Language("japanese")
```

### 按 F2 切换中英文（开发调试用）
```renpy
init python:
    def toggle_lang():
        current = _preferences.language
        if current == "english":
            _preferences.language = "schinese"
        else:
            _preferences.language = "english"
        renpy.restart_interaction()

    config.underlay.append(
        renpy.Keymap(toggle_language=toggle_lang)
    )

define config.keymap["toggle_language"] = ["f2"]
```

---

## 十、字体回退

### 按语言动态切换字体
```renpy
init python:
    def update_font_for_lang():
        lang = _preferences.language if _preferences.language else "english"
        if lang in ("schinese", "tchinese", "japanese", "korean"):
            gui.text_font = "fonts/NotoSansSC-Regular.otf"
        else:
            gui.text_font = "fonts/SourceSansPro-Regular.ttf"
        gui.name_text_font = gui.text_font

    config.start_interact_callbacks.append(update_font_for_lang)
```

---

## 十一、提示/通知

### 顶部提示
```renpy
$ renpy.notify("获得关键道具！")

# 自定义通知样式（在 screens.rpy 中覆盖）
style notify_frame:
    background "#000000cc"
    xalign 0.5
    yalign 0.1
```

---

## 十二、计时器 / 倒计时

### 基础倒计时
```renpy
label timer_demo:
    $ timer = 10
    show screen timer_screen(timer)
    while timer > 0:
        $ timer -= 1
        $ renpy.restart_interaction()
        pause 1.0
    "时间到！"
    hide screen timer_screen

screen timer_screen(t):
    frame:
        xalign 0.5 yalign 0.0
        text "剩余 [t] 秒" size 24
```

---

## 十三、抖动 / 屏幕震动

### 画面震动效果
```renpy
transform shake:
    linear 0.05 xoffset 10
    linear 0.05 xoffset -10
    linear 0.05 xoffset 5
    linear 0.05 xoffset 0

# 使用
show screen shake_overlay
pause 0.5
hide screen shake_overlay

screen shake_overlay:
    add Solid("#000") at shake alpha 0.3
```

---

## 十四、鼠标悬停效果

```renpy
screen hover_test():
    textbutton "点我":
        action NullAction()
        hovered Show("hover_info")
        unhovered Hide("hover_info")

screen hover_info():
    frame:
        xalign 0.5 yalign 0.3
        text "鼠标悬停在这里！"
```

---

## 十五、自动滚动的 Viewport

```renpy
screen auto_scroll():
    viewport id "vp":
        draggable True
        vbox:
            for i in range(50):
                text "自动滚动文本行 [i]"
    # 通过按钮跳转到底部
    textbutton "到底部":
        action Scroll("viewport", "maximum", "vp")
```

---

> **排版约定**:
> - `#` 注释标记了"描述"
> - 每个模式包含可用代码和简短说明
> - 具体参数（坐标、颜色、路径）需要根据实际项目调整
