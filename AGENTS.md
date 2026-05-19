# Grimoire Agent Protocol

This file is the source of truth for agents working in this repository. `CLAUDE.md` is a symbolic link to this file so Claude Code and Codex use the same instructions.

## Repository Intent

Grimoire is a personal, public skill library for reusable coding-agent workflows. Keep the repository practical: shared skill content belongs under `skills/<skill>/SKILL.md`, while client-specific packaging belongs under the matching plugin manifest directory.

## Working Rules

- Prefer small, readable skills over broad catch-all instructions.
- Keep skill names stable and literal so different clients can trigger them predictably.
- Do not add roadmap lists or promised future spells until there is a real skill to commit.
- Use Conventional Commits for commit messages, such as `{type}({scope}): {summary}`.
- Use branch names that expose the Conventional Commit type, such as `{type}/{slug}`.
- Verify JSON manifests before committing.
- Verify `CLAUDE.md` remains a symbolic link to `AGENTS.md` before publishing.

## Compatibility Notes

Codex is the primary authoring target. Claude Code compatibility is maintained by keeping shared instructions in Markdown skill files and by exposing the same repository protocol through the `CLAUDE.md` symlink.
