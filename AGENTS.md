# Grimoire Agent Protocol

This file is the source of truth for agents working in this repository. `CLAUDE.md` is a symbolic link to this file so Claude Code and Codex use the same instructions.

## Repository Intent

Grimoire is a personal, public skill library for reusable coding-agent workflows. Keep the repository practical and source-owned.

## Working Rules

- Prefer small, readable skills over broad catch-all instructions.
- Keep skill names stable and literal so different clients can trigger them predictably.
- Do not add roadmap lists or promised future spells until there is a real skill to commit.
- Use Conventional Commits for commit messages.
- Choose commit and pull request scopes by the smallest durable responsibility affected by the change, not by the broadest package, repository area, or file path.
- Use branch names that expose the Conventional Commit type.
- Verify JSON manifests before committing.

## Pull Requests

Before creating or updating a pull request, read `.github/pull_request_template.md` and use its current section structure for the PR body. Use a Conventional Commit-style pull request title with an appropriately narrow scope. Fill in applicable content from the template; delete template prompts and inapplicable checklist items instead of leaving placeholders behind.

## Maintenance Policy

Read `docs/maintaining-grimoire.md` before changing skills, plugin manifests, repository instructions, compatibility files, sidecar metadata, publishing checks, or README content.

## Compatibility Notes

Codex is the primary authoring target. Claude Code compatibility is maintained by keeping shared instructions in Markdown skill files and by exposing the same repository protocol through the `CLAUDE.md` symlink.
