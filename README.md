<div align="center">
  <p>
    <img src="assets/readme/hero.png" width="960" alt="Archmage reading a glowing code grimoire in a magical library">
  </p>
  <h1>Grimoire</h1>
  <p><strong>Reusable workflow skills for coding agents.</strong></p>
  <p><a href="README.ko.md">한국어</a></p>
</div>

Grimoire is the source library maintained by `hon454`. Its installable plugins are packaged under `plugins/` for Codex-first use and Claude Code-compatible readers where the underlying skill format overlaps.

## Status

This repository currently exposes the Archmage, Book of Engineering, and Book of Git plugins plus repository-local maintenance policy. It does not promise roadmap contents beyond the skills and policy committed here.

## Plugins

Grimoire currently publishes these installable plugins:

| Plugin | Purpose |
| --- | --- |
| <img src="plugins/archmage/assets/icon.png" width="36" alt="Archmage icon"> **Archmage** | Operational workflows for helping coding agents use Grimoire consistently: choosing applicable workflows, loading the right context, and starting from a shared operating model. |
| <img src="plugins/book-of-engineering/assets/icon.png" width="36" alt="Book of Engineering icon"> **Book of Engineering** | Engineering workflows for preserving work context across sessions, with an emphasis on current-state understanding, durable handoff context, and asynchronous continuity. |
| <img src="plugins/book-of-git/assets/icon.png" width="36" alt="Book of Git icon"> **Book of Git** | Git workflows for keeping local repositories understandable and recoverable, with guarded support for workspace hygiene, branch discipline, and repository cleanup. |

## Contents

- `plugins/archmage/`: the installable Archmage plugin package.
- `plugins/archmage/skills/using-grimoire/SKILL.md`: the installable bootstrap skill that requires agents to check and load applicable Grimoire skills before acting.
- `plugins/book-of-engineering/`: the installable Book of Engineering plugin package.
- `plugins/book-of-engineering/skills/work-briefing/SKILL.md`: the explicit-invocation handoff skill that writes current-state work briefings.
- `plugins/book-of-git/`: the installable Book of Git plugin package.
- `plugins/book-of-git/skills/git-workspace-cleanup/SKILL.md`: the explicit-invocation Git cleanup skill that prunes local worktrees and branches back to main, then updates main.
- `assets/readme/`: README-specific visual assets.
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
