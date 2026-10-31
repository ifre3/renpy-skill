# `config.replace_text` 钩子：无 `tl/` 汉化的实现与排查

> 两个方向：自己写汉化时它是 [translation_workflow.md](translation_workflow.md) 第 7 节的兜底手段；
> 拆别人的发行版时它是**第三方机翻**的判定特征——**游戏里根本没有 `game/tl/`，却在显示中文**。
> 本文是这条钩子的唯一完整出处（引擎源码依据 + 载荷识别 + 拆除步骤）。

---

## 0. 为什么这套钩子"巧妙"（先讲原理，再讲怎么拆）

第三方的实现不只是"藏代码"，它选对了**替换时机**，因此拿到了 `tl/` 拿不到的东西。
理解这点是判断「要不要拆、能不能拆」的前提。

| | `tl/` 官方翻译 | `config.replace_text` 钩子 |
|---|---|---|
| 生效时机 | 脚本**解析期**（`translate` 块匹配） | 文本**渲染前、tokenize 之后** |
| 收录范围 | 引擎能静态扫到的字符串 | **任何**经过 `Text` 的东西，含运行时拼接 |
| 改原脚本？ | 不改，但要生成/维护 tl 文件 | 完全不改，一个 `.rpy` + 一张词表 |
| 标签/插值 | 翻译者要自己保住 `{i}`、`[pn]` | **天然免疫**：只收到 `TEXT` token |
| 语言切换 | 要配 `Language()` / `tl` 目录 | 钩子无条件生效，无语言概念 |
| 可维护 | 高（标准格式、工具链齐全） | 低（词表是黑盒，质量取决于整句命中率） |

**巧妙之处在"只处理 TEXT token"**：`{i}` 已被切成 `TAG` 原样透传，`[pn]` 留在
`TEXT` 内但词表里通常没同形条目。所以它能做到「标签完好、插值不坏、只有英文变中文」，
而人工 tl 翻译恰恰最容易在这两处出错（本项目 26 处插值被译坏、627 处标签丢失）。

所以：**它质量不如 tl，但它不会犯 tl 最常犯的错**。这个取舍值得写清楚。

**代价也要讲明白**：

- 词表是黑盒，44917 条里 3049 条单词兜底会产出碎片（见第 5 节）
- 无语言切换能力——这就回到本文 4.1 节：要语言选项就必须回 `tl/`
- 无法增量修正：改一句要动整个词表，不像 tl 文件按句可编辑
- 性能：钩子挂在**每条文本的必经之路**上，词表越大越卡（见 0.2 节）

### 0.1 决策：什么时候保留钩子、什么时候换 `tl/`

| 你的目标 | 建议 |
|---|---|
| 只想"能看中文"，不在乎能不能切语言 | **保留钩子**，别动它（拆它是纯风险） |
| 要语言切换 / 要能逐句校对 / 要长期维护 | 换 `tl/`，按 4.1 节**先搬后删** |
| 只想去掉载荷里的引流/联网部分 | 按第 4 节**局部拆**（保 `replace_text`，删其余） |
| 项目已有完整 `tl/`，钩子只是历史残留 | 直接删（4.1 节已验证 lint 无回归） |

### 0.2 性能影响：钩子在每条文本的必经之路上

**调用频率（机制事实，源自第 1 节接入点）**：钩子在 `Text.__init__` 的
`apply_custom_tags` 里被调，而**每次创建 Text 对象都会走一遍**——对白每推进
一句、screen 每次刷新含变化文本的名字框/倒计时/通知，都是新的 `Text`。这是
每帧热路径上的**纯 Python 回调**（tokenize 之后、布局之前），没有 C 加速，
也没有跨帧缓存替你挡：同一段文字换一行插值就重新走全流程。

**代价量级（机制推断，未逐机实测）**：第三方实例的词表是 44917 条。若实现是
"遍历词表逐条 `str.replace`"，单次调用就是 O(词表规模 × 文本长)——每句对白
对 4.5 万条做全量扫描，低端机上推进对白会感到卡顿；历史记录/回看页面一次性
重建大量 Text 时最明显。

