# Grimoire

[한국어](README.ko.md)

Grimoire is my personal collection of reusable workflow skills for coding agents.

Grimoire is the source library maintained by `hon454`. Its installable plugin is `archmage`, packaged under `plugins/archmage` for Codex-first use and Claude Code-compatible readers where the underlying skill format overlaps.

## Status

This repository currently exposes the Archmage plugin and repository-local maintenance policy. It does not promise roadmap contents beyond the skills and policy committed here.

## Contents

- `plugins/archmage/`: the installable Archmage plugin package.
- `plugins/archmage/skills/using-grimoire/SKILL.md`: the installable bootstrap skill that requires agents to check and load applicable Grimoire skills before acting.
- `docs/maintaining-grimoire.md`: repository-local policy for changing Grimoire skills, plugin packaging, compatibility files, documentation, and publishing checks.
- `.agents/plugins/marketplace.json`: the Codex marketplace catalog that exposes `archmage` from `./plugins/archmage`.
- `.claude-plugin/marketplace.json`: the local Claude-compatible marketplace catalog that exposes `archmage` from `./plugins/archmage`.
- `AGENTS.md`: the source-of-truth agent protocol for this repository.
- `CLAUDE.md`: a symbolic link to `AGENTS.md` for Claude Code compatibility.

## Installation Notes

For Codex-compatible clients, add this repository as a plugin marketplace:

```bash
codex plugin marketplace add hon454/grimoire
```

Then open the Codex plugin directory and install `archmage` from the Grimoire marketplace:

```text
codex
/plugins
```

The Codex marketplace catalog points to the local plugin path `./plugins/archmage`. Inside that package, `plugins/archmage/.codex-plugin/plugin.json` points to the installable skill directory, including `plugins/archmage/skills/using-grimoire/SKILL.md`.

For Claude Code-compatible local marketplace readers, `.claude-plugin/marketplace.json` exposes `archmage` from `./plugins/archmage`, matching the Archmage metadata in `plugins/archmage/.claude-plugin/plugin.json`.

`docs/maintaining-grimoire.md` is repo-local policy for contributors and agents working in this repository. It is not an installable user workflow.

## License

MIT
