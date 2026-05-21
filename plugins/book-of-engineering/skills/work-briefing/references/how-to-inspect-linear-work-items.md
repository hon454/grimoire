# How To Inspect Linear Work Items

Use this reference only after Linear is detected or explicitly named.

## Detection Signals

Treat these as Linear signals:

- Linear issue identifiers in user input, branch names, commit messages, docs, or diffs
- Linear URLs in repository documents or comments
- available Linear host tools
- repository or project conventions that mention Linear

If a key could also belong to another tracker, prefer Linear only when a Linear URL, Linear tool result, project convention, or user wording supports it.

## Inspection Order

1. Inspect explicit Linear issue IDs or URLs from the user.
2. Inspect Linear issue IDs found in branch names, recent commits, changed files, and relevant docs.
3. If no explicit issue is found, inspect recent active issues associated with the current user.
4. If a likely active issue is found, inspect nearby issues from the same Linear project.
5. If no likely active issue is found, inspect active issues assigned to the current user.

## Limits

Use small limits so the briefing stays focused:

- active issue candidates: up to 5
- detailed active issue reads: up to 2
- same-project issue list: up to 10
- same-project detailed reads: up to 3
- assigned active fallback list: up to 10

Do not turn this into a full project audit.

## Evidence To Record

Record:

- confirmed or likely current issue
- confidence level: high, medium, or low
- why it appears current
- same-project context that changes the next action
- assigned queue items only when they clarify what to do next
- unavailable Linear tools or access failures

## Report Guidance

In `Tracker Context`, distinguish confirmed items from candidates.

Prefer language like:

- "Current likely issue"
- "Same-project context"
- "Assigned queue"
- "Confidence"
- "Evidence"

Do not claim an issue is the current work item unless the evidence is strong. If confidence is low, say that repository-only context may be more reliable.
