# tl_check — tl 翻译文件质检 v3 分级细则

> 本文是 `scripts/sdk/tl_check.py` 分级细则与崩溃边界的**唯一完整出处**；SKILL.md 与脚本表只留路由，不重复。
> 用法：`python scripts/sdk/tl_check.py <项目路径> --lang schinese [--fix] [--add-tflag] [--max-examples N]`

## 三级报告

### 崩溃级（引擎显示到该行直接 raise）

- **未知文本标签 / 关闭无开放标签 / 不接受关闭的标签 / 未闭合大括号**：引擎在 `config.safe_text=False`（默认）时直接 raise；工具会读取项目配置自动降级。
- **未闭合 `[`**：渲染抛 "String ends with an open format operation"；原文本身未闭合则豁免译文。
- **`[]` 插值不匹配中的"变量被改名/多出未定义变量"**（`[totaldays]`→`[总天数]`、人名写成 `[Tora]`）——工具虽归显示级，引擎同样 KeyError 崩溃，**按崩溃级处理**：还原变量名或删掉方括号。
- **译文裸 `%`**（`50%都是油`）在 safe_text=False 下也崩，写 `%%`。

### 显示级

- `{}` 标签新旧不一致、全角伪标签 `【i】`、空译文、`[]` 插值不匹配。
- 插值旗标丢失：原文 `[x!t]` 译文删成 `[x]`，值通道断；译文**补 `!t` 合法不报**。
- 新增换行符：译文换行数超过原文。
- 残留日文假名：译文夹 `そりゃ` 这类残片，汉字不算——`先輩` 不报；`--lang ja*`（目标语言为日语）时自动跳过。

### 提示级

- new==old 的未翻译行、含拉丁字母或日文假名的整句未翻译；**不计入退出码**。

## 行为细节

- 递归扫描 `tl/<lang>/` 全部子目录（发行项目常按 game/ 目录镜像分层，如
  `Girls Scripts/`），报告里的文件标识是相对 tl 的路径；只扫顶层的旧版会
  漏掉大多数翻译文件（实测 AfterDark 0.26：顶层 10 个 vs 实际 70 个）。
- 识别项目自定义文本标签：`config.custom_text_tags["x"]` /
  `renpy.register_text_tag("x")` 并入已知标签，`config.self_closing_custom_text_tags`
  按不接受关闭处理——动态文本游戏（kinetic_text_tags 类）的 `{chaos}`/`{bt}`
  不再误报"未知标签/关闭无开放标签"。
- 按引擎源码模拟：标签大小写敏感、花括号内空格不剥离。
- 说话人正则支持带点表达式（`mc.name`）、下标（`the_group[0]`）、引号字面量（`"Janitor"`）——Lab Rats 2 类游戏台词不再漏检。
- `--fix` 自动修机械性问题：`%(变量名被翻)` 还原、`{ i }`/`{/B}` 规范化。
- `--fix --add-tflag`：给译文中与原文一致的裸插值补 `!t` 旗标（值先过 strings 表，`[mc.name]` 中文名显示必需；`[x:.1f]` 等格式规格与含裸 `!` 的表达式自动跳过）。
- 输出行号是**译文行**，直接定位要改的行。

## 相关

- 发行版常把 .mp3/.ttf 直接放 game/ 根目录，`check_assets` 已扫描根目录。
- tl 目录之外的 .rpy 侧质检（空译文/名字框漏译/变量完整性/崩溃风险）走 `renpy-tools-cli`，见 [tools_boundaries.md](tools_boundaries.md)。
