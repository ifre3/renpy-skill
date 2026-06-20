# Ren'Py 常见陷阱 & 最佳实践

当 AI 使用 bridge.py 和 patterns.py 生成代码后，可能需要手动调整以下事项。

---

## 图片资源

- **bridge.py 不自动生成图片资源** — `show("eileen happy")` 只生成代码，图片文件需手动放入 `game/images/`
- 图片命名约定：`images/` 下的 `png/jpg/webp` 自动注册，无需 `image` 语句
- 模式生成的图片引用（如 gallery 的 `imagebutton`）需确保对应图片存在

## 字体

- `cjk_font` 模式生成的字体配置指向 `game/` 目录下的字体文件
- 中文字体文件通常较大（10-20MB），注意分发体积
- 如果字体缺失，Ren'Py 会静默回退到系统默认字体，不会报错

## 缩进

- bridge.py 自动管理缩进，但如果手动拼接 `.rpy` 代码片段，Ren'Py 要求 4 空格缩进
- `python:` 块内的 Python 代码也必须 4 空格缩进
- 混合 tab 和空格会导致 `SyntaxError`

## 变量作用域

- `default` 声明的变量是全局持久化变量（保存在存档中）
- `define` 声明的变量是全局常量（每次启动重新计算）
- 在 `python:` 块中修改全局变量需用 `globals()["var_name"]` 或 `store.var_name`
- bridge.py 的 `default()` 和 `define()` 方法正确生成对应语句

## Screen 刷新

- screen 默认每秒刷新多次，在 screen 的 python 块中避免重操作
- 复杂计算应放在 label 中的 Python 块，结果存变量，screen 只读变量

## 图片引用

- `show eileen happy` 中的空格表示图片 tag + 属性：tag=`eileen`，attribute=`happy`
- 同一个 tag 的新 show 会自动替换旧图片
- `scene bg cafe` 清除所有图片并显示 bg cafe

## 角色定义

- 在 bridge.py 中 `character("e", "艾琳")` 生成的代码等价于：
  ```renpy
  define e = Character("艾琳")
  ```
- `Character` 支持大量参数：`color`, `who_color`, `what_color`, `image`, `callback` 等
- 旁白（无角色名）用 `say(None, "文本")` 实现

## 存档兼容性

- 修改 `default` 变量的初始值不会影响已有存档（存档中保留旧值）
- 添加新 `default` 变量不影响已有存档
- 删除 `default` 变量可能导致加载旧存档时报错
- 建议大版本更新时用 `after_load` label 做数据迁移

## label / jump / call

- `jump("label_name")` 是 GOTO，不返回
- `call("label_name")` 是子程序，遇到 `return` 返回调用点
- `show screen` 在 label 间跳转时可能需要手动 `hide screen`

## 菜单流程

- `menu` 语句后的选项值（如 `"coffee"`）是跳转目标的 label 名
- bridge.py 的 `menu([("显示文字", "跳转label"), ...])` 自动生成正确的 `.rpy`
- 每个 menu 选项对应的 label 必须存在，否则 lint 会报错

## 转场

- `with fade` 作用于当前语句之后
- `with None` 清除转场队列
- ATL transform 定义在 `transform` 块中，可在 `show` 时通过 `at` 子句引用

## 诊断限制

- `diagnose.py` 只能检测已知错误模式（SyntaxError、NameError、文件缺失等）
- 逻辑错误（如剧情分歧条件写反）不会被捕获
- 嵌套的 Python 语法错误（如 `python:` 块内的错误）定位可能不准确
 
 ## 存档迁移
 
 - 修改 `default` 变量的初始值不会影响已有存档（存档中保留旧值）
 - 删除 `default` 变量可能导致加载旧存档时报错
 - Ren'Py 8.5.3 提供 `config.after_load_callbacks` 和 `config.before_load_callbacks` 用于版本迁移
 - 官方建议使用 `after_load label 做数据迁移（参考：renpy/common/00start.rpy）
 - 生成新存档后旧存档仍可加载，但回滚到旧存档可能触发迁移代码重复执行
 - 使用 `after_load_migration` pattern 可以自动生成迁移骨架
