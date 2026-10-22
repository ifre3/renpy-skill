# 名字栏（namebox）翻译：写法识别与全串精确匹配

> 2026-10-18，Dissonance_0.14 实测。这份文档记录两类「工具静默失效」的坑，
> 以及引擎侧的源码依据。**不要凭印象改这里的匹配逻辑。**

## 一句话结论

namebox 显示中文，取决于 `tl/<lang>` 里是否存在与名字栏**完整串精确相等**的
`old` 条目。名字串带 `{color=}` 标签时，`old` 也必须带标签。

## 坑 1：只认 `Character("Name")` 会扫出 0 个名字

Ren'Py 项目把人名做成名字栏有两类写法：

```renpy
# 写法 A：标准
define e = Character("Eri", color="#ff0000")

# 写法 B：没有 Character，人名是裸字符串变量，直接当说话人
define nih = "{color=#0f37f2}Niwa{/color}"
nih "Ready."
```

Dissonance_0.14 **整个项目零个 `Character()`**，47 个说话人全是写法 B。

只匹配 `Character("Name")` 的后果不是「漏报」而是**假绿灯**：

```
$ sync_namebox_translation.py ...
扫描角色定义: .../game
  找到 0 个 Character 名字定义
...
无需补充翻译，所有术语表中的角色名字均已翻译。   # ← 空集上的断言
```

第三类是内联说话人，也要认：

```renpy
"Ailing Man" "Uggghhhhhh..."
```

识别逻辑统一在 `scripts/shared/namebox.py` 的 `scan_namebox_names()`，
输出 `NameDef`（含 `value` 完整串 / `plain` 裸名 / `say_lines` 台词数 / `kind`）。
`checks/check_charname_translation.py` 与 `translate/sync_namebox_translation.py`
共用它。

### 裸 define 什么时候才算说话人

`define monday = "images/calender/monday.png"` 不是人名。判定条件是
**真的被当说话人用过**——项目里存在 `^\s*nih\s+["']` 形式的行。
同时跳过：

| 跳过对象 | 例子 | 理由 |
|---------|------|------|
| 资源路径 | `images/...`、`audio/x.mp3` | 不是名字 |
| 含插值 | `define t = "[pn]"` | 运行时才知道（玩家自定义名） |
| 纯符号 | `define y = "???"` | 有意的悬念标记，不该翻 |

## 坑 2：匹配是**全串精确**，不是「去标签后比」

引擎查找函数在 `renpy/translation/__init__.py:545-564`：

```python
def translate(self, old):
    new = self.translations.get(old, None)        # 整串精确
    if new is not None:
        return new
    if new is None:
        notags = re.sub(r"\{\#.*?\}", "", old)    # 只剥离 {#...} 注释标签
        new = self.translations.get(notags, None)
```

只剥离 `{#...}`（翻译注释），**`{color=}` `{i}` 等文本标签一律不剥**。于是：

| `old` 条目 | 能命中的名字串 |
|-----------|---------------|
| `old "Eri"` | `"Eri"` ✅ / `"{color=#d599aa}Eri{/color}"` ❌ |
| `old "{color=#d599aa}Eri{/color}"` | `"{color=#d599aa}Eri{/color}"` ✅ |
| `old "{#weekday}Monday"` | `"{#weekday}Monday"` ✅ / `"Monday"` ✅ |

**补条目时 `new` 必须连标签一起写**，否则角色配色会丢：

```renpy
    old "{color=#d599aa}Eri{/color}"
    new "{color=#d599aa}绘里{/color}"      # ← 少标签 = 名字栏掉色
```

`splice_tags()` 负责这件事：只替换标签之间的文本段。有多个文本段时
（`{b}Fox{/b} the Fox`）语义有歧义，返回 `None` 交人工判断，不猜。

## 坑 3：`old` 重复是**致命**的，不是覆盖

同一条串可能既是 define 变量、又被内联说过：

```renpy
define c = "Cashier"          # script.rpy
label s:
    "Cashier" "Welcome."      # MomoeEve.rpy
```

名字栏显示的是**同一个串**，必须合并成一条。写两条 `old "Cashier"` 会让
引擎在启动时直接抛异常（`renpy/translation/__init__.py:534`）：

```
Exception: A translation for "Cashier" already exists at game/tl/schinese/zz_namebox.rpy:102.
```

这条是**跑 lint 才发现的**——两个工具都只按缺失/命中判断，不会发现
自己即将产出重复条目。`scan_namebox_names()` 因此按 `value` 合并同名来源
（保留台词数最大的那个，其余记进 `notes` 的「同名来源」），
`write_namebox_file()` 落盘前再拦一道，重复即拒绝写入。

**生成任何 tl 文件后都要跑一次引擎 lint**，静态检查发现不了的。

```bash
cd <游戏根> && ./lib/py3-windows-x86_64/python.exe <启动>.py . lint
```

## 运行时链路（为什么裸字符串说话人也会被翻译）

裸字符串说话人**会**走字符串翻译通道——这点容易误判成「裸 define 翻不了」：

```
nih "台词"
  → renpy/ast.py:583              Say.execute → eval_who 求值出字符串
  → renpy/exports/sayexports.py:129-130   isinstance(who, basestring) 分支
  → renpy/defaultstore.py:420-422         say() 现场 who = Character(who)
  → renpy/character.py:1444               who = self.name
  → renpy/character.py:1454               prefix_suffix("who", ...)
  → renpy/character.py:1348-1349          substitute(s, translate=True)
  → renpy/substitutions.py:344-345        translate_string(s)
  → renpy/translation/__init__.py:545     精确字典查找
```

结论：不管名字是 `Character` 定义、裸 define 还是内联，都收敛到同一个
字符串翻译表。**key 必须是含标签的完整串**。

## 工具用法

```bash
# 检查：哪些说话人没有译文（退出码 1 = 有缺失，不是崩溃）
python checks/check_charname_translation.py <项目> -l schinese

# 生成待填骨架（new 留空）
python checks/check_charname_translation.py <项目> \
    --stub game/tl/schinese/zz_namebox.rpy

# 按术语表批量补（--stub 写独立文件，不污染既有翻译文件）
python translate/sync_namebox_translation.py --project <项目> \
    --glossary 术语表.xlsx --stub game/tl/schinese/zz_namebox.rpy --apply
```

`--stub` 是**必带路径**式开关：不传就没有路径可写，天然 opt-in。
`--apply` 才是真写盘；两个工具都默认试运行。

## 落到项目里：名字栏显示英文怎么办

按顺序走：

1. `check_charname_translation` 拿到缺失名单（带台词数，按重要性排序）；
2. 缺的译名补进**术语表**（`术语表.xlsx`，AiNiee 三栏 `原文|译文|备注`）；
3. `sync_namebox_translation --stub ... --apply` 生成 `zz_namebox.rpy`；
4. 重跑 `check_charname_translation` 确认退出码 0。

带标签的名字**不要**手工去 `tl` 里找对应 `old`——找不存在的，
名字栏那串是从 `define` 的值里来的，键就是那个值本身。

## 相关

- [translation_workflow.md](translation_workflow.md) — 术语表取证与定稿流程
- [renpy_gotchas.md](renpy_gotchas.md) — 字体静默回退等引擎行为陷阱
- `scripts/shared/namebox.py` — 识别 / 查找 / 生成条目的唯一实现
- `scripts/tests/test_namebox_shared.py` — 28 用例锁住上述语义