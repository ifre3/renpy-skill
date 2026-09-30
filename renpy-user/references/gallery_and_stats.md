# 画廊 & 数值系统 & 性能预设 实战指南

> 补充 snippets.md 中的基础画廊写法，深入实战细节；数值部分从零搭建；性能预设完整实现

---

## 零、性能预设（原版/平衡/流畅）完整实现

### 需求
提供三个性能预设按钮（原版 / 平衡 / 流畅），玩家在设置界面里一键切换。要求：

- 切换即时生效（部分设置）
- 部分需要重启生效的，存 `persistent` 下次启动自动应用
- 不影响游戏正常运行

### 0.1 核心配置对照表

| 配置项 | 原版（高画质） | 平衡 | 流畅（低配） | 生效时机 |
|--------|-------------|------|------------|--------|
| `config.gl2` | True | True | False | 重启 |
| `config.image_cache_size` | 512 | 256 | 64 | 即时 |
| `config.video_frame_limit` | 60 | 30 | 15 | 即时 |
| `config.atl_skip` | False | True | True | 即时 |
| `config.image_fps` | 30 | 15 | 8 | 即时 |
| `config.predict_statements` | 10 | 5 | 2 | 即时 |
| `config.profile_rollback` | True | False | False | 重启 |

### 0.2 完整实现代码（带多层容错）

创建 `game/performance_presets.rpy`：

```renpy
# ============================================================
# 性能预设系统 —— 带容错保护
# ============================================================

# --- 持久化当前预设（带 fallback）---
default persistent.performance_preset = "original"

# --- 安全设定函数（核心容错层）---
init python:
    import traceback

    def _safe_set_config(name, value, fallback=None):
        """
        安全设置 config 属性。
        容错场景：
        - config 属性不存在（旧版 Ren'Py）
        - config 被锁定/冻结（某些加密游戏）
        - config 是 read-only 属性
        """
        try:
            if hasattr(config, name):
                setattr(config, name, value)
                return True
            else:
                if fallback is not None:
                    # 用其他方式尝试
                    return False
                return False
        except (AttributeError, TypeError, RuntimeError):
            # config 被冻结或只读，静默跳过
            return False

    def _safe_renpy_notify(msg):
        """
        安全显示通知。某些游戏重写了 notify 或禁止修改 screen 栈。
        """
        try:
            renpy.notify(msg)
        except Exception:
            pass  # 通知不是关键功能，静默忽略

    def _is_persistent_usable():
        """检查 persistent 是否可写（部分 demo/加密游戏不支持）"""
        try:
            test_key = "_perf_test_key"
            if hasattr(persistent, test_key):
                return True
            setattr(persistent, test_key, True)
            delattr(persistent, test_key)
            return True
        except Exception:
            return False

    def apply_performance_preset(preset):
        """
        应用性能预设，带完全容错。
        preset: "original" / "balanced" / "smooth"
        
        容错清单：
        ✓ config 属性不存在
        ✓ config 被冻结/只读
        ✓ persistent 不可写（demo/加密游戏）
        ✓ 旧版 Ren'Py 缺少属性
        ✓ renpy.notify 被覆写
        ✓ screens 加载失败
        ✓ 运行时变量被其它 mod 占用
        """
        # --- 第 1 步：校验 preset 参数 ---
        valid_presets = {"original", "balanced", "smooth"}
        if preset not in valid_presets:
            preset = "original"  # 遇到非法值，回退到原版

        # --- 第 2 步：保存到 persistent（如果有）---
        if _is_persistent_usable():
            try:
                persistent.performance_preset = preset
            except Exception:
                pass  # 不能存就算了，不影响本次运行

        # --- 第 3 步：按预设设置参数（逐项容错）---
        # 每个配置独立 try，一个失败不影响其他
        
        if preset == "original":
            _safe_set_config("image_cache_size", 512, 256)
            _safe_set_config("video_frame_limit", 60, 30)
            _safe_set_config("atl_skip", False)
            _safe_set_config("image_fps", 30, 15)
            _safe_set_config("predict_statements", 10, 5)
            # GL2 启用（安全调用）
            try:
                renpy.gl2()
            except Exception:
                config.gl2 = True
                _safe_set_config("gl2", True)

        elif preset == "balanced":
            _safe_set_config("image_cache_size", 256, 128)
            _safe_set_config("video_frame_limit", 30, 24)
            _safe_set_config("atl_skip", False)
            _safe_set_config("image_fps", 15, 10)
            _safe_set_config("predict_statements", 5, 3)
            try:
                renpy.gl2()
            except Exception:
                _safe_set_config("gl2", True)

        elif preset == "smooth":
            _safe_set_config("image_cache_size", 64, 32)
            _safe_set_config("video_frame_limit", 15, 20)
            _safe_set_config("atl_skip", True)
            _safe_set_config("image_fps", 8, 10)
            _safe_set_config("predict_statements", 2, 1)
            _safe_set_config("gl2", False)
            # 额外低配优化（非必须，失败不管）
            try:
                config.gl_disable_videodecoder = True
            except Exception:
                pass
            try:
                config.allow_underfill = False
            except Exception:
                pass

        # --- 第 4 步：通知玩家 ---
        _safe_renpy_notify(get_preset_label(preset))

    def get_preset_label(preset):
        labels = {
            "original": _("性能模式：【原版】高画质"),
            "balanced": _("性能模式：【平衡】"),
            "smooth": _("性能模式：【流畅】低配优化"),
        }
        return labels.get(preset, _("已切换性能预设"))

# --- 接口：供 settings screen 调用 ---
init python:
    def set_performance_original():
        apply_performance_preset("original")

    def set_performance_balanced():
        apply_performance_preset("balanced")

    def set_performance_smooth():
        apply_performance_preset("smooth")

    def get_performance_preset():
        """返回当前预设名称（安全读取 persistent）"""
        if _is_persistent_usable():
            try:
                val = persistent.performance_preset
                if val in {"original", "balanced", "smooth"}:
                    return val
            except Exception:
                pass
        return "original"  # fallback
```

