# Ren'Py 常见陷阱 & 最佳实践

经验性知识，不一定在官方文档或训练数据中覆盖。

---

## 图片资源

- 图片放入 `game/images/` 自动注册，无需 `image` 语句
- 命名影响 tag/attribute：`eileen happy.png` → `show eileen happy`
- 同一 tag 的 `show` 替换旧图，`scene` 清除所有图片

## 字体

- 中文字体文件通常 10-20MB，注意分销体积
- 字体缺失时 Ren'Py **静默回退**到系统默认，不报错，结果就是界面字全是方块
- 检查字体是否生效的方法：运行后看设置界面

## 缩进

- Ren'Py 的缩进**只按空格计数**（lexer 用 `lstrip(" ")`），tab 不计入缩进宽度，混用 tab/空格会报 `Indentation mismatch` 或 `SyntaxError`
- 全程统一 4 空格缩进最稳妥，`python:` 块内同理

## 变量作用域

- `define` = 全局常量（每次启动重新计算，**不改**）
- `default` = 全局变量（保存在存档中，可改）
- 修改 default 变量的初始值**不影响已有存档**（存档保留旧值）
- 删除 default 变量 → 加载旧存档报错
- `python:` 块中修改全局变量用 `store.var_name` 或 `globals()["var_name"]`

## 存档兼容

- 大版本更新时用 `after_load` label 做数据迁移：

```renpy
label after_load:
    if not hasattr(persistent, "version"):
        $ persistent.version = "1.0"
    return
```

## Screen 刷新

- screen 每秒刷新多次（约 30-60fps）
- 不要在 screen 的 Python 块里做重操作（如循环、文件IO）
- 复杂计算放到 label 中的 Python 块，screen 只读结果

## Character 全参

`Character()` 有 50+ 参数，不限于 color 和 image。可设：

```renpy
define e = Character(
    "艾琳",
    who_font="SourceHanSansSC-Regular.otf",     # 名字字体
    what_font="SourceHanSansSC-Regular.otf",     # 对话字体
    what_size=22,
    what_outlines=[(1, "#000", 0, 0)],           # 文字描边，中文可读性提升
    show_side_image=Image("gui/side_eileen.png",
                          xalign=0.0, yalign=1.0),
    ctc="ctc_arrow",                             # 点击继续指示器
    callback=renpy.python.revertable_function,   # 声音等回调
)
```

## label / jump / call

- `jump` = GOTO，不返回
- `call` = 子程序调用，`return` 回到调用点
- `show screen` 在 label 间跳转后可能需要手动 `hide screen`

## 屏幕语言 (SL2) 常见坑

- `bar` 的 `value` 必须是 `BarValue` 子类（`AnimatedValue`、`FieldValue` 等），不是整数
- `viewport` 配合 `side_` 前缀属性：`side_xscroll`, `side_yscroll`
- `imagebutton` 的 `idle`/`hover` 值必须是图片名，不是文件路径
- `style_prefix` 只影响直接子元素，不影响孙元素

## 汉化实战陷阱（2026-09 LostInYou 项目验证）

### 中文显示方块 → font_replacement_map 全局映射
游戏自带字体（手写体/漫画体/DejaVuSans）通常**不含中文字形**，切换语言后汉字渲染成方块。逐个改 `Character(who_font=...)` 覆盖不全——`{font=...}` 标签和 gui 偏好设置会绕过去。正确做法是全局替换，新建一个 `.rpy`：

```renpy
init python:
    for _f in ("badcomic.ttf", "DejaVuSans.ttf", "DejaVuSans-Bold.ttf"):
        for _b in (False, True):
            for _i in (False, True):
                config.font_replacement_map[(_f, _b, _i)] = "fonts/msyh.ttc"
```

这能同时覆盖样式、gui 偏好和文本标签里的所有字体引用。注意 `.ttc` 极少数情况下不兼容，备选 `simhei.ttf`。

