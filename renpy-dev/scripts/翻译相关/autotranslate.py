#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
autotranslate.py — Ren'Py TL 增量批量翻译工具（统一管线）

能力一览:
    - 增量: 只翻译空条目，跳过已翻译；--skip-same 跳过原文=译文
    - 批量: 按字符数分批（默认 ~1000 字符/批），不截断句子
    - 断点续传: 缓存进度，中断后再次运行从未完成处继续
    - 标签保护: 使用 ``{{P1}}`` 占位符保护标签、变量和转义
    - 标签校验: 译文回填前检查格式标记数量、完整性和标签嵌套
    - 变量保护: [c_mc_name!t] 等变量及标志隐藏在占位符中
    - 术语表预替换: --glossary 加载 JSON，在发给 LLM 前统一英文人名
    - 安全: 原子写入 + 强制 .bak 备份 + 原文/行号/角色三重匹配
    - 限速: 429 自动退避重试
    - 可配置: --api-url / --api-key / --model / --max-chars 命令行覆盖
    - JSON 回填: --input 从 JSON 文件加载翻译结果直接回填

用法:
    python autotranslate.py scan      <tl_dir> [--dry-run] [--skip-same]
    python autotranslate.py translate <tl_dir> [--api-url URL] [--api-key KEY]
                                     [--model NAME] [--max-chars N] [--skip-same]
                                     [--retry-failed]
    python autotranslate.py apply     <tl_dir> [--dry-run]
    python autotranslate.py apply     <tl_dir> --input translations.json
    python autotranslate.py status    <tl_dir>

复用模块:
    - check_untranslated.py: scan_file / collect_rpy_files / has_real_text
    - 公共/backup.py: atomic_write_text
