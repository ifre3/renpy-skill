# Patterns API 参考

patterns.py 内置的 10 个预制模式，每个返回 `RenPyScript` 实例，调用 `.write("filename.rpy")` 写入文件或 `.render()` 获取字符串。

所有模式通过 `apply("模式名", {参数})` 调用。

---

## 目录

- [gallery](#gallery) - 图片画廊 + 解锁系统
- [cjk_font](#cjk_font) - 中/日/韩字体配置
- [splash](#splash) - 开场动画
- [nvl_mode](#nvl_mode) - NVL 模式适配
- [save_load](#save_load) - 存档/读档增强
- [preferences](#preferences) - 设置界面扩展
- [credit_roll](#credit_roll) - 制作人员名单滚动
- [day_night](#day_night) - 早晚切换系统
- [affection](#affection) - 好感度系统
- [choice_timer](#choice_timer) - 菜单计时器
- [after_load_migration](#after_load_migration) - 存档兼容性(版本迁移)
- [layeredimage](#layeredimage) - LayeredImage 立绘系统

---

## gallery

图片画廊 + 解锁系统。含分页翻页、解锁通知。

```python
apply("gallery", {
    "images": [
        ("unlock_bg_beach", "bg beach", "海滩"),
        ("unlock_bg_cafe",  "bg cafe",  "咖啡店"),
    ],
    "cols": 3,           # 每行列数（默认 3）
    "rows": 2,           # 每页行数（默认 2）
    "screen_name": "gallery",  # screen 名称（默认 "gallery"）
})
```

**参数说明：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `images` | list[(var, img, label)] | `[]` | 解锁变量名、图片名、显示名 |
| `cols` | int | 3 | 每行列数 |
| `rows` | int | 2 | 每页行数 |
| `screen_name` | str | "gallery" | screen 名称 |

**生成的代码包含：** 解锁函数、解锁变量、分页 screen、解锁全部 debug label。

---

## cjk_font

全局配置中/日/韩字体（需将字体文件放入 `game/` 目录）。

```python
apply("cjk_font", {
    "font": "SourceHanSansSC-Regular.otf",
    "bold": "SourceHanSansSC-Bold.otf",  # 可选
    "size": 22,
})
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `font` | str | "SourceHanSansSC-Regular.otf" | 字体文件名（需在 game/ 下） |
| `bold` | str | None | 粗体文件名 |
| `size` | int | 22 | 基础字号 |

---

## splash

开场 logo 动画（淡入 → 停留 → 淡出）。

```python
apply("splash", {
    "logo": "logo",        # logo 图片名
    "bg_color": "#000",    # 背景色
    "fade_in": 1.0,        # 淡入时间（秒）
    "hold": 2.0,           # 停留时间（秒）
    "fade_out": 1.0,       # 淡出时间（秒）
})
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `logo` | str | "logo" | 图片名（不含扩展名） |
| `bg_color` | str | "#000" | CSS 颜色 |
| `fade_in` | float | 1.0 | 淡入时间 |
| `hold` | float | 2.0 | logo 停留时间 |
| `fade_out` | float | 1.0 | 淡出时间 |

---

## nvl_mode

NVL 模式基础配置。无参数。

```python
apply("nvl_mode")
```

配置项：NVL 高度、间距、列表长度、覆盖层等。

---

## save_load

存档/读档系统增强。调整存档数量、开启自动存档。

```python
apply("save_load", {
    "slots": 12,      # 手动存档数
    "auto_slots": 6,  # 自动存档数
})
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `slots` | int | 12 | 手动存档栏位数 |
| `auto_slots` | int | 6 | 自动存档数 |

---

## preferences

设置界面扩展。可按需开关各功能模块。

```python
apply("preferences", {
    "text_speed": True,
    "afm": True,        # 自动前进
    "volume": True,
    "fullscreen": True,
})
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `text_speed` | bool | True | 文字速度滑块 |
| `afm` | bool | True | 自动前进时间 |
| `volume` | bool | True | 音量设置 |
| `fullscreen` | bool | True | 全屏开关 |

---

## credit_roll

制作人员名单滚动。

```python
apply("credit_roll", {
    "title": "Staff Roll",
    "credits": [
        ("剧本", "张三"),
        ("美术", "李四"),
        "特别感谢：所有测试玩家",  # 纯文本也支持
    ],
    "speed": 30.0,
    "bg_color": "#000",
})
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `title` | str | "Staff Roll" | 标题 |
| `credits` | list[str|tuple|dict] | `[]` | 条目列表 |
| `speed` | float | 30.0 | 滚动速度 |
| `bg_color` | str | "#000" | 背景色 |

---

## day_night

早/晚切换系统。生成 `set_time()` / `is_day()` / `is_night()` / `is_evening()` / `bg_with_time()` 等辅助函数，可选 BGM 切换。

```python
apply("day_night", {
    "transition": "dissolve",
    "bgm_day": "bgm_day.ogg",      # 可选
    "bgm_evening": "bgm_evening.ogg",
    "bgm_night": "bgm_night.ogg",
})
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `transition` | str | "dissolve" | 切换转场效果 |
| `bgm_day` | str | None | 白天 BGM 文件名（可选） |
| `bgm_evening` | str | None | 傍晚 BGM 文件名（可选） |
| `bgm_night` | str | None | 夜晚 BGM 文件名（可选） |

**用法示例：**
```renpy
$ set_time("evening")
scene expression bg_with_time("bg_street")  # → bg_street_evening
```

---

## affection

好感度系统。多角色、多等级、状态栏。

```python
apply("affection", {
    "characters": [
        {"var": "e", "name": "艾琳"},
        {"var": "l", "name": "陆辰"},
    ],
    "tiers": 5,         # 好感度等级数
    "max_points": 20,   # 每级点数
    "screen": True,     # 是否生成状态界面
})
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `characters` | list[dict] | `[]` | 角色列表，每项含 `var`（变量名）和 `name`（显示名） |
| `tiers` | int | 5 | 等级数 |
| `max_points` | int | 20 | 每级所需点数 |
| `screen` | bool | True | 是否生成 `affection_status` screen |

**用法示例：**
```renpy
$ change_affection("e", 5)  # 艾琳好感+5
if e_affection_tier >= 3:
    e "你对我真好..."
```

---

## choice_timer

菜单计时器：选项超时自动触发默认选项。

```python
apply("choice_timer", {
    "timeout": 10.0,        # 超时秒数
    "default_choice": 0,    # 默认选项索引
})
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `timeout` | float | 10.0 | 超时秒数 |
| `default_choice` | int | 0 | 超时后默认选择第几个（0-based） |


---

## after_load_migration

存档兼容性：版本升级后的数据迁移。

基于 Ren'Py 8.5.3 官方机制：
- `config.after_load_callbacks` (renpy/common/00start.rpy)
- `config.before_load_callbacks`
- `config.after_load_transition`

```python
apply("after_load_migration", {
    "version": "1.0",
    "migrations": [
        ("0.5", "gold = gold * 2"),
        ("0.8", "renpy.set_variable('inventory', [])"),
    ],
})
```

**参数说明：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `version` | str | `"1.0"` | 当前游戏版本号 |
| `migrations` | list[(str,str)] | `[]` | [(旧版本, Python 代码), ...] |

**生成的代码内容：**
- `save_version` 持久化变量记录存档版本号
- `after_load_migration()` 函数遍历迁移列表执行升级代码
- 自动注册 `config.after_load_callbacks`
- 设置 `config.after_load_transition = dissolve`

---

## layeredimage

LayeredImage 立绘系统（多图层、多属性）。

基于 Ren'Py 8.5.3 官方：
- [LayeredImage 文档](doc/layeredimage.html)
- `renpy/common/00layeredimage.rpy`

```python
apply("layeredimage", {
    "name": "eileen",
    "path": "images/sprites",
    "layers": [
        {"attribute": "表情", "dir": "facial", "default": "normal"},
        {"attribute": "服装", "dir": "outfit", "default": "casual"},
    ],
})
```

**参数说明：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `name` | str | `"sprite"` | 立绘变量名 |
| `path` | str | `"images/sprites"` | 图片基础路径 |
| `layers` | list[dict] | `[]` | 图层定义列表 |

**layers 每个元素的字段：**

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `attribute` | str | `"base"` | 属性名(图层组名) |
| `dir` | str | 同 attribute | 图片子目录名 |
| `default` | str | `""` | 默认显示的属性值 |

**使用方式：**
```renpy
show eileen 表情=happy 服装=casual
show eileen 表情=angry
```
