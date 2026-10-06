# Ren'Py 工程进阶工具速查

> rpyc 反编译 / rpa 解包的工具选型、版本坑、场景命令已统一收在 [player_tools.md](player_tools.md)（rpycdec 优先，含 unrpyc 8.5 边界与 unrpa RPA-3.0 失败报告），本文件不再重复；反编译另可用已装的 **renpy-script-decompile** 技能。

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

> ⚠️ **方法 2 的边界（AfterDark 0.26 实测踩坑）**：若游戏自己在 say/preferences 屏里
> 写了 `font persistent.xxx`（无障碍字体机制、显示时求值），它的优先级**高于**
> translate style/python 的覆盖——表现为「按钮正常、对白异常」。
> `check_fonts.py` 会检测这种机制并预警；解法是把该行表达式改成语言感知：
> `font ("Fonts/SourceHanSansLite.ttf" if _preferences.language == "schinese" else persistent.pref_text_font)`

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

## 二、RPA 与补丁投放的关键结论

工具命令见 [player_tools.md](player_tools.md)，这里只留三条加载优先级结论：

- Ren'Py 引擎加载时，会优先加载**非打包的文件**：`game/` 根目录下的同名 `.rpy` 覆盖 `.rpyc`，`.rpa` 内的文件优先级最低
- 所以做汉化/Mod 补丁**无需重新打包**：直接把修改过的 `.rpy` 放进 `game/` 即可生效，删除即还原
- 部分游戏 RPA 用自定义密钥（非默认 0xDEADBEEF），需要逆向或猜测

**版权与授权**: 反编译/解包仅供学习、汉化、合法 MOD 使用，尊重原作者权利；字体商用前检查协议（Noto/思源是 SIL OFL，可商用）。

---

## 三、下载加速 & 国内镜像大全

### 3.1 Ren'Py SDK 下载

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

### 3.2 Gradle 国内镜像（Android 打包最关键）

Ren'Py 打 Android 包时会自动下载 Gradle 和 Maven 依赖。**这是最常见的卡死点**。

#### 3.2.1 修改 Gradle Wrapper（下载 Gradle 本身）

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

#### 3.2.2 修改 Maven 仓库镜像（下载依赖包）

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

#### 3.2.3 全局配置（所有 Gradle 项目生效）

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

### 3.3 pip 国内源

| 源 | 地址 |
|----|------|
| 清华大学 | `https://pypi.tuna.tsinghua.edu.cn/simple` |
| 阿里云 | `http://mirrors.aliyun.com/pypi/simple/` |
| 中科大 | `https://pypi.mirrors.ustc.edu.cn/simple/` |

临时使用：
```bash
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple rpycdec
```

永久配置（Windows `%USERPROFILE%\pip\pip.ini`）：
```ini
[global]
index-url = https://pypi.tuna.tsinghua.edu.cn/simple
[install]
trusted-host = pypi.tuna.tsinghua.edu.cn
```

### 3.4 GitHub Release 通用加速

```
# 原链接
https://github.com/user/repo/releases/download/v1.0/file.zip

# 加速代理（ghproxy.net / gh-proxy.com 当前存活；实例经常变动，先查聚合页 https://ghproxy.link）
https://ghproxy.net/https://github.com/user/repo/releases/download/v1.0/file.zip
```

适用：Ren'Py SDK / rpatool / unrpyc / 字体文件 等所有 GitHub 资源。

> **已死的旧方案，网上旧教程仍在传，别用**：`mirror.ghproxy.com`（域名被拿下）、`hub.fastgit.xyz`（FastGit 已停服）。免费镜像易死，下载失败先到聚合页换活实例，或改用本地加速（Watt Toolkit / FastGithub）。

### 3.5 Ren'Py 编译加速实用建议

- **Android 打包首次编译**极其漫长（Gradle + SDK 几 G），建议晚上睡觉前跑；或**预先手动下载** Gradle 包放到 `%USERPROFILE%\.gradle\wrapper\dists\` 下跳过自动下载
- **Web 版 (WASM)** 需下载 emscripten SDK，同样建议走 GitHub 加速代理（见 3.4）
- **Windows 打包**最快，基本没什么外部依赖
- **关闭杀毒软件**实时扫描能显著提升 Ren'Py 编译速度（生成的大量 .rpyc 文件会被扫描）
