# renpy-skill

Ren'Py 开发技能包。基于 Ren'Py 8.5.3。

## 内容

- **renpy-dev** — 工程工具链：CLI 封装、lint、项目分析、错误诊断、导出迁移
- **renpy-user** — 内容创作：脚本生成、16 种预制模式、项目脚手架

## 用法

```bash
# 设置 SDK 路径
set RENPY_SDK=D:/renpy-8.5.3-sdk

# lint 检查
python cli.py /path/to/project lint --error-code
```

## 预制模式

gallery · cjk_font · splash · nvl_mode · save_load · preferences · credit_roll · day_night · affection · choice_timer · after_load_migration · layeredimage · fault_tolerance · phone · inventory · music_room

## 说明

- 两个 skill 独立，不共享代码
- 兼容 Ren'Py 8.0+
