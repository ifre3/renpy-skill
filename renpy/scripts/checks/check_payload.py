#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""载荷体检：识别 Ren'Py 工程里的混淆载荷，并区分「引流」与「汉化」。

## 为什么要有这个脚本

第三方机翻/整合包常把代码塞进 `config.replace_text` 钩子所在的 blob 里，
形态是多层混淆（`exec(base64.b64decode(...))` → XOR → 再 `exec`），且往往
**引流与汉化同 blob**。拆的时候删错一段，汉化就全没了——这是实录过的事故。

现有 `langcheck`（checks/check_i18n.py）的正则只抓
`exec(zlib.decompress|__import__|eval)`，**不覆盖 `base64.b64decode`**，
实测会漏本次实证形态 `exec(__import__("base64").b64decode(...))`。
本脚本补上这条，并把「哪几行是引流、哪几行是汉化依赖」直接标出行号。

## 三条不可协商的纪律（本脚本只是执行它们）

1. **只静态解，不执行**。解出的源码只做正则匹配，绝不 `exec`/`eval`——
   载荷就是靠执行来做事的，静态分析是唯一安全的读法。
2. **严格只读**：不加开关时不写任何文件，`--out` 才落盘到你在命令行点名的路径。
3. **报告不替人下拆除结论**，只给「证据行号 + 必保留清单」，拆除动作留给
   references/replace_text_hook.md 第 4 节指导的人和 AI。判据半层抜くと事故る。

## 用法

    python renpy-tools-cli.py payloadscan <游戏目录>              # 只打报告
    python renpy-tools-cli.py payloadscan <游戏目录> --out <dir>  # 另存解出的载荷
    python renpy-tools-cli.py payloadscan <游戏目录> --json       # 机器可读

