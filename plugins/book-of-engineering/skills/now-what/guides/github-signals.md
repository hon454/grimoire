# GitHub Signals

Use GitHub only for current-work signals inside the default boundary.

## Check

- Connected pull request for the current branch, detected PR URLs, or explicit PR refs.
- Detected issue IDs, explicit issue refs, or issues linked from the connected PR.
- CI/check status for the connected PR or explicit PR.
- Review state, requested changes, unresolved review threads, and recent comments on the connected PR or explicit PR.
- Milestone, project, label, or assignee signals only when attached to an in-boundary issue or PR.

## Prefer

Prioritize signals that change the next action:

1. Failing or pending required checks.
2. Requested changes, unresolved review threads, or maintainer comments awaiting response.
3. Merge readiness, stale PR state, or branch drift.
4. Issue blockers, milestone pressure, or project expectation attached to the current work.

## Avoid

- Do not search all assigned issues, all open PRs, broad project boards, or organization-wide priorities unless the user asks for that wider scope.
- Do not perform a full code review, CI investigation, issue triage, or project audit.
- Do not post comments, update labels, change assignees, close issues, merge PRs, or create issues.
- Do not treat absent GitHub access as a blocker unless it changes confidence in the recommendation.