**自己写钩子时按开销从小到大拦（写法契约）**：

1. `init` 时一次性的活不进钩子：词表加载、`re.compile` 全部在 init 完成，
   钩子内不做 I/O、不建大对象、不调 `renpy.loader.load`。
2. 先走 O(1) 精确命中：整句映射绝大多数是**整串相等**，`dict.get(text)` 命中
   直接返回，只有未命中才落到正则。
3. 单词兜底合成**一条** alternation 正则（`\b(?:a|b|c)\b`，init 时编译一次），
   回调里查 dict——**不要**对几千个单词逐个跑 `re.sub`。
4. 加快速预过滤：文本不含源语言字符（如纯 ASCII 判断对英→中词表反向早退，
   或"已含 CJK 则直接返回"）时原样返回——并存态（4.1 节）下已译好的中文
   就是这样零成本穿过的。

**给排查/拆除决策加一条判据**：游戏推进对白明显掉帧、而 `ls game/tl` 又不存在
时，先量词表规模（第 3 节第 4 步解出来看条数）再下结论；0.1 节的保留/更换
取舍在性能敏感的项目上应向"换 `tl/`"倾斜——`tl/` 的翻译是解析期匹配，
渲染热路径上零额外成本。

---

## 1. 引擎侧接入点

`config.replace_text` 在 `renpy/config.py:628` 声明为 `None`。非空时两处启用：

| 位置 | 作用 |
|------|------|
| `renpy/text/text.py:2320-2321` | `Text.__init__` 中 tokenize 之后调 `apply_custom_tags` |
| `renpy/text/text.py:2881-2882` | `apply_custom_tags` 内逐 token 替换 `TEXT` 类型 |
| `renpy/text/extras.py:191` | alt text（无障碍朗读文本）走同一条路径 |

```python
# text.py:2317-2321（Text.__init__）
tokens = self.tokenize(text)
if renpy.config.custom_text_tags or renpy.config.self_closing_custom_text_tags \
        or (renpy.config.replace_text is not None):
    tokens = self.apply_custom_tags(tokens)

# text.py:2876-2885（apply_custom_tags）
t = tokens.pop(0)
kind, text = t
if kind == TEXT and renpy.config.replace_text:
    rv.append((TEXT, str(renpy.config.replace_text(text))))
elif kind != TAG:
    rv.append(t)
```

**关键：时机是「渲染前、tokenize 之后」**，不是脚本解析时。它只收到已经切成
token 的纯文本片段；`{i}`、`{color=…}` 已被识别为 `TAG`，`[pn]`、`[atsuko_bond]`
等插值留在 `TEXT` 内但不会被匹配（除非映射表里恰好有同形条目）。
所以标签与变量名天然不受影响——排查时看到「标签完好、只有英文变中文」就是这个机制。

配套要点：

- 只处理 `TEXT` token。`kind != TAG` 的分支原样透传，`DISPLAYABLE` 同理。
- 返回值被 `str()` 包一次，故可返回非字符串，但必须是能 `str()` 的东西。
- 钩子对**所有** `Text` 生效，含 screen 文本、名字框、历史记录、通知。
- 无 `tl/` 依赖：`config.replace_text` 与 `config.language` / `Language()` 无关。

## 2. 第三方机翻的载荷形态

发行版里常见的封装（2026-10 实例，Dissonance 0.14）：

```renpy
# game/AtsukoEve.rpy:1411
init python:
    # This causes the screen named `screen` to be hidden, if it is shown.
    import zlib
    try:
        with renpy.loader.load("audio/dl_failed.mp3") as dl_failed:
            exec(zlib.decompress(zlib.decompress(dl_failed.read())))
    except Exception:
        pass
```

特征组合，逐条都可在发行版里验证：

