# linear/ — 剧情线性模式

> **要点已内联到 [../README.md](../README.md)「linear/ — 剧情线性模式」一节**，本文件只留子命令速查。

给 Ren'Py 游戏增加 / 修改**线性模式**（按顺序自动串剧情，跳过沙盒地图导航）。

| 命令 | 适用游戏 | 作用 |
|---|---|---|
| `analyze <游戏目录>` | 任意 | 检测是否内置线性机制、统计场景候选 |
| `add <游戏目录>` | 纯沙盒（无线性机制） | 生成 `game/zzz_linear_mode.rpy` 补丁 |
| `modify <游戏目录>` | 自带事件表 | 校验完整性、导出 CSV、`--append-new` 追加遗漏 |

```bash
python renpy-tools-cli.py linear analyze MyGame-1.0-pc
python renpy-tools-cli.py linear add MyGame-1.0-pc --min-says 4
python renpy-tools-cli.py linear modify MyGame-1.0-pc --csv events.csv --append-new
```

`add` 只新增 `game/zzz_linear_mode.rpy`，**不改原脚本，删除即还原**。
已知边界与手动干预方式见 [../README.md](../README.md)。