"""

import argparse
import json
import os
import re
import sys
import time
from collections import Counter

try:
    import requests
except ImportError:  # scan/apply/status 不依赖 requests
    requests = None

# UTF-8 输出（Windows 终端兼容）
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# 让本脚本能 import 同目录和上级目录的模块
_HERE = os.path.dirname(os.path.abspath(__file__))
_TOOLS = os.path.dirname(_HERE)
_BACKUP_DIR = os.path.join(_TOOLS, "公共")
for p in (_HERE, _TOOLS, _BACKUP_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from check_untranslated import scan_file, collect_rpy_files, has_real_text  # noqa: E402
from backup import atomic_write_text  # noqa: E402
from rpy_syntax import (  # noqa: E402
    encode_rpy_string_content,
    iter_bracket_spans,
    parse_new_line,
    parse_old_line,
    parse_original_comment,
    parse_translation_line,
    replace_literal_content as replace_rpy_literal_content,
)


# ============================================================================
# 配置
# ============================================================================

DEFAULT_CONFIG = {
    # 不内置任何服务端点：用 --api-url 参数或环境变量 RENPY_TRANSLATE_API_URL
    # 指定 OpenAI 兼容端点。密钥绝不写入源码，优先 RENPY_TRANSLATE_API_KEY。
    "api_url": os.environ.get("RENPY_TRANSLATE_API_URL", ""),
    "api_key": os.environ.get("RENPY_TRANSLATE_API_KEY"),
    "model": "auto",
    "source_language": "English",
    "target_language": "Simplified Chinese",
    "batch_chars": 1000,  # 每批约 N 字符
    "batch_interval_sec": 1.5,  # 批与批之间的间隔
    "request_timeout": 120,
    "max_retries": 2,
    "temperature": 0.6,
}


def load_config(args=None):
    """返回配置，优先用命令行参数覆盖默认值。"""
    cfg = dict(DEFAULT_CONFIG)
    if args is not None:
        if getattr(args, "api_url", None):
            cfg["api_url"] = args.api_url
        if getattr(args, "api_key", None):
            cfg["api_key"] = args.api_key
        if getattr(args, "model", None):
            cfg["model"] = args.model
        if getattr(args, "max_chars", None):
            cfg["batch_chars"] = args.max_chars
        if getattr(args, "glossary", None):
            cfg["glossary_path"] = args.glossary
    return cfg


# ============================================================================
# 术语表预替换
# ============================================================================


def load_glossary(glossary_path):
    """加载术语表 JSON，返回 {en_name: zh_name} 字典。

    支持两种格式:
      1. {"Tomori": "灯里", ...}          — 直接映射
      2. [{"en": "Tomori", "zh": "灯里"}, ...] — 列表格式
    """
    if not glossary_path or not os.path.isfile(glossary_path):
        return {}
    with open(glossary_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        return {k: v for k, v in data.items() if k and v}
    if isinstance(data, list):
        result = {}
        for item in data:
            if isinstance(item, dict):
                en = item.get("en") or item.get("english") or item.get("original")
                zh = item.get("zh") or item.get("chinese") or item.get("translation")
                if en and zh:
                    result[en] = zh
        return result
    return {}


def apply_glossary(text, glossary):
    """在英文原文中把人名替换为标准中文译名。

    使用 \b 单词边界 + 精确匹配，不误伤子串。
    例如 "Tomori" 不会匹配 "Tomorin"，"Li" 不会匹配 "Like"。

    在 protect_rpy_tags 之后调用，标签已被替换为 {{Pn}} 占位词，
    不会误伤标签内容。
    """
    if not glossary:
        return text
    for en_name, zh_name in glossary.items():
        pattern = r'\b' + re.escape(en_name) + r'\b'
        text = re.sub(pattern, zh_name, text)
    return text


# ============================================================================
# 缓存
# ============================================================================

CACHE_FILENAME = ".autotranslate_cache.json"


def cache_path(tl_dir):
    return os.path.join(tl_dir, CACHE_FILENAME)


def load_cache(tl_dir):
    """加载翻译缓存。不存在或损坏时返回空骨架。"""
    path = cache_path(tl_dir)
    skeleton = {"tl_dir": os.path.abspath(tl_dir), "entries": []}
    if not os.path.isfile(path):
        return skeleton
    try:
        with open(path, "r", encoding="utf-8-sig") as stream:
            data = json.load(stream)
    except (OSError, ValueError):
        return skeleton
    if not isinstance(data, dict) or not isinstance(data.get("entries", []), list):
        return skeleton
    data.setdefault("tl_dir", os.path.abspath(tl_dir))
    data["entries"] = [entry for entry in data["entries"] if isinstance(entry, dict)]
    return data


def save_cache(tl_dir, cache):
    """原子写缓存，避免进程中断留下半个 JSON。"""
    path = cache_path(tl_dir)
    cache["tl_dir"] = os.path.abspath(tl_dir)
    payload = json.dumps(cache, ensure_ascii=False, indent=2)
    atomic_write_text(path, payload, encoding="utf-8")


def entry_key(entry):
    """缓存身份包含原文，防止源文件变化后误用旧行号缓存。"""
    return (
        entry.get("file"),
        entry.get("line"),
        entry.get("type"),
        entry.get("char", ""),
        entry.get("orig", ""),
    )


# ============================================================================
# 扫描（复用 check_untranslated）
# ============================================================================


def collect_pending(tl_dir, skip_same=False):
    """扫描所有 .rpy，返回待翻译条目列表。

    每条: {"file": 相对路径, "line": 行号, "type": tb/on/cd, "orig": 原文}
    skip_same=False (默认): 只收空译文 new ""
    skip_same=True: 也收原文=译文的条目
    """
    rpy_files = collect_rpy_files(tl_dir)
    pending = []
    for rpy in rpy_files:
        items = scan_file(rpy, strict=not skip_same)
        if not items:
            continue
        rel = os.path.relpath(rpy, tl_dir).replace(os.sep, "/")
        for it in items:
            orig = it["orig"]
            if not has_real_text(orig):
                continue
            # strict=True 只返回 empty；strict=False 返回 empty + same
            # skip_same=True 时 strict=False，两者都收
            # skip_same=False 时 strict=True，只收 empty
            entry = {
                "file": rel,
                "line": it["line"],
                "type": it["type"],
                "orig": orig,
            }
            if it["type"] == "cd":
                entry["char"] = it.get("char", "")
            pending.append(entry)
    return pending


# ============================================================================
# 分批
# ============================================================================


def make_batches(entries, max_chars):
    """按字符数累加分批，返回 [[entry,...], ...]。

    单条超过 max_chars 时单独成批（不切割原文）。
    """
    batches = []
    cur = []
    cur_chars = 0
    for e in entries:
        n = len(e["orig"])
        if cur and cur_chars + n > max_chars:
            batches.append(cur)
            cur, cur_chars = [], 0
        cur.append(e)
        cur_chars += n
    if cur:
        batches.append(cur)
    return batches


# ============================================================================
# Ren'Py 标签保护 —— 占位词方案，防止 API 丢掉 {tag} 和 [var]
# ============================================================================
# 原理: 把 {i}, {/i}, [c_mc_name] 等替换为 {{P1}} {{P2}} 占位符。
# {{Pn}} 是 Jinja2/Mustache 通用模板语法，LLM 训练数据中见过大量样本，
# 天然当变量保留而非当标点删除。
# 纯 ASCII，所有 tokenizer 100% 覆盖。
# 同一标签字符串始终映射到同一编号，便于校验。
# 变量的 !t 标志被隐藏，LLM 无法擅自添加或删除。


# 一次扫描同时保护：已有占位符、反斜杠转义、Ren'Py 的 [[ / {{ 转义、
# 文本标签和变量。负向前瞻可避免把 {{color}} 的内部误识别为标签。
_PROTECT_RE = re.compile(
    r"\{\{P\d+\}\}"
    r"|\\(?:[^\r\n]|$)"
    r"|\[\["
    r"|\{\{(?=[^{])"
    r"|(?<!\{)\{(?!\{)[^}\n]+\}(?!\})"
    r"|(?<!\[)\[[a-zA-Z_][a-zA-Z0-9_]*(?:![A-Za-z]+)?\](?!\])"
)


def _format_spans(text):
    """返回所有需保护格式片段的非重叠半开区间。"""
    spans = {
        (match.start(), match.end()) for match in _PROTECT_RE.finditer(text or "")
    }
    spans.update(iter_bracket_spans(text or ""))

    merged = []
    for start, end in sorted(spans):
        if merged and start < merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def protect_rpy_tags(text):
    """将 Ren'Py 标签和变量替换为 {{Pn}} 占位词。

    返回 (protected_text, placeholder_map)。
    placeholder_map: {"P1": "{i}", "P2": "{/i}", "P3": "[c_mc_name]"}。
    同一标签字符串始终映射到同一编号。
    """
    placeholder_map = {}  # "P1" -> "{i}"
    reverse_map = {}  # "{i}" -> "P1"
    counter = [0]

    def register(original):
        if original in reverse_map:
            return "{{" + reverse_map[original] + "}}"
        counter[0] += 1
        placeholder = "P" + str(counter[0])
        placeholder_map[placeholder] = original
        reverse_map[original] = placeholder
        return "{{" + placeholder + "}}"

    chunks = []
    cursor = 0
    for start, end in _format_spans(text):
        chunks.append(text[cursor:start])
        chunks.append(register(text[start:end]))
        cursor = end
    chunks.append(text[cursor:])
    return "".join(chunks), placeholder_map


def restore_rpy_tags(text, placeholder_map):
    """将 {{Pn}} 占位词还原为原始 Ren'Py 标签。"""
    for p, original in placeholder_map.items():
        text = text.replace("{{" + p + "}}", original)
    return text


