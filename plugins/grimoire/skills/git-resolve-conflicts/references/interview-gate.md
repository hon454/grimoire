# Interview Gate

Use this reference before asking about or resolving any non-mechanical conflict.

## Ask The User

Stop and interview the user before editing when the conflict affects:

- Product behavior, UX flow, pricing, billing, permissions, authentication, authorization, privacy, or security.
- Public APIs, data schemas, migrations, serialized formats, protocol contracts, configuration semantics, or backward compatibility.
- Ownership boundaries, module responsibility, feature flags, rollout behavior, or which implementation is canonical.
- Delete/modify or deletion-retention choices where one side removed a file, function, route, migration, test, fixture, or asset that the other side changed.
- Test expectations, snapshots, or fixtures when expected behavior cannot be inferred from source changes alone.
- Any conflict where both sides are coherent but encode different intent.

## Do Not Ask For Mechanical Conflicts

Resolve without interviewing only when the conflict is mechanical and the intended result is clear:

- Import ordering, formatting, whitespace, or comment placement.
- Adjacent edits where both sides can be preserved without changing behavior.
- Simple rename follow-through where references clearly point to the new name.
- Generated output or lockfiles that can be safely regenerated from already-resolved source files.
- Test snapshots regenerated after the user-approved or mechanically resolved source change.

If a mechanical-looking conflict reveals a semantic choice, stop and interview.

## Question Format

Ask specific, file-scoped, decision-oriented questions:

- "In `src/auth/session.ts`, should the resolved behavior keep the base branch's token rotation change, the PR branch's legacy-session fallback, or both with a clear precedence rule?"
- "The base branch deletes `api/v1/users.ts`, while this branch modifies it. Should this endpoint stay deleted, be restored, or move into the new route structure?"
- "For `package-lock.json`, may I resolve source conflicts first and regenerate the lockfile with `npm install`?"

Avoid vague questions that push the merge burden onto the user:

- "Which side should I take?"
- "What should I do with this file?"
- "Can I just accept theirs?"
- "Is this conflict okay?"

Present the observed base-side intent, topic-side intent, and the smallest viable choices.

## Ours And Theirs During Rebase

Before using `ours` or `theirs` in a rebase conflict, explain:

- `ours` is the already-rebased side, usually the fetched remote base plus replayed commits.
- `theirs` is the topic branch commit currently being replayed.

Never ask "ours or theirs?" without translating those labels into branch/base meaning.

## Conflict-Specific Rules

### Delete/Modify

Ask unless repository context clearly proves the deleted path was replaced and the topic-side change should move to the replacement.

If retaining the change, apply it to the surviving file or replacement location rather than blindly restoring stale structure.

### Rename

Resolve pure rename follow-through directly. Ask when both sides rename differently, one side renames while the other rewrites behavior, or the destination changes responsibility.

### Lockfiles

Resolve package manifests first, then regenerate lockfiles with the repository package manager. Ask before changing dependency versions, package manager choice, or lockfile format.

Record the regeneration command when used.

### Generated Files

Resolve source inputs first, then regenerate generated files. Ask when the generator is unknown, unavailable, or generated output encodes product/API choices not visible in source.

Do not hand-merge generated files unless regeneration is impossible and the change is clearly mechanical.

### Test Snapshots And Fixtures

Resolve source behavior first. Regenerate snapshots or fixtures only after intended behavior is known. Ask when both sides intentionally changed expected behavior or the snapshot result chooses one product behavior over another.

Record whether the snapshot was regenerated or manually adjusted.

## Conflict Resolution Notes

When the user answers an interview question, preserve the decision in the final summary as a conflict resolution note:

```text
Conflict resolution notes:
- <path>: <user decision>. Applied by <brief implementation summary>.
```

For multi-file decisions, group related files under one note only when the same user decision controlled all of them.
