---
name: work-briefing
description: Explicit-invocation-only skill for creating an asynchronous engineering handoff briefing for current-state work. Use only when the user explicitly invokes $work-briefing, /book-of-engineering:work-briefing, or asks to use the work-briefing skill.
disable-model-invocation: true
---

# Work Briefing

Create a current-state handoff briefing for the user's future self. The output is a Markdown document saved in the workspace and a concise session summary that points to that file.

This is not a verification, implementation, or review workflow. Preserve work context; do not improve the work.

## Invocation

Use this skill only when the user explicitly invokes it. In Codex, the explicit invocation form is `$work-briefing`. In Claude Code-compatible plugin readers, the explicit invocation form is `/book-of-engineering:work-briefing`.

## Start Message

Before inspecting files or tools, tell the user which sources you will check. Use the language selected by `Briefing Language`.

Include these source categories when applicable:

- available issue tracker work items
- repository documents such as specs, ADRs, architecture notes, technical-debt notes, and planning docs
- recent commits and the current revision
- pull requests connected to the current branch
- local repository changes

## Source Order

Use this order unless the user gives a narrower scope:

1. Explicit user-provided work item URLs, issue IDs, PR URLs, branch names, or paths.
2. Detected issue tracker context for the current workspace.
3. Repository documents related to the work.
4. Recent commits and the current revision.
5. Pull requests connected to the current branch.
6. Local changed files and diff summary.

Issue tracker context may be more important than local diffs for this skill. Local repository state is still required evidence whenever the workspace is a repository.

## Issue Tracker Detection

The first version supports Linear and GitHub.

Detect tracker context from explicit user input, git remotes, branch names, commit messages, repository documents, changed files, and available host tools.

Only read a tracker reference after detecting that service or when the user explicitly names it:

- For Linear work items, read `references/how-to-inspect-linear-work-items.md`.
- For GitHub work items, read `references/how-to-inspect-github-work-items.md`.

If neither Linear nor GitHub is detected or available, continue with repository-only context. The briefing must still succeed without issue tracker access.

If tracker access fails or required host tools are unavailable, tell the user in the session and record the limitation in `Evidence`.

## Repository Documents

Look for obvious work context in repository documents before relying on diff interpretation. Prefer docs whose names or paths indicate:

- specs
- product requirements
- ADRs or decisions
- architecture
- technical debt
- plans
- `.grimoire`

Do not perform an exhaustive repository audit. Read only documents that are clearly connected to the detected work item, current branch, recent commits, changed files, or user-provided scope.

## What Not To Do

- Do not use subagents.
- Do not run, infer, or search for test, build, lint, migration, deploy, or mutation commands by default.
- Do not create a `Verification` section by default.
- Do not warn immediately about ordinary work risks; put them in `Blockers And Risks`.
- Do not overwrite existing briefing files.
- Do not add YAML frontmatter to the generated briefing.

Only mention verification when the user explicitly asks for it, when verification results are already present in the conversation or obvious local artifacts, or when a verification-related issue is a blocker or risk.

Immediately tell the user only about operational problems that affect briefing generation, such as inability to identify a workspace, inability to write the artifact, or unavailable tracker access.

## Artifact

Create the output directory if needed:

```text
.grimoire/work-briefings/
```

Write one Markdown file:

```text
.grimoire/work-briefings/<YYYY-MM-DD-HHMM>-<git-short-hash>.md
```

Use the user's local timezone when known. If the workspace has no git hash, use:

```text
.grimoire/work-briefings/<YYYY-MM-DD-HHMM>-no-git.md
```

If the target filename already exists, append `-2`, `-3`, and so on instead of overwriting.

## Briefing Language

Choose the briefing prose language from the first clear signal:

1. Use the language the user explicitly requested for the briefing or session response.
2. Use the user's natural-language messages in the current session.
3. Use the host operating system language when already available.
4. Use English.

Ignore skill triggers, default prompts, assistant text, tool output, commands, identifiers, paths, URLs, quoted source text, and section templates when choosing the session language. Section headings may remain in English for scanability.

Preserve stable identifiers and useful excerpts for commands, file paths, branch names, issue IDs, URLs, and error text, but redact sensitive values before writing the briefing. Redact secrets, tokens, credentials, signed URL query strings, private email addresses, and private workspace, customer, or user metadata. When redaction affects evidence, note that redaction occurred in `Evidence` without exposing the original value.

## Briefing Structure

Use this structure unless the user asks for another format:

```markdown
# Work Briefing

Generated: 2026-05-21 14:30 KST
Workspace: /path/to/workspace
Revision: abc1234
Scope: Current workspace handoff

## Current State

## Tracker Context

## Repository Context

## What Changed

## Working Intent

## Blockers And Risks

## Next Actions

## Resume Instructions

## Evidence
```

Use `Tracker Context` to separate confirmed current work items from candidates. Use `Evidence` to list sources checked, unavailable sources, and any confidence limits.

## Session Response

After writing the file, respond briefly with:

- the artifact path
- the strongest current-work signal found
- any operational limitation that affected the briefing

Do not paste the full briefing unless the user asks.
