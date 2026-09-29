---
name: renpy-user
description: "Ren'Py 游戏开发参考。当你需要写 Ren'Py 对话、调试中文显示、了解存档兼容性或项目结构思路时激活。不生成代码模板。"
compatibility: "renpy>=8.0"
metadata:
  openclaw:
    emoji: 📖
    permissions: ["file.read", "exec"]
    os: ["darwin", "linux", "windows"]
---

# Ren'Py User — 参考

## 这个 Skill 做什么

**不生成代码，不输出模板。** AI 直接写 `.rpy` 源代码。

- 提供 Ren'Py 的**经验性陷阱和最佳实践**（参考 `references/renpy_gotchas.md`）
- 指向本地 SDK 文档位置
- 需要工程工具链（lint/打包/诊断/测试）→ 加载 **renpy-dev** Skill

## 本地 SDK

Ren'Py SDK 路径（已安装）：`D:\workplace\renpy-8.5.3-sdk`

关键路径：

| 用途 | 路径 |
|------|------|
| SDK 可执行文件 | `D:\workplace\renpy-8.5.3-sdk\renpy.exe` |
| 官方文档 | `D:\workplace\renpy-8.5.3-sdk\doc\` |
| SDK Python 解释器 | `D:\workplace\renpy-8.5.3-sdk\lib\py3-windows-x86_64\python.exe` |

## 速查：AI 直接输出 Ren'Py

### 对话与分支

```renpy
define e = Character("艾琳", color="#c8ffc8")

label start:
    scene bg cafe
    with fade
    e happy "今天天气真好。"

    menu:
        "约她出去":
            jump date_route
        "开个玩笑":
            jump joke_route
```

### 全参数 Character（参考源码 renpy/character.py 的 ADVCharacter）

`Character()` 支持 50+ 参数。常用：

```renpy
define e = Character(
    "艾琳",
    color="#c8ffc8",
    who_color="#ffffff",        # 角色名颜色
    who_font="SourceHanSansSC-Regular.otf",
    window_background="gui/textbox.png",
    what_size=22,
    what_font="SourceHanSansSC-Regular.otf",
    what_outlines=[(1, "#000", 0, 0)],  # 文字描边
    image="eileen",              # 立绘 tag
    voice_tag="eileen",
    callback=voice_callback,     # 声音回调
    ctc="ctc_arrow",             # 点击继续指示器
    ctc_position="fixed",
    show_side_image=Image("gui/side_eileen.png", xalign=0.0, yalign=1.0),
    screen="say",                # 自定义 say screen
)
```

### ATL 动画

```renpy
transform bounce:
    easeout_back 0.5 zoom 1.1
    easein_back 0.5 zoom 1.0

transform slide_in_left:
    xalign -0.2
    easein 1.0 xalign 0.5

show eileen at bounce
show eileen at slide_in_left
```

### SL2 屏幕

```renpy
screen stats_screen():
    vbox:
        xalign 0.5 yalign 0.5
        spacing 10
        text "状态面板":
            size 28 bold True
        bar:
            value AnimatedValue(value=hp, range=max_hp)
            xmaximum 300
        textbutton "返回" action Return()
```

### LayeredImage

```renpy
layeredimage eileen:
    always "sprites/eileen/body.png"
    attribute happy:
        "sprites/eileen/happy.png"
    attribute sad:
        "sprites/eileen/sad.png"
    group outfit:
        attribute casual:
            "sprites/eileen/casual.png"
        attribute formal:
            "sprites/eileen/formal.png"
```

### 音频

```renpy
play music "bgm_day.ogg" fadein 2.0
play sound "sfx_click.ogg"
stop music fadeout 1.0
queue music ["track1.ogg", "track2.ogg"]
$ renpy.music.register_channel("sfx2", "sfx", False)
```

### 持久化

```renpy
$ persistent.unlocked_ending = True
if persistent.unlocked_ending:
    "你解锁了真结局！"

label after_load:
    if not hasattr(persistent, "unlocked_ending"):
        $ persistent.unlocked_ending = False
    return
```

## 建议：用 renpy-mcp 代替手写

如果你在实际开发 Ren'Py 项目，建议用现成的 MCP Server 而非本 Skill：

- **banjtheman/renpy_mcp_server**: 创建项目、生成对话、生成图片、构建 web 版
- **fracturedring/renpy-mcp**: 多工具 MCP 架构、Story Map GUI、自动 lint
- **youichi-uda/renpy-mcp-pro**（付费）: 故事图、运行中游戏控制

参考文件：`references/renpy_gotchas.md`
