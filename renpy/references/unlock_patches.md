# 玩家侧一键解锁：画廊 / CG / 回放补丁

> 目标场景：**别人的游戏**（无源码），想让画廊、CG 鉴赏、场景回放全部可看。
> 机制结论基于 Ren'Py 8.5.3 引擎源码审读（`renpy/common/00gallery.rpy`、`renpy/exports/persistentexports.py`），该结构自 6.99.13 起长期稳定。
> 社区参照：ZLZK《Universal Gallery Unlocker》（F95zone，2022-2024，664 赞）——本页打法是其思路的引擎源码级重实现，覆盖面更广。

> **不要用 URM 代替本页**：[Universal Ren'Py Mod](player_tools.md) 也是投放式、也不碰原文件，但它的「场景重放」建在 `persistent._seen_ever`（看过的 **label**）上，而画廊判定走 `persistent._seen_images`（看过的**图片**）——两个字典不同，URM 解不了画廊。要开画廊必须用下面的三重旁路（本页已纳入判据链）。
> 若用户要的是「重看看过的剧情」而非「开锁没看过的」，那直接用 URM 更方便。

---

## 一、引擎解锁判定链（为什么这么打）

`renpy/common/00gallery.rpy`（行号基于 8.5.3）：

```
玩家点画廊按钮
  └─ Gallery.make_button() → Gallery.Action(name)   L411/L454
       └─ __GalleryButton.check_unlock()             L130
            ├─ 遍历 button.conditions（g.condition("persistent.unlock_x") 挂在这）
            │    └─ __GalleryArbitraryCondition.check → eval(表达式)   L34
            └─ 遍历 button.images → __GalleryImage.check_unlock
                 └─ __GalleryUnlockCondition.check → renpy.seen_image(i)  L45
                      └─ renpy/exports/persistentexports.py L113
                           name 归一化为 tuple(name.split())，查 persistent._seen_images
```

三个可直接下手的点：

1. `renpy.seen_image()` → 恒真，所有 `unlock_image`/`unlock` 判定全过
2. Gallery 实例的 `conditions` 列表 → 清空，`persistent.xxx` 开关判定全过
3. `Gallery.Action()` → 强制返回动作，绕过 `check_unlock` 整条链

注意两个易混的 persistent 字典（都在 `persistentexports.py`）：

| 键 | 用途 | 和画廊的关系 |
|----|------|------------|
| `persistent._seen_images` | 看过的**图片**（`seen_image` 查它） | 画廊解锁判定本体 |
| `persistent._seen_ever` | 看过的 **label**（`seen_label` 查它） | 与画廊无关，别写错 |

---

## 二、方案 A（首选）：投放式补丁文件

把下面内容存为 `game/zzz_player_unlock.rpy` 放进游戏 `game/` 目录，启动游戏即生效。**模拟模式：不写任何 persistent/存档数据，删除本文件即完全还原。**

```renpy
################################################################################
## zzz_player_unlock.rpy — 通用画廊/CG 解锁补丁（模拟模式，可整体删除还原）
## 原理: renpy skill — references/unlock_patches.md（引擎判定链 + 三重旁路）
## 卸载: 删除本文件和同目录 zzz_player_unlock.rpyc（.rpyc 残留会继续生效！）
## 适用: Ren'Py 6.99.13+；.rpa 加密游戏需先解包再投放
################################################################################

init 999 python:

    # ---- 1) seen 判定恒真：覆盖 unlock / unlock_image 的全部判定路径 ----
    def _pu_seen(*args, **kwargs):
        return True

    renpy.seen_image = _pu_seen
    seen_image = _pu_seen        # store 层同名兜底（个别游戏直接调 store 名）

    # ---- 3) 定位引擎私有 Action 类（按名字后缀找，兼容文件前缀修饰）----
    _pu_GA = None
    for _pu_k in list(vars(store)):
        if _pu_k.endswith("__GalleryAction"):
            _pu_GA = vars(store)[_pu_k]
            break

    # ---- 2) 清空所有已注册 Gallery 对象的全部解锁条件 ----
    # 覆盖 g.condition("persistent.unlock_x") / allprior / 自定义表达式判定；
    # 只清内存对象，不落盘。限定扫描深度与数量，防大游戏卡 init。
    def _pu_sweep_galleries():
        cleared = 0
        found = []
        pool = [vars(store)]
        seen_ids = set()
        while pool and len(found) < 64:
            layer = pool.pop(0)
            if not isinstance(layer, dict):
                continue
            for v in layer.values():
                _pu_id = id(v)
                if _pu_id in seen_ids:
                    continue
                seen_ids.add(_pu_id)
                if isinstance(v, Gallery):
                    found.append(v)
                elif isinstance(v, dict) and len(pool) < 8:
                    pool.append(v)
                elif isinstance(v, (list, tuple)) and 0 < len(v) <= 256 and len(pool) < 8:
                    pool.append(dict(enumerate(v)))
        for g in found:
            for b in getattr(g, "button_list", []):
                cleared += len(getattr(b, "conditions", []))
                b.conditions = []
                for img in getattr(b, "images", []):
                    cleared += len(getattr(img, "conditions", []))
                    img.conditions = []
        return cleared

    # ---- 3) Action 强制返回可用动作：绕过 check_unlock 整条链 ----
    # 对 "条件挂在按钮上但按钮在 init 期才检查一次" 的游戏也生效。
    def _pu_force_actions():
        if _pu_GA is None:
            return 0

        def _pu_action(self, name):
            b = self.buttons[name]
            return _pu_GA(self, b.index)

        Gallery.Action = _pu_action
        return 1

    _pu_force_actions()
    _pu_cleared = _pu_sweep_galleries()
```

**卸载**：删除 `zzz_player_unlock.rpy` **和** `zzz_player_unlock.rpyc`（只删 .rpy 的话，残留的 .rpyc 仍会被引擎加载执行）。删除后重启游戏，解锁状态全部消失（模拟模式的定义）。

**想永久解锁（连补丁一起带走也能保留状态）**：在上面文件末尾追加持久化段，游戏启动一次后即可把补丁整个删掉：

```renpy
    # ---- 可选追加：持久化真实解锁（写 persistent，跑一次后可整体删除补丁）----
    # 键格式与引擎 mark_image_seen 完全一致；_seen_ever 是 label 已读表，别用错。
    import renpy.display.image as _pu_di
    for _pu_name in list(getattr(_pu_di, "image_names", []) or _pu_di.images.keys()):
        try:
            persistent._seen_images[tuple(str(i) for i in _pu_name)] = True
        except Exception:
            pass
    renpy.save_persistent()
```

持久段只写"图片已看"，不清 `g.condition("persistent.xxx")` 开关——那些开关如果不清，模拟段的 sweep 仍会在补丁在位时兜底。

---

## 三、方案 B：控制台一行（不想装文件）

游戏内 Shift+O（需 `config.console=True` 或开发者版），粘贴：

```python
renpy.seen_image = lambda *a, **k: True
```

然后回车，再粘第二条（清 Gallery 条件并刷新界面）：

```python
_g=[v for v in vars(store).values() if isinstance(v,Gallery)]; [(setattr(b,'conditions',[]),[setattr(i,'conditions',[]) for i in b.images]) for g in _g for b in g.button_list]; renpy.restart_interaction()
```

控制台方式只对本次运行有效，关游戏即还原——适合"临时看一眼"。

---

## 四、非标准画廊（游戏自造的画廊类/界面）

引擎的 `Gallery` 类管不到游戏手搓的画廊（自定义类 + `if persistent.unlock_x` 判定）。两种打法：

**打法 1：monkeypatch 游戏自己的判定函数**（ZLZK 逐游戏适配同款思路）：

```renpy
init 999 python:
    # 类名从反编译源里找（见打法 2），把它的解锁判定函数直接恒真
    GalleryScene.is_unlocked = lambda *args, **kwargs: True
```

**打法 2：找到 persistent 开关名，直接翻**：

1. 用 **rpycdec**（本技能 player_tools.md 已收录）反编译 `screens.rpyc` / 画廊相关 `.rpyc`
2. 搜 `condition(`、`is_unlocked`、`persistent.unlock`、`persistent.cg`
3. 控制台逐个 `persistent.开关名 = True`，最后 `renpy.save_persistent()`

---

## 五、边界与已知失败模式

| 场景 | 表现 | 处理 |
|------|------|------|
| `.rpa` 加密 + 自定义解释器（LOP 系游戏） | 连 screens 都反编译不出 | 放弃——ZLZK 同样判死，先解包（player_tools.md 的 rpa 工具）再试 |
| 游戏在 **init 期**调用 `make_button` 并缓存按钮对象 | 补丁后按钮仍是锁样式（action 当时已算成 None 并被缓存） | 类似 Halfway House（ZLZK 也失败）：走方案 B 翻 persistent 开关，或打法 2 找 flag |
| 游戏重定义了 `Gallery` 子类并重写 `Action` | 补丁的 `Gallery.Action` 覆盖不到子类 | 打法 1 monkeypatch 子类 |
| 手搓画廊把 make_button 结果缓存进列表/字典 | sweep 扫不到（对象不在 Gallery 实例里） | 打法 2 |
| 补丁只删 .rpy 没删 .rpyc | "卸载了怎么还解锁着" | 删 .rpyc，引擎对 rpyc 残留照常加载 |
| 用 `renpy.is_seen` 做已读标记的界面 | 全部显示"已读" | 预期行为，不是 bug |
| Web 版 / 手机版 | game/ 目录只读或导出为 .rpa | 先在 PC 版操作，或打包前投放 |

**设计对照**：`init 999` 的取值——官方约定区间（-999～999）上限，晚于游戏画廊定义（通常 init 0～500），同级内按文件名字母序执行，`zzz_player_unlock.rpy` 天然最后加载；实测 `init 1000` 也能跑但 lint 会警告超区间。ZLZK 无法处理"persistent 检查在 init 0 同时完成按钮缓存"的游戏，本补丁的 `Action` 覆盖能把其中"按钮引用画廊对象"的那部分救回来，缓存死的仍要走控制台。

---

## 六、来源

- 引擎源码：`renpy-8.5.3-sdk/renpy/common/00gallery.rpy`（判定链 L130/L34/L45）、`renpy/exports/persistentexports.py`（`seen_image` L113、`mark_image_seen` L129、`_seen_ever` 是 label 表）
- ZLZK《Universal Gallery Unlocker》讨论串（机制描述、逐游戏适配经验、失败模式清单）：https://f95zone.to/threads/universal-gallery-unlocker-2024-01-24-zlzk.136812/
- 官方 Gallery/Replay/MusicRoom API：https://www.renpy.org/doc/html/rooms.html