| 特征 | 判据 |
|------|------|
| 无 `game/tl/` 目录 | `ls game/tl` 不存在，但游戏显示中文 |
| 载荷伪装成音频 | `game/audio/dl_failed.mp3` 实际不是 MP3（无 `ID3`/帧同步头） |
| 双层 zlib | `zlib.decompress(zlib.decompress(data))` |
| `init python` + `exec` | 词法上就是 `exec(...)`，grep `exec(zlib` 即可命中 |
| `try/except: pass` 吞异常 | 载荷失效时**静默**回退，日志无痕——仅凭 log 判断不了它跑过 |
| 与弹窗引流同文件 | 同一载荷常同时含 `config.overlay_screens.append(...)` 与 `define_screen` |

实测数据：6 KB「音频」解出 18.5 KB Python。该载荷同时做三件事——发 HMAC 签名
网络请求取远程配置、注册 `welcome_popup` 覆盖层推站外链接、装 `config.replace_text`。
三者耦合在同一个 blob 里，但只有第三件是汉化依赖。

> **2026-10-11 补充（Dissonance 0.14 终态）**：本条目的判据「无 `game/tl/`」
> 只是**初始**特征，不是常态。该游戏后来补了完整的 `game/tl/schinese/`
> （44,387 对白块全覆盖），此时两套机制**并行生效**：
>
> - `tl/` 管对白；钩子管 `newscreens.rpy` 的 UI 文本（`tl` 里只译了 4 条，
>   337 条去重 UI 文本中 280 条仍只靠词表）。
> - 钩子跑在渲染前、tokenize 之后，对**已译好的中文**基本无匹配（词表是
>   英→中），实测 5 条中文译文输入零改动——所以并存不会互相污染。
>
> 判定是否已进入并存态：`ls game/tl` 存在**且**仍能 grep 到 `exec(zlib`。
> 此时不要直接删钩子，否则那 280 条 UI 文本会退回英文。

## 3. 识别流程

```bash
# 1. 先确认「无 tl 却有中文」
ls game/tl 2>/dev/null || echo "no tl/"

# 2. 找执行点（这一步是决定性的）
grep -rn "exec(\|zlib.decompress\|loader.load(" game/*.rpy

# 3. 验载荷不是真音频
python -c "d=open(r'game/audio/dl_failed.mp3','rb').read(); print(d[:8])"

# 4. 解出来读（只读，不落盘到 game/）
python -c "import zlib,sys; sys.stdout.buffer.write(zlib.decompress(zlib.decompress(open(r'game/audio/dl_failed.mp3','rb').read())))"
```

`.rpyc` 里搜不到关键字是正常的——`.rpyc` 为 zlib 压缩且槽位序列化，明文 grep 无效。
要查编译产物需先反编译（`scripts/unrpyc.py` 或 renpy-script-decompile 技能），
或按 [player_tools.md](player_tools.md) 的路子直接读 `.rpy` 源。

## 4. 拆除（保汉化、去引流）

载荷里汉化与引流通常是同一段代码，**不要整块删**。做法：只保留
`config.replace_text` 及其依赖（词表加载、`re` 编译、匹配函数），删掉网络请求、
AES/HMAC 实现、`define_screen` 与 `overlay_screens.append`，重新按原封装写回。
调用点（上面的 `init python` 块）不动即可继续工作。

### 4.0 拆除前必做的三件事（2026-10-21 事故后加，血泪）

**① 先跑 `payloadscan` 拿证据行号**，别靠肉眼 grep：
现有 `langcheck` 的正则只抓 `exec(zlib.decompress|__import__|eval)`，
**不覆盖 `base64.b64decode`**；而多层载荷的第一层常常就是这个形态。
```
python renpy-tools-cli.py payloadscan <项目>
```

**② 多层形态：外层干净不代表没有 payload。** 实证形态（三层）：

| 层 | 位置 | 内容 |
|---|---|---|
| 1 | `game/*.rpy` 的 `exec(__import__("base64").b64decode(...))` | 只是 **loader**，本身完全干净 |
| 2 | 第 1 层解出（XOR 121 + 整数列表 XOR） | 还是 loader：加载 DLL、读 `.dat` |
| 3 | `rentransl/<hash>.dat`（DLL 对称解密 + zlib） | **真正的 payload**：`overlay_screens` 引流 + `replace_text` 汉化 |