### 0.2b 极简版（不带容错，适合自己写的游戏）

如果游戏是你自己写的、不担心加密/冻结问题，直接看这个缩略版：

```renpy
default persistent.performance_preset = "original"

init python:
    def set_perf(p):
        persistent.performance_preset = p
        if p == "original":
            config.image_cache_size = 512
            config.video_frame_limit = 60
            config.image_fps = 30
            renpy.gl2()
        elif p == "balanced":
            config.image_cache_size = 256
            config.video_frame_limit = 30
            config.image_fps = 15
            renpy.gl2()
        else:  # smooth
            config.image_cache_size = 64
            config.video_frame_limit = 15
            config.image_fps = 8
            config.gl2 = False
        renpy.notify(_("已切换"))
```

### 0.3 设置界面 —— 直接嵌入已有 screens.rpy

在 `screens.rpy` 的 **preferences screen** 中找到合适位置，加几行就行：

```renpy
screen preferences():
    # ... 原有的 preferences 代码 ...
    
    # ====== 以下为新增：性能预设 ======
    vbox:
        style_prefix "radio"
        label _("性能模式")
        
        textbutton _("原版（高画质）") action Function(set_performance_original)
        textbutton _("平衡")           action Function(set_performance_balanced)
        textbutton _("流畅（低配）")   action Function(set_performance_smooth)
    
    null height 10
    # ====== 新增结束 ======
    
    # ... 原有后续代码 ...
```

带选中高亮（更专业版）：

```renpy
screen performance_preset_buttons():
    $ current = get_performance_preset()
    vbox:
        style_prefix "radio"
        label _("性能模式")
        
        textbutton _("原版（高画质）"):
            action Function(set_performance_original)
            selected (current == "original")
        
        textbutton _("平衡"):
            action Function(set_performance_balanced)
            selected (current == "balanced")
        
        textbutton _("流畅（低配）"):
            action Function(set_performance_smooth)
            selected (current == "smooth")

# 在 preferences screen 中嵌入
screen preferences():
    # ...
    use performance_preset_buttons
    # ...
```

