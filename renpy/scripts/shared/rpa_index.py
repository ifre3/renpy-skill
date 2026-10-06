#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rpa_index.py — 读取 Ren'Py .rpa 归档的文件名清单（不做解包）。

为什么需要：发行版游戏把图片/音频/字体打进 .rpa，而源码引用不带归档名。
check_assets 这类"引用 vs 实际文件"对比工具若只看磁盘，会把归档内的
资源全部误报为缺失（实测 AfterDark 0.26：420 图 + 1566 音频全是误报）。

这里只提取**名字集合**，不读取文件内容，因此不用处理各打包器的逐文件
存储差异（zlib / 原始字节 / prefix 前缀混淆），只解析索引。

支持：
  RPA-3.0  头行 `RPA-3.0 <hex索引偏移> <hex异或密钥>`，索引为 zlib+pickle，
           条目 offset/length 与密钥异或（名字提取用不到 offset，无需还原）
  RPA-2.0  头行 `RPA-2.0 <hex索引偏移>`，索引为裸 pickle，无异或

返回小写归一化（反斜杠→正斜杠）的名字集合；解析失败的单个归档跳过并
返回错误信息，由调用方决定是否提示——资源检查不应因坏包整体阻塞。
"""

import pickle
import zlib
from pathlib import Path


def archive_names(game_dir):
    """收集 game/ 下所有 .rpa 内的文件名。

    返回 (names, errors)：names 为小写名字集合（含目录路径），errors 为
    "归档名: 原因" 字符串列表。
    """
    names, errors = set(), []
    game = Path(game_dir)
    if not game.is_dir():
        return names, ["%s: 不是目录" % game]

    for rpa in sorted(game.glob("*.rpa")):
        try:
            with open(rpa, "rb") as f:
                header = f.readline().split()
                if not header:
                    raise ValueError("空文件头")
                magic = header[0].decode("ascii", "replace")
                if magic == "RPA-3.0" and len(header) >= 3:
                    f.seek(int(header[1], 16))
                    index = pickle.loads(zlib.decompress(f.read()))
                elif magic == "RPA-2.0" and len(header) >= 2:
                    f.seek(int(header[1], 16))
                    index = pickle.loads(f.read())
                else:
                    raise ValueError("未知归档格式 %r" % magic)
            for k in index:
                names.add(str(k).lower().replace("\\", "/"))
        except Exception as exc:  # 单个坏包不阻塞整体检查
            errors.append("%s: %s" % (rpa.name, exc))

    return names, errors


def names_by_ext(names, exts):
    """从归档名字集合里筛出指定扩展名（exts 为小写集合，含点）。

    输出一律小写：archive_names 已归一化小写，这里再兜一层，调用方无需
    关心大小写。"""
    out = set()
    for n in names:
        nl = n.lower()
        dot = nl.rfind(".")
        if dot >= 0 and nl[dot:] in exts:
            out.add(nl)
    return out
