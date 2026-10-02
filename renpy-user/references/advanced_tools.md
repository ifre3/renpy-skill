# Ren'Py 工程进阶工具速查

## 一、字体修改完全指南

### 方法 1：最基础 — 改 gui.rpy（有源码时）

直接修改 `gui.rpy` 中的字体定义：

```renpy
## The font used for in-game text.
define gui.text_font = "fonts/NotoSansSC-Regular.otf"
## The font used for character names.
define gui.name_text_font = "fonts/NotoSansSC-Bold.otf"
## The font used for out-of-game text.
define gui.interface_text_font = "fonts/NotoSansSC-Regular.otf"
## The font used for button text.
define gui.button_text_font = "fonts/NotoSansSC-Regular.otf"
## The font used for choice buttons.
define gui.choice_button_text_font = "fonts/NotoSansSC-Regular.otf"
```

字体文件放到 `game/fonts/` 目录下。

### 方法 2：通过 translate + style 全局替换（汉化时常用）

新建一个 `.rpy` 文件（如 `font_patch.rpy`）：

```renpy
## 方式一：通过 config.font_replacement_map 劫持默认字体
init 200 python:
    config.language = 'chinese'
    if config.language == 'chinese':
        config.font_replacement_map["DejaVuSans.ttf", True,  False] = ("fonts/ch.ttf", True,  False)
        config.font_replacement_map["DejaVuSans.ttf", True,  True]  = ("fonts/ch.ttf", True,  True)
        config.font_replacement_map["DejaVuSans.ttf", False, False] = ("fonts/ch.ttf", False, False)

## 方式二：通过 translate block 覆盖默认 style
translate chinese style default:
    font "fonts/ch.ttf"

translate chinese python:
    gui.button_text_font     = "fonts/ch.ttf"
    gui.glyph_font           = "fonts/ch.ttf"
    gui.interface_text_font  = "fonts/ch.ttf"
    gui.text_font            = "fonts/ch.ttf"
    gui.name_text_font       = "fonts/ch.ttf"
```

**原理**: `config.font_replacement_map` 可以让 Ren'Py 在加载指定字体时，无感替换成你提供的字体。适合汉化时**不修改原脚本**。

### 方法 3：语言实时切换字体（用户可选字体）

```renpy
## 在 preferences 界面中加入字体选择
init python:
    gui.text_font        = gui.preference("font", None)
    gui.name_text_font   = gui.preference("font", None)
    gui.interface_text_font = gui.preference("font", None)

screen preferences():
    ## ... 原有界面 ...
    vbox:
        style_prefix "check"
        label _("字体")
        textbutton _("默认字体") action gui.SetPreference("font", None)
        textbutton "思源黑体"     action gui.SetPreference("font", "fonts/SourceHanSansSC-Regular.otf")
        textbutton "霞鹜文楷"     action gui.SetPreference("font", "fonts/LXGWWenKai-Regular.ttf")
```

### 方法 4：语言切换时联动字体

```renpy
## 语言 + 字体同步切换
screen language_picker():
    vbox:
        textbutton "简体中文":
            action [
                Language("schinese"),
                gui.SetPreference("font", "fonts/NotoSansSC-Regular.otf")
            ]
        textbutton "English":
            action [
                Language(None),
                gui.SetPreference("font", None)
            ]
```

### 字体文件放在哪

```
game/
├── fonts/              # 推荐位置
│   ├── NotoSansSC-Regular.otf
│   ├── NotoSansSC-Bold.otf
│   └── SourceSansPro-Regular.ttf
├── tl/
│   └── schinese/
│       └── fonts/      # 翻译专用字体路径（方法2支持）
│           └── 江西拙楷2.0.ttf
```

### 推荐免费 CJK 字体

| 字体 | 类型 | 下载 |
|------|------|------|
| Noto Sans SC | 无衬线 | Google Fonts |
| Noto Serif SC | 衬线 | Google Fonts |
| 思源黑体 | 无衬线 | GitHub adobe-fonts |
| 思源宋体 | 衬线 | GitHub adobe-fonts |
| 霞鹜文楷 | 楷体 | GitHub lxgw |
| 站酷快乐体 | 手写 | GitHub googlefonts |

---

## 二、.rpyc 反编译（unrpyc）

### 简介
**unrpyc** 是 Ren'Py 脚本反编译器，能将编译后的 `.rpyc` 还原为可读的 `.rpy` 源码。

