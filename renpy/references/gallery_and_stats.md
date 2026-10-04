# 画廊 & 数值系统 & 性能预设 — 结论与陷阱

> 只收模型写不全/记不准的结论与实测经验，不含完整实现（AI 直接写 .rpy）；基础画廊写法见 snippets.md。
> 模板被砍说明：性能预设/分页画廊/养成循环属常规工程，按下方结论自行组装即可。

---

## 一、性能预设（原版/平衡/流畅）

### 1.1 核心配置对照表（记不全的部分）

| 配置项 | 原版（高画质） | 平衡 | 流畅（低配） | 生效时机 |
|--------|-------------|------|------------|--------|
| `config.gl2` | True | True | False | **重启** |
| `config.image_cache_size` | 512 | 256 | 64 | 即时 |
| `config.video_frame_limit` | 60 | 30 | 15 | 即时 |
| `config.atl_skip` | False | True | True | 即时 |
| `config.image_fps` | 30 | 15 | 8 | 即时 |
| `config.predict_statements` | 10 | 5 | 2 | 即时 |
| `config.profile_rollback` | True | False | False | 重启 |

辅助参数：`config.image_cache_debug`（调试看缓存命中，线上关）、`config.hw_video_decode`（流畅模式建议关，低端显卡兼容）、`config.allow_underfill`（关掉可减少卡顿）、`config.gl_disable_videodecoder`（流畅模式）。

### 1.2 容错模式（对别人游戏做预设/补丁时的核心层）

给 config/persistent 赋值一律包容错，模式固定：

```renpy
def _safe_set_config(name, value):
    try:
        if hasattr(config, name):
            setattr(config, name, value)
            return True
    except (AttributeError, TypeError, RuntimeError):
        pass  # 冻结/只读/旧版缺属性，静默跳过
    return False
```

持久化用 `persistent.performance_preset`，并在 `label before_main_menu:`（或 splashscreen）恢复——**不要在 `init -1` 直接 apply**，此时 store 未完全初始化。gl2 这类重启项：切换时 UI 提示"需重启生效"，下次启动由 before_main_menu 实际应用。

### 1.3 已知翻车场景（实测）

| 翻车场景 | 表现 | 处理 |
|---------|------|------|
| 游戏加密/`config` 被 `.pyd` 锁死 | 赋值抛异常 | try 包住，捕获 `RuntimeError` 静默跳过 |
| `persistent` 不可写（某些 demo） | 抛 `AttributeError` | 写前用测试键 `setattr+delattr` 探测，不可用就不存 |
| 旧版 7.x 缺 `config.atl_skip` 等 | `setattr` 抛 `AttributeError` | `hasattr` 前置检查 |
| 游戏重写了 `renpy.notify` | 通知弹不出 | try 包住，不阻塞主流程 |
| `renpy.gl2()` 不存在（极旧版） | 调用抛异常 | try 包住，回退 `config.gl2 = True` |
| init 阶段太早 | screen 操作崩 | screen 操作放 `Function`/lambda 延迟执行 |
| 多个 mod 竞争同一 config | 设置被覆盖 | 预设写入 persistent，启动恢复 |
| screen 嵌套在 `style_prefix` 里 | 按钮无样式/不显示 | screen 独立封装 + `use` 嵌入，style 隔离 |

**一句话**：最坏情况是预设不生效，绝不会让游戏闪退。UI 接入：preferences 里 `textbutton action Function(set_perf_xxx)`，选中态 `selected (current == "xxx")`。

---

## 二、画廊系统（CG Gallery）

### 2.1 核心机制（唯一必须理解的点）

`Gallery` 通过 `unlock_image()` 绑定图片名，**运行时该图片被 `renpy.show()`/`scene` 显示过一次就自动解锁**，无需手动 unlock。`g.unlock_image("cg1")` 的参数必须与 `scene cg1` 的引用名完全一致（`image cg1 = "cg/cg1.webp"` 定义名，不是文件路径）——名字对不上是最常见的"画廊永远锁着"原因。

```renpy
init python:
    g_cg = Gallery()
    g_cg.locked_button = Transform("locked_thumb", alpha=0.5)  # 未解锁缩略图
    g_cg.button("cg1")            # 按钮标识
    g_cg.unlock_image("cg1")      # 一个 button 可配多个 unlock_image（翻页 CG）
    g_cg.button("cg2")
    g_cg.unlock_image("cg2_1")
    g_cg.unlock_image("cg2_2")
```

### 2.2 CG 回放（Replay）

```renpy
g_cg.button("replay_btn")
g_cg.unlock_image("kiss_scene")   # 绑定 label 名
g_cg.replay("kiss_scene")         # 标记为可回放
# 回放目标 label 内先 $ renpy.block_rollback() 禁回退，结尾 return
# 分支 CG：$ g_cg.replay("kiss_scene", scope=dict(choice_a=True))
```

### 2.3 Music Room 要点

`MusicRoom(fadeout=1.0)`；曲目用 `g_music.add("bgm/theme.ogg")` 注册；`always_unlocked` 控制默认解锁；screen 里动作是 `g_music.Play(...)` / `.Stop()` / `.Next()` / `.Previous()`。按钮网格用 `g_cg.make_button(name, thumb)` 生成，分页时页码存 `persistent.gallery_page`，`grid 3 2` + SetVariable 翻页即可（常规工程，自行组装）。

---

## 三、数值系统

### 3.1 结论

- 默认值用 `default`（进存档），绝不用 `$` 首次赋值（存档语义坑，见 gotchas define vs default 条目）。
- 类封装数值（`class CharacterStats`）可行，但**对象进存档后类定义不能改字段名/移动位置**，否则旧存档反序列化崩——复杂养成优先用扁平 `default` 变量 + dict。
- 按字符串名动态修改变量（buff/clamp 场景）的正确姿势是 `setattr(renpy.store, name, val)` / `renpy.store.__dict__.get(name, 0)`，不要用 globals()。
- 菜单影响数值 + 过线触发事件（`if intelligence >= 10: call event_x`）属常规写法，直接写。

### 3.2 金手指 / 调试

- 开发控制台：`options.rpy` 里 `define config.console = True`，Shift+O 调出（详见 debugging.md）。
- screen 内改值动作速查（做作弊面板/调试按钮够用）：

| 动作 | 作用 |
|------|------|
| `SetVariable("name", val)` | 修改全局变量 |
| `SetField(obj, "attr", val)` | 修改对象属性 |
| `Function(func)` | 调用任意函数（解锁 CG 用 `g.unlock(btn)`） |
| `Jump("label")` / `Call("label")` | 跳转 / 调用子脚本 |
| `Show("screen")` / `ShowMenu("gallery")` | 显示界面 / 打开菜单页 |

- 解锁二周目类内容：直接 `persistent.unlocked_extra = True`（persistent 跨周目保留）。
- 存档外部编辑：`.save` 是 gzip+pickle，位置 `%APPDATA%\RenPy\<游戏名>\save\`；工具链见 player_tools.md（存档编辑），别手搓。
