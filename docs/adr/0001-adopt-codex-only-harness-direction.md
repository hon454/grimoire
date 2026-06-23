# ADR 0001: Adopt Codex-Only Harness Direction

## Status

Accepted

## Context

Grimoire started as a reusable workflow skill library for coding agents, with Codex as the primary target and Claude Code compatibility maintained where the Markdown skill format overlapped.

That compatibility goal has created ongoing maintenance costs. Shared wording must avoid Codex-specific behavior, compatibility metadata needs to stay aligned across clients, and repository policy has to describe more than the environment where Grimoire is actually used.

The repository owner uses Grimoire in Codex. Future Grimoire work should be able to use Codex-specific skills, plugins, hooks, app connectors, tool discovery, Desktop behavior, and repository automation directly.

## Decision

Grimoire will become a Codex-only harnessing repository.

The repository may contain more than standalone skills. Its durable scope includes:

- Codex skills.
- Codex plugins.
- Hooks and harness configuration.
- Workflow and instruction files.
- MCP, app, and tool integration guidance.
- Codex Desktop-oriented repository operations.
- Reusable components that help Codex agents work predictably.

Claude Code and other coding-agent compatibility are no longer supported repository goals.

## Alternatives Considered

### Continue Claude/Codex compatibility

This preserves portability, but keeps the repository constrained by the lowest common behavior between clients and requires continued compatibility documentation and metadata maintenance.

### Codex-first with cheap portability

This keeps optional portability when it is inexpensive, but leaves ambiguity about when compatibility work is required and when Codex-specific behavior can be used freely.

### Codex-only harnessing repository

This matches the owner's real usage and makes Codex behavior the only compatibility target.

## Consequences

- `CLAUDE.md` is removed instead of being maintained as a symlink to `AGENTS.md`.
- New repository policy, README content, and maintenance guidance should describe Grimoire as Codex-only.
- New skills, plugins, hooks, and workflow assets may use Codex-specific terminology and assumptions directly.
- Existing skills and legacy compatibility artifacts do not have to be migrated in this change. They should be tracked separately and updated intentionally.
- Claude Code and other agent compatibility tests, documentation promises, and support policy are discontinued.

## Non-Goals

- Preserve Claude Code compatibility.
- Keep agent-neutral wording when Codex-specific wording is clearer.
- Migrate every existing skill in this decision change.
- Maintain shared runtime assumptions across multiple coding agents.