- GitHub: https://github.com/CensoredUsername/unrpyc
- GitCode 镜像: https://gitcode.com/gh_mirrors/un/unrpyc

### 安装
```bash
git clone https://github.com/CensoredUsername/unrpyc
cd unrpyc
pip install -r requirements.txt
# 或
python setup.py install
```

### 基本使用
```bash
# 反编译单个文件
python unrpyc.py script.rpyc

# 批量处理整个目录
python unrpyc.py game/scripts/

# 覆盖已有输出文件
python unrpyc.py -c script.rpyc

# 导出 AST 语法树（调试用）
python decompiler/astdump.py script.rpyc > ast_output.txt
```

### 版本对应

| unrpyc 分支 | Python | Ren'Py 版本 |
|-------------|--------|-------------|
| master (v2.x) | Python 3.9+ | Ren'Py 8.x ~ 6.18.0 |
| legacy (v1.x) | Python 2.7 | Ren'Py 7.x ~ 6.x |

> **2026-10 版本边界**：master 对 Ren'Py **8.5** 字节码的支持仍在 [PR #265](https://github.com/CensoredUsername/unrpyc/pull/265)，截至 2026-10 未确认合入 master（master 已验证到 8.4）。8.5 编译的游戏反编译失败时，优先改用本机已装的 **renpy-script-decompile** 技能。

### 输出
- 反编译后的 `.rpy` 文件生成在**原 `.rpyc` 同目录**下
- 保留原始代码逻辑和注释（如果有的话）

---

## 三、.rpa 资源解包

### 工具一览

| 工具 | 功能 | 地址 |
|------|------|------|
| **rpatool** | RPA 创建/解包/删除/追加，支持 v2/v3（规范源头 shizmob，**已迁 Codeberg，GitHub 侧停更**：https://codeberg.org/shizmob/rpatool ） | https://github.com/shizmob/rpatool |
| **rpa-toolkit** | .rpa/.rpi 解包/创建 + .rpyc/.rpymc 反编译，活跃维护的现代替代 | https://github.com/regiellis/rpa-toolkit |
| **unrpa** | 只解包，更轻量（⚠️ 2025 起新游戏的 RPA-3.0 档案有解析失败报告，见其 issue #50；失败改用 rpycdec unrpa 或 rpa-toolkit） | https://github.com/Lattyware/unrpa |
| **rpaExtract** | Windows GUI 工具 | renpy.cn 论坛 |

### rpatool 使用

```bash
# 查看档案内容
python rpatool.py -l game.scripts.rpa

# 提取所有文件到当前目录
python rpatool.py -x game.scripts.rpa

# 提取特定文件
python rpatool.py -o output_dir -x archive.rpa script.rpyc ui.png

# 提取时重命名（映射）
python rpatool.py -x test.rpa script.rpyc=/home/foo/output.rpyc

# 创建 RPA 档案（默认 RPAv3）
python rpatool.py -c new.rpa script.rpy sprites/

# 创建 RPAv2 档案
python rpatool.py -2 -c legacy.rpa assets/

# 使用自定义密钥创建（RPAv3）
python rpatool.py -k 12345 -c protected.rpa images/

# 追加文件到已有档案
python rpatool.py -a existing.rpa sprites_new/

# 从档案删除文件（输出到新文件）
python rpatool.py -o new.rpa -d old.rpa foo.jpg
```

### unrpa 使用（轻量解包）

```bash
# 简单解包
python -m unrpa archive.rpa

# 解包到指定目录
python -m unrpa archive.rpa --destination ./output

# debug 模式
python -m unrpa archive.rpa --verbose
```

---

## 四、常用 RPA 结构

```
archive.rpa
├── game/
│   ├── script.rpyc
│   ├── screens.rpyc
│   ├── options.rpyc
│   ├── gui.rpyc
│   └── images/
│       ├── bg.png
│       └── chara.png
```

**注意**:
- Ren'Py 引擎加载时，会优先加载**非打包的文件**（同名 `.rpy` 会覆盖 `.rpyc`）
- 所以汉化补丁通常直接放 `.rpy` 文件到 `game/` 目录，不需要重新打包
- `.rpa` 内的文件比 `game/` 根目录下的文件优先级低

---

## 五、典型工作流

