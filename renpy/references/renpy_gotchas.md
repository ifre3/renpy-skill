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

## UI 微调（字号/位置/文本框）

常规 style/screen 语法 AI 直接写即可，这里只收会翻车的点：

- **gui.rpy 是双层结构**：`define gui.text_size = 33` 是变量，style 块通过 `size gui.text_size` 引用它。直接改 style 里的数值，下次 launcher「更改界面/重新生成 GUI」或模板同步时会被变量值覆盖；改变量才是一等入口。重新生成会用新模板**整体重写** gui.rpy/screens.rpy，手工改动全部丢失——改别人的项目别碰这个功能
- **字号各处独立，不联动**：对话框 `gui.text_size`、名字 `gui.name_text_size`、选项 `gui.choice_button_text_size`、按钮 `gui.button_text_size`、历史 `gui.history_text_size` 各是各的；用户说"字太小"先确认是哪一处
- **outline 不随字号缩放**：`gui.rpy` 里 `gui.text_size` 提大后，say_dialogue style 的 `outlines [(2, ...)]` 仍是写死像素，描边比例会失衡，需同步改
- **中文可读字号**：CJK 同号比拉丁字小一圈，英文默认 22 对应中文建议 24+；且 DejaVuSans（gui 默认字体）没有中文字形，只调字号不改字体仍是方块——先解决字形再调字号
- **三套位置属性语义不同**：`xalign/yalign` = pos+anchor 联动（对齐语义）；`offset` 是布局后的平移，不参与 anchor/布局计算，只用来做像素级微调；把 `anchor (0.5, 1.0)` 和 `xalign 0.5` 混用会双重偏移
- **文本框位置/大小改 gui 变量**：`gui.textbox_height / textbox_width / textbox_xalign / textbox_ypos`；对话框内边距在 `style say_window`（或 say screen 里的 window）的 padding
- **改别人的发行版不需要解包**：新建 `game/zz_override.rpy`（文件名靠后保证后加载，后定义的 style 属性覆盖先前的），直接写 style override 即可生效，原 .rpyc 不用动：
  ```renpy
  style say_dialogue:
      size 30
      line_spacing 4
  style window:
      background Frame("gui/textbox.png", 40, 40)
  ```

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

- 回调有两处挂点（8.5+）：`config.after_load_callbacks`（读档后，做实际迁移）、`config.before_load_callbacks`（读档前，适合提示"正在升级存档"）
- **回滚到迁移前的旧存档会重新触发迁移代码** → 迁移逻辑必须幂等（重复执行无副作用），否则玩家一按 Ctrl 就炸
- 迁移代码不要用 `exec()` 执行字符串（注入面 + traceback 不可读）；版本比较别用字符串（`"0.10" < "0.9"` 按字典序为 True），拆成 int 元组比

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

### 改了 tl/*.rpy 游戏仍显示旧译文 → 翻译缓存
Ren'Py 启动时优先加载已编译的 `.rpyc`，部分发行版/工具链下 `.rpy` 的时间戳刷新不触发重编译（尤其 `game/` 打包成 `.rpa`、或工具只回填了 `.rpy` 时），改完译文进游戏还是英文。清两级缓存再启动：

```bash
del /s /q "game\tl\*.rpyc"
rmdir /s /q "game\cache"
```

`game/cache/` 存的是截图/字体渲染等运行缓存，删了会重新生成，无风险；`.rpyc` 删掉后引擎从 `.rpy` 重编译。与上一条呼应：删 `.rpyc` 前确认 `.rpy` 是好的——它是唯一恢复源。


### exe「打不开/一闪就没」→ 排查遗留调试钩子
游戏能加载完脚本和渲染器却随即退出、无 traceback.txt，先查 `game/` 里有没有上一轮调试留下的自动退出钩子（典型：`zz_debug.rpy` 在 `config.start_interact_callbacks` 里截图失败后调 `renpy.quit()`，其截图报错 `'Interface' object has no attribute 'surftree'` 是**次生错误**，首次 interact 时首帧还没画出来，screenshot 必然失败）。`.rpy` 和 `.rpyc` 要一起移走，否则编译版照样执行：

```bash
mv game/zz_debug.rpy game/zz_debug.rpyc ../_debug_backup/
```

判定游戏是否真崩：看 Windows 事件日志 `Get-WinEvent -FilterHashtable @{LogName='Application'; Id=1000,1001}` 有无该 exe 记录；无记录 = 进程是被外部（沙盒作业对象/父进程退出）清掉的，不是崩溃。

