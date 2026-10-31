# -*- coding: utf-8 -*-
"""Ren'Py 语言码 ↔ 英文展示名映射与默认语言（零依赖叶子模块，只放数据与纯函数）。

## 为什么存在（2026-10-31，第十一批 i18n 参数化）

autotranslate 的翻译 prompt 需要英文语言名（如 "Japanese"），而命令行、
tl 目录名、config.language 用的是 Ren'Py 语言码（如 "japanese"）。过去
`target_language` 写死 "Simplified Chinese"、各检查器 `-l` 默认值各自
硬编码 "schinese"，翻到非中文只能改源码。本模块收口三件事：

- `DEFAULT_LANG`：所有翻译相关 `-l` 参数的唯一默认值出处。
  `tool_registry.DEFAULT_LANG` 从这里 re-export（门面 API 不变）；
- `LANG_DISPLAY_NAMES`：Ren'Py 官方语言码 → 英文展示名。新增语言加一行即可；
- `resolve_language()`：CLI 传入值 → 语言名。语言码自动转展示名，
  自由文本语言名原样透传（AI prompt 认得 "Brazilian Portuguese"）。

语言码与 Ren'Py 官方清单一致：`game/tl/<码>` 目录名、`config.language`
取值、SDK 翻译模板生成命令 `renpy.sh translate <码>` 三处同码。
"""

DEFAULT_LANG = "schinese"

#: Ren'Py 常用语言码 → 英文展示名（给 AI 翻译 prompt 与人类阅读用）。
LANG_DISPLAY_NAMES = {
    "schinese": "Simplified Chinese",
    "tchinese": "Traditional Chinese",
    "japanese": "Japanese",
    "korean": "Korean",
    "english": "English",
    "french": "French",
    "german": "German",
    "spanish": "Spanish",
    "italian": "Italian",
    "russian": "Russian",
    "ukrainian": "Ukrainian",
    "polish": "Polish",
    "czech": "Czech",
    "dutch": "Dutch",
    "portuguese": "Portuguese",
    "brazilian_portuguese": "Brazilian Portuguese",
    "arabic": "Arabic",
    "hebrew": "Hebrew",
    "turkish": "Turkish",
    "vietnamese": "Vietnamese",
    "thai": "Thai",
    "indonesian": "Indonesian",
    "malay": "Malay",
    "filipino": "Filipino",
    "hungarian": "Hungarian",
    "romanian": "Romanian",
    "bulgarian": "Bulgarian",
    "greek": "Greek",
    "finnish": "Finnish",
    "swedish": "Swedish",
    "danish": "Danish",
    "norwegian": "Norwegian",
}


def lang_display_name(code):
    """语言码 → 英文展示名；未知码原样返回（调用方自行兜底）。"""
    return LANG_DISPLAY_NAMES.get(code, code)


def resolve_language(value):
    """CLI 传入值 → 翻译源/目标语言名。

    规则：先按语言码查表（大小写不敏感、容忍首尾空白），命中返回展示名
    （"japanese" → "Japanese"）；未命中视为用户直接给了语言名，原样透传；
    None / 空串原样返回，默认值交给调用方。
    """
    if not value:
        return value
    v = value.strip()
    return LANG_DISPLAY_NAMES.get(v.lower(), v)
