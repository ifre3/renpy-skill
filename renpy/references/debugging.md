# Ren'Py 排错 & 调试速查

> 通用 Python 异常（IndexError/NameError/TypeError/KeyError 等）直接判读 traceback 即可，不列对照表；
> Ren'Py 特有报错与版本坑见 [renpy_gotchas.md](renpy_gotchas.md)，汉化崩溃分类见 `scripts/sdk/tl_check.py` 的三级报告。
> lint 执行走 `scripts/sdk/cli.py <项目> lint`（或 SDK `renpy.exe <项目> lint --quit`，CI 直出退出码）；
> lint 能查什么属模型常识，此处不重复。

---

## 一、运行时调试（Shift+ 快捷键）

游戏运行时按以下按键（仅开发模式下可用）：

| 按键 | 功能 | 最常用场景 |
|------|------|----------|
| **Shift+D** | 开发者菜单 | **最常用** — 跳转到任意 label、修改变量、打开/关闭 screen |
| **Shift+O** | 控制台（Python 交互） | 实时查看/修改变量：`>>> persistent.xxx` |
| **Shift+R** | 重新加载脚本 | **第二常用** — 改完代码不用重启游戏，直接重载 |
| **Shift+E** | 显示最近异常的 traceback | 看完整调用栈 |
| **Shift+F** | 显示帧率（FPS） | 性能调优用 |
| **Shift+G** | 图像缓存信息 | 看当前缓存了哪些图片、占用多少 |
| **Shift+I** | 鼠标下元素信息 | 排查图片/按钮的位置、大小、变换 |
| **Shift+Y** | 变量查看器 | 全局变量列表，查看当前值 |
| **Shift+H** | 隐藏/显示所有界面 | 截屏用、检查界面层级 |
| **Ctrl+Shift+D** | 启动时进入开发者模式 | 启动阶段报错时看详细信息 |

开发者菜单（Shift+D）最常用 3 项：交互目录（查看/点选跳转所有 label）、修变量（跑任意 Python 语句）、打开/关闭屏幕（排查 UI 层级遮挡）。

---

## 二、控制台（Shift+O）常用调试语句

```python
# 修改变量
>>> score = 999

# 查看 persistent
>>> persistent.unlocked_cg

# 调用函数
>>> renpy.jump("good_ending")
>>> renpy.show_screen("cheat_menu")
>>> renpy.full_restart()

# 查看所有已注册的 image 名字
>>> sorted(renpy.game.script.namemap.keys())[:20]

# 查看当前显示的 screen（返回 screen 对象或 None）
>>> renpy.get_screen("say")

# 手动触发 GC/清理缓存
>>> renpy.free_memory()
```

---

## 三、运行时断点与追踪

### 3.1 用 `renpy.pause()` 卡住

```renpy
label buggy_scene:
    show karen happy
    "这里逻辑有问题"
    $ renpy.pause()          # ← 卡在这里，去控制台查变量
```

### 3.2 用 `renpy.watch()` 追踪变量变化

```renpy
init python:
    renpy.watch("charisma")

# 以后每次 charisma 改变，控制台都会输出日志
# charisma: 0 -> 10
```

### 3.3 用 `renpy.log()` 输出日志

```renpy
$ renpy.log("进入事件 library，当前好感度 = [affinity]")
# 日志保存在 %APPDATA%\RenPy\<游戏名>\log.txt
```

### 3.4 用 `raise` 强制触发断点

```renpy
if score > 1000:
    $ raise Exception(f"分数异常高: {score}")
```

---

## 四、常见 Bug 分类速查

### 4.1 启动时崩溃 / 白屏

```
排查顺序：错误弹窗 → game/traceback.txt → log.txt → lint
常见原因：init python 块异常 / 图片路径错 / 字体缺失 / screen 语法错 / import 失败
```

### 4.2 变量不起作用 / 读档后值不对

1. 用了 `$ score = 0` 而不是 `default score = 0` → `$` 赋值运行时生效，读档后不还原；用 `default` 定义初始值
2. 函数里改全局变量没写 `global score`
3. 同一周目读档丢失 → 检查是否自动存档覆盖了手动存档
4. 浮点偏好值用 `==` 比较 → `0.1 + 0.2 != 0.3`，用 `abs(a - b) < 0.001`

### 4.3 图片显示问题

```
排查：image 名冲突（lint 报）→ game/images/ 实际文件名 → 大小写（"Bg_Room.png" ≠ "bg_room.png"！）
     → 格式（支持 png/jpg/webp，不支持 bmp/gif）→ 尺寸（>4096x4096 部分显卡不支持）
最佳实践：图片名统一小写+下划线；放 game/images/ 下
```

### 4.4 界面问题（按钮无反应/布局错位）

