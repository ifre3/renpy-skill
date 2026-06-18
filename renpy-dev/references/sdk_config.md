# SDK 配置 & CLI 参考

## SDK 路径检测

`cli.py` 按以下优先级自动检测 Ren'Py SDK 根目录：

1. **环境变量 `RENPY_SDK`**（推荐）
   ```powershell
   $env:RENPY_SDK = "D:\workplace\renpy-8.5.3-sdk"
   ```

2. **构造函数参数**
   ```python
   cli = RenPyCLI(sdk_path="D:/renpy-sdk")
   ```

3. **向上查找** — 从脚本所在目录向上遍历，寻找含 `renpy.py` 的目录

4. **常见路径 fallback** — `~/renpy-sdk`（用户主目录下）

检测失败时抛出 `RuntimeError` 并给出配置提示。

---

## CLI 命令速查

所有方法返回 `dict` 格式：`{"command": "...", "stdout": "...", "stderr": "...", "returncode": 0}`

### 运行

```python
from cli import RenPyCLI
cli = RenPyCLI()

cli.run("项目路径")          # 启动游戏
cli.quit_cmd("项目路径")     # 立即退出
cli.director("项目路径")     # Interactive Director
cli.rmpersistent("项目路径") # 清除存档（⚠️ 不可恢复）
```

### 检查 & 测试

```python
cli.lint("项目路径")
cli.lint("项目路径", error_code=True)       # 失败时返回码非零
cli.lint("项目路径", output_file="report.txt")

cli.compile("项目路径")                      # 强制重编译
cli.compile("项目路径", keep_orphan_rpyc=True)

cli.test("项目路径")                         # 自动化测试
```

### 打包 & 分发

```python
cli.distribute("项目路径")                           # 桌面版（Windows/macOS/Linux）
cli.distribute("项目路径", destination="D:/output")  # 指定输出目录

cli.android_build("项目路径")    # Android（耗时）
cli.ios_create("项目路径")       # iOS Xcode 项目
cli.web_build("项目路径")        # Web (HTML5)

cli.update_old_game("项目路径")  # 迁移旧版项目
```

### 多语言

```python
cli.translate("项目路径", "chinese")               # 生成翻译模板
cli.dialogue("项目路径", "chinese")                # 导出对话
cli.dialogue("项目路径", "chinese", strings=True)  # 导出字符串
cli.extract_strings("项目路径", output="out.txt")
cli.merge_strings("项目路径", "chinese")           # 合并回项目
```

### GUI & 项目管理

```python
cli.generate_gui("项目路径")     # ⚠️ 覆盖现有 GUI 文件
cli.gui_images("项目路径")       # 生成 GUI 图片
cli.set_project("项目路径", "我的故事")
cli.version()                   # 显示 Ren'Py 版本号
cli.json_dump("项目路径", "info.json")
cli.help()                      # 全局帮助
cli.help("项目路径", "lint")    # 命令详情
```

---

## 模块级便捷函数

也可不创建实例，直接调用模块级函数：

```python
from cli import lint, compile, distribute, run, translate, test, version

lint("项目路径", error_code=True)
run("项目路径")
distribute("项目路径", "D:/output")
version()
```

---

## 命令行入口

```bash
python cli.py lint "D:/my_game" --error-code
python cli.py run "D:/my_game"
python cli.py distribute "D:/my_game" --destination "D:/output"
python cli.py translate "D:/my_game" --language chinese
python cli.py version
```

---

## 依赖

- Python 3.7+
- 无第三方包依赖（标准库 `subprocess` + `os` + `json`）
- 需要 Ren'Py SDK 已安装且路径可访问