### 0.4 启动时自动加载持久化的预设

在 `script.rpy` 最前面或创建 `game/init.rpy`：

```renpy
# 游戏启动时自动恢复上次选择的性能预设
label splashscreen:
    $ apply_performance_preset(persistent.performance_preset)
    return  # 如果不需要开场画面，这一句让 splashscreen 直接通过

# 或者用 init 方式（更早加载，适合 config.gl2 需要重启生效的变量）
init -1 python:
    # 注意：此时 renpy.store 尚未完全初始化，部分 API 不可用
    # 简单的方式：存标志位，apply 函数里判断
    pass

# 更稳妥的方案：在 splashscreen 或 early label 中设置
label before_main_menu:
    $ apply_performance_preset(persistent.performance_preset)
    return
```

### 0.5 进阶：重启提示

对于 `config.gl2` 这样需要重启的变量，在界面上标注清楚：

```renpy
screen performance_preset_buttons():
    $ current = get_performance_preset()
    vbox:
        style_prefix "radio"
        label _("性能模式")
        
        textbutton _("原版（高画质）") action Function(set_performance_original)
        textbutton _("平衡")           action Function(set_performance_balanced)
        textbutton _("流畅（低配）")   action Function(set_performance_smooth)
        
        # 如果当前预设需要重启，提示
        if current != persistent.performance_preset:
            text _("⚠ 切换渲染模式需重启游戏生效") size 14 color "#ff6"
        
    # 下次启动时，before_main_menu 会调用 apply_performance_preset
    # 把 persistent.performance_preset 实际设置进去
```

### 0.6 完整文件参考

整个系统就两个文件：

```
game/
├── performance_presets.rpy   ← 预设定义 + apply 函数
└── screens.rpy               ← preferences screen 中加几行按钮（或 use）
```

**实际新增代码**：performance_presets.rpy 约 50 行 + screens.rpy 修改约 10 行。

### 0.8 已知翻车场景 & 对应处理

| 翻车场景 | 表现 | 我们的处理 |
|---------|------|----------|
| 游戏加密/`config` 被 `.pyd` 锁死 | 直接赋值 `config.xxx = val` 抛异常 | `_safe_set_config` 用 try 包住，捕获 `RuntimeError` 静默跳过 |
| `persistent` 不存在（某些 demo） | `persistent.xxx` 抛 `AttributeError` | `_is_persistent_usable()` 检测，不可用就不存 |
| 旧版 Ren'Py（7.x 以下）`config.atl_skip` 不存在 | `setattr` 抛 `AttributeError` | `hasattr(config, name)` 前置检查，不存在就跳过 |
| 游戏重写了 `renpy.notify`（走自己 toast） | 通知弹不出来 | `_safe_renpy_notify` try 包住，不阻塞流程 |
| `renpy.gl2()` 函数不存在（极旧版） | 函数调用抛异常 | try 包住，回退到 `config.gl2 = True` |
| init 阶段太早执行（screen 还没加载） | screen 相关操作崩 | 所有 screen 操作放到 lambda/Function 里延迟执行 |
| 多个 mod 竞争 same config | 设置被覆盖 | 预设写入 `persistent`，启动时恢复，覆盖后下次重启仍恢复 |
| 设置界面嵌套在 `style_prefix` 里没对齐 | 按钮无样式甚至不显示 | screen 独立封装 + `use` 嵌入，style 隔离 |

**一句话**：最坏情况就是性能预设不生效，但**绝不会让游戏闪退或卡死**。

| 参数 | 作用 |
|------|------|
| `config.image_cache_debug` | 调试时看缓存命中，线上关掉 |
| `config.hw_video_decode` | 硬件视频解码，流畅模式下建议关（兼容某些低端显卡） |
| `config.allow_underfill` | 允许图像未预加载时显示，流畅模式关掉可减少卡顿 |
| `config.skipping` | 是否允许跳过 — 流畅模式默认打开 |
| `_preferences.afm_enable` | 自动前进模式，可以关闭减少无谓的动画 |

