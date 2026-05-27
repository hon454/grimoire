---
name: now-what
description: "Recommend what to do next for current work by inspecting available work signals. Do not use for handoff files, implementation planning, status reports, or broad backlog triage."
disable-model-invocation: true
---

# Now What

Personal standup for an active workspace: inspect current-work signals, recommend the next action, and stop.

Use only when explicitly invoked as `$now-what`, `/book-of-engineering:now-what`, or "use the now-what skill".

## Language

Use the host OS preferred language for all user-facing prose, including the source notice, headings, and recommendation. If the invocation explicitly requests a language, use that language. If the OS language is unavailable, use English.

Preserve code, commands, paths, branch names, issue IDs, PR titles, commit subjects, and other technical identifiers as written. Do not infer language from this skill file, repo prose, tool output, tracker text, copied templates, or quoted artifacts.

## First Message

Before inspecting files, git, trackers, or PRs, send one short source notice in the response language:

- which source categories you will check when available
- that missing or inaccessible sources will be skipped

Default source categories: explicit user refs; local repo state; current branch; recent commits; local changes; related docs; GitHub issues/PRs/checks/reviews/projects/milestones; Linear issues/projects/cycles/statuses/due dates/target dates.

## Scope

Look broadly at current-work signals. Keep external tracker lookup narrow.

Default boundary: current workspace, current branch, recent commits, local diff, related docs, connected PR, detected issue IDs, detected PR URLs, and explicit user refs.

Do not search all assigned GitHub issues, all assigned Linear issues, unrelated backlogs, or org-wide priorities unless the user asks for that wider scope.

Optional sources are optional. Continue without GitHub, Linear, repo, or docs when unavailable; mention the gap only if it changes confidence.

## Inputs And Output

Inputs: current workspace; explicit user refs; local repo state; current branch; recent commits; local diff; related docs; connected GitHub or Linear signals when available.

Output: 2-3 current-work options, one recommendation, one first move, and any confidence-changing source gaps. No saved files.

## Decision Rule

Pick the recommendation by this order:

1. Blocking or time-sensitive work: failing CI, stale review, blocked collaborator, due date, milestone, project target, or cycle.
2. Current-thread continuity: branch, commits, local diff, or the next shippable step from active work.
3. External commitment: linked PR, review, assignment, comment, project membership, or status expectation.
4. Risk reduction: unclear requirement, failed verification, broken build/test, or work needing decomposition.
5. Momentum: small action that stabilizes the workspace or creates a useful next decision.

This is judgment guidance, not a scorecard. Prefer the option that best preserves momentum without ignoring urgency.

## Questions

Ask one concise question before recommending only when the answer would materially change the recommendation.

Otherwise, recommend with assumptions and put non-blocking questions at the end.

## Output

Write concise Markdown directly in the session. Do not save a file.

Use 2-3 options. Mark one as the recommendation. For each option, include:

- why now
- signals: urgency, continuity, impact, size
- tradeoff

Then give one first move. Keep it decision-oriented, not a full audit trail.

Omit empty sections. Do not include a "Not Now" section by default; mention deferred work only when it prevents distraction or risk.

## Stop

Stop after the recommendation.

Do not write briefing, handoff, or planning files. Do not generate delegate prompts. Do not invoke planning, implementation, review, handoff, or tracker-update skills. Do not create branches, commits, PRs, issues, or Linear updates. Do not run verification commands or start the recommended work unless explicitly asked.