### 机翻弄坏 %(...)s 格式串 → ValueError 秒崩
Ren'Py 对每条 Say 文本都执行 `what % tag_quoting_dict`，所以译文里任何裸 `%`（包括机翻把 `100%都` 里的 % 当普通字符）都会在运行时崩 `ValueError: unsupported format character`。三种典型损坏：`%(player_name)啊`（丢类型字符 s）、`%(玩家名字)s`（变量名被翻译）、`100%都`（裸 % 未转义为 %%）。同类问题还有 `[text]→[文本]`（插值变量名被翻译，KeyError）和 `{#month_short}→{#{month short}`（{#…} 标签被机翻改写）。修复前先备份，别信任何自动替换——上一版替换正则漏掉 `%` 反而把 16 行全写坏，靠备份救回来的。全量扫描用：

```bash
python <skill>/scripts/sdk/tl_check.py <项目目录> --lang schinese --fix
```

`{i}{/i}` 被机翻丢弃不崩，只是丢样式，可留在报告里人工决定。

### 发行版自带 7.4.8：别用 8.x 专属 API（2026-10 SenseiOvernight 验证）
旧作自带引擎常是 7.4.8，没有 `config.label_callbacks`（8.0+ 才加的列表形式），访问直接抛 `Exception: config.label_callbacks is not a known configuration variable.` 崩在 init；7.x 只有单数 `config.label_callback`，签名同为 `(label, abnormal)`。写补丁时用兼容分支：

```renpy
try:
    config.label_callbacks.append(cb)   # 8.0+
except Exception:                       # defaultstore.__getattr__ 抛的是 Exception, 不是 AttributeError
    config.label_callback = cb          # 7.x
```

两个连带坑（同一个补丁里连着炸了三层，全是引擎版本差异）：
- **label 回调在 init 阶段就会被触发**（`gui.init()` → `call_in_new_context("_style_reset")` 执行 init label），那时 `default` 变量尚未建立，回调里裸读 store 变量 → `AttributeError: 'StoreModule' object has no attribute ...`。回调内一律 `getattr(store, "name", 默认值)` 兜底 + 整体 try。
- **`[]` 插值不支持算术表达式**：`text "[a+1]"` → `NameError: Name 'a+1' is not defined.`。先 `$ x = a + 1`，再 `text x`（直接接表达式最稳，连插值都省了）。

用游戏自带引擎就地验证，不需要装 SDK（`lib/windows-x86_64/python.exe` 就是 py2.7 解释器）：

```bash
cd <游戏根目录>
./lib/windows-x86_64/python.exe Sensei*.py . lint                        # 语法+init 阶段全跑
SDL_VIDEODRIVER=windows ./lib/windows-x86_64/python.exe Sensei*.py . test <用例名>   # 跑界面
```

`test` 必须显式指定 `SDL_VIDEODRIVER=windows`，否则 SDL 回退 dummy 驱动，报 `OpenGL support is either not configured in SDL or not available`——那是验证环境的问题，不是游戏的问题。`pause 0.5` 之间 `renpy.show_screen` / `hide_screen` 即可确认界面能否渲染，用 `renpy.quit()` 结束。

### 补丁给旧存档新增 default 变量 → 运行中 NameError（2026-10 SenseiOvernight 同日二次验证）
补丁（悬浮按钮/目录类 MOD）新增 `default` 变量后，**载入补丁加入前的旧存档**会 `NameError: name 'xxx' is not defined`：7.4.8 的 default 重放是条件赋值（`set_default` 检查存档 pickle 里的 `ever_been_changed`），且悬浮 screen 挂在 `config.overlay_screens` 里每个 interact 都求值，必炸在剧情中途。三层防御：

```renpy
# 1. 读 store 变量一律安全读取, 别裸读
def lm_get(name, default):
    return getattr(renpy.store, name, default)

# 2. after_load 回调显式补齐缺失变量
config.after_load_callbacks.append(ensure_defaults)

# 3. screen 名与 store 变量名不要同名 (screen lm_overlay + default lm_overlay 会纠缠)
```

内置值对象也会踩同一个坑：`VariableInputValue("x")` 的 `get_text()` 直接 `globals()[self.variable]`，变量缺失 → `KeyError`；渲染前 `renpy.store.__dict__.setdefault("x", "")` 兜底。`ToggleVariable` 同理不稳，自写 toggle 函数最稳。

**发行前复现手法**：testcase 里 `$ renpy.store.__dict__.pop("变量", None)` 把相关变量删光再 `renpy.show_screen(...)`，就能在测试环境重现旧存档场景，不用真的找旧存档。

