---
name: using-grimoire
description: Use when an agent needs to understand how to work with the Grimoire skill library, add new spells, or keep Codex and Claude Code compatibility intact.
---

# Using Grimoire

Grimoire is a Codex-first, Claude-compatible collection of workflow skills.

## Core Rule

Shared skill behavior belongs in `skills/<skill>/SKILL.md`. Client-specific setup belongs in `.codex-plugin/` or `.claude-plugin/`.

## When Adding a Spell

1. Choose a stable, literal directory name under `skills/`.
2. Put the complete skill instructions in that directory's `SKILL.md`.
3. Keep the trigger description concrete enough that an agent can decide when to use it.
4. Avoid client-specific tool names unless the skill truly depends on that client.
5. Update repository documentation only for durable facts that changed.

## Compatibility Checks

- `AGENTS.md` remains the source of truth for repository instructions.
- `CLAUDE.md` remains a symbolic link to `AGENTS.md`.
- `.codex-plugin/plugin.json` points to `./skills/`.
- `.claude-plugin/plugin.json` describes the same package identity.
