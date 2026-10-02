# ⚙️ setup — 项目配置与环境设置

| 脚本 | 用途 |
|------|------|
| `setup_i18n.py` | 多语言初始化：语言选择界面、字体配置、翻译目录 |
| `switch_default_language.py` | 切换默认语言（简中/英文/其他） |
| `add_fonts.py` | 字体添加：复制到 fonts/ + 更新字体配置文件 |
| `add_performance_panel.py` | 添加可调节性能面板（FPS/帧时间/渲染器） |

**典型工作流：**
```bash
# 初始化多语言项目
python tools/setup/setup_i18n.py <game>
# 添加字体
python tools/setup/add_fonts.py <game> --font path/to/font.ttf
# 切换默认语言
python tools/setup/switch_default_language.py <game> --lang schinese
```
