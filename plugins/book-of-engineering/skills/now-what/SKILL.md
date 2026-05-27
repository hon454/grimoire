---
name: now-what
description: Recommend what to do next for current work by inspecting available work signals. Do not use for handoff files, implementation planning, status reports, or broad backlog triage.
disable-model-invocation: true
---

# Now What

Personal standup for an active workspace: inspect current-work signals, recommend the next action, and stop.

Use only when explicitly invoked as `$now-what`, `/book-of-engineering:now-what`, or "use the now-what skill".

## Language

Use the host OS preferred language for all user-facing prose, including the source notice, headings, and recommendation. If the invocation explicitly requests a language, use that language. If the OS language is unavailable, use English.

Preserve code, commands, paths, branch names, issue IDs, PR titles, commit subjects, and other technical identifiers as written. Do not infer language from this skill file, repo prose, tool output, tracker text, copied templates, or quoted artifacts.

## Source Notice

Include one short source notice near the top of the response. If the host supports interim messages, send it before inspection; otherwise make it the first line of the final response.

The notice should state:

- which source categories were or will be checked when available
- that missing or inaccessible sources are skipped

Default source categories within the default boundary: explicit user refs; local repo state; current branch; recent commits; local changes; related docs; GitHub signals; Linear signals.

## Scope

Look broadly at current-work signals. Keep external tracker lookup narrow.

Default boundary: current workspace, current branch, recent commits, local diff, related docs, connected PR, detected issue IDs, detected PR URLs, and explicit user refs.

Do not search all assigned GitHub issues, all assigned Linear issues, unrelated backlogs, or org-wide priorities unless the user asks for that wider scope.

Optional sources are optional. Continue without GitHub, Linear, repo, or docs when unavailable; mention the gap only if it changes confidence.

## External Source Guides

When checking GitHub signals, follow `guides/github-signals.md`.

When checking Linear signals, follow `guides/linear-signals.md`.

Read only the guide for an available or explicitly requested source.

## Contract

Inputs are available current-work signals from the default boundary.

Return 2-3 current-work options, one recommendation, one first move, and any confidence-changing source gaps. Do not save files.

## Decision Rule

Pick the recommendation by this order:

1. Blocking or time-sensitive work: failing CI, stale review, blocked collaborator, due date, milestone, project target, or cycle.
2. Current-thread continuity: branch, commits, local diff, or the next shippable step from active work.
3. External commitment: linked PR, review, assignment, comment, project membership, or status expectation.
4. Risk reduction: unclear requirement, failed verification, broken build/test, or work needing decomposition.
5. Momentum: small action that stabilizes the workspace or creates a useful next decision.

This is judgment guidance, not a scorecard. Prefer the option that best preserves momentum without ignoring urgency.

## Questions

Do not stop for clarification by default.

If priority is ambiguous, make a reasonable assumption, provide 2-3 viable options, and put at most one non-blocking question at the end.

Ask one concise question before recommending only when no meaningful recommendation can be made without the answer.

## Output

Write concise Markdown directly in the session. Do not save a file.

Use 2-3 options. Mark one as the recommendation. For each option, include a concise rationale. When useful, cover:

- why now
- signals: urgency, continuity, impact, size
- tradeoff

Merge or omit rationale parts when the signal is obvious, weak, or would create filler.

Then give one first move. Keep it decision-oriented, not a full audit trail.

Omit empty sections. Do not include a "Not Now" section by default; mention deferred work only when it prevents distraction or risk.

## Stop

Stop after the recommendation.

Do not write briefing, handoff, or planning files. Do not generate delegate prompts. Do not invoke planning, implementation, review, handoff, or tracker-update skills. Do not create branches, commits, PRs, issues, or Linear updates. Do not run verification commands or start the recommended work unless explicitly asked.