# ============================================================================
# API 调用
# ============================================================================

SYSTEM_PROMPT_TEMPLATE = """你是专业的 Galgame/视觉小说字幕翻译。将{source}翻译为{target}。

这是游戏对白和旁白，请按以下要求翻译：

【风格要求】
1. 口语化、像真人说话——拒绝翻译腔，不要直译英文语法结构（从句嵌套、被动语态、定语堆叠）
2. 用中文短句、停顿、语气词（啊、呢、嘛、吧、哦），让台词自然
3. 保留原文情绪和标点节奏：感叹号(!)、问号(?)、省略号(...)、破折号(——) 都原样对应
4. 旁白用第一人称口吻（中文习惯），保留角色的吐槽、自嘲、幽默感
5. 译文长度尽量接近原文，不要明显膨胀（游戏文本框有显示限制）

【内容忠实性】
- 忠实处理原作中的全部内容，不回避、不淡化、不省略、不美化
- 粗俗、幽默、成人或其他敏感内容都应按原文语气直译
- 不自行删改情节、动作、程度词或角色态度

【Ren'Py 格式保护（绝对不能改）】
- 文本中出现的 {{{{P1}}}} {{{{P2}}}} {{{{P3}}}} 等是格式占位符，代表原文中的样式标签和变量
- 占位符必须原样保留在译文中，位置对应到翻译后的中文内容上
- 不能删除、合并、拆分、新增任何占位符
- 占位符数量必须与原文完全一致

【标签位置规则（最重要）】
- {{{{P1}}}} 和 {{{{P2}}}} 是成对的开闭标签，包裹的是强调内容
- 示例：原文 "It was {{{{P1}}}}really{{{{P2}}}} good." -> 译文 "{{{{P1}}}}真的{{{{P2}}}}很好。"
- 示例：原文 "She is {{{{P1}}}}my{{{{P2}}}} friend." -> 译文 "她是{{{{P1}}}}我的{{{{P2}}}}朋友。"
- 如果原文用占位符强调某个词，译文也要用占位符强调对应的中文词
- 单个占位符（如 {{{{P3}}}}）原样保留在译文对应的语义停顿位置

【输出格式】
- 严格输出 JSON 数组，id 与输入一一对应
- 不要加任何解释、Markdown、代码块标记
- 输入 [{{"id":0,"text":"Hi, {{{{P1}}}}name{{{{P2}}}}..."}}]
- 输出 [{{"id":0,"text":"嗨，{{{{P1}}}}名字{{{{P2}}}}……"}}]"""


def call_api(cfg, system_prompt, user_content):
    """调用 OpenAI 格式的 chat/completions，返回 assistant 文本。

    失败抛异常。重试逻辑在外层 do_translate 处理。
    """
    payload = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": cfg["temperature"],
    }
    headers = {"Content-Type": "application/json"}
    if cfg.get("api_key"):
        headers["Authorization"] = f"Bearer {cfg['api_key']}"
    resp = requests.post(
        cfg["api_url"],
        json=payload,
        headers=headers,
        timeout=cfg["request_timeout"],
    )
    resp.raise_for_status()
    obj = resp.json()
    # OpenAI 格式: choices[0].message.content
    return obj["choices"][0]["message"]["content"]


def parse_response(text, batch):
    """从 API 响应中解析出翻译列表，按 id 对应回 batch。

    返回: [(entry, translation), ...]，长度等于 batch。
    解析失败的条目 translation 为 None。
    """
    # 1. 直接 json.loads
    arr = None
    try:
        arr = json.loads(text)
    except ValueError:
        pass

    # 2. 提取 [...] 片段再解析
    if not isinstance(arr, list):
        m = re.search(r"\[.*\]", text, re.DOTALL)
        if m:
            try:
                arr = json.loads(m.group(0))
            except ValueError:
                arr = None

    # 3. 提取 ```json ... ``` 内的数组
    if not isinstance(arr, list):
        m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
        if m:
            try:
                arr = json.loads(m.group(1))
            except ValueError:
                arr = None

    # 按 id 映射回 batch
    by_id = {}
    if isinstance(arr, list):
        for item in arr:
            if not isinstance(item, dict) or "id" not in item or "text" not in item:
                continue
            identifier = item["id"]
            if isinstance(identifier, str) and re.fullmatch(r"\d+", identifier):
                identifier = int(identifier)
            if isinstance(identifier, bool) or not isinstance(identifier, int):
                continue
            if isinstance(item["text"], str):
                by_id[identifier] = item["text"]

    results = []
    for i, entry in enumerate(batch):
        trans = by_id.get(i)
        results.append((entry, trans))
    return results


def _format_tokens(text):
    """提取必须原样保留的标签、变量和转义序列。"""
    text = text or ""
    return [text[start:end] for start, end in _format_spans(text)]


_VARIABLE_TOKEN_RE = re.compile(r"^\[(.+)\]$")
_VARIABLE_FLAG_RE = re.compile(r"^(.*?)(!+[A-Za-z]+)$")


def tags_in_text(text):
    """提取文本中的 Ren'Py 格式标记，返回集合（兼容旧 API）。"""
    return set(_format_tokens(text))


# 成对标签：开标签 -> 闭标签
PAIRED_TAGS = {
    "alpha": "/alpha",
    "alt": "/alt",
    "art": "/art",
    "axis": "/axis",
    "instance": "/instance",
    "feature": "/feature",
    "b": "/b",
    "i": "/i",
    "u": "/u",
    "a": "/a",
    "plain": "/plain",
    "font": "/font",
    "color": "/color",
    "outlinecolor": "/outlinecolor",
    "size": "/size",
    "noalt": "/noalt",
    "s": "/s",
    "shader": "/shader",
    "rt": "/rt",
    "rb": "/rb",
    "k": "/k",
    "cps": "/cps",
}


