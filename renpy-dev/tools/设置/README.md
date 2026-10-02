# ⚙️ setup — 项目配置与环境设置

| 脚本 | 用途 |
|------|------|
| `switch_default_language.py` | 切换默认语言（简中/英文/其他） |
| `add_fonts.py` | 字体添加：复制到 fonts/ + 更新字体配置文件 |
| `add_performance_panel.py` | 添加可调节性能面板（FPS/帧时间/渲染器），`--remove` 移除 |
| `remove_translated.py` | 移除文件名 `_translated` 重复后缀 |
| `patch_android_tablet.py` | 安卓平板变体强制补丁（须拷入 Ren'Py SDK 内运行） |
| `unrpyc.py` | 下载 unrpyc 并反编译 .rpyc |

> 多语言初始化用 `../../scripts/setup_i18n.py`（重构版；本目录原始版已移除）。

**典型工作流：**
```bash
# 初始化多语言项目
python ../../scripts/setup_i18n.py <game>
# 添加字体
python tools/设置/add_fonts.py <game> --font path/to/font.ttf
# 切换默认语言
python tools/设置/switch_default_language.py <game> --lang schinese
```
