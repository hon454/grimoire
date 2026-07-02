---
name: magical-rate-limit-reset-check
description: Check ChatGPT rate-limit reset credits from local Codex credentials and report only the safe reset-credit summary.
---

# Magical Rate Limit Reset Check

Use this skill only when the user explicitly asks to check ChatGPT
rate-limit reset credits using this device's Codex credentials.

## Workflow

1. Run the bundled script from this skill directory:

   ```bash
   python3 <skill-dir>/scripts/magical_rate_limit_reset_check.py
   ```

2. If the script reports HTTP 401, tell the user the credentials are expired or
   the Authorization header was not accepted.

3. Report `available_count` once, then list each credit as a short block.
   Omit `title` in the default human-readable output because reset credits are
   normally the same kind. Keep `title` available only in JSON output. Do not
   use a table unless the user asks for one.

## Secret Handling

Never print, quote, summarize, or partially reveal `access_token`,
`refresh_token`, cookies, bearer headers, raw authorization headers, or full
unique IDs. Do not include raw API responses in the final answer.

The script converts UTC timestamps to the local timezone before printing them.