def _unbalanced_paired_tags(text):
    stack = []
    errors = []
    token_re = re.compile(r"\{(/?)([a-zA-Z]+)(?:=[^}]*)?\}")
    for match in token_re.finditer(text or ""):
        closing, name = match.group(1), match.group(2)
        if name not in PAIRED_TAGS:
            continue
        expected_close = PAIRED_TAGS.get(name)
        if not closing and expected_close:
            stack.append(name)
        elif closing:
            close_name = closing + name
            if not stack:
                errors.append(f"多余闭标签 {{{close_name}}}")
            elif stack[-1] != name:
                errors.append(
                    f"嵌套错误: 期望 {{/{stack[-1]}}}，实际 {{{close_name}}}"
                )
                if name in stack:
                    while stack and stack[-1] != name:
                        stack.pop()
                    if stack:
                        stack.pop()
            else:
                stack.pop()
    if stack:
        errors.append("未闭合标签: " + ", ".join("{" + name + "}" for name in stack))
    return errors


def validate_translation(orig, trans):
    """校验译文是否完整保留变量、标签、转义及标签结构。"""
    issues = []
    if trans is None:
        return ["译文为空（解析失败）"]
    if not trans.strip():
        return ["译文为空字符串"]

    orig_tokens = _format_tokens(orig)
    trans_tokens = _format_tokens(trans)
    orig_vars = []
    trans_vars = []
    orig_other = Counter()
    trans_other = Counter()
    for token in orig_tokens:
        match = _VARIABLE_TOKEN_RE.fullmatch(token)
        if match:
            content = match.group(1)
            flag_match = _VARIABLE_FLAG_RE.match(content)
            if flag_match:
                orig_vars.append((flag_match.group(1), flag_match.group(2).lstrip("!")))
            else:
                orig_vars.append((content, ""))
        else:
            orig_other[token] += 1
    for token in trans_tokens:
        match = _VARIABLE_TOKEN_RE.fullmatch(token)
        if match:
            content = match.group(1)
            flag_match = _VARIABLE_FLAG_RE.match(content)
            if flag_match:
                trans_vars.append((flag_match.group(1), flag_match.group(2).lstrip("!")))
            else:
                trans_vars.append((content, ""))
        else:
            trans_other[token] += 1

    missing = orig_other - trans_other
    extra = trans_other - orig_other
    if missing:
        issues.append(
            "丢失标签/转义: "
            + ", ".join(f"{token}×{count}" for token, count in sorted(missing.items()))
        )
    if extra:
        issues.append(
            "新增/改写格式标记: "
            + ", ".join(f"{token}×{count}" for token, count in sorted(extra.items()))
        )

    orig_var_counts = Counter(name for name, _flag in orig_vars)
    trans_var_counts = Counter(name for name, _flag in trans_vars)
    for name, count in (orig_var_counts - trans_var_counts).items():
        issues.append(f"丢失变量: [{name}]×{count}")
    for name, count in (trans_var_counts - orig_var_counts).items():
        issues.append(f"新增变量: [{name}]×{count}")
    for name in sorted(set(orig_var_counts) & set(trans_var_counts)):
        old_flags = Counter(flag for var_name, flag in orig_vars if var_name == name)
        new_flags = Counter(flag for var_name, flag in trans_vars if var_name == name)
        # 原文无 !t、译文主动增加 !t 是合法翻译修复；原文已有标志时不能丢。
        if any(old_flags) and old_flags != new_flags:
            issues.append(f"变量标志被删除或改写: [{name}]")

    for detail in _unbalanced_paired_tags(trans):
        issues.append("标签结构错误: " + detail)

    # 保留更具体的开闭数量提示，便于人工定位。
    for tag_open, tag_close in PAIRED_TAGS.items():
        orig_open = len(re.findall(r"\{%s(?:=[^}]*)?\}" % re.escape(tag_open), orig))
        orig_close = len(re.findall(r"\{%s\}" % re.escape(tag_close), orig))
        trans_open = len(re.findall(r"\{%s(?:=[^}]*)?\}" % re.escape(tag_open), trans))
        trans_close = len(re.findall(r"\{%s\}" % re.escape(tag_close), trans))
        if orig_open != trans_open:
            issues.append(
                f"{{{tag_open}}}开标签数量不一致(原文{orig_open}译文{trans_open})"
            )
        if orig_close != trans_close:
            issues.append(
                f"{{{tag_close}}}闭标签数量不一致(原文{orig_close}译文{trans_close})"
            )

    return issues


# ============================================================================
# 命令实现
# ============================================================================


def escape_for_rpy(text):
    """把运行时文本转义为双引号 .rpy 字符串内容。"""
    return encode_rpy_string_content(text, '"')


def entry_anchor_matches(lines, entry):
    """验证缓存行号处仍是预期原文，防止陈旧缓存写到错误条目。"""
    try:
        index = int(entry.get("line", 0)) - 1
    except (TypeError, ValueError):
        return False
    if index < 0 or index >= len(lines):
        return False

    expected = entry.get("orig")
    if not isinstance(expected, str):
        return False
    if entry.get("type") == "on":
        parsed = parse_old_line(lines[index])
    else:
        source = parse_original_comment(lines[index])
        parsed = source[0] if source is not None else None
    return parsed is not None and parsed.value == expected


