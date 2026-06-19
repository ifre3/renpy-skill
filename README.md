# Ren'Py Skills

the skill package for Ren'Py 8.x development, encapsulating most of the Ren'Py 8.x syntax. This project is in early stages and was developed collaboratively with AI tools.

## Included Skills

| Skill | Trigger | Purpose |
|-------|---------|---------|
| `renpy-dev` | Engineering toolchain | Packaging, linting, testing, diagnostics, exporting |
| `renpy-user` | Content creation | Writing scenes, building projects, setting visuals, affection systems, galleries |

## Quick Start

```bash
# Enable both skills
hermes skill enable renpy-dev
hermes skill enable renpy-user
```

## Directory Structure

```
my/
├── renpy-dev/          # Development tools skill (self-contained unit)
│   ├── SKILL.md        # Skill definition and documentation
│   ├── scripts/        # Python tool scripts
│   └── references/     # SDK configuration reference
├── renpy-user/         # Content creation skill (self-contained unit)
│   ├── SKILL.md        # Skill definition and documentation
│   ├── scripts/        # Python scripts (scaffold/bridge/patterns)
│   └── references/     # Patterns API and common pitfalls
└── README.md           # This file
```

## Maintenance Notes

- Each skill is a **self-contained independent unit** — no code sharing across skills
- `_version_guard.py` is duplicated in both skills by design (required by skill spec)
- `.gitignore` only excludes runtime artifacts: `__pycache__/`, `*.pyc`, `*.pyo`, `.env`
- Build artifacts (`my.zip`) and diagnostic reports (`say.md`) are excluded and should not be committed
- After modifying any skill, run `hermes skill validate <name>` to check syntax

## Development Tips

- When adding new features, update the corresponding skill's Trigger table in `SKILL.md`
- Refer to the `hermes-agent-skill-authoring` skill for complete SKILL.md authoring conventions

## Status

- **Stage:** Early development
- **Target SDK:** Ren'Py ≥ 8.0
- **Collaboration:** Built with AI assistance
