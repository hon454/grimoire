# GitHub Operations

## Tool selection

Prefer GitHub CLI (`gh`) over GitHub connectors when `gh` supports the required
operation. Use a connector only when higher-priority instructions or explicit
user intent require it, `gh` lacks the required capability, `gh` cannot run, or
the GitHub Authentication procedure ends in a permitted connector fallback.

If an executable `gh` reports an authentication or principal-verification
failure, follow [GitHub Authentication](github-authentication.md) before
choosing a fallback. Do not classify a sandbox-only failure as an expired or
revoked credential.

If neither tool can perform a required write, stop with an explicit blocked
outcome. For work that can be handed off, return a draft instead.

## Security

Never print, copy, log, or expose tokens or credential-store secrets. Do not
inspect secret values merely to choose a tool or execution boundary. Redact
secrets from commands, tool output, evidence, review replies, issues, and logs.

Keep diagnostic operations read-only. If a failed operation may mutate GitHub
state, do not replay it to distinguish authentication failure from sandbox
isolation.

## Execution boundaries

Preserve the direct `gh` command prefix when approval or escalation is
prefix-based. Prefer an executor-native deadline; do not wrap `gh` with a shell,
interpreter, or timeout utility merely to add a deadline when the wrapper may
lose credential-store access or invalidate the approved command prefix.

Escalate only the exact read-only probe or GitHub operation that needs access to
the compatible boundary. Never broaden host access, expose credentials, or
repeat a potentially mutating command merely to distinguish authentication
failure from sandbox isolation.