退出码沿用仓库惯例：0 = 没查出载荷，1 = 查出了（**不是崩溃**）。
"""

import argparse
import base64
import json
import os
import re
import sys

_SHARED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shared")
if _SHARED_DIR not in sys.path:
    sys.path.insert(0, _SHARED_DIR)

from base_checker import PROJECT, BaseChecker  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# --------------------------------------------------------------------------
# 形态特征：每种给一个「名字 + 正则 + 怎么静态解出来」
# 现有 langcheck 缺 base64 / codecs / marshal / ctypes 四条，这里补齐。
# --------------------------------------------------------------------------

#: 单行就能认出来的动态执行形态（含 base64 —— 现有检测器漏的那条）
EXEC_LAYER_PATTERNS = (
    ("exec(base64.b64decode)",
     re.compile(r'exec\s*\(\s*(?:__import__\(\s*["\']base64["\']\s*\)\s*\.)?'
                r'b64decode\s*\(')),
    ("exec(base64.b64decode+XOR)",
     re.compile(r'exec\s*\(\s*(?:__import__\(\s*["\']base64["\']\s*\)\s*\.)?'
                r'b64decode\s*\([^)]*\)\s*\)?')),
    ("exec(zlib.decompress)",
     re.compile(r'exec\s*\(\s*zlib\.decompress\s*\(')),
    ("exec(codecs.decode)",
     re.compile(r'exec\s*\(\s*(?:codecs\.)?decode\s*\(')),
    ("marshal.loads",
     re.compile(r'marshal\.loads\s*\(')),
    ("eval(compile(...))",
     re.compile(r'eval\s*\(\s*compile\s*\(')),
    ("exec(eval(...))",
     re.compile(r'exec\s*\(\s*eval\s*\(')),
)

#: 资源侧特征：DLL 加载、伪装文件、网络
CTYPES_RE = re.compile(r'ctypes\.(?:CDLL|WinDLL|OleDLL|cdll\.LoadLibrary)\s*\(')
LOADABLE_RES_RE = re.compile(r'renpy\.(?:loader\.)?(?:load|loadable|file)\s*\(')

#: 引流证据：弹窗/开屏/联网/ banking 式推站
DRAIN_PATTERNS = (
    ("overlay_screens", re.compile(r'config\.overlay_screens\s*(?:=|\.append)')),
    ("define_screen", re.compile(r'renpy\.define_screen\s*\(')),
    ("OpenURL", re.compile(r'OpenURL\s*\(')),
    ("webbrowser.open", re.compile(r'webbrowser\.open\s*\(')),
    ("start_callbacks", re.compile(r'config\.start_callbacks\s*(?:=|\.append)')),
    ("requests/urlopen", re.compile(
        r'(?:requests\.(?:get|post)|urllib\.request\.urlopen|urlopen)\s*\(')),
)

#: 外链域名：http(s):// 与裸 domain
URL_RE = re.compile(r'https?://[^\s"\'\\)\]}，。、）]+')
DOMAIN_RE = re.compile(
    r'\b(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+'
    r'(?:com|cn|net|org|vip|me|top|xyz|io|info|biz|cc|co|club|site|online)\b',
    re.I,
)

#: 汉化依赖：这些【必须保留】，删了汉化就断。
#: `_b_*` 内建别名是本脚本存在的直接原因——上一版拆除时删掉了
#: `_b_globals/_b_hasattr/...` 的定义行，上一层 `exec` 在真实环境里直接
#: NameError，汉化整个消失，而桩验证当时是通过的。名字写死在这里当护栏。
LOCALIZE_PATTERNS = (
    ("config.replace_text", re.compile(r'config\.replace_text\s*(?:=|\.append)')),
    ("builtins 别名 (_b_*)", re.compile(r'^\s*(?:import\s+builtins\s+as\s+_b'
                                       r'|_[a-z_]*\s*=\s*_b\.[a-zA-Z_]+)', re.M)),
)

#: 保护名单：出现在解出代码里就提示「别删」
PROTECTED_NAMES = (
    "_b_globals", "_b_hasattr", "_b_set", "_b_Exception", "_b_str", "_b_int",
    "_b_len", "_b_range", "_b_getattr", "_b_type", "_b_list", "_b_dict",
)

#: 高熵 .dat / 伪装资源：非音频却叫音频后缀，或压缩比异常
AUDIO_SUFFIXES = (".mp3", ".ogg", ".wav", ".opus", ".flac")


def _rel(path, root):
    try:
        return os.path.relpath(path, root).replace("\\", "/")
    except ValueError:
        return str(path)


def iter_candidate_files(game_dir):
    """列出要扫的文件。跳过引擎目录与二进制音频（见 scan_file 说明）。"""
    skip = {"renpy", "lib", "cache", "saves", "tl"}
    out = []
    for dirpath, dirnames, filenames in os.walk(game_dir):
        dirnames[:] = [d for d in dirnames if d not in skip]
        for fn in filenames:
            low = fn.lower()
            if low.endswith((".rpy", ".py")) or low.endswith((".dat", ".bin")):
                out.append(os.path.join(dirpath, fn))
    return sorted(out)


def _try_b64_xor(blob_text, xor_range=range(1, 256)):
    """静态解一层 XOR：返回 (解出的文本, xor_key) 或 (None, None)。

    只做 XOR + utf-8 解码校验，不执行任何东西。判据：解出来得像 Python 源码
    （含 `def ` 或 `import `），才算解对，避免随机字节碰巧 utf-8 通过。
    """
    try:
        raw = base64.b64decode(blob_text, validate=False)
    except Exception:
        return None, None
    for k in xor_range:
        if len(raw) > 65536:
            sample = raw[:65536]
        else:
            sample = raw
        try:
            cand = bytes(b ^ k for b in sample).decode("utf-8", errors="strict")
        except Exception:
            continue
        if ("def " in cand or "import " in cand) and _looks_like_code(cand):
            if len(raw) > len(sample):
                try:
                    cand = bytes(b ^ k for b in raw).decode("utf-8", errors="strict")
                except Exception:
                    continue
            return cand, k
    return None, None


def _xor_int_list(code):
    """解「整数列表 XOR」层：`_x([38, 38, 16, 20, ...])` → 明文。

    这是比字符 XOR 更深的一层：函数名/变量名全部表驱动化，`__builtins__.dict`
    、`'replace_text'`、`'overlay_screens'` 这些关键字都不会以明文出现，所以
    不解码就**永远扫不到真正的承重代码**——正是它让第一版判成「无证据」。
    """
    # key = 列表长度中的众数无用；真正的 XOR key 从函数体 `^ N` 取，可能是 XOR 121
    defs = re.findall(r'def\s+(_[A-Za-z_]\w*)\s*\([^)]*\)\s*:\s*'
                      r'return\s+[^\n]*?\^\s*(\d{1,3})', code)
    defs += re.findall(r'\b(_[A-Za-z_]\w*)\s*=\s*lambda[^:]*:\s*[^\n]*?'
                       r'\^\s*(\d{1,3})', code)
    if not defs:
        return code
    out = code
    for fname, key in defs:
        k = int(key)
        # 阈值不能设太严：`_x([3, 21, 16, 27])` 只有 4 个元素，解出来正是
        # 'ctypes' 这类关键名——卡 `{20,}` 会把它们整批漏掉，导致第二层
        # 永远扫不到 replace_text / overlay_screens（实测过：漏得干干净净）。
        pat = re.compile(re.escape(fname) + r"\s*\(\s*\[([0-9,\s]{7,}?)\]\s*\)")
        # 每次替换后文本变了，从头重新找。单个列表解不出来（多半是 ELF 魔数
        # `[6,60,53,63]` 这类二进制常量）时**跳过它继续**，不能 break——
        # 早期版本一遇失败就退出整个函数，85 处里只解了 1 处，等于没解。
        for _guard in range(20000):
            m = pat.search(out)
            if not m:
                break
            nums = [int(x) for x in re.findall(r"\d+", m.group(1))]
            done = False
            if len(nums) >= 2:
                try:
                    dec = "".join(chr(n ^ k) for n in nums)
                except Exception:
                    dec = ""
                # 解出来必须是可读文本（乱码多为二进制魔数，跳过）
                if dec and all(ch.isprintable() or ch in "\n\t" for ch in dec):
                    out = out[:m.start()] + repr(dec) + out[m.end():]
                    done = True
            if not done:
                # 跳过这一处：占位后继续找下一个
                out = out[:m.start()] + repr("?") + out[m.end():]
    return out


def _apply_named_xor(code, max_layers=4):
    """解「自定义 XOR 函数层」——这是双层载荷的第二层。

    双层载荷形态（本次实证）：第一层 b64decode 出来是**明文源码**，但它本身
    只是定义了一个 XOR 解码函数 `_x(_a)`，真正的 payload 是同一段里对它调用的
    `exec(_x('....'))`。所以要认出 `exec(名字('字面量'))` 这种模式并执行静态 XOR。

    判据：`exec(` 后紧跟一个标识符，再跟一个长字符串字面量，且该文件里这个
    标识符被定义为 `^ <数字>` 的 XOR 函数。全部静态完成，不 eval。
    """
    out = code
    for _ in range(max_layers):
        # 找 `^ <int>` 的 XOR 函数定义，拿到函数名 → key
        xor_defs = dict(re.findall(
            r'def\s+(_[A-Za-z_]\w*)\s*\([^)]*\)\s*:\s*[^\n]*?\^\s*(\d{1,3})', out))
        xor_defs.update(re.findall(
            r'\b(_[A-Za-z_]\w*)\s*=\s*lambda[^:]*:\s*[^\n]*?\^\s*(\d{1,3})', out))
        if not xor_defs:
            break
        changed = False
        for fname, key in xor_defs.items():
            k = int(key)
            # `exec(_x('...'))` 或 `_x('...')` 被赋给变量后再 exec
            for m in re.finditer(re.escape(fname) + r"\s*\(\s*'([^']{200,})'\s*\)",
                                 out):
                blob = m.group(1)
                try:
                    cand = "".join(chr(ord(c) ^ k) for c in blob)
                except Exception:
                    continue
                if _looks_like_code(cand):
                    out = out[:m.start()] + cand + out[m.end():]
                    changed = True
                    break
            if changed:
                break
        if not changed:
            break
    return out


def _scan_recursive(text, source_label, max_depth=3):
    """按层 recursively 解并合并证据：每层都贡献证据行号。

    为什么必须递归：单层扫会得出「未见引流/汉化证据」的错误结论——实证的那条
    载荷的外层确实干净，脏东西全在第二层，只扫外层等于给事故发通行证。
    """
    merged = None
    current = text
    label = source_label
    # 先一路解到不动点（每层可能同时有 int-list / char / base64 三种编码），
    # 再把每一层的证据合并起来。逐层累积而非只取最后一层：外层告诉你"这里有
    # 载荷"，内层告诉你"它到底干什么"，少了哪一半都会误判。
    for depth in range(max_depth):
        hit = scan_code(current, label)
        if hit:
            if merged is None:
                merged = hit
            else:
                for key in ("forms", "drain", "localize"):
                    merged[key] = merged.get(key, []) + hit.get(key, [])
                merged["urls"] = sorted(set(merged.get("urls", []))
                                        | set(hit.get("urls", [])))
                merged["protected"] = sorted(set(merged.get("protected", []))
                                             | set(hit.get("protected", [])))
        prev = None
        nxt = current
        while prev != nxt:
            prev = nxt
            nxt = _xor_int_list(prev)
            nxt = _apply_named_xor(nxt)
            nxt = _apply_base64(nxt)
        if nxt == current:
            break
        current = nxt
        label = f"{source_label} ← 第{depth + 2}层"
    return current, merged


def _apply_base64(code):
    """把 `exec(__import__("base64").b64decode('...'))` 静态换成解码结果。"""
    out = code
    pat = re.compile(
        r'(?:__import__\(\s*["\']base64["\']\s*\)\s*\.\s*)?b64decode\s*\(\s*'
        r'[\'"]([A-Za-z0-9+/=]{200,})[\'"]\s*\)')
    for m in list(pat.finditer(out)):
        try:
            dec = base64.b64decode(m.group(1)).decode("utf-8", errors="replace")
        except Exception:
            continue
        if not _looks_like_code(dec):
            continue
        out = out.replace(m.group(0), repr(dec)[1:-1])
    return out


def _looks_like_code(text):
    """粗判是不是 Python 源码（用于 XOR 爆破的正确性判定）。"""
    hits = sum(1 for tok in ("import ", "def ", "renpy.", "config.", "  ")
               if tok in text)
    printable = sum(1 for ch in text[:2000] if ch.isprintable() or ch in "\n\t")
    denom = min(len(text), 2000) or 1
    return hits >= 2 and printable / denom > 0.9


def _extract_b64_literal(line):
    """从一行里抠出 base64 字面量（可能是 XOR 过的）。"""
    m = re.search(r'["\']([A-Za-z0-9+/=]{200,})["\']', line)
    return m.group(1) if m else None


def scan_code(text, source_label):
    """在一段源码里找形态 / 引流 / 汉化三类证据，行号一并给出。"""
    lines = text.splitlines()
    forms, drain, localize = [], [], []
    urls = set()
    for i, line in enumerate(lines, 1):
        for tag, rx in EXEC_LAYER_PATTERNS:
            if rx.search(line):
                forms.append({"line": i, "form": tag,
                              "snippet": line.strip()[:160]})
                break
        if CTYPES_RE.search(line):
            forms.append({"line": i, "form": "ctypes.CDLL 加载 DLL",
                          "snippet": line.strip()[:160]})
        if LOADABLE_RES_RE.search(line):
            forms.append({"line": i, "form": "renpy 动态资源加载",
                          "snippet": line.strip()[:160]})
        for tag, rx in DRAIN_PATTERNS:
            if rx.search(line):
                drain.append({"line": i, "kind": tag,
                              "snippet": line.strip()[:160]})
        for tag, rx in LOCALIZE_PATTERNS:
            if rx.search(line):
                localize.append({"line": i, "kind": tag,
                                 "snippet": line.strip()[:160]})
        for u in URL_RE.findall(line):
            urls.add(u)
        for d in DOMAIN_RE.findall(line):
            urls.add(d)
    protected = sorted({n for n in PROTECTED_NAMES if n in text})
    if forms or drain or localize or urls:
        return {
            "source": source_label,
            "forms": forms,
            "drain": drain,
            "localize": localize,
            "urls": sorted(urls),
            "protected": protected,
            "lines": len(lines),
        }
    return None


def _is_binary_resource(path):
    return path.lower().endswith(AUDIO_SUFFIXES)


def scan_file(path, game_dir, try_decode=True):
    """扫单个文件（必要时按层递归解混淆），返回 finding 或 None。

    二进制音频默认**不扫**：OGG 元数据里到处是域名/URL（音频商署名、youtube
    链接），实测能刷出上百条假阳性把真警报淹掉——只扫 .rpy/.py/.dat 才有用。
    真要查伪装资源，另行精读。
    """
    if _is_binary_resource(path):
        return None
    rel = _rel(path, game_dir)
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError:
        return None
    try:
        text = raw.decode("utf-8", errors="replace")
    except Exception:
        return None
    if not try_decode:
        return scan_code(text, rel)

    _, merged = _scan_recursive(text, rel)
    return merged


def has_encrypted_dat(game_dir):
    """项目里有没有疑似加密资源（头部不可读的 .dat / .bin）。"""
    for dirpath, dirnames, filenames in os.walk(game_dir):
        dirnames[:] = [d for d in dirnames if d not in ("renpy", "lib", "cache")]
        for fn in filenames:
            if fn.lower().endswith((".dat", ".bin")):
                try:
                    with open(os.path.join(dirpath, fn), "rb") as fh:
                        head = fh.read(8)
                except OSError:
                    continue
                # 纯文本 .dat 不算加密；头部不是可打印 ASCII 就是二进制/加密
                if head and not all(32 <= b < 127 or b in (9, 10, 13) for b in head):
                    return True
    return False


def _default_out_dir(game_root):
    """默认导出目录：`<游戏根>/.renpy-skill-tmp/payload_<时间戳>/`。

    点号前缀在 Windows 是隐藏风格，紧邻 game/ 但不污染观感；由调用方显式
    `--out` 才创建，本脚本不替你把东西写进游戏。
    """
    import time
    return os.path.join(game_root, ".renpy-skill-tmp",
                        "payload_" + time.strftime("%Y%m%d_%H%M%S"))


def collect_findings(game_dir):
    files = iter_candidate_files(game_dir)
    findings = []
    for p in files:
        f = scan_file(p, game_dir)
        if f:
            findings.append(f)
    return findings


def _verdict(f):
    """给一条 finding 下「按哪套流程拆」的建议。**不给具体删哪行**。

    关键区分：有没有**真引流动作**（`overlay_screens`/`define_screen`/联网调用）。
    光有 URL 不算——`.rpy` 里署个资源站链接是常事，把它判成引流会淹没真警报。
    """
    real_drain = bool(f.get("drain"))
    has_urls = bool(f.get("urls"))
    has_local = bool(f.get("localize"))

    if real_drain and has_local:
        return ("二者同 blob：只删引流（见上「引流证据」行号），"
                "replace_text 及其依赖必须保留")
    if real_drain:
        return "疑似引流：可按 overlay_screens/define_screen/联网三类定点删"
    if has_local:
        return "疑似纯汉化：无引流动作证据，建议不动"
    if has_urls:
        return ("仅见外链文本，无引流动作（可能是资源署名/更新检查），"
                "不足以判定为引流")
    return "仅有混淆形态，未见引流/汉化证据：需人工看内层"


def print_report(findings, game_dir):
    if not findings:
        print("[OK] 未发现混淆载荷形态。")
        return 0
    print(f"发现 {len(findings)} 处载荷形态：\n")
    for f in findings:
        src = f.get("source", "?")
        print(f"  ⚠ {src}")
        forms = f.get("forms") or []
        if forms:
            kinds = sorted({x["form"] for x in forms})
            print(f"      形态: {', '.join(kinds)}")
            for x in forms[:3]:
                print(f"        行 {x['line']}: {x['snippet'][:110]}")
        if f.get("xor_key") is not None:
            print(f"      已静态解一层：XOR {f['xor_key']}，"
                  f"内层 {f.get('decoded_chars', 0)} 字符")
        if f.get("drain"):
            lines_n = ", ".join(str(x["line"]) for x in f["drain"][:12])
            kinds = sorted({x["kind"] for x in f["drain"]})
            print(f"      引流证据: {', '.join(kinds)} ({len(f['drain'])} 处, "
                  f"行 {lines_n})")
        if f.get("urls"):
            print(f"      外链域名: {', '.join(f['urls'][:8])}")
        if f.get("localize"):
            lines_n = ", ".join(str(x["line"]) for x in f["localize"][:8])
            kinds = sorted({x["kind"] for x in f["localize"]})
            print(f"      汉化依赖: {', '.join(kinds)} (行 {lines_n})"
                  f"  ← 【必须保留】")
        if f.get("protected"):
            print(f"      保护名单命中: {', '.join(f['protected'][:10])}"
                  f"  ← 删掉这些名字，上一层 exec 会 NameError，汉化全丢")
        print(f"      → {_verdict(f)}")
        print()
    print("拆除前的完整步骤见 references/replace_text_hook.md 第 4 节。")
    print("注：本脚本只静态解混淆层，不执行任何解出的代码。")
    # 能力边界写在报告末尾**一次**，不逐文件重复（早期版本挂在每个 finding 上，
    # 于是每个 .rpy 都"疑似有加密资源"，纯噪音）。
    if has_encrypted_dat(game_dir):
        print("⚠ 项目内含加密 .dat 资源：三层载荷的第三层可能藏在那里，"
              "需 DLL 才能解密，本工具不静态解——"
              "若外层只报「混淆形态」而无证据，真 payload 多半在里面。")
    return 1


def export_decoded(findings, out_path):
    """把解出的内层源码落盘。**只存不执行**，供人/AI 后续精读。"""
    os.makedirs(out_path, exist_ok=True)
    written = []
    for i, f in enumerate(findings, 1):
        code = f.get("decoded_source")
        if not code:
            continue
        name = f"layer{i}_" + re.sub(r'[^\w.-]', "_", f.get("source", str(i)))
        name = (name[:60] or f"layer{i}") + ".py"
        dest = os.path.join(out_path, name)
        with open(dest, "w", encoding="utf-8", errors="replace") as fh:
            fh.write(code)
        written.append(dest)
    index = os.path.join(out_path, "report.txt")
    with open(index, "w", encoding="utf-8", errors="replace") as fh:
        for f in findings:
            fh.write(f"{f.get('source')}\n  {_verdict(f)}\n")
            for x in (f.get("drain") or []):
                fh.write(f"  引流 行{x['line']}: {x['snippet'][:100]}\n")
            for x in (f.get("localize") or []):
                fh.write(f"  汉化 行{x['line']}: {x['snippet'][:100]}\n")
    return written


class PayloadChecker(BaseChecker):
    """载荷体检器（checks/ 侧）。严格只读：不加 `--out` 只打印。

    takes=PROJECT 且不需要 tl 目录——恰恰相反，本检查器最常见的场景正是
    **没有 tl 目录**（第三方机翻），所以 requires_tl=False 是刻意的。
    """

    name = "payloadscan"
    summary = "识别混淆载荷并区分引流/汉化证据（只读）"
    takes = PROJECT
    requires_tl = False

    def run(self, ctx):
        game_dir = str(ctx.project)
        if not os.path.isdir(game_dir):
            return 0
        return print_report(collect_findings(game_dir), game_dir)


#: 门面发现用的实例（契约见 shared/base_checker.py）
CHECKER = PayloadChecker()


def main():
    ap = argparse.ArgumentParser(
        description="扫描 Ren'Py 工程中的混淆载荷，区分引流与汉化证据（只读）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  python check_payload.py <游戏目录>
  python check_payload.py <游戏目录> --out ./dump
  python check_payload.py <游戏目录> --json
""",
    )
    ap.add_argument("project", help="游戏根目录或 game/ 目录")
    ap.add_argument("--out", dest="out_path", nargs="?", const=True,
                    help="把解出的内层源码存到此目录（默认 "
                         "<游戏根>/.renpy-skill-tmp/payload_<时间戳>/）")
    ap.add_argument("--json", dest="json_path",
                    help="输出 JSON 报告到此路径")
    ap.add_argument("-l", "--language", default=None,
                    help="语言代码（本工具不读 tl 目录，仅兼容统一 CLI 透传）")
    args = ap.parse_args()

    project = args.project
    game_dir = os.path.join(project, "game") if os.path.isdir(
        os.path.join(project, "game")) else project
    if not os.path.isdir(game_dir):
        print(f"Error: directory not found: {game_dir}")
        return 1

    findings = collect_findings(game_dir)

    if args.out_path:
        root = project
        out_path = (_default_out_dir(root) if args.out_path is True
                    else str(args.out_path))
        written = export_decoded(findings, out_path)
        print(f"已解出 {len(written)} 份内层源码至 {out_path}（未执行）")

    if args.json_path:
        payload = []
        for f in findings:
            payload.append({
                "source": f.get("source"),
                "forms": f.get("forms", []),
                "drain": f.get("drain", []),
                "localize": f.get("localize", []),
                "urls": f.get("urls", []),
                "protected": f.get("protected", []),
                "verdict": _verdict(f),
            })
        with open(args.json_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        print(f"JSON report: {args.json_path}")
        return 1 if findings else 0

    return print_report(findings, game_dir)


if __name__ == "__main__":
    sys.exit(main() or 0)