1. Shift+I 查看元素实际位置大小；Shift+H 隐藏所有 screen 排查遮挡
2. 确认 action 是 `Function` 还是 `Jump`
3. 陷阱：xalign 0.0=左 0.5=中 1.0=右；frame 无 xsize/ysize 时内容为 0 可能不显示；`sensitive False` 按钮变灰但可能仍在点击区域

### 4.5 翻译 / 文本问题

```
部分没翻译 → lint 查翻译同步；新加对话后要重新 generate translations
中文乱码 → rpy 文件编码须 UTF-8 without BOM
强制刷新翻译：$ renpy.reload_translation()
```

### 4.6 存档问题

1. 存了不能序列化的对象（lambda、screen、file handle）→ 检查 persistent 和存档内容
2. 存档文件损坏 → `%APPDATA%\RenPy\<游戏名>\save\` 手动删
3. 跨版本兼容：新增变量用 `default`；删除变量前 `hasattr` 检查；用版本号管理 persistent：

```renpy
default persistent.save_version = 1
init python:
    if persistent.save_version < 2:
        persistent.new_field = 0
        persistent.save_version = 2
```

存档迁移的完整规则（双回调挂点、幂等要求）见 [renpy_gotchas.md](renpy_gotchas.md)。

---

## 五、Log 文件查阅

| 日志文件 | 路径 | 用途 |
|---------|------|------|
| `log.txt` | `%APPDATA%\RenPy\<游戏名>\` | 主日志，包含 `renpy.log()` 输出 |
| `traceback.txt` | 游戏目录 `game/` | 崩溃时的调用栈 |
| `errors.txt` | 游戏目录 `game/` | 非致命错误收集 |
| `saves/` | `%APPDATA%\RenPy\<游戏名>\` | 存档文件，可删除排查问题 |

```powershell
Get-Content "$env:APPDATA\RenPy\游戏名\traceback.txt" -Tail 50
```

---

## 六、报错判读：唯二值得记的引擎特有行为

- `IOError: Couldn't find file 'xxx'` 一律是**资源路径/大小写**问题（Ren'Py 路径大小写敏感，`Bg_Room.png` ≠ `bg_room.png`）
- 致命错误的 traceback 除错误弹窗外，还会落在 `game/traceback.txt` 与 `game/errors.txt`，发行版玩家机器上也能拿到

---

## 七、终极武器：二分法隔离

当完全搞不清是哪里的 bug 时：

```
1. 复制一份项目文件夹
2. 删掉一半的 .rpy 文件
3. 看 bug 还在不在：还在 → bug 在剩下的另一半里；没了 → 在被删的那一半里
4. 缩小范围重复，锁定到文件后删代码块继续二分
```

最土但最有效，尤其适合逻辑复杂的老项目。

---

## 八、预防性设置（开发期，让 bug 尽早暴露）

```renpy
define config.developer = True         # 启用开发者菜单
define config.debug_sound = True       # 调试声音
define config.debug_image_cache = True # 调试图像缓存
define config.rollback_enabled = True  # 启用回滚（暴露序列化问题）
# 发布前关闭 developer/debug 开关
```

---

## 九、发布版容错配置（发行期兜底，调试期禁用）

与第八节相反的一套：开发期要**暴露**错误，发行期要**兜底**。让玩家在缺资源、缺 label、旧存档损坏时看到友好提示而不是 traceback。配置项均对 Ren'Py 8.5.3 源码校对过。

```renpy
# ── 1. 异常处理钩子：按异常类型选择性吞掉（⚠️ 会掩盖 bug，开发期严禁启用）──
init python:
    def _release_handler(*args):
        # 返回 True = 异常已处理，不再弹出错误界面
        for p in ("NameError", "KeyError", "IndexError"):
            if p in str(args[0]):
                renpy.notify("遇到小问题，已自动跳过。")
                return True
        return False
    # config.exception_handler = _release_handler   # ← 只在发行版启用

# ── 2. 存档加载失败兜底：读档崩溃时走这个 label，而不是白屏/崩溃 ──
label load_failed:
    "存档版本过旧，无法读取，已返回主菜单。"
    jump start

init python:
    config.load_failed_label = "load_failed"
    config.save_dump = True                 # 存档内容转储，便于排查存档问题
    config.after_load_transition = dissolve # 读档过渡画面

# ── 3. 缺失内容兜底：返回替代目标；返回 None = 放弃兜底（保持默认崩溃行为）──
init python:
    config.missing_label_callback = lambda name: "missing_label"    # 返回存在的 label 名
    # config.missing_image_callback = lambda name: <可显示的 Image 对象或 None>

label missing_label:
    "剧情跳转到了未完成的部分。"
    jump start
```

要点：
- `missing_label_callback` 返回的 label **必须真实存在**，否则二次崩
- `config.exception_handler` 一旦启用会掩盖真 bug，只在发布候选版开启，且返回 True 前先 `renpy.log()` 记录
- 这套与 `config.developer = True` 互斥：开发期暴露，发行期兜底