### Ren'Py 8 兼容性：get_size() 返回 float
Ren'Py 8（Python 3）里 `renpy.render(...).get_size()` 返回**浮点数**，而 `random.randint()` 只收整数 → 游戏从旧版迁移时自定义 Creator Defined Displayable 常崩 `TypeError: 'float' object cannot be interpreted as an integer`。修法：render 里 `cwidth, cheight = int(cwidth), int(cheight)`。同类问题：所有旧游戏代码里把 render 尺寸直接喂给需要 int 的 API 的地方。

### 动态拼接字符串无法被静态翻译收集
`renpy.say(None, "..." + 变量 + "...")`、`renpy.notify("..." + ...)` 这类**运行时拼接**的字符串，Ren'Py 的翻译收集器扫不到，任何 tl 文件都覆盖不了。修法分两步（LostInYou 项目验证有效）：

1. 源码侧用 `_()` 包装，拼接变量改为大写占位符，运行时 replace 回来（占位符全大写避免与 `[插值]`/`{标签}` 内容冲突）：

```python
# 原来：renpy.say(None, "{i}Your affection with " + name + " has increased to " + str(v) + "...{/i}")
renpy.say(None, _("{i}Your affection with [CHARACTER] has increased to [VALUE]...{/i}")
          .replace("[CHARACTER]", name).replace("[VALUE]", str(v)))
```

2. 在 `game/tl/<lang>/` 新建或追加字符串翻译条目，`new` 里保留同样的大写占位符：

```renpy
translate schinese strings:
    old "{i}Your affection with [CHARACTER] has increased to [VALUE]...{/i}"
    new "{i}你与[CHARACTER]的好感度提升到了[VALUE]……{/i}"
```

注意 `_()` 依赖翻译已加载，放在 `init python` 里可能取不到——运行期调用（label/screen 内）没问题。

### .rpyc 是译文的恢复源
`game/tl/<lang>/*.rpy` 被误改/清空后，只要**还没跑过游戏或 lint**，对应 `.rpyc` 的 slot1 里就是上次编译的完整译文 AST（slot2 是 TranslateSay 链，不适用），可原样反序列化恢复——跑过游戏/lint 就被覆盖，窗口关闭。所以：**批量改译文前先备份**，误改后第一件事是别启动游戏。反序列化细节见 **renpy-script-decompile** 技能，不重复。

### exe「打不开/一闪就没」→ 排查遗留调试钩子
游戏能加载完脚本和渲染器却随即退出、无 traceback.txt，先查 `game/` 里有没有上一轮调试留下的自动退出钩子（典型：`zz_debug.rpy` 在 `config.start_interact_callbacks` 里截图失败后调 `renpy.quit()`，其截图报错 `'Interface' object has no attribute 'surftree'` 是**次生错误**，首次 interact 时首帧还没画出来，screenshot 必然失败）。`.rpy` 和 `.rpyc` 要一起移走，否则编译版照样执行：

```bash
mv game/zz_debug.rpy game/zz_debug.rpyc ../_debug_backup/
```

判定游戏是否真崩：看 Windows 事件日志 `Get-WinEvent -FilterHashtable @{LogName='Application'; Id=1000,1001}` 有无该 exe 记录；无记录 = 进程是被外部（沙盒作业对象/父进程退出）清掉的，不是崩溃。

### 机翻弄坏 %(...)s 格式串 → ValueError 秒崩
Ren'Py 对每条 Say 文本都执行 `what % tag_quoting_dict`，所以译文里任何裸 `%`（包括机翻把 `100%都` 里的 % 当普通字符）都会在运行时崩 `ValueError: unsupported format character`。三种典型损坏：`%(player_name)啊`（丢类型字符 s）、`%(玩家名字)s`（变量名被翻译）、`100%都`（裸 % 未转义为 %%）。同类问题还有 `[text]→[文本]`（插值变量名被翻译，KeyError）和 `{#month_short}→{#{month short}`（{#…} 标签被机翻改写）。修复前先备份，别信任何自动替换——上一版替换正则漏掉 `%` 反而把 16 行全写坏，靠备份救回来的。全量扫描用：

```bash
python <renpy-dev>/scripts/tl_check.py <项目目录> --lang schinese --fix
```

`{i}{/i}` 被机翻丢弃不崩，只是丢样式，可留在报告里人工决定。
