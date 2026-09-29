# Ren'Py 常见陷阱 & 最佳实践

经验性知识，不一定在官方文档或训练数据中覆盖。

---

## 图片资源

- 图片放入 `game/images/` 自动注册，无需 `image` 语句
- 命名影响 tag/attribute：`eileen happy.png` → `show eileen happy`
- 同一 tag 的 `show` 替换旧图，`scene` 清除所有图片

## 字体

- 中文字体文件通常 10-20MB，注意分销体积
- 字体缺失时 Ren'Py **静默回退**到系统默认，不报错，结果就是界面字全是方块
- 检查字体是否生效的方法：运行后看设置界面

## 缩进

- Ren'Py 的缩进**只按空格计数**（lexer 用 `lstrip(" ")`），tab 不计入缩进宽度，混用 tab/空格会报 `Indentation mismatch` 或 `SyntaxError`
- 全程统一 4 空格缩进最稳妥，`python:` 块内同理

## 变量作用域

- `define` = 全局常量（每次启动重新计算，**不改**）
- `default` = 全局变量（保存在存档中，可改）
- 修改 default 变量的初始值**不影响已有存档**（存档保留旧值）
- 删除 default 变量 → 加载旧存档报错
- `python:` 块中修改全局变量用 `store.var_name` 或 `globals()["var_name"]`

## 存档兼容

- 大版本更新时用 `after_load` label 做数据迁移：

```renpy
label after_load:
    if not hasattr(persistent, "version"):
        $ persistent.version = "1.0"
    return
```

## Screen 刷新

- screen 每秒刷新多次（约 30-60fps）
- 不要在 screen 的 Python 块里做重操作（如循环、文件IO）
- 复杂计算放到 label 中的 Python 块，screen 只读结果

## Character 全参

`Character()` 有 50+ 参数，不限于 color 和 image。可设：

```renpy
define e = Character(
    "艾琳",
    who_font="SourceHanSansSC-Regular.otf",     # 名字字体
    what_font="SourceHanSansSC-Regular.otf",     # 对话字体
    what_size=22,
    what_outlines=[(1, "#000", 0, 0)],           # 文字描边，中文可读性提升
    show_side_image=Image("gui/side_eileen.png",
                          xalign=0.0, yalign=1.0),
    ctc="ctc_arrow",                             # 点击继续指示器
    callback=renpy.python.revertable_function,   # 声音等回调
)
```

## label / jump / call

- `jump` = GOTO，不返回
- `call` = 子程序调用，`return` 回到调用点
- `show screen` 在 label 间跳转后可能需要手动 `hide screen`

## 屏幕语言 (SL2) 常见坑

- `bar` 的 `value` 必须是 `BarValue` 子类（`AnimatedValue`、`FieldValue` 等），不是整数
- `viewport` 配合 `side_` 前缀属性：`side_xscroll`, `side_yscroll`
- `imagebutton` 的 `idle`/`hover` 值必须是图片名，不是文件路径
- `style_prefix` 只影响直接子元素，不影响孙元素
