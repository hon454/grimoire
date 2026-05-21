# How To Inspect GitHub Work Items

Use this reference only after GitHub is detected or explicitly named.

## Detection Signals

Treat these as GitHub signals:

- git remote URLs pointing to GitHub
- GitHub issue or pull request URLs in user input, docs, commits, or diffs
- issue or PR references such as `owner/repo#123`, `#123`, or `GH-123`
- an open pull request for the current branch
- available GitHub host tools or `gh` authentication

Numeric references like `#123` are ambiguous outside a GitHub repository. Use repository remote and surrounding text before treating them as GitHub work items.

## Inspection Order

1. Inspect explicit GitHub issue or pull request URLs from the user.
2. Inspect the pull request for the current branch, if one exists.
3. Inspect GitHub issue or PR references found in branch names, recent commits, changed files, and relevant docs.
4. Inspect open issues assigned to the current user in the current repository.
5. Inspect open pull requests authored by the current user in the current repository.

## Limits

Use small limits so the briefing stays focused:

- explicit or branch-linked PRs: up to 2
- referenced issues or PRs: up to 5
- assigned issue fallback list: up to 10
- authored PR fallback list: up to 10

Do not scan unrelated repositories unless the user explicitly names them.

## Evidence To Record

Record:

- current branch pull request, if found
- linked or referenced issues
- authored PRs or assigned issues only when they clarify what to do next
- review state or CI state only as tracker context, not as a verification workflow
- unavailable GitHub tools or access failures

## Report Guidance

In `Tracker Context`, distinguish current branch PRs from broader assigned or authored work.

Use `Blockers And Risks` for stalled reviews, unresolved requested changes, or visible failing checks when already present in GitHub context. Do not run checks or create a separate `Verification` section by default.