```
提取资源                       修改/翻译                   重新打包（可选）
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ rpatool  │───→│ unrpyc   │───→│ 修改.rpy │───→│ rpatool  │
│ 解压.rpa  │    │ 反编译.rpyc│    │ 改字体/翻译│    │ 回压.rpa  │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
                     │
                     ↓
              ┌──────────┐
              │ 直接放.rpy│（不改rpa，优先级更高）
              └──────────┘
```

**重要**: Ren'Py 加载时，`game/` 根目录下的 `.rpy` 文件优先级高于 `.rpa` 中的 `.rpyc`。所以做补丁时**无需重新打包**，直接把修改过的 `.rpy` 文件放到 `game/` 下即可生效。

---

## 六、注意事项

1. **版权**: 反编译和解包仅供学习/汉化/合法MOD使用，请尊重原作者权利
2. **RPA 密钥**: 部分游戏使用自定义密钥（非默认 0xDEADBEEF），需要逆向或猜测
3. **字体授权**: 字体文件有各自的开源/商用协议，商用前请检查（Noto/思源是 SIL OFL，可商用）
4. **Ren'Py 版本**: 不同版本的 .rpyc 格式可能不同，unrpyc 需要对应版本
5. **路径问题**: Windows 下始终用 `/` 分隔路径，不要用 `\`

---

## 七、下载加速 & 国内镜像大全

### 7.1 Ren'Py SDK 下载

| 渠道 | 地址 | 说明 |
|------|------|------|
| 官网 | https://www.renpy.org/latest.html | 直连慢，推荐下面方式 |
| renpy.cn 国内网盘汇总 | https://www.renpy.cn/thread-50-1-1.html | 蓝奏云/百度云等，更新到 2021.03 停更 |
| GitHub Releases | https://github.com/renpy/renpy/releases | 走 ghproxy 镜像可加速 |

推荐方式：从 GitHub Releases 下载，配合代理（最新稳定版以 https://www.renpy.org/release_list.html 为准，2026-10 为 8.5.3）：

```
# 原地址
https://github.com/renpy/renpy/releases/download/8.5.3/renpy-8.5.3-sdk.7z
# 加速代理（当前存活实例；代理经常变动，先查聚合页 https://ghproxy.link）
https://ghproxy.net/https://github.com/renpy/renpy/releases/download/8.5.3/renpy-8.5.3-sdk.7z
```

Ren'Py 中文文档国内直连：
- renpy.cn 国内镜像: https://www.renpy.cn
- Gitee (码云) 镜像: https://gitee.com/renpy

### 7.2 Gradle 国内镜像（Android 打包最关键）

Ren'Py 打 Android 包时会自动下载 Gradle 和 Maven 依赖。**这是最常见的卡死点**。

#### 7.2.1 修改 Gradle Wrapper（下载 Gradle 本身）

找到 Ren'Py Android 项目下的 `gradle/wrapper/gradle-wrapper.properties`：

```properties
# 将 distributionUrl 替换为国内镜像
distributionUrl=https\://mirrors.cloud.tencent.com/gradle/gradle-8.4-bin.zip
#             ^^^ 腾讯云镜像（推荐，速度快）
```

**腾讯云 Gradle 镜像**（首选）：`https://mirrors.cloud.tencent.com/gradle/`
**阿里云 Gradle 镜像**：`https://mirrors.aliyun.com/macports/distfiles/gradle/`

常用版本：
```
https://mirrors.cloud.tencent.com/gradle/gradle-8.4-bin.zip
https://mirrors.cloud.tencent.com/gradle/gradle-8.0-bin.zip
https://mirrors.cloud.tencent.com/gradle/gradle-7.6.1-bin.zip
```

#### 7.2.2 修改 Maven 仓库镜像（下载依赖包）

