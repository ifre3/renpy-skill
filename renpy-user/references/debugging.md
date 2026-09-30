# Ren'Py 排错 & 调试速查

> 从内置 lint 到运行时调试，涵盖社区常见 bug 的排查思路

---

## 一、Ren'Py 内置 Lint（最强 bug 检测器）

### 用法

```bash
# 命令行（在 Ren'Py SDK 目录下执行）
renpy.sh <项目目录> lint

# Windows
renpy.exe <项目目录> lint

# 或在启动器（Launcher）中 → 选择项目 → Lint
```

### Lint 能查出什么

| 检测项 | 说明 | 示例 |
|-------|------|------|
| 未定义的标签 | `jump`/`call` 指向不存在的 `label` | `jump nonexistent_label` |
| 未使用的标签 | 定义了但没有被任何地方引用 | 噪音较多，可以忽略 |
| 图片名冲突 | 两处 `image` 定义了相同名字 | `image bg room = ...` 定义两次 |
| 图片不存在 | `image` 指向的文件找不到 | `image bg room = "images/bg.jpg"` 但文件不存在 |
| 角色定义不完整 | `define` 角色缺少 `color` 等属性 | `define e = Character("艾米")` 缺少 `what_color` 等 |
| 翻译不同步 | 翻译文件比源文件少条目 | 新增对话后忘了更新翻译 |
| 屏幕语法错误 | screen/transform 中的错误 | 属性拼错、缺少 `:` |
| 变量未初始化 | 使用了 `default` 之外的变量 | 在 label 中直接用 `$ score = 0` 而不是 `default` |
| init 优先级冲突 | 同优先级 init 块中定义相同变量 | 两个 `init python:`（都是默认 -999）修改同一变量 |
| Python 语法错误 | `$` 或 `python:` 块内的代码 | 缩进不对、漏了冒号 |
| 无效的跳转目标 | 跳转到 `define` 或 `screen` 而不是 `label` | `jump main_menu`（main_menu 是特殊 label） |

### 常见 Lint 报错解读

```
# 错误：标签未定义
"my_script.rpy:10 Could not find label 'bad_end'"
→ script.rpy 第 10 行跳转到了一个不存在的 label
→ 修复：可能拼写错，或者忘记定义了

# 警告：图片尺寸未知
"images/bg.jpg has no known resolution (1080x1920)"
→ 图片文件和游戏窗口尺寸不匹配（不是错误，但建议统一）

# 警告：未使用的标签
"Unused label 'debug_scene'"
→ 定义了但没被调用，开发期正常，发布前确认是否有用

# 错误：两处定义了相同内容
"image 'bg_room' is defined twice"
→ 两个 rpy 文件里都定义了 image bg_room，重命名一个
```

### 在 CI 中跑 Lint

```bash
# 不进入交互模式，直接输出结果并退出
renpy.exe "C:\RenPy\project" lint --quit
```

---

## 二、运行时调试（Shift+ 快捷键）

游戏运行时按以下按键（仅开发模式下可用）：

| 按键 | 功能 | 最常用场景 |
|------|------|----------|
| **Shift+D** | 开发者菜单 | **最常用** — 跳转到任意 label、修改变量、打开/关闭 screen |
| **Shift+O** | 控制台（Python 交互） | 实时查看/修改变量：`>>> persistent.xxx`、`>>> len(renpy.game.script.namemap)` |
| **Shift+R** | 重新加载脚本 | **第二常用** — 改完代码不用重启游戏，直接重载 |
| **Shift+E** | 显示最近异常的 traceback | 看完整调用栈 |
| **Shift+F** | 显示帧率（FPS） | 性能调优用 |
| **Shift+G** | 图像缓存信息 | 看当前缓存了哪些图片、占用多少 |
| **Shift+I** | 鼠标下元素信息 | 排查图片/按钮的位置、大小、变换 |
| **Shift+Y** | 变量查看器 | 全局变量列表，查看当前值 |
| **Shift+H** | 隐藏/显示所有界面 | 截屏用、检查界面层级 |
| **Ctrl+Shift+D** | 启动时进入开发者模式 | 启动阶段报错时看详细信息 |

### 开发者菜单（Shift+D）常用操作

```
开发者菜单:
├─ 交互目录         ─ 查看所有 label，点选跳转
├─ 修改变量         ─ 运行任意 Python 语句
├─ 查看持久化数据    ─ 显示所有 persistent 变量
├─ 显示属性         ─ 显示所有屏幕属性覆盖
├─ 主题化测试        ─ 切换主题
├─ 样式调试器       ─ 查看 widget style
├─ 打开/关闭屏幕     ─ 方便调试 UI
├─ 显示异常信息      ─ 显示最近错误
└─ 退出
```

