# 线性模式工具 (linear_mode.py)

给 Ren'Py 游戏增加 / 修改 **线性模式**（Linear Mode：按顺序自动串剧情，跳过沙盒地图导航）。

## 三个子命令

| 命令 | 适用游戏 | 作用 |
|---|---|---|
| `analyze <游戏目录>` | 任意 | 检测是否内置线性机制、统计场景候选，给出建议 |
| `add <游戏目录>` | 纯沙盒（无线性机制） | 生成 `game/zzz_linear_mode.rpy` 剧情目录补丁 |
| `modify <游戏目录>` | 自带事件表（如 LostInYou 的 `get_event_list`） | 校验事件表完整性、导出 CSV、追加新版本遗漏事件 |

```bash
# 1. 先分析
python linear_mode.py analyze "D:/games/MyGame-1.0-pc"

# 2a. 无线性机制 → 生成补丁
python linear_mode.py add "D:/games/MyGame-1.0-pc" --min-says 4

# 2b. 有事件表 → 校验 + 导出顺序 + 追加遗漏
python linear_mode.py modify "D:/games/MyGame-1.0-pc" --csv events.csv --append-new
```

## add 生成的补丁功能（不改动任何原脚本，删文件即还原）

- 屏幕右上角**仅一个悬浮按钮**：`Linear` 线性模式开关（开启后场景结束进入导航/地图标签时，自动跳到下一个剧情场景，只重定向顶层跳转，场景内部 `call` 的子流程不受影响）
- `Shift+L` 快速打开场景目录：手动上一/下一/跳转场景、`Variable Helper` 补设沙盒 flag 都在目录里

### 已知边界（游戏自定义程度高时）

- 场景列表由「对话密度 + 桩标签过滤」自动推导，个别纯菜单 hub 可能误入/漏入：
  用 `--min-says` 调阈值，`--include/--exclude` 手工增删，或生成后直接编辑补丁里的 `LM_STORY` 列表
- 跨场景依赖的变量不会自动构造（Variable Helper 手动补）

## modify 校验内容

- 事件表内引用的标签是否都有定义（缺失会导致 `pick_event` 跳转崩溃）
- 是否有 `event_*` 标签没进事件表（新版本新增内容被线性模式漏掉）→ `--append-new` 自动追加（带 `.bak`）

## 注意

- 游戏只有 `.rpyc` 无 `.rpy` 时，先用 `tools/设置/unrpyc.py` 反编译
- 补丁 UI 文本为英文：部分游戏未内置中文字体，中文会显示方块
- 自动播放依赖 `config.label_callbacks`（Ren'Py 7.4+ / 8.x 均支持）