Ren'Py Android 构建目录一般在 `Ren'Py SDK/rapt/buildlib/`，修改对应 `build.gradle` 或 `settings.gradle`：

Groovy DSL (`build.gradle`)：
```groovy
repositories {
    maven { url 'https://maven.aliyun.com/repository/public' }
    maven { url 'https://maven.aliyun.com/repository/google' }
    maven { url 'https://maven.aliyun.com/repository/gradle-plugin' }
    maven { url 'https://maven.aliyun.com/repository/jcenter' }
    google()
    mavenCentral()
}
```

Kotlin DSL (`settings.gradle.kts`)：
```kotlin
pluginManagement {
    repositories {
        maven { setUrl("https://maven.aliyun.com/repository/google") }
        maven { setUrl("https://maven.aliyun.com/repository/public") }
        maven { setUrl("https://maven.aliyun.com/repository/gradle-plugin") }
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}
```

#### 7.2.3 全局配置（所有 Gradle 项目生效）

创建 `%USERPROFILE%\.gradle\init.gradle`：

```groovy
allprojects {
    repositories {
        maven { url 'https://maven.aliyun.com/repository/public' }
        maven { url 'https://maven.aliyun.com/repository/google' }
        maven { url 'https://maven.aliyun.com/repository/gradle-plugin' }
        maven { url 'https://maven.aliyun.com/repository/jcenter' }
    }
}
```

### 7.3 pip 国内源

| 源 | 地址 |
|----|------|
| 清华大学 | `https://pypi.tuna.tsinghua.edu.cn/simple` |
| 阿里云 | `http://mirrors.aliyun.com/pypi/simple/` |
| 中科大 | `https://pypi.mirrors.ustc.edu.cn/simple/` |

临时使用：
```bash
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple unrpyc
```

永久配置（Windows `%USERPROFILE%\pip\pip.ini`）：
```ini
[global]
index-url = https://pypi.tuna.tsinghua.edu.cn/simple
[install]
trusted-host = pypi.tuna.tsinghua.edu.cn
```

### 7.4 Android SDK Manager 镜像（已过时，仅存档）

> ⚠️ 本节镜像约为 2016 年代产物，**现已基本失效**。现代做法：直连官方源 + 系统代理，或本地加速工具（Watt Toolkit / FastGithub）。

Android Studio → Preferences → Appearance & Behavior → System Settings → Android SDK → 设置代理：

```
HTTP Proxy Server: mirrors.neusoft.edu.cn
HTTP Proxy Port: 80
☑ Force https://... sources to be fetched using http://...
```

备用镜像：
| 镜像站 | 地址 | 端口 |
|--------|------|------|
| 中国科学院 | mirrors.opencas.cn | 80 |
| 大连东软信息学院 | mirrors.neusoft.edu.cn | 80 |
| 上海 GDG | sdk.gdgshanghai.com | 8000 |

### 7.5 GitHub Release 通用加速

```
# 原链接
https://github.com/user/repo/releases/download/v1.0/file.zip

# 加速代理（ghproxy.net / gh-proxy.com 当前存活；实例经常变动，先查聚合页 https://ghproxy.link）
https://ghproxy.net/https://github.com/user/repo/releases/download/v1.0/file.zip
```

适用：Ren'Py SDK / rpatool / unrpyc / 字体文件 等所有 GitHub 资源。

> **已死的旧方案，网上旧教程仍在传，别用**：`mirror.ghproxy.com`（域名被拿下）、`hub.fastgit.xyz`（FastGit 已停服）。免费镜像易死，下载失败先到聚合页换活实例，或改用本地加速（Watt Toolkit / FastGithub）。

### 7.6 国内主流镜像站汇总

| 镜像站 | 网址 | 覆盖范围 |
|--------|------|----------|
| 阿里云 | mirrors.aliyun.com | Maven/Gradle/pip/npm/Docker |
| 腾讯云 | mirrors.cloud.tencent.com | Gradle/npm/Docker |
| 清华大学 | mirrors.tuna.tsinghua.edu.cn | 全栈 (pip/Maven/系统ISO等) |
| 中科大 | mirrors.ustc.edu.cn | 全栈 |
| 华为云 | mirrors.huaweicloud.com | npm/Maven/pip/Docker |

### 7.7 Ren'Py 编译加速实用建议

- **Android 打包首次编译**极其漫长（Gradle + SDK 几 G），建议晚上睡觉前跑
- 或**预先手动下载** Gradle 包放到 `%USERPROFILE%\.gradle\wrapper\dists\` 下，跳过自动下载
- **Web 版 (WASM)** 需下载 emscripten SDK，同样建议走 GitHub 加速代理（见 7.5）
- **Windows 打包**最快，基本没什么外部依赖
- **关闭杀毒软件**实时扫描能显著提升 Ren'Py 编译速度（生成的大量 .rpyc 文件会被扫描）
- Ren'Py 编译时可用 `--fast` 跳过一些非必要检查
