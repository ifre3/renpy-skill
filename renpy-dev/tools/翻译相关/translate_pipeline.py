#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
translate_pipeline.py — 已合并到 autotranslate.py（统一管线）

本文件已废弃。所有功能已合并到 autotranslate.py:
    - scan / translate / apply / status 三步分离
    - 缓存断点续传
    - 标签保护 (protect/restore_rpy_tags)
    - 标签校验 (validate_translation)
    - --api-url / --api-key / --model / --max-chars 命令行覆盖
    - --skip-same / --dry-run / --input JSON 回填
    - cd (角色对话 c_xxx "") 类型回填已支持

用法请参考: python autotranslate.py --help
"""

import sys
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from autotranslate import main  # noqa: E402

if __name__ == "__main__":
    main()
