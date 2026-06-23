# ADR 0001: Adopt Codex Harness Direction

## Status

Accepted

## Context

Grimoire started as a reusable workflow skill library with broadly phrased shared Markdown skill files.

That broad framing has created ongoing maintenance costs. Shared wording avoids Codex-specific behavior, repository policy describes environments outside the owner's daily use, and new Codex capabilities require extra explanation before they can be used directly.

The repository owner uses Grimoire in Codex. Future Grimoire work should be able to use Codex-specific skills, plugins, hooks, app connectors, tool discovery, Desktop behavior, and repository automation directly.

## Decision

Grimoire will become a Codex harnessing repository.

The repository may contain more than standalone skills. Its durable scope includes:

- Codex skills.
- Codex plugins.
- Hooks and harness configuration.
- Workflow and instruction files.
- MCP, app, and tool integration guidance.
- Codex Desktop-oriented repository operations.
- Reusable components that help Codex agents work predictably.

## Alternatives Considered

### Keep the Broad Library Shape

This preserves the original repository shape, but keeps Codex-specific behavior indirect and makes each new harness feature harder to document cleanly.

### Keep Skills as the Primary Unit

This keeps the repository narrow, but does not fit hooks, app connector guidance, Desktop workflows, or other harness components that should live with the skills they support.

### Codex Harnessing Repository

This matches the owner's real usage and gives Codex behavior a clear home across skills, plugins, hooks, workflow instructions, and tool integrations.

## Consequences

- The old mirror instruction symlink is removed.
- New repository policy, README content, and maintenance guidance should describe Grimoire as a Codex harnessing repository.
- New skills, plugins, hooks, and workflow assets may use Codex-specific terminology and assumptions directly.
- Existing skills and older packaging artifacts do not have to be migrated in this change. They should be tracked separately and updated intentionally.

## Non-Goals

- Migrate every existing skill in this decision change.
- Redesign plugin package boundaries in this decision change.