---

## 一、画廊系统（CG Gallery）完整实战

### 1.1 核心机制：自动解锁

**关键理解**：Ren'Py 的 `Gallery` 类通过 `unlock_image()` 绑定图片名，**运行时只要这张图片被 `renpy.show()` 显示过一次，就自动解锁**。无需手动调用 unlock。

```renpy
init python:
    g_cg = Gallery()
    g_cg.locked_button = "locked_thumb"    # 未解锁时的缩略图
    g_cg.locked_button = Transform("locked_thumb", alpha=0.5)  # 也可以用带效果的

    # 按钮标识 "cg1" → 显示 game/cg/cg1.webp 时自动解锁
    g_cg.button("cg1")
    g_cg.unlock_image("cg1")

    # 一个按钮绑定多张图（翻页式CG）
    g_cg.button("cg2")
    g_cg.unlock_image("cg2_1")
    g_cg.unlock_image("cg2_2")

# 游戏中放这段，cg1 解锁
scene cg1
"好美的画面..."

# 游戏中放这段，cg2_1 和 cg2_2 都解锁
scene cg2_1
pause 1
scene cg2_2
pause 1
```

### 1.2 图片引用方式

```renpy
# 方式 A：用 image 语句定义
image cg1 = "cg/cg1.webp"

# 方式 B：用 define 定义变量（推荐，更清晰）
define cg.kiss = "cg/kiss.webp"

# 方式 C：直接用路径字符串
g_cg.unlock_image("cg/kiss.webp")

# ⚠ 注意事项
# - unlock_image 的参数必须和 scene/show 时的引用名完全一致
# - 建议统一用 image 语句或 define 定义，不要混合
```

### 1.3 带翻页的画廊界面

```renpy
screen gallery_main():
    tag menu
    use game_menu(_("画廊"), scroll="viewport"):
        vbox:
            spacing 20
            # 第一行
            hbox:
                spacing 20
                add g_cg.make_button("cg1", "thumb_cg1", xalign=0.5, yalign=0.5)
                add g_cg.make_button("cg2", "thumb_cg2", xalign=0.5, yalign=0.5)
                add g_cg.make_button("cg3", "thumb_cg3", xalign=0.5, yalign=0.5)
                add g_cg.make_button("cg4", "thumb_cg4", xalign=0.5, yalign=0.5)
            # 第二行
            hbox:
                spacing 20
                add g_cg.make_button("cg5", "thumb_cg5", xalign=0.5, yalign=0.5)
                add g_cg.make_button("cg6", "thumb_cg6", xalign=0.5, yalign=0.5)
    textbutton _("返回"):
        action Return()
        xalign 0.95 yalign 0.95
```

### 1.4 分页画廊（CG 数量多时）

```renpy
default persistent.gallery_page = 0

init python:
    # 定义所有 CG 按钮
    cg_buttons = [
        ("cg1", "thumb_cg1"),
        ("cg2", "thumb_cg2"),
        ("cg3", "thumb_cg3"),
        ("cg4", "thumb_cg4"),
        ("cg5", "thumb_cg5"),
        ("cg6", "thumb_cg6"),
        ("cg7", "thumb_cg7"),
        ("cg8", "thumb_cg8"),
    ]

screen gallery_paged():
    tag menu
    use game_menu(_("画廊"), scroll="viewport"):
        $ per_page = 6
        $ total = len(cg_buttons)
        $ pages = (total + per_page - 1) // per_page
        $ page = persistent.gallery_page
        $ start = page * per_page
        $ end = min(start + per_page, total)

        grid 3 2:
            xalign 0.5 yalign 0.3
            spacing 30
            for i in range(start, end):
                $ btn_name, thumb = cg_buttons[i]
                add g_cg.make_button(btn_name, thumb, xalign=0.5, yalign=0.5)

        # 翻页按钮
        hbox:
            xalign 0.5 yalign 0.85
            spacing 40
            if page > 0:
                textbutton _("上一页") action SetVariable("persistent.gallery_page", page - 1)
            text _("第 [page+1]/[pages] 页")
            if page < pages - 1:
                textbutton _("下一页") action SetVariable("persistent.gallery_page", page + 1)
```

