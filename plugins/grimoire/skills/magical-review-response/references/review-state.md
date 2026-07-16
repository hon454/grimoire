# Review State Authority Contract

Read this reference before invoking `scripts/review_state.py` or interpreting a
Review Session state.

## Contents

- [Commands and storage](#commands-and-storage)
- [Candidate rules](#candidate-rules)
- [State shape](#state-shape)
- [Source operations](#source-operations)
- [Evidence and decision operations](#evidence-and-decision-operations)
- [Execution operations](#execution-operations)
- [Lifecycle, recovery, and purge](#lifecycle-recovery-and-purge)
- [Derived execution gate](#derived-execution-gate)

## Commands and Storage

Use global options before the command:

```text
<python> review_state.py --grimoire-home "<GRIMOIRE_HOME>" apply --thread-id "<uuid>" --candidate "<candidate.json>"
<python> review_state.py --grimoire-home "<GRIMOIRE_HOME>" show --thread-id "<uuid>"
<python> review_state.py --grimoire-home "<GRIMOIRE_HOME>" recover-html --thread-id "<uuid>"
<python> review_state.py --grimoire-home "<GRIMOIRE_HOME>" purge --thread-id "<uuid>" --expected-revision <n>
```

`apply` is the only state-changing command. `recover-html` regenerates the
derived HTML without changing state. `show` validates state and returns a
non-sensitive summary. `purge` deletes one terminal Session after strict
preflight.

The host-provided Thread ID must be a string for which `uuid.UUID(value)` parses
and `str(parsed) == value`. Nil and any UUID version are accepted. Missing,
blank, uppercase, braced, compact, or otherwise noncanonical values fail without
a fallback ID.

The resolved `GRIMOIRE_HOME` itself may be a symlink. Every managed path below
it must remain under the resolved root, be owned by the current UID, and not be
a symlink. Create directories as `0700` and files as `0600`.

## Candidate Rules

Pass one JSON object containing exactly:

- `op`
- `expected_revision`
- the fields defined for that operation below

Do not include unknown fields. Booleans do not satisfy integer fields. Duplicate
JSON names, NaN/Infinity, non-UTF-8 input, an unknown operation, wrong types, or
a stale `expected_revision` fail without changing committed state. Candidate
input and resulting state each have a 10 MiB limit. A candidate is an ephemeral
input outside the Session directory; remove it after the operation returns. The
State Authority never copies it into the Session directory.

The State Authority owns and never accepts candidate values for:

- owner and canonical Thread binding
- Source, Item, Evidence, evaluation, request, decision, authorization, journal,
  and attempt IDs
- revision and timestamps
- Evidence and decision fingerprints

Every successful state-changing operation increments global `revision` by
exactly one. `expected_revision` is a stale-candidate guard for one serial root
writer, not a process lock.

## State Shape

`schema_version` is `1`. Top-level state contains:

- `owner.thread_id`
- global `revision`
- `lifecycle`: `active`, `completed`, or `stopped`
- authority timestamps
- one `source`
- `items` keyed by authority Item UUID and deterministic `item_order`
- at most one `pending_request`
- immutable `request_history`

Do not store or infer a Change domain, phase, next action, progress percentage,
or `can_execute`. Derive workflow status from raw state.

Each Item contains:

- stable `source_key`, kind, source scope state, and source text/context
- presentation text used by the deterministic renderer
- versioned Evidence and evaluation history
- current proposal and computed decision fingerprint
- at most one active authorization plus archived authorization history
- decision history
- local progress: `not_started`, `in_progress`, or `completed`
- remote mutation journals and immutable attempt IDs

The renderer places authority Item UUIDs in DOM IDs. User-provided source,
translation, code, paths, questions, and other display text appear only as
escaped text nodes.

## Source Operations

### `initialize_session`

Require `expected_revision: 0` and one `source`.

GitHub Source:

```json
{
  "op": "initialize_session",
  "expected_revision": 0,
  "source": {
    "type": "github_pr",
    "host": "github.com",
    "owner": "base-owner",
    "repo": "base-repo",
    "pr_number": 123
  }
}
```

The initial GitHub Source is stale until a complete collection succeeds.

Pasted feedback Source:

```json
{
  "op": "initialize_session",
  "expected_revision": 0,
  "source": {
    "type": "pasted_feedback",
    "batch_text": "the entire paste",
    "items": [
      {"original": "first review ask"},
      {"original": "second independent review ask"}
    ]
  }
}
```

The batch text, Source ID, and initial Item identities are immutable. There is no
replace, dedupe, merge, migration, reset, or history-transfer operation.

### `update_github_source`

Require only `collection` in addition to common fields. Follow
`guides/github.md` for the exact identity, pagination, and snapshot shape.

If any reviews, threads, or comments pagination is incomplete, any error exists,
or snapshot is null, preserve the prior complete snapshot, set Source status to
stale, mark Item Evidence stale, and revoke pending requests and active
authorizations in the same state transition.

On a complete snapshot, upsert unresolved thread Items by GraphQL node ID.
Include outdated unresolved threads. Upsert explicitly classified reply
sub-items and actionable review-body Items. Preserve tracked Items that later
resolve as `resolved_out_of_scope`. A head/base OID, comment, scope, or review
change is a Source signal and stales current Evidence.

Reject a collection whose canonical PR identity differs from the Session
Source. Switching PRs requires reconciliation, explicit stop, purge, and new
initialization.

## Evidence and Decision Operations

### `update_item_analysis`

Require:

- `item_id`
- `evidence`
- non-empty `reason`
- `diff`
- `presentation`
- non-empty `choices`
- `recommended_choice_id`
- `action_envelope`

Evidence semantic fields are exact:

```json
{
  "reviewer_ask": "semantic ask",
  "reviewer_intent": "semantic intent",
  "claims": ["verified claim"],
  "code": [
    {
      "path": "src/file.py",
      "revision": "commit-or-worktree-revision",
      "start_line": 10,
      "end_line": 12,
      "text": "short excerpt"
    }
  ],
  "examples": [
    {"input": "input", "behavior": "behavior", "outcome": "outcome"}
  ],
  "assumptions": [],
  "gaps": []
}
```

Presentation fields are `title`, `translation`, `interpretation`,
`reviewer_intent`, `evidence_diff`, `alternatives`, `recommendation`, and
`question`. Each alternative has `choice_id`, `label`, and `tradeoff`.
Presentation wording and order are excluded from the decision fingerprint.

Each choice has exact fields `id`, `label`, `tradeoff`, and `semantic_action`.
The semantic action has:

- `decision_type`: `fix`, `explain`, `question`, `defer_reject`, `duplicate`, or
  `outdated`
- semantic `summary`
- `local_changes`, each with `area` and `change_kind`
- exact `platform_actions`

The Action Envelope has exact fields:

- semantic `purpose`
- `allowed_areas`
- `allowed_change_kinds`
- `excluded`
- `validations`
- explicit `repository_actions`, limited to `commit`, `push`, `merge`, `release`,
  and `deployment`
- exact `platform_actions`

Each platform action has `kind`, `target`, semantic `summary`, and
`reviewer_authored`. Supported kinds are `github_reply`, `github_resolve`,
`github_pr_body_update`, and `github_rereview`.

Every choice-local change and choice-platform action must fit within the common
Action Envelope. The State Authority fingerprints schema/domain, Item and Source
identity, current Evidence ID/version/fingerprint, the full choice-ID-to-action
map, recommended choice ID, and the full Action Envelope.

If semantic Evidence matches the current version, restore or keep that version
valid and record the evaluation diff. If it differs, mark the prior current
version invalid once and append one new valid version. Invalid versions never
return to valid or change semantic content.

### `mark_evidence_stale`

Require `item_id`, non-empty `reason`, and `diff`. Keep the current Evidence
version but set its current status stale. Revoke its pending request and active
authorization atomically. Use this when revalidation cannot yet produce valid
Evidence.

### `request_decision`

Require `item_id` and a non-empty exact `question`. Source and Evidence must be
ready/valid, proposal must exist, no Session request may already be pending, and
the Item must not already have active authorization. The authority issues a new
request UUID and publishes HTML before committing state.

### `record_decision`

Require `item_id`, current `request_id`, and offered `choice_id`. The request,
Item, expected revision, decision fingerprint, and choice must all match. Consume
the pending request into history and create one active authorization bound to the
chosen choice, fingerprint, and Action Envelope.

A consumed or invalidated request ID cannot be reused. Returning a proposal from
A to B to A never searches history or restores the old authorization.

## Execution Operations

### Local progress

`start_local_work` requires `item_id`, `area`, and `change_kind`. It transitions
only `not_started → in_progress` and checks both the chosen semantic action and
active envelope.

`complete_local_work` requires `item_id` and non-empty `validation_summary`. It
transitions only `in_progress → completed` while authorization and Evidence are
still current.

Do not reset local status. Reconcile persisted `in_progress` against the
worktree; stale unexpected facts before continuing.

### Remote journal

`prepare_remote_mutation` requires `item_id` and the exact platform `action`. It
creates a journal and a unique `pending` attempt only when the chosen action and
active envelope contain the action. One Item cannot create a second journal for
the same action; use the existing journal's retry transition instead.

`cancel_pending_remote_mutation` requires `item_id`, `journal_id`, `attempt_id`,
and a non-empty reason. Use it only after confirming the remote call did not
start. It transitions that `pending` attempt to terminal `failed`, records
`confirmed_not_applied: true`, and stales Evidence because execution diverged
from the approved plan.

`start_remote_mutation` requires `item_id`, `journal_id`, and `attempt_id`, and
transitions `pending → in_progress` immediately before the call. It rechecks the
journal's exact action against the current chosen semantic action and active
envelope.

`finish_remote_mutation` adds `outcome`, non-empty `summary`, and
`confirmed_not_applied`. It transitions `in_progress` to:

- `succeeded` for a known applied result
- `failed` only with `confirmed_not_applied: true`
- `uncertain` for an ambiguous call boundary

`failed` and `uncertain` are unexpected execution facts that stale Evidence and
revoke authority in the same operation.

`mark_remote_uncertain` requires an `in_progress` attempt plus `reason`; use it
on resume before any retry.

`reconcile_remote_mutation` requires an `uncertain` attempt, `outcome` of
`succeeded` or confirmed-not-applied `failed`, summary, and confirmation flag.
It may run while Evidence is stale because reconciliation is the prerequisite
to new authorization.

`retry_remote_mutation` requires a journal whose latest attempt is reconciled
`failed` plus a new current authorization. It appends a new pending attempt and
never rewinds the old one, after rechecking the exact journal action.

`close_authorization` requires `item_id` and `reason`. It rejects local
`in_progress` or remote `pending`, `in_progress`, or `uncertain`, then archives
the active authorization.

## Lifecycle, Recovery, and Purge

`set_session_lifecycle` requires `lifecycle` of `completed` or `stopped` and a
reason. It consumes a pending request and archives active authorizations.
`completed` additionally rejects in-progress local work and unfinished remote
attempts. Terminal state blocks new decisions and execution but still permits
remote reconciliation needed for safe purge.

Every update follows this order:

1. Validate candidate and current state.
2. Build and validate the complete next state in memory.
3. Render final HTML from that state and the fixed template.
4. Write both fixed temporary files.
5. Replace `state.json`.
6. Replace `review.html`.

Failure before state replacement preserves committed files. Interruption after
state replacement may leave old HTML. `recover-html` ignores temporary contents,
validates committed state, and regenerates HTML without changing state. The
contract covers process interruption, not power-loss durability.

Purge requires a terminal state and exact expected revision. It rejects any
`in_progress` or `uncertain` remote attempt. Before the first unlink it inspects
the entire Thread directory: only the four allowed artifact names may exist,
and each present entry must be a current-UID-owned regular non-symlink file.

Purge unlinks `review.html` and fixed temporary files individually, reloads and
revalidates state, unlinks `state.json` last, then removes only the empty Thread
directory. It does not glob, recurse, use `shutil.rmtree`, or touch a repository
or worktree. If interrupted before state deletion, `recover-html` can rebuild the
derived artifact.

## Derived Execution Gate

Derive permission immediately before a mutation. It is true only when:

- lifecycle is active
- Source is ready
- current Evidence is valid
- proposal fingerprint equals the active authorization fingerprint
- authorization choice is current
- requested local or platform action appears in both the chosen semantic action
  and active Action Envelope

Do not use HTML revision, chat memory, a past decision, write permission, or the
Thread UUID alone as an execution capability.