第 3 层 `ctypes.CDLL` 名字/AES 密钥在包里硬编码，静态解不了——
所以**只扫到第 1、2 层就报「无证据」会是假阴性**。报告会提示「存在加密 .dat」，
此时真 payload 多半在里面，必须人工精读，别当成绿灯。

**③ 保护名单——删到下面任何一个名字，上一层 `exec` 立刻崩：**

```python
# 载荷惯用的 builtins 别名（第 2/3 层开头就这样定义）
import builtins as _b
_b_globals = _b.globals; _b_hasattr = _b.hasattr; _b_set = _b.set
_b_Exception = _b.Exception; _b_getattr = _b.getattr   # …还有很多
```

**事故实录**：拆引流时删网络请求，删除范围从 `if _PY2:` 一路吃掉这些别名定义
（含 `import builtins as _b`）。结果第 3 层还没来得及装 `replace_text` 就
`NameError`，**汉化整个消失**。

**④ 桩环境验证会骗人，这是同类事故的根因。** 当时验证脚本里手写了
`_b_globals = lambda: g` 注入桩的 globals，于是缺了定义的载荷在桩里照样跑通；
真实环境里没人给它注入，**一跑就 NameError**。
> 判据：**桩必须复现上一层的执行作用域**（用 `_b.globals()` 真实取值，而不是外部注入）。
> 验证通过 ≠ 真实能跑。删完务必真的启动一次游戏看汉化在不在。

做完 ①②③④ 再动手，且**先备份**（`tmp/` 或游戏根 `.renpy-skill-tmp/`，见 README 第 7 条）。

### 4.1 并存态下改用 `tl/`（2026-10-11 实测流程）

当 `tl/` 已完整、钩子只残余 UI 文本价值时，正确顺序是**先搬后删**：

1. 从词表（`audio/dl_success.mp3`）里取**整句命中**的条目（跳过单词兜底，
   那些碎片映射质量差，不值得进正式翻译文件）。
2. 生成 `game/tl/schinese/<name>_translated.rpy`，写成
   `translate schinese strings:` + `old "..." / new "..."` 块。UI 文本是
   字符串翻译，不是对白——写错成对白块不会被引用。
3. **先删钩子、跑 lint 验证**（确认无 `ScriptError`、对白块数不变），
   再把 `audio/dl_failed.mp3`、`dl_success.mp3` 一并清掉。

Dissonance 实测：搬 280 条 UI 文本，删钩子后 lint 照常加载 44,387 对白块，
`tl` 译文零污染。

拆除后的验证（比「游戏能启动」强得多）：

```python
# 用 Ren'Py 桩环境执行新旧两版 payload，对比
# ① config.overlay_screens 是否从非空变空
# ② 同一批样本文本经 config.replace_text 的输出是否逐字相同
```

`replace_text` 是纯函数，桩环境只需 stub `renpy.loader.load` / `config.screen_*`
即可跑，不必启动游戏。实例中 9 条样本文本新旧输出全同。

## 5. 质量判据

词表替换的质量取决于**整句命中率**，不是词表大小：

- 44917 条映射里 41868 条整句（中位 59 字符）、3049 条单词
- 整句未命中才走单词正则兜底，于是产出 `"我 应该 大概 折断 那么 habit."` 这类碎片
- 单词兜底还会误伤：`'had' -> 不是`、`'was' -> 确实` 这类虚词映射本身有错
- 虚词映射会漏进引擎内部文本（实测映射表含 `for (float i = 0.; ...` 这类 blur shader 代码）

**要提升质量只有一条路：补全整句映射**，让兜底极少触发。改词表不动 `.rpy`。

---

## 与其他条目的关系

- 自己汉化时：`translation_workflow.md` 第 7 节（兜底顺序 oldnew → 额外文本提取 → 本钩子）
- 翻译完全不显示 / 只显示一半 → `translation_troubleshooting.md` 第 1、2 章
- 反编译、`.rpyc`、解包 → `player_tools.md`
- 检测器可用性：本条目目前是**纯知识**，无配套脚本。`check_i18n.py` 查的是
  `Language()` / `config.language` 链路，对本机制无感——因为它本来就不走 `tl/`。