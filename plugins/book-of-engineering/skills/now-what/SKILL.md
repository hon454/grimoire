---
name: now-what
description: Explicit-invocation-only current-work triage for recommending what to do next from workspace, git, document, GitHub, and Linear signals. Use only when the user explicitly invokes $now-what, /book-of-engineering:now-what, or asks to use the now-what skill. Do not use for handoff files or implementation planning.
disable-model-invocation: true
---

# Now What

## Overview

Inspect current-work context, recommend what to do next, and stop. This is a personal standup workflow for deciding the next action, not a handoff, planning, execution, review, or tracker-update workflow.

## Invocation

Use this skill only when the user explicitly invokes it. In Codex, the explicit invocation form is `$now-what`. In Claude Code-compatible plugin readers, the explicit invocation form is `/book-of-engineering:now-what`.

## Response Language

Use the host OS preferred language for user-facing prose, including the source notice and final recommendation. If the user explicitly requests a response language in the invocation, use that language for prose.

If the host OS preferred language is unavailable or unreadable, use English.

Preserve code, commands, paths, branch names, issue IDs, PR titles, commit subjects, and technical identifiers as written. Do not infer the response language from this skill file, repository prose, tool output, tracker text, commit messages, copied templates, or quoted artifacts.

## Source Notice

Before inspecting work sources such as files, git, trackers, or pull requests, send a short source notice in the response language. Say which source categories will be checked when available and that missing or inaccessible sources will be skipped.

Default source categories:

- explicit issue IDs, PR URLs, branch names, or paths from the user
- local repo state, current branch, recent commits, local changes, and related docs
- GitHub issues, PRs, checks, reviews, projects, and milestones detected from current-work references
- Linear issues, projects, cycles, target dates, due dates, and statuses detected from current-work references

Keep the notice short. It is an orientation message, not a report.

## Scope

Inspect broad current-work signals, but keep external tracker lookup scoped to the current work.

Default boundaries are the current workspace, current branch, recent commits, local changes, related docs, and tracker metadata directly detected from the workspace, branch, commits, connected PR, or explicit user references.

Do not search all assigned GitHub issues, all assigned Linear issues, unrelated project backlogs, or organization-wide priorities unless the user explicitly asks for that wider scope.

Optional sources are optional. Continue when GitHub, Linear, repository, or document context is unavailable; state the limitation only when it matters to confidence.

## Priority Model

Use this order as judgment guidance, not as a rigid scorecard:

1. Blocking or time-sensitive work: blocked collaborators, failing CI, stale review requests, due dates, project target dates, milestones, or cycles.
2. Current-thread continuity: current branch, recent commits, local diff, or the next shippable step from the work just in progress.
3. External commitment: linked PRs, reviews, assignment, comments, project membership, or status expectations.
4. Risk reduction: unclear requirements, failed verification, broken build or tests, or work that must be decomposed.
5. Momentum: small actions that stabilize the workspace or create a useful next decision point.

For each option, show concise rationale:

- `Why now`: the main reason this option belongs in the current decision set.
- `Signals`: urgency, continuity, impact, and size as `low`, `medium`, or `high`; use `small`, `medium`, or `large` for size.
- `Tradeoff`: what gets delayed or what risk remains if this option is chosen.

## Questions

Ask one concise question before recommending only when missing context would materially change the recommendation. Otherwise, recommend with stated assumptions and put non-blocking questions in the final `Questions` section.

## Output

Write the final response directly in the session as concise Markdown. Do not save it to a file.

Use this shape unless the evidence calls for a shorter form:

```md
## Based On

- Git: current branch, recent commits, and local changes when available
- GitHub: related PR, issue, check, project, or milestone when detected
- Linear: related issue, project, cycle, due date, or target date when detected
- Docs: related specs, ADRs, plans, or repository notes when detected

## Now What

**Recommendation:** Fix the failing PR check first.

## Options

1. **Fix the failing PR check**
   - Why now: it blocks merge and already has reviewer attention
   - Signals: urgency high, continuity high, impact high, size medium
   - Tradeoff: delays new feature work

2. **Finish the local issue changes**
   - Why now: local edits are active and context loss risk is high
   - Signals: urgency medium, continuity high, impact medium, size small
   - Tradeoff: does not unblock the PR today

## First Move

- Open the failed check log and identify whether the failure maps to the latest local diff.

## Questions

- Should milestone pressure override the PR check if the linked issue is due today?
```

Omit unavailable sections or empty bullets. Keep the response focused on the decision, not on a full audit trail.

Do not include a `Not Now` section by default. Mention deferred work only when the user asks, when a tempting lower-priority task is likely to distract from urgent work, or when deferring it avoids meaningful risk.

## Stop Conditions

Stop after the recommendation. Do not write briefing, handoff, or planning files; generate delegate prompts; invoke planning, implementation, review, handoff, or tracker-update skills; create branches, commits, PRs, issues, or Linear updates; run verification commands unless explicitly asked; or start executing the recommended work.

## Common Mistakes

| Mistake | Correction |
| --- | --- |
| Treating the workflow as a handoff briefing | Keep the output in-session and decision-oriented. |
| Searching all assigned work by default | Follow only current repo, branch, commit, PR, issue, and explicit user references. |
| Asking before every recommendation | Ask first only when the missing answer would materially change the recommendation. |
| Letting English repo text set the response language | Use the host OS preferred language unless the invocation explicitly requests another language. |