---

## 三、控制台（Shift+O）常用调试语句

```python
# 修改变量
>>> score = 999
>>> charisma = 100

# 查看变量
>>> score
999

# 查看 persistent
>>> persistent.unlocked_cg
True

# 调用函数
>>> renpy.full_restart()
>>> renpy.jump("good_ending")
>>> renpy.show_screen("cheat_menu")

# 重置场景
>>> renpy.scene()

# 查看所有已注册的 image 名字
>>> sorted(renpy.game.script.namemap.keys())[:20]

# 查看当前显示的 screen
>>> renpy.get_screen("say")     # 返回 screen 对象（或 None）

# 手动触发 GC/清理缓存
>>> renpy.free_memory()

# 查看配置（只读）
>>> config.gl2
True
```

---

## 四、运行时断点调试

### 4.1 用 `renpy.pause()` 卡住

```renpy
label buggy_scene:
    show karen happy
    "这里逻辑有问题"
    $ renpy.pause()          # ← 卡在这里，去控制台查变量
    # 按任意键继续
    "继续后续..."
```

### 4.2 用 `renpy.watch()` 追踪变量变化

```renpy
# 在 init 中注册监视
init python:
    renpy.watch("charisma")
    renpy.watch("affinity")

# 以后每次 charisma 改变，控制台都会输出日志
# charisma: 0 -> 10
```

### 4.3 用 `renpy.log()` 输出日志

```renpy
# 在关键位置输出调试日志
$ renpy.log("进入事件 library，当前好感度 = [affinity]")
$ renpy.log("选择分支：读者选项 A / B / C")

# 日志保存在：
# Windows: %APPDATA%\RenPy\<游戏名>\log.txt
```

### 4.4 用 `raise` 强制触发断点

```renpy
label debug_check:
    if score > 1000:
        $ raise Exception(f"分数异常高: {score}")
```

---

## 五、常见 Bug 分类 & 排查

### 5.1 启动时崩溃 / 白屏

```
症状：启动后直接闪退 or 白屏
排查顺序：
  1. 看错误弹窗 — Ren'Py 会弹出错误对话框
  2. 打开 log.txt — %APPDATA%\RenPy\<游戏名>\log.txt
  3. 运行 lint — renpy.exe <project> lint

常见原因：
  ├─ init python 块崩溃 → Python 代码异常
  ├─ 图片文件不存在 → 路径写错了或文件没放进去
  ├─ 字体文件缺失 → fonts 目录下没放字体文件
  ├─ screen 语法错误 → 缺少闭合标签或属性名拼错
  └─ import 失败 → 引用了一个不存在的 python 模块
```

### 5.2 跳转到错误场景

```
症状：玩家选某个选项后去了完全不对的地方

排查：
  1. Shift+D → 交互目录 → 检查 label 是否存在
  2. 菜单中的跳转目标写错：menu 里的 jump/call 写错了 label 名
  3. 看看是不是 label 名大小写搞混了（Ren'Py 区分大小写）
```

### 5.3 变量不起作用 / 读档后变量值不对

```
症状：变量改了但下次读档不保持、条件永远不触发

常见原因：
  1. 用了 $ score = 0 而不是 default score = 0
     → $ 赋值在运行时生效，读档后不还原
     → 解决：用 default 定义初始值

  2. 变量在 python 函数里改的但没声明 global
     → 在函数内第一行写 global score

  3. persistent 变量跨周目没问题但同一周目读档丢失
     → 检查是不是存了两次档（自动存档覆盖了手动存档）

  4. 用 == 比较了浮点数
     → 偏好值 0.1 + 0.2 != 0.3！
     → 用 abs(a - b) < 0.001 或乘整比较
```

### 5.4 图片显示问题

```
症状：图片不显示、显示黑的、显示错图

排查顺序：
  1. Image 名字冲突 — lint 会报 "image defined twice"
  2. 文件路径错误 — 检查 game/images/ 下实际文件名
  3. 大小写问题 — "Bg_Room.png" ≠ "bg_room.png"（！）
  4. 格式不支持 — Ren'Py 支持 png/jpg/webp，不支持 bmp/gif
  5. 图片太大 — 超过 4096x4096 某些显卡不支持

最佳实践：
  ├─ 所有图片名统一小写+下划线
  ├─ 通过 image 语句定义，不要直接写在 show/scene 里
  └─ 图片放在 game/images/ 下，不要混在其他目录
```

### 5.5 界面相关问题

