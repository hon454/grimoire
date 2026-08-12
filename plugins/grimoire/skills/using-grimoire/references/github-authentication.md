# GitHub Authentication

Use this reference only when `gh` reports an authentication failure, cannot
verify the intended account, or may be isolated from its credential source.

## Verification

Identify the target host, intended account, `gh` executable, and active
credential source without reading secret values. Check only whether applicable
environment variables such as `GH_TOKEN`, `GITHUB_TOKEN`,
`GH_ENTERPRISE_TOKEN`, or `GITHUB_ENTERPRISE_TOKEN` are present; never print
their values.

If `gh` is absent or cannot execute, return immediately to the connector or
draft/blocked outcomes already selected under GitHub Operations. Otherwise, use
bounded read-only probes:

```bash
gh auth status --active --hostname HOST
gh api --hostname HOST /user
```

Require the `/user` response to match the intended principal. A valid account
for the host is insufficient when it is not the intended account.

Treat a failure observed only inside an isolated sandbox as inconclusive when
`gh` may depend on credentials outside that boundary. Retry the same probes
exactly once outside the sandbox with the narrowest required approval, using
`sandbox_permissions=require_escalated` in Codex. Do not replay a mutating
operation for diagnosis.

Classify the bounded result once:

- If the outside-boundary probes succeed for the intended principal, classify
  the sandbox result as an execution-boundary mismatch and run only the required
  scoped operation there.
- If they confirm an authentication failure, ask the user to reauthenticate.
- If they confirm a different principal, do not write; request the intended
  account or an explicit authentication change.
- If approval is denied, the probes time out, transport fails, or evidence
  remains incomplete, do not retry. Use a permitted connector or return an
  explicit draft/blocked outcome.

## Authentication security

Never run `gh auth token`, `gh auth status --show-token`, raw credential-store
queries, or any command that prints, copies, logs, or exposes a token or
credential-store secret.

Do not run `gh auth login`, `gh auth logout`, `gh auth refresh`, or
`gh auth switch`; edit the `gh` configuration directory; inject an environment
token; or change credential storage as a diagnostic. Require explicit user
intent before mutating authentication state, and perform that mutation only
from a user-approved boundary outside the isolated agent sandbox that can
access the intended credential source. Never select `--insecure-storage` or
plaintext storage automatically.

## Platform notes

Treat these platform behaviors as possibilities to verify, not as diagnoses of
every authentication failure. Use only the note matching the active execution
environment.

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