def find_target_line(lines, entry, allow_nonempty=False, max_gap=10):
    """在原文之后查找唯一匹配的译文目标，返回 ``(索引, literal)``。"""
    try:
        start = int(entry.get("line", 0))
    except (TypeError, ValueError):
        return -1, None
    if not entry_anchor_matches(lines, entry):
        return -1, None

    expected_char = entry.get("char", "") if entry.get("type") == "cd" else ""
    for index in range(start, min(start + max_gap, len(lines))):
        line = lines[index]
        if parse_old_line(line) is not None or parse_original_comment(line) is not None:
            break
        if entry.get("type") == "on":
            parsed = parse_new_line(line)
            speaker = ""
        else:
            target = parse_translation_line(line)
            parsed = target[0] if target is not None else None
            speaker = target[1] if target is not None else ""
        if parsed is None:
            continue
        if expected_char and speaker != expected_char:
            continue
        if not expected_char and entry.get("type") == "tb" and speaker:
            continue
        if not allow_nonempty and parsed.value != "":
            continue
        return index, parsed
    return -1, None


def replace_literal_content(line, literal, translated):
    """替换字符串内容并保留缩进、角色前缀、空白及尾部 say 属性。"""
    return replace_rpy_literal_content(line, literal, translated)


def read_text_lines(filepath):
    """读取翻译文件并返回 ``(lines, newline)``，保留原换行风格。"""
    with open(filepath, "r", encoding="utf-8", newline="") as stream:
        content = stream.read()
    newline = "\r\n" if "\r\n" in content else "\n"
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    return normalized.split("\n"), newline


def safe_project_path(base_dir, relative_path):
    """解析翻译目录内路径，拒绝 ``..`` 越界和绝对路径。"""
    if not isinstance(relative_path, str) or not relative_path:
        return None
    if os.path.isabs(relative_path):
        return None
    base = os.path.abspath(base_dir)
    candidate = os.path.abspath(os.path.join(base, relative_path.replace("/", os.sep)))
    try:
        common = os.path.commonpath([base, candidate])
    except ValueError:
        return None
    if os.path.normcase(common) != os.path.normcase(base):
        return None
    return candidate


# ----------------------------------------------------------------------------
# scan
# ----------------------------------------------------------------------------


def cmd_scan(args):
    tl_dir = args.tl_dir
    if not os.path.isdir(tl_dir):
        print(f"Error: 目录不存在: {tl_dir}")
        sys.exit(1)

    print(f"扫描 {tl_dir} ...\n")
    pending = collect_pending(tl_dir, skip_same=getattr(args, "skip_same", False))

    by_file = {}
    for e in pending:
        by_file.setdefault(e["file"], []).append(e)

    if getattr(args, "dry_run", False):
        for e in pending:
            preview = e["orig"][:80].replace("\n", " ")
            print(f"  {e['file']}:{e['line']}  [{e['type']}]  {preview}")
        print()
        print("=" * 50)
        print(f"Total: {len(pending)} 待翻译 (dry-run)")
        return pending

    for e in pending:
        preview = e["orig"][:80].replace("\n", " ")
        print(f"  {e['file']}:{e['line']}  [{e['type']}]  {preview}")

    print()
    print("=" * 50)
    print(f"Total: {len(pending)} 待翻译")
    print(f"Files: {len(by_file)}")
    for f in sorted(by_file):
        chars = sum(len(e["orig"]) for e in by_file[f])
        print(f"  {f}: {len(by_file[f])} 条 / {chars} 字符")
    return pending


# ----------------------------------------------------------------------------
# translate
# ----------------------------------------------------------------------------