```
症状：button 点了没反应、布局错位、text 显示不全

排查：
  1. Shift+I 查看元素信息 — 检查 frame/button 的实际位置和大小
  2. 确认 action 是否正确 — button 的 action 是 Function 还是 Jump
  3. 检查 style_prefix — 某些样式会继承父容器的不当属性
  4. 看看是否被其他 screen 挡住了 — 用 Shift+H 隐藏所有 screen

常见陷阱：
  ├─ xalign/yalign 用混 — 0.0=左 0.5=中 1.0=右
  ├─ frame 没有设置 xsize/ysize — 内容为 0 时 frame 可能不显示
  └─ sensitive 设为 False — 按钮变灰但可能还在点击区域
```

### 5.6 翻译 / 文本问题

```
症状：部分对话没翻译、显示原文、显示乱码

排查：
  1. 运行 lint 检查翻译同步 — 会报 "untranslated string"
  2. 检查 translation 文件的格式 — 每句都要有 old 和 new
  3. 检查生成翻译的步骤：新加对话后要重新 generate translations
  4. 中文乱码：确保 rpy 文件编码是 UTF-8 without BOM

# 手动强制刷新翻译
$ renpy.reload_translation()
```

### 5.7 存档问题

```
症状：存档失败、读档崩溃、跨版本读档崩溃

常见原因：
  1. 存档里存了不能序列化的对象（lambda、screen、file handle）
     → 检查 persistent 和存档里是否存了复杂 Python 对象
  2. 代码改了但存档里是旧的对象结构
     → 用 MultiPersistent 或不兼容检测
  3. 存档文件损坏
     → 去 %APPDATA%\RenPy\<游戏名>\save\ 手动删

跨版本兼容：
  ├─ 新增变量用 default 设置默认值
  ├─ 删除变量前先检查存不存在：if hasattr(persistent, 'old_field'): del
    
  └─ 用版本号管理 persistent：
    default persistent.save_version = 1
    init python:
        if persistent.save_version < 2:
            persistent.new_field = 0
            persistent.save_version = 2
```

---

## 六、Log 文件查阅

| 日志文件 | 路径 | 用途 |
|---------|------|------|
| `log.txt` | `%APPDATA%\RenPy\<游戏名>\` | 主日志，包含 `renpy.log()` 输出 |
| `traceback.txt` | 游戏目录 `game/` | 崩溃时的调用栈 |
| `errors.txt` | 游戏目录 `game/` | 非致命错误收集 |
| `saves/` | `%APPDATA%\RenPy\<游戏名>\` | 存档文件，可删除排查问题 |

### 快速查看最新错误

```bash
# PowerShell
Get-Content "$env:APPDATA\RenPy\游戏名\traceback.txt" -Tail 50

# 查看最后 50 行
notepad "$env:APPDATA\RenPy\游戏名\log.txt"
```

---

## 七、常见报错英文 → 中文解读

| 英文报错 | 中文意思 | 常见原因 |
|---------|---------|---------|
| `IndexError: list index out of range` | 列表索引越界 | 访问了不存在的列表元素 |
| `NameError: name 'xxx' is not defined` | 变量未定义 | 拼写错误或未初始化 |
| `AttributeError: 'NoneType' object has no attribute 'xxx'` | 空对象取属性 | 某个函数返回了 None |
| `TypeError: 'int' object is not callable` | 整数被当函数调用 | 函数名和变量名冲突了 |
| `SyntaxError: invalid syntax` | 语法错误 | `:` 漏了、引号不匹配 |
| `IOError: Couldn't find file 'xxx'` | 找不到文件 | 路径写错或文件没放 |
| `KeyError: 'xxx'` | 字典键不存在 | 访问了不存在的 dict key |
| `RecursionError: maximum recursion depth exceeded` | 递归过深 | 函数无限递归或死循环 |

---

## 八、终极武器：二分法隔离

当完全搞不清是哪里的 bug 时：

```
1. 复制一份项目文件夹
2. 删掉一半的 .rpy 文件
3. 看 bug 还在不在
   ├── 还在 → bug 在剩下的另一半里
   └── 没了 → bug 在被删的那一半里
4. 缩小范围，重复 2-3 步
5. 锁定到具体文件 → 文件内删代码块继续二分
```

这是最土但最有效的方法，尤其适合逻辑复杂的老项目。

---

## 九、预防性设置

在 `options.rpy` 中启用这些，让 bug 尽早暴露：

```renpy
# 开发阶段强烈建议打开
define config.developer = True         # 启用开发者菜单
define config.debug_sound = True       # 调试声音
define config.debug_image_cache = True # 调试图像缓存
define config.image_cache_debug = True # 更详细缓存日志
define config.rollback_enabled = True  # 启用回滚（暴露序列化问题）

# 发布前关闭
# define config.developer = False
# define config.debug_sound = False
```
