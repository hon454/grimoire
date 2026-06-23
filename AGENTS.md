# Grimoire Agent Protocol

This file is the source of truth for Codex agents working in this repository.

## Repository Intent

Grimoire is a personal Codex harnessing repository for reusable skills, plugins, hooks, workflow instructions, and tool integrations. Keep the repository practical and source-owned.

## Working Rules

- Prefer small, readable skills over broad catch-all instructions.
- Keep skill names stable and literal so Codex can trigger them predictably.
- Do not add roadmap lists or promised future spells until there is a real skill to commit.
- Use Conventional Commits for commit messages.
- Choose commit and pull request scopes by the smallest durable responsibility affected by the change, not by the broadest package, repository area, or file path.
- Use branch names that expose the Conventional Commit type.
- Verify JSON manifests before committing.

## Pull Requests

Before creating or updating a pull request:

- Read `.github/pull_request_template.md`.
- Use the template's current section structure for the PR body.
- Use a Conventional Commit-style pull request title.
- Choose the pull request title scope by the smallest durable responsibility affected by the change.
- Fill in applicable template content with concrete details.
- Delete template prompts and inapplicable checklist items instead of leaving placeholders behind.

## Maintenance Policy

Read `docs/maintaining-grimoire.md` before changing skills, plugin manifests, repository instructions, hooks, sidecar metadata, publishing checks, or README content.
