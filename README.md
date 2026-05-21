# Grimoire

[한국어](README.ko.md)

Grimoire is my personal collection of reusable workflow skills for coding agents.

Grimoire is the source library maintained by `hon454`. Its installable plugins are packaged under `plugins/` for Codex-first use and Claude Code-compatible readers where the underlying skill format overlaps.

## Status

This repository currently exposes the Archmage, Book of Engineering, and Book of Git plugins plus repository-local maintenance policy. It does not promise roadmap contents beyond the skills and policy committed here.

## Contents

- `plugins/archmage/`: the installable Archmage plugin package.
- `plugins/archmage/skills/using-grimoire/SKILL.md`: the installable bootstrap skill that requires agents to check and load applicable Grimoire skills before acting.
- `plugins/book-of-engineering/`: the installable Book of Engineering plugin package.
- `plugins/book-of-engineering/skills/work-briefing/SKILL.md`: the explicit-invocation handoff skill that writes current-state work briefings.
- `plugins/book-of-git/`: the installable Book of Git plugin package.
- `plugins/book-of-git/skills/git-workspace-cleanup/SKILL.md`: the explicit-invocation Git cleanup skill that prunes local worktrees and branches back to main, then updates main.
- `assets/book-of/`: approved default book-family visual assets for `book-of-*` plugin scaffolding.
- `docs/maintaining-grimoire.md`: repository-local policy for changing Grimoire skills, plugin packaging, compatibility files, documentation, and publishing checks.
- `.agents/plugins/marketplace.json`: the Codex marketplace catalog that exposes local plugins from `./plugins/`.
- `.claude-plugin/marketplace.json`: the local Claude-compatible marketplace catalog that exposes local plugins from `./plugins/`.
- `AGENTS.md`: the source-of-truth agent protocol for this repository.
- `CLAUDE.md`: a symbolic link to `AGENTS.md` for Claude Code compatibility.

## Installation Notes

For Codex-compatible clients, add this repository as a plugin marketplace:

```bash
codex plugin marketplace add hon454/grimoire
```

Then open the Codex plugin directory and install `archmage`, `book-of-engineering`, or `book-of-git` from the Grimoire marketplace:

```text
codex
/plugins
```

The Codex marketplace catalog points to local plugin paths under `./plugins/`. Each plugin's `.codex-plugin/plugin.json` points to its installable skill directory.

For Claude Code-compatible local marketplace readers, `.claude-plugin/marketplace.json` exposes the same local plugin packages from `./plugins/`, matching the metadata in each plugin's `.claude-plugin/plugin.json`.

`docs/maintaining-grimoire.md` is repo-local policy for contributors and agents working in this repository. It is not an installable user workflow.

## License

MIT
