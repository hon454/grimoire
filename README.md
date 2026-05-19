# Grimoire

Grimoire is my personal collection of reusable workflow skills for coding agents.

The repository starts Codex-first and stays compatible with Claude Code where the underlying skill format overlaps. The shared source of truth is `skills/<skill>/SKILL.md`; client-specific metadata lives in `.codex-plugin/` and `.claude-plugin/`.

## Status

This repository is a new public skeleton. It intentionally includes only the starter usage skill for now.

## Contents

- `skills/using-grimoire/SKILL.md`: a starter skill that explains how agents should treat this repository.
- `AGENTS.md`: the source-of-truth agent protocol for this repository.
- `CLAUDE.md`: a symbolic link to `AGENTS.md` for Claude Code compatibility.

## Installation Notes

For Codex-compatible clients, install or reference this repository as a plugin and use the `.codex-plugin/plugin.json` manifest. The Codex manifest points to `./skills/`.

For Claude Code-compatible clients, install or reference this repository as a plugin and use the `.claude-plugin/plugin.json` manifest. The local Claude marketplace catalog in `.claude-plugin/marketplace.json` exposes this repo from `./`.

No Codex local marketplace folder is committed in this skeleton. Add one later only if local marketplace testing or multi-plugin cataloging becomes necessary.

## License

MIT