def cmd_translate(args):
    tl_dir = args.tl_dir
    if not os.path.isdir(tl_dir):
        print(f"Error: 目录不存在: {tl_dir}")
        sys.exit(1)

    cfg = load_config(args)
    glossary = load_glossary(cfg.get("glossary_path"))
    print(f"API: {cfg['api_url']}")
    print(f"Model: {cfg['model']}")
    print(f"批次大小: ~{cfg['batch_chars']} 字符/批")
    print(f"限速间隔: {cfg['batch_interval_sec']}s/批")
    if glossary:
        print(f"术语表: {cfg.get('glossary_path', '')} ({len(glossary)} 条)")
    else:
        print("术语表: 无")
    print()

    skip_same = getattr(args, "skip_same", False)
    pending = collect_pending(tl_dir, skip_same=skip_same)
    if not pending:
        print("[OK] 没有待翻译条目")
        return
    if requests is None:
        print("[ERROR] translate 需要 requests：python -m pip install requests")
        return 1

    # 加载缓存，构建已完成索引
    cache = load_cache(tl_dir)
    cache["model"] = cfg["model"]
    cache["api_url"] = cfg["api_url"]
    done_keys = {
        entry_key(e)
        for e in cache["entries"]
        if e.get("status") in ("done", "warn")
    }

    # warn 也属于已完成翻译：再次请求 API 只会重复写缓存。警告条目仍会在
    # apply 前保留给用户检查，但不会被自动重翻。
    todo = [e for e in pending if entry_key(e) not in done_keys]
    print(
        f"待翻译: {len(pending)} 总计 / {len(pending) - len(todo)} 已完成 / {len(todo)} 本次处理\n"
    )

    if not todo:
        print("[OK] 全部已完成，可用 apply 写回")
        return

    batches = make_batches(todo, cfg["batch_chars"])
    total_batches = len(batches)
    print(f"分批: {total_batches} 批\n")

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        source=cfg["source_language"], target=cfg["target_language"]
    )

    success = 0
    failed = 0
    warned = 0
    batch_no = 0
    t_start = time.time()

    for batch in batches:
        batch_no += 1
        # 构造请求 JSON（占位词保护 + 术语表预替换）
        batch_protected = []
        batch_maps = []
        for i, e in enumerate(batch):
            protected, pmap = protect_rpy_tags(e["orig"])
            protected = apply_glossary(protected, glossary)
            batch_protected.append({"id": i, "text": protected})
            batch_maps.append(pmap)
        user_json = json.dumps(batch_protected, ensure_ascii=False)

        # 重试
        results = None
        last_err = ""
        for attempt in range(cfg["max_retries"] + 1):
            try:
                resp_text = call_api(cfg, system_prompt, user_json)
                results = parse_response(resp_text, batch)
                break
            except requests.exceptions.HTTPError as e:
                status = e.response.status_code
                body = ""
                try:
                    body = e.response.text[:200]
                except Exception:
                    pass
                last_err = f"HTTP {status}" + (f": {body}" if body else "")

                if status == 429:
                    wait = 5 * (attempt + 1)
                    print(f"  [批 {batch_no}/{total_batches}] 429 限流，等 {wait}s")
                    time.sleep(wait)
                    continue
                if 400 <= status < 500 and status not in (408, 409, 425):
                    print(f"  [批 {batch_no}/{total_batches}] {last_err}（不可重试）")
                    break
                wait = 2**attempt
                print(
                    f"  [批 {batch_no}/{total_batches}] {last_err}，{wait}s 后重试"
                )
                time.sleep(wait)
            except (requests.exceptions.RequestException, ValueError, KeyError) as e:
                last_err = str(e)[:120]
                wait = 2**attempt
                print(f"  [批 {batch_no}/{total_batches}] {last_err}，{wait}s 后重试")
                time.sleep(wait)

        if results is None:
            failed += len(batch)
            for entry in batch:
                cache["entries"].append(
                    {
                        "file": entry["file"],
                        "line": entry["line"],
                        "type": entry["type"],
                        "orig": entry["orig"],
                        "trans": None,
                        "status": "failed",
                        "error": last_err,
                    }
                )
            print(
                f"  [批 {batch_no}/{total_batches}] ✗ 失败 ({len(batch)} 条): {last_err}"
            )
            save_cache(tl_dir, cache)
            time.sleep(cfg["batch_interval_sec"])
            continue

        # 处理本批结果（占位词还原 + 校验）
        batch_summary = []
        for idx, (entry, trans) in enumerate(results):
            pmap = batch_maps[idx]
            if trans:
                trans = restore_rpy_tags(trans, pmap)
            issues = validate_translation(entry["orig"], trans)
            status = "done" if not issues else "warn"
            if issues:
                warned += 1
                batch_summary.append(
                    f"    [WARN] {entry['file']}:{entry['line']} {issues}"
                )
            else:
                success += 1
            cache_entry = {
                "file": entry["file"],
                "line": entry["line"],
                "type": entry["type"],
                "orig": entry["orig"],
                "trans": trans,
                "status": status,
            }
            if entry.get("char"):
                cache_entry["char"] = entry["char"]
            cache["entries"].append(cache_entry)

        elapsed = time.time() - t_start
        print(
            f"  [批 {batch_no}/{total_batches}] ✓ {len(batch)} 条  累计 {success} 成功 / {warned} 警告 / {failed} 失败  ({elapsed:.0f}s)"
        )
        for line in batch_summary:
            print(line)

        save_cache(tl_dir, cache)
        time.sleep(cfg["batch_interval_sec"])

    elapsed = time.time() - t_start
    print()
    print("=" * 50)
    print(f"完成: {success} 成功 / {warned} 警告 / {failed} 失败 / {len(todo)} 总计")
    print(f"耗时: {elapsed:.0f}s  平均: {elapsed / max(len(todo), 1):.1f}s/条")
    if warned:
        print(
            f"\n有 {warned} 条警告（格式可能损坏），默认不会回填；"
            "人工修正缓存或确认后可用 --include-warnings 应用"
        )
    if failed:
        print(f"\n{failed} 条失败，可用 --retry-failed 重试")
    print(f'\n下一步: python autotranslate.py apply "{tl_dir}"')


def cmd_translate_retry(args):
    """重试失败的条目。"""
    tl_dir = args.tl_dir
    cache = load_cache(tl_dir)
    failed_entries = [e for e in cache["entries"] if e.get("status") == "failed"]
    if not failed_entries:
        print("[OK] 没有失败的条目")
        return
    print(f"重试 {len(failed_entries)} 条失败条目...")

    # 从缓存中移除失败条目，让它们重新进入 todo
    cache["entries"] = [e for e in cache["entries"] if e.get("status") != "failed"]
    save_cache(tl_dir, cache)
    # 走正常 translate 流程
    cmd_translate(args)


# ----------------------------------------------------------------------------
# apply
# ----------------------------------------------------------------------------