### 1.5 CG 回放（Replay）

```renpy
# 定义一个可回放的章节
label kiss_scene:
    $ renpy.block_rollback()  # 禁止回退
    scene bg_room
    show karen happy
    karen "我喜欢你..."
    return

init python:
    g_cg.button("replay_btn")
    g_cg.unlock_image("kiss_scene")  # 绑定 label 名
    g_cg.replay("kiss_scene")       # 标记为可回放

# 如果 CG 中还有分支选择，可以用:
$ g_cg.replay("kiss_scene", scope=dict(choice_a=True))
```

### 1.6 Music Room（音乐鉴赏）

```renpy
init python:
    g_music = MusicRoom(fadeout=1.0)   # fadeout=淡出秒数
    
    g_music.add("bgm/theme.ogg")      # 添加音乐
    g_music.add("bgm/sad.ogg")
    g_music.add("bgm/ending.ogg")
    g_music.always_unlocked = True     # 设置某些歌曲默认解锁
    g_music.always_unlocked = False
    
    def unlock_bgm(path):
        """在游戏中调用此函数解锁指定音乐"""
        g_music.add(path)

screen music_room():
    tag menu
    use game_menu(_("音乐鉴赏"), scroll="viewport"):
        hbox:
            xalign 0.5 yalign 0.4
            spacing 30
            textbutton _("播放") action g_music.Play("bgm/theme.ogg")
            textbutton _("停止") action g_music.Stop()
            textbutton _("下一首") action g_music.Next()
            textbutton _("上一首") action g_music.Previous()
```

---

## 二、数值系统（属性/养成/状态）

### 2.1 基础数值定义

```renpy
# 养成类游戏最简框架：三属性 + 好感度

# --- 定义默认值（用 default！不是 $ 赋值）---
default charisma = 0      # 魅力
default intelligence = 0  # 智力
default strength = 0      # 力量
default affinity = 0      # 好感度
default day = 1           # 天数

# --- 界面显示 ---
screen stats_display():
    frame:
        xalign 1.0 yalign 0.0
        xpadding 15 ypadding 10
        vbox:
            text "魅力: [charisma]" color "#f66"
            text "智力: [intelligence]" color "#6cf"
            text "力量: [strength]" color "#6f6"
            text "好感度: [affinity]" color "#f9f"
            text "第 [day] 天"

# 在游戏界面叠加显示
label start:
    show screen stats_display
    "数值系统启动！"
```

### 2.2 属性变化事件

```renpy
# 选择分支影响数值——经典模式
label event_library:
    "图书馆里，你看到..."
    
    menu:
        "认真看书":
            $ intelligence += 3
            $ charisma += 1
            "你专心读了一下午书。"
            
        "搭讪旁边的同学":
            $ charisma += 2
            $ affinity += 1
            "你鼓起勇气聊了几句。"
            
        "把书扔到一边睡觉":
            $ intelligence -= 1
            $ strength += 1
            "你一觉睡到天黑。"
    
    # 数值过线触发条件
    if intelligence >= 10:
        "你的智力达到 10，触发学霸事件！"
        call event_scholar
    
    elif affinity >= 5:
        "好感度达到 5，触发约会事件！"
        call event_date
    
    $ day += 1
```

### 2.3 用类封装数值（适合复杂项目）

