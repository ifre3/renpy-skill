#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backup.py — Ren'Py 工具集共享备份模块

功能:
  在工具首次修改某个文件之前，自动将该文件拷贝为同目录下的 .bak 文件。
  若 .bak 已存在则跳过，确保最原始版本被永久保留。

用法:
  from backup import create_bak
  create_bak("/path/to/script.rpy")   # 首次调用生成 script.rpy.bak
  create_bak("/path/to/script.rpy")   # 再次调用跳过（.bak 已存在）

设计原则:
  - 幂等: 多次调用安全，不会覆盖已有 .bak
  - fail closed: 备份失败会抛出异常，调用方不得继续覆盖原文件
  - 透明: 调用方无需额外参数，在写入文件前一行调用即可
"""

import os
import shutil
import tempfile


def ensure_bak(filepath):
    """确保备份存在；备份创建失败时抛出异常。

    本函数与兼容入口 :func:`create_bak` 都采用 fail-closed 语义。写回翻译的
    推荐路径是 :func:`atomic_write_text(..., backup=True)`，可同时避免备份失败
    和写入中断导致原文件损坏。
    """
    if not os.path.isfile(filepath):
        raise FileNotFoundError(filepath)

    bak_path = filepath + ".bak"
    if os.path.lexists(bak_path):
        if not os.path.isfile(bak_path):
            raise IsADirectoryError(f"备份路径不是文件: {bak_path}")
        return False

    shutil.copy2(filepath, bak_path)
    return True


def create_bak(filepath):
    """为文件创建 .bak 备份（仅首次）。

    在 filepath 同目录下生成 ``<filename>.bak``。若备份已存在则不覆盖。
    为兼容旧调用方保留此名称；与 :func:`ensure_bak` 一样采用 fail-closed
    语义，备份失败会抛出异常，防止调用方继续覆盖原文件。
    """
    try:
        return ensure_bak(filepath)
    except OSError as e:
        print(f"  [ERROR] 备份失败，已阻止写入: {filepath}: {e}")
        raise


def atomic_write_text(
    filepath,
    text,
    *,
    encoding="utf-8",
    backup=False,
    newline=None,
):
    """以同目录临时文件 + ``os.replace`` 原子写回文本。

    Args:
        filepath: 目标文件。
        text: 要写入的完整文本。
        encoding: 文件编码，默认 UTF-8（无 BOM）。
        backup: 写回前是否强制确保 ``.bak`` 存在。
        newline: 传给 ``open`` 的换行模式；``None`` 使用平台默认值。

    备份或写入失败时保留原文件，并清理临时文件。
    """
    filepath = os.path.abspath(filepath)
    directory = os.path.dirname(filepath) or "."

    if backup:
        ensure_bak(filepath)

    # 避免调用方传入 CRLF 文本时，文本层再把每个 \n 转成 \r\n 而产生
    # \r\r\n。newline='' 表示调用方要求原样写入。
    target_newline = os.linesep if newline is None else newline
    if target_newline == "\n":
        text = text.replace("\r\n", "\n").replace("\r", "\n")
    elif target_newline in ("\r", "\r\n"):
        text = text.replace("\r\n", "\n").replace("\r", "\n")

    fd, temp_path = tempfile.mkstemp(
        prefix=f".{os.path.basename(filepath)}.",
        suffix=".tmp",
        dir=directory,
        text=True,
    )
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline=newline) as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())

        # 尽量保留原文件权限；元数据中的 mtime 应由本次写入自然更新。
        if os.path.exists(filepath):
            os.chmod(temp_path, os.stat(filepath).st_mode)

        os.replace(temp_path, filepath)
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def create_bak_multi(filepaths):
    """批量为多个文件创建 .bak 备份。

    Args:
        filepaths: 文件路径列表

    Returns:
        int: 成功创建备份的文件数
    """
    count = 0
    for fp in filepaths:
        if create_bak(fp):
            count += 1
    return count