def cmd_apply(args):
    tl_dir = os.path.abspath(args.tl_dir)
    if not os.path.isdir(tl_dir):
        print(f"Error: 目录不存在: {tl_dir}")
        return 1

    # --input 模式: 从 JSON 文件加载翻译结果直接回填
    input_file = getattr(args, "input", None)
    if input_file:
        return _apply_from_json(
            tl_dir,
            input_file,
            getattr(args, "dry_run", False),
            overwrite=getattr(args, "overwrite", False),
        )

    cache = load_cache(tl_dir)
    allowed_statuses = {"done"}
    if getattr(args, "include_warnings", False):
        allowed_statuses.add("warn")
    done = [
        e
        for e in cache["entries"]
        if e.get("status") in allowed_statuses
        and isinstance(e.get("trans"), str)
        and e.get("trans") != ""
        and not e.get("applied")
    ]
    if not done:
        warning_count = sum(1 for e in cache["entries"] if e.get("status") == "warn")
        print("[ERROR] 缓存中没有可安全应用的翻译，请先运行 translate")
        if warning_count:
            print(
                f"  另有 {warning_count} 条 warn；人工修正缓存后可用 "
                "--include-warnings 应用"
            )
        return 1

    by_file = {}
    for entry in done:
        by_file.setdefault(entry["file"], []).append(entry)

    dry = args.dry_run
    total = 0
    skipped = 0
    print(
        f"准备写回 {len(done)} 条翻译到 {len(by_file)} 个文件"
        + ("（DRY-RUN，不实际写入）" if dry else "")
    )
    print()

    for rel_path, entries in sorted(by_file.items()):
        abs_path = safe_project_path(tl_dir, rel_path)
        if abs_path is None or not os.path.isfile(abs_path):
            print(f"  [SKIP] 非法或不存在的文件路径: {rel_path}")
            skipped += len(entries)
            continue

        lines, newline = read_text_lines(abs_path)

        prepared = []
        for entry in sorted(entries, key=lambda item: item["line"]):
            target, literal = find_target_line(lines, entry, allow_nonempty=False)
            if target < 0:
                print(
                    f"  [SKIP] {rel_path}:{entry['line']} "
                    "原文已变化、目标非空或找不到安全位置"
                )
                continue
            old_line = lines[target]
            new_line = replace_literal_content(old_line, literal, entry["trans"])
            if dry:
                print(f"  [DRY] {rel_path}:{target + 1}")
                print(f"        - {old_line.rstrip()}")
                print(f"        + {new_line}")
            else:
                lines[target] = new_line
            prepared.append((entry, target))

        if dry:
            total += len(prepared)
            skipped += len(entries) - len(prepared)
            continue

        if not prepared:
            skipped += len(entries)
            continue

        try:
            atomic_write_text(
                abs_path,
                "\n".join(lines),
                encoding="utf-8",
                backup=True,
                newline=newline,
            )
        except OSError as exc:
            print(f"  [ERROR] {rel_path} 写入失败: {exc}")
            skipped += len(prepared)
            continue

        for entry, _target in prepared:
            entry["applied"] = True
        total += len(prepared)
        print(f"  {rel_path}: 写入 {len(prepared)} 条")

    if not dry:
        save_cache(tl_dir, cache)

    print()
    print("=" * 50)
    print(f"完成: {total} 写入 / {skipped} 跳过")
    if not dry and total:
        print("已自动备份为 .bak 文件")
        print(f'\n验证: python check_untranslated.py "{tl_dir}"')
    return 0 if total else 1


def _apply_from_json(tl_dir, json_path, dry_run=False, overwrite=False):
    """从 JSON 加载翻译结果并安全回填。

    JSON 格式: ``[{"file": "相对路径", "line": 行号, "type": "tb/on/cd",
    "orig": "原文", "trans": "译文", "char": "角色变量"(cd类型)}, ...]``。

    默认只写空译文并要求行号处的原文完全匹配。覆盖非空译文必须显式传入
    ``--overwrite``；路径越界、格式标记损坏或角色不匹配都会跳过。
    """
    if not os.path.isfile(json_path):
        print(f"Error: JSON 文件不存在: {json_path}")
        return 1

    try:
        with open(json_path, "r", encoding="utf-8-sig") as stream:
            items = json.load(stream)
    except (OSError, ValueError) as exc:
        print(f"Error: 无法读取 JSON: {exc}")
        return 1

    if isinstance(items, dict) and isinstance(items.get("entries"), list):
        items = items["entries"]
    if not isinstance(items, list):
        print("[ERROR] JSON 顶层必须是数组，或含 entries 数组的对象")
        return 1

    valid = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if not isinstance(item.get("trans"), str) or item["trans"] == "":
            continue
        if not isinstance(item.get("orig"), str):
            continue
        if not isinstance(item.get("line"), int) or isinstance(item["line"], bool):
            continue
        if item.get("type", "tb") not in ("tb", "on", "cd"):
            continue
        if safe_project_path(tl_dir, item.get("file")) is None:
            print(f"  [SKIP] 非法路径: {item.get('file')!r}")
            continue
        valid.append(item)

    if not valid:
        print("[ERROR] JSON 中没有结构有效的可回填翻译条目")
        return 1

    by_file = {}
    for entry in valid:
        by_file.setdefault(entry["file"], []).append(entry)

    total = 0
    skipped = len(items) - len(valid)
    print(
        f"从 {json_path} 加载 {len(valid)} 条有效翻译，回填到 {len(by_file)} 个文件"
        + ("（DRY-RUN，不实际写入）" if dry_run else "")
        + ("（允许覆盖非空译文）" if overwrite else "（仅写空译文）")
    )
    print()

    for rel_path, entries in sorted(by_file.items()):
        abs_path = safe_project_path(tl_dir, rel_path)
        if abs_path is None or not os.path.isfile(abs_path):
            print(f"  [SKIP] 文件不存在: {rel_path}")
            skipped += len(entries)
            continue

        lines, newline = read_text_lines(abs_path)

        prepared = []
        for entry in sorted(entries, key=lambda item: item["line"]):
            issues = validate_translation(entry["orig"], entry["trans"])
            if issues:
                print(f"  [SKIP] {rel_path}:{entry['line']} 译文格式异常: {issues}")
                continue
            target, literal = find_target_line(
                lines,
                entry,
                allow_nonempty=overwrite,
            )
            if target < 0:
                print(
                    f"  [SKIP] {rel_path}:{entry['line']} "
                    "原文/角色已变化、目标非空或找不到安全位置"
                )
                continue
            if literal.value == entry["trans"]:
                print(f"  [SAME] {rel_path}:{target + 1} 已经是目标译文")
                continue

            old_line = lines[target]
            new_line = replace_literal_content(old_line, literal, entry["trans"])
            if dry_run:
                print(f"  [DRY] {rel_path}:{target + 1}")
                print(f"        - {old_line.rstrip()}")
                print(f"        + {new_line}")
            else:
                lines[target] = new_line
            prepared.append(entry)

        skipped += len(entries) - len(prepared)
        if dry_run:
            total += len(prepared)
            continue
        if not prepared:
            continue

        try:
            atomic_write_text(
                abs_path,
                "\n".join(lines),
                encoding="utf-8",
                backup=True,
                newline=newline,
            )
        except OSError as exc:
            print(f"  [ERROR] {rel_path} 写入失败: {exc}")
            skipped += len(prepared)
            continue
        total += len(prepared)
        print(f"  {rel_path}: 写入 {len(prepared)} 条")

    print()
    print("=" * 50)
    print(f"完成: {total} 写入 / {skipped} 跳过")
    if not dry_run and total:
        print("已自动备份为 .bak 文件")
    return 0 if total else 1


