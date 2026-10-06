# ⚙️ 设置 — 项目适配与打包环境

| 脚本 | 用途 |
|------|------|
| `switch_default_language.py` | 切换默认语言（简中/英文/其他） |
| `fix_lang_button.py` | 修复语言按钮写死/缺目标语言项（默认试运行，`--apply` 落盘 + .bak） |
| `add_fonts.py` | 字体添加：复制到 fonts/ + 更新字体配置文件 |
| `add_performance_panel.py` | 添加可调节性能面板（FPS/帧时间/渲染器），`--remove` 移除 |
| `remove_translated.py` | 移除文件名 `_translated` 重复后缀 |
| `patch_android_tablet.py` | 安卓平板变体强制补丁（须拷入 Ren'Py SDK 内运行） |
| `patch_android_tablet.bat` | 上述补丁的双击交互入口（apply / restore / status） |

> 多语言初始化统一用 `../sdk/setup_i18n.py`（重构版；本目录原始版已移除）。
> .rpyc 反编译兜底工具已移至 scripts 根：`../unrpyc.py`（亦可走 renpy-tools-cli 的 `unrpyc` 命令）。

## 主题分组

- **语言适配**（"让游戏跑出中文"）：`switch_default_language.py` / `fix_lang_button.py` / `add_fonts.py`；多语言基础设施在 `../sdk/setup_i18n.py`
- **通用增强**：`add_performance_panel.py` / `remove_translated.py`
- **平台与 mod**：`patch_android_tablet.py(.bat)`（安卓平板，须拷入 SDK 内运行）、`urm_install.py`（URM 安装/卸载/体检）

## 写入类工具实测清单（改动后必做）

写入类工具没有自动化测试，安全网是「默认试运行 + `--apply` 落盘 + 首次 `.bak`」。改完任一写入类工具后，在样例游戏上跑三连：

1. **试运行**：不带 `--apply` 跑一遍，核对打印的改动清单与预期一致；
2. **落盘**：加 `--apply`，确认文件已改、同目录生成 `.bak`；
3. **回滚**：`Copy-Item <文件>.bak <文件> -Force` 还原，再跑一次试运行确认行为一致。

（`urm_install.py` 的门界/回滚已有 29 个自动化用例覆盖，改动后按本清单另加人工三连即可。）

**典型工作流：**
```bash
# 初始化多语言项目
python ../sdk/setup_i18n.py <game>
# 添加字体
python add_fonts.py <game> --font path/to/font.ttf
# 切换默认语言
python switch_default_language.py <game> --lang schinese
# 修复语言按钮写死/缺目标语言项（试运行 → --apply 实际写入）
python fix_lang_button.py <game> --apply
```
