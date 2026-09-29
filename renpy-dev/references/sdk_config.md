# SDK 配置 & CLI 参考

> 本文件与 `scripts/cli.py` 的**实际签名**对齐（2026-09 修订）。
> 所有方法返回 `subprocess.CompletedProcess`（含 `.returncode` / `.stdout` / `.stderr`），不是 dict。
> 格式化展示用 `cli.format_result(result)`。

## SDK 路径检测

`cli.py` / `test_runner.py` 共用 `scripts/sdk_common.py` 检测，按以下优先级确定 Ren'Py SDK 根目录：

0. **构造函数参数**
   ```python
   cli = RenPyCLI(sdk_path="D:/workplace/renpy-8.5.3-sdk")
   ```
1. **环境变量 `RENPY_SDK`**（最推荐）
   ```powershell
   $env:RENPY_SDK = "D:\workplace\renpy-8.5.3-sdk"   # 当前会话
   [Environment]::SetEnvironmentVariable("RENPY_SDK","D:\workplace\renpy-8.5.3-sdk","User")  # 永久
   ```
2. **向上查找** — 从脚本所在目录向上遍历，寻找含 `renpy.py` 的目录
3. **已知路径列表 `_KNOWN_SDK_PATHS`**（`sdk_common.py` 顶部，唯一维护点）
   ⚠️ 本机新装/升级 SDK 后在此追加一行即可，无需改检测逻辑。
4. **常见路径 fallback** — `~/renpy-sdk`

检测失败时抛出 `RuntimeError`，提示设置环境变量或修改 `_KNOWN_SDK_PATHS`。

---

## CLI 命令速查（与实际签名一致）

### 运行

```python
from cli import RenPyCLI
cli = RenPyCLI()

cli.run("项目路径")                    # 启动游戏 (renpy.py <basedir>)
cli.quit("项目路径")                   # 立即退出 (renpy.py <basedir> quit)
cli.director("项目路径")               # Interactive Director
cli.rmpersistent("项目路径")           # 清除存档（⚠️ 不可恢复）
```

### 检查 & 测试

```python
cli.lint("项目路径")                                # 检查脚本
cli.lint("项目路径", error_code=True)               # 失败时返回码非零
cli.lint("项目路径", filename="script.rpy")         # 只查单个文件
cli.lint("项目路径", no_orphan_tl=True, by_character=True, all_problems=True)

cli.compile("项目路径")                             # 强制重编译
cli.compile("项目路径", keep_orphan_rpyc=True)      # 保留孤儿 .rpyc

cli.test("项目路径")                                # 自动化测试
cli.test("项目路径", testcase="test_start", junit_xml="report.xml")
```

### 打包 & 分发

```python
cli.distribute("项目路径")                          # 桌面版（Windows/macOS/Linux）
cli.distribute("项目路径", packagedest="D:/output") # 指定输出目录（注意参数名是 packagedest）
cli.distribute("项目路径", package=["pc", "mac"], no_archive=True)

cli.android_build("项目路径")            # Android（耗时）
cli.ios_create("项目路径", "D:/ios")    # iOS Xcode 项目
cli.web_build("项目路径")               # Web (HTML5)
cli.update("项目路径", "https://...")   # 从网络更新项目
```

### 多语言

```python
cli.translate("项目路径", "chinese")                          # 生成翻译模板
cli.translate("项目路径", "chinese", count=True)               # 统计待翻译条数
cli.dialogue("项目路径", "chinese")                            # 导出对话
cli.extract_strings("项目路径", "chinese", "out.json")         # 导出字符串为 JSON
cli.merge_strings("项目路径", "chinese", "translations.json")  # 合并回项目
```

### GUI & 项目管理

```python
cli.generate_gui("项目路径")             # ⚠️ 覆盖现有 GUI 文件
cli.generate_gui("项目路径", width=1920, height=1080, accent="#c8ffc8")
cli.gui_images("项目路径")               # 生成 GUI 图片
cli.get_projects_directory()
cli.set_projects_directory("D:/renpy-projects")
cli.set_project("D:/renpy-projects/my_game")
```

---

## 命令行入口

```bash
python cli.py "D:/my_game" lint --sdk "D:/workplace/renpy-8.5.3-sdk"
python cli.py "D:/my_game" run
python cli.py "D:/my_game" distribute
python cli.py "D:/my_game" translate chinese   # 翻译需要语言参数（extra 位置参数）
```

可用命令：`run | lint | compile | test | distribute | translate | android_build | web_build`
`--sdk` 可选；translate 需要 extra 位置参数指定语言；退出码透传子进程返回码。

---

## 依赖

- Python 3.7+
- 无第三方包依赖（标准库 `subprocess` + `os` + `json`）
- 需要 Ren'Py SDK 已安装且路径可访问（见上方检测顺序）