# ----------------------------------------------------------------------------
# status
# ----------------------------------------------------------------------------


def cmd_status(args):
    tl_dir = args.tl_dir
    pending = collect_pending(tl_dir, skip_same=getattr(args, "skip_same", False))
    cache = load_cache(tl_dir)

    by_file = {}
    for e in pending:
        by_file.setdefault(e["file"], []).append(e)

    done_count = sum(1 for e in cache["entries"] if e.get("status") == "done")
    warn_count = sum(1 for e in cache["entries"] if e.get("status") == "warn")
    failed_count = sum(1 for e in cache["entries"] if e.get("status") == "failed")

    # 已完成但已写回检测：与 pending 取交集判断还剩多少
    done_keys = {
        entry_key(e)
        for e in cache["entries"]
        if e.get("status") in ("done", "warn")
    }
    remaining = [e for e in pending if entry_key(e) not in done_keys]

    print(f"扫描: {len(pending)} 待翻译 ({len(by_file)} 文件)")
    print(f"缓存: {done_count} 已完成 / {warn_count} 警告 / {failed_count} 失败")
    print(f"剩余: {len(remaining)} 待翻译")
    if cache.get("model"):
        print(f"模型: {cache['model']}")
    if remaining:
        chars = sum(len(e["orig"]) for e in remaining)
        print(f"剩余字符量: {chars} (预计 {(chars // 1000) + 1} 批)")


# ============================================================================
# 入口
# ============================================================================


def positive_int(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("必须是大于 0 的整数")
    return number


def main():
    ap = argparse.ArgumentParser(
        description="Ren'Py TL 增量批量翻译工具（统一管线）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  python autotranslate.py scan      "game/tl/schinese"
  python autotranslate.py scan      "game/tl/schinese" --dry-run --skip-same
  python autotranslate.py translate "game/tl/schinese"
  python autotranslate.py translate "game/tl/schinese" --api-url http://127.0.0.1:52704/v1/chat/completions --model glm-5
  python autotranslate.py translate "game/tl/schinese" --skip-same --max-chars 800
  python autotranslate.py translate "game/tl/schinese" -g glossary.json
  python autotranslate.py translate "game/tl/schinese" --retry-failed
  python autotranslate.py apply     "game/tl/schinese" --dry-run
  python autotranslate.py apply     "game/tl/schinese"
  python autotranslate.py apply     "game/tl/schinese" --input translations.json
  python autotranslate.py apply     "game/tl/schinese" --include-warnings
  python autotranslate.py status    "game/tl/schinese"

API key:
  Windows PowerShell: $env:RENPY_TRANSLATE_API_KEY="your-key"
  Git Bash / Linux:   RENPY_TRANSLATE_API_KEY=your-key python autotranslate.py ...
""",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_scan = sub.add_parser("scan", help="扫描待翻译条目")
    p_scan.add_argument("tl_dir")
    p_scan.add_argument("--dry-run", action="store_true", help="只扫描不翻译")
    p_scan.add_argument(
        "--skip-same", action="store_true", help="包含原文=译文条目（默认只扫空译文）"
    )
    p_scan.set_defaults(func=cmd_scan)

    p_trans = sub.add_parser("translate", help="批量翻译，写入缓存")
    p_trans.add_argument("tl_dir")
    p_trans.add_argument("--api-url", help="API 地址 (覆盖默认)")
    p_trans.add_argument(
        "--api-key",
        help="API Key（推荐改用环境变量 RENPY_TRANSLATE_API_KEY，避免泄露）",
    )
    p_trans.add_argument("--model", help="模型名 (覆盖默认)")
    p_trans.add_argument(
        "--max-chars",
        type=positive_int,
        help="每批最大字符数 (覆盖默认)",
    )
    p_trans.add_argument(
        "--glossary", "-g",
        help="术语表 JSON 文件路径（预替换人名，避免 LLM 翻错）",
    )
    p_trans.add_argument("--skip-same", action="store_true", help="也翻译原文=译文条目")
    p_trans.add_argument("--retry-failed", action="store_true", help="只重试失败的条目")
    p_trans.set_defaults(func=cmd_translate)

    p_apply = sub.add_parser("apply", help="把缓存写回 .rpy")
    p_apply.add_argument("tl_dir")
    p_apply.add_argument("--dry-run", action="store_true", help="只预览不写入")
    p_apply.add_argument(
        "--input", help="从 JSON 加载翻译结果回填（非缓存）"
    )
    p_apply.add_argument(
        "--include-warnings",
        action="store_true",
        help="允许应用缓存中 status=warn 的译文（人工确认后使用）",
    )
    p_apply.add_argument(
        "--overwrite",
        action="store_true",
        help="JSON 回填时允许覆盖非空译文（默认禁止）",
    )
    p_apply.set_defaults(func=cmd_apply)

    p_status = sub.add_parser("status", help="显示进度")
    p_status.add_argument("tl_dir")
    p_status.add_argument("--skip-same", action="store_true", help="包含原文=译文条目")
    p_status.set_defaults(func=cmd_status)

    args = ap.parse_args()
    if getattr(args, "retry_failed", False):
        result = cmd_translate_retry(args)
    else:
        result = args.func(args)
    return result if isinstance(result, int) else 0


if __name__ == "__main__":
    sys.exit(main() or 0)
