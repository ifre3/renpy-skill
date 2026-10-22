# setup/ — 项目适配与打包环境（写入类）

> **要点已内联到 [../README.md](../README.md)「setup/ — 写入类工具」一节**，本文件只留脚本清单。

| 脚本 | 用途 |
|------|------|
| `setup_i18n.py` | 多语言基础设施（生成 tl/ 目录、语言 Screen、字体配置） |
| `switch_default_language.py` | 切换默认语言 |
| `fix_lang_button.py` | 修复语言按钮写死 / 缺目标语言项（默认试运行，`--apply` 落盘） |
| `add_fonts.py` | 字体添加：复制到 fonts/ + 更新字体配置 |
| `setup_fonts.py` | 字体适配（detect / config / fallback / list） |
| `add_performance_panel.py` | 可调节性能面板，`--remove` 移除 |
| `remove_translated.py` | 移除文件名 `_translated` 重复后缀 |
| `urm_install.py` | URM 安装/卸载/体检（不代下载，`--apply` 才落盘） |
| `patch_android_tablet.py`(.bat) | 安卓平板适配补丁（须拷入 SDK 内运行） |

本组无自动化测试，安全网是「默认试运行 + `--apply` 落盘 + 首次 `.bak`」；
改动后请按 [../README.md](../README.md) 的**试运行 / 落盘 / 回滚三连**验证。