```renpy
init python:
    class CharacterStats:
        def __init__(self, name):
            self.name = name
            self.hp = 100
            self.mp = 50
            self.atk = 10
            self.defense = 5
            self.exp = 0
            self.level = 1
            self.affinity = 0
        
        def take_damage(self, dmg):
            actual = max(dmg - self.defense, 0)
            self.hp -= actual
            if self.hp <= 0:
                self.hp = 0
                return "defeated"
            return "alive"
        
        def gain_exp(self, amount):
            self.exp += amount
            if self.exp >= self.level * 100:
                self.level_up()
        
        def level_up(self):
            self.level += 1
            self.exp = 0
            self.atk += 3
            self.defense += 2
            self.hp = 100 + self.level * 10
            self.mp = 50 + self.level * 5
        
        def __repr__(self):
            return f"{self.name} Lv.{self.level} HP:{self.hp}"

# 创建角色
default player = CharacterStats("勇者")
default enemy = CharacterStats("史莱姆")

# 战斗事件
label battle_test:
    while player.hp > 0 and enemy.hp > 0:
        $ enemy.take_damage(player.atk)
        "[player] 攻击 [enemy]"
        if enemy.hp <= 0:
            $ player.gain_exp(50)
            "战胜了史莱姆！获得 50 经验"
            jump battle_end
        $ player.take_damage(enemy.atk)
        "[enemy] 反击！"
    "你被击败了..."
label battle_end:
    return
```

### 2.4 限制数值范围

```renpy
# 方法一：每次修改后 clamp
$ charisma = max(0, min(100, charisma + 5))

# 方法二：定义一个安全函数（推荐）
init python:
    def mod_stat(name, delta, min_val=0, max_val=999):
        """安全修改数值，支持整数和小数"""
        cur = renpy.store.__dict__.get(name, 0)
        new_val = max(min_val, min(max_val, cur + delta))
        setattr(renpy.store, name, new_val)
        return new_val

# 使用
$ mod_stat("charisma", 3, max_val=100)
$ mod_stat("strength", -5, min_val=0)
```

### 2.5 百分比增益/减益

```renpy
init python:
    def apply_buff(stat_name, percent, duration=1):
        """百分比修改，duration 表示持续几回合"""
        cur = renpy.store.__dict__.get(stat_name, 0)
        new_val = int(cur * (1 + percent))
        setattr(renpy.store, stat_name, new_val)
        # 记录 buff
        if not renpy.store.__dict__.get("_buffs"):
            renpy.store._buffs = []
        renpy.store._buffs.append((stat_name, cur, duration))
    
    def tick_buffs():
        """每回合结束调用，移除过期 buff"""
        if hasattr(renpy.store, '_buffs'):
            remaining = []
            for stat_name, original, dur in renpy.store._buffs:
                if dur <= 1:
                    setattr(renpy.store, stat_name, original)
                else:
                    remaining.append((stat_name, original, dur - 1))
            renpy.store._buffs = remaining

# 战斗中
$ apply_buff("atk", 0.5, duration=3)  # 攻击力 +50%，持续 3 回合
```

---

## 三、调试 & 金手指（修改变量）

### 3.1 开发者控制台

```renpy
# 按 F8 调出控制台（仅在开发版有效）
$ console = True   # 启用内置控制台（options.rpy 里设置）

# 在控制台中可以直接输入 Python 语句：
# >>> persistent.charisma = 999
# >>> config.developer = True
```

### 3.2 作弊界面

```renpy
screen cheat_menu():
    modal True
    frame:
        xalign 0.5 yalign 0.5
        xpadding 30 ypadding 20
        vbox:
            spacing 10
            text "金手指" size 30 bold True
            text "魅力: [charisma]"
            textbutton "+10" action SetVariable("charisma", charisma + 10)
            textbutton "满"  action SetVariable("charisma", 999)
            text "智力: [intelligence]"
            textbutton "+10" action SetVariable("intelligence", intelligence + 10)
            textbutton "满"  action SetVariable("intelligence", 999)
            text "好感度: [affinity]"
            textbutton "+10" action SetVariable("affinity", affinity + 10)
            textbutton "满"  action SetVariable("affinity", 999)
            null height 20
            textbutton "解锁全部CG" action Function(unlock_all_cg)
            textbutton "跳转到结局" action Jump("ending")
            textbutton "销毁存档" action Function(delete_all_saves)
            null height 10
            textbutton "关闭" action Hide("cheat_menu")

init python:
    def unlock_all_cg():
        """解锁画廊中所有 CG"""
        for btn in ["cg1", "cg2", "cg3", "cg4"]:
            g_cg.unlock(btn)
        renpy.notify("已解锁全部 CG！")
    
    def delete_all_saves():
        """删除所有存档（谨慎使用）"""
        renpy.unlink_save("1")
        renpy.unlink_save("2")
        renpy.unlink_save("3")
        renpy.unlink_save("4")
        renpy.unlink_save("5")
        renpy.notify("已清除所有存档")

# 游戏中调出：按 C 键
init python:
    def check_cheat_key():
        if renpy.get_key(ord('C')):
            renpy.show_screen("cheat_menu")
```

