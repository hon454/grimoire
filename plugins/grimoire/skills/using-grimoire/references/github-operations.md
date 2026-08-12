# GitHub Operations

## Tool selection

Prefer GitHub CLI (`gh`) over GitHub connectors when `gh` supports the required
operation. Use a connector only when higher-priority instructions or explicit
user intent require it, `gh` lacks the required capability, or `gh` remains
unavailable after authentication verification at a compatible execution
boundary.

Do not choose a connector merely because `gh` reports missing, unreadable, or
invalid authentication inside an isolated sandbox.

## Authentication verification

Identify the target host, intended account, `gh` executable, and active
credential source without reading secret values. Check only whether applicable
environment variables such as `GH_TOKEN`, `GITHUB_TOKEN`,
`GH_ENTERPRISE_TOKEN`, or `GITHUB_ENTERPRISE_TOKEN` are present; never print
their values.

Treat an authentication failure observed only inside an isolated sandbox as
inconclusive when `gh` may depend on credentials outside that boundary. Retry
the same read-only check outside the sandbox with the narrowest required
approval, using `sandbox_permissions=require_escalated` in Codex. If the failed
operation may mutate GitHub state, do not replay it for diagnosis; use direct
read-only probes such as:

```bash
gh auth status --hostname HOST
gh api --hostname HOST /user
```

When the compatible-boundary check succeeds, classify the sandbox result as an
execution-boundary mismatch and run only the required scoped operation there.
Ask the user to reauthenticate only when `gh auth status` also reports an
authentication failure outside the sandbox. Treat timeouts, transport errors,
missing approvals, and other incomplete evidence as inconclusive rather than as
proof that credentials expired or were revoked.

## Security

Keep authentication diagnostics read-only. Never run `gh auth token`,
`gh auth status --show-token`, raw credential-store queries, or any command that
prints, copies, logs, or exposes a token or credential-store secret.

Do not run `gh auth login`, `gh auth logout`, `gh auth refresh`, or
`gh auth switch`; edit the `gh` configuration directory; inject an environment
token; or change credential storage as a diagnostic. Require explicit user
intent before mutating authentication state, and perform that mutation only
from a user-approved boundary outside the isolated agent sandbox that can
access the intended credential source. Never select `--insecure-storage` or
plaintext storage automatically.

## Execution boundaries

Preserve the direct `gh` command prefix when approval or escalation is
prefix-based. Prefer an executor-native deadline; do not wrap `gh` with a shell,
interpreter, or timeout utility merely to add a deadline when the wrapper may
lose credential-store access or invalidate the approved command prefix.

Escalate only the exact read-only probe or GitHub operation that needs access to
the compatible boundary. Never broaden host access, expose credentials, or
repeat a potentially mutating command merely to distinguish authentication
failure from sandbox isolation.

## Platform notes

Treat these platform behaviors as possibilities to verify, not as diagnoses of
every authentication failure.

### macOS

Secure `gh` credentials may live in Keychain. A readable `hosts.yml` without an
`oauth_token` does not prove that the user is logged out, and a sandbox may be
unable to access the login Keychain.

### Windows

Secure `gh` credentials may live in Windows Credential Manager. A sandbox,
service, container, or different user session may not share the interactive
user's credential boundary.

### Linux

Secure `gh` credentials may be available through Secret Service and its session
D-Bus. Headless, containerized, remote, or isolated sessions may not expose that
service. `gh` may fall back to plaintext configuration when secure storage is
unavailable; never enable that fallback automatically.

### WSL

Distinguish Linux `gh` inside a WSL distribution from Windows `gh.exe`. Treat
their executables, configuration, users, credential stores, and execution
boundaries as separate until verified; authentication in one environment does
not prove authentication in the other.