### 3.3 修改 persistent 数据

```renpy
# persistent 是跨周目保留的数据
# 用金手指解锁二周目内容

default persistent.unlocked_extra = False

label ending:
    "故事结束了..."
    
    if persistent.unlocked_extra:
        jump extra_content
    else:
        if ending_score >= 80:
            $ persistent.unlocked_extra = True
            "解锁了额外内容！重新开始游戏体验新剧情。"
        return

# 金手指直接启用
init python:
    def unlock_extra():
        persistent.unlocked_extra = True
        renpy.notify("已解锁二周目内容！重新开始游戏即可体验。")
```

### 3.4 存档修改（外部编辑）

```powershell
# Ren'Py 存档保存在：
# Windows: %APPDATA%\RenPy\<游戏名>\save\
# 格式是 .save 文件，本质是 Python pickle

# 用 Python 脚本读取（仅供调试自己的游戏）：
# python -c "
# import pickle, gzip
# with gzip.open('savefile.save', 'rb') as f:
#     data = pickle.load(f)
# print(data.keys())
# for k, v in data.items():
#     print(k, '=', v)
# "
```

### 3.5 内置运行时修改用到的函数

| 函数 | 作用 | 示例 |
|------|------|------|
| `SetVariable("name", val)` | 修改全局变量 | `SetVariable("hp", 100)` |
| `SetField(obj, "attr", val)` | 修改对象属性 | `SetField(player, "hp", 100)` |
| `Function(func)` | 调用任意函数 | `Function(unlock_all_cg)` |
| `Jump("label")` | 跳转到指定标签 | `Jump("ending_good")` |
| `Call("label")` | 调用子脚本 | `Call("event_special")` |
| `Show("screen")` | 显示界面 | `Show("cheat_menu")` |
| `ShowMenu("gallery")` | 打开画廊 | `ShowMenu("gallery")` |

---

## 四、完整示例：一周目养成 + 画廊

```renpy
# gallery_system.rpy
init python:
    g_cg = Gallery()
    g_cg.locked_button = "gui/locked.png"
    g_cg.button("good_end")
    g_cg.unlock_image("good_end_cg")
    g_cg.button("bad_end")
    g_cg.unlock_image("bad_end_cg")

    def get_happy_level():
        score = charisma + intelligence + strength + affinity
        return score

screen play_stats():
    frame:
        xalign 0.0 yalign 0.0
        vbox:
            text "魅力: [charisma]"
            text "智力: [intelligence]"
            text "力量: [strength]"
            text "好感度: [affinity]"

# script.rpy
default charisma = 0
default intelligence = 0
default strength = 0
default affinity = 0
default day = 1
default max_days = 30

label start:
    show screen play_stats
    call day_loop
    "游戏结束！"
    
    if get_happy_level() >= 200:
        scene good_end_cg
        "好结局达成！"
    else:
        scene bad_end_cg
        "再接再厉..."
    return

label day_loop:
    while day <= max_days:
        "第 [day] 天"
        menu:
            "学习":
                $ intelligence += 3
            "锻炼":
                $ strength += 3
            "社交":
                $ charisma += 2
                $ affinity += 1
        $ day += 1
```
