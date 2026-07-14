<div align="center">
  <p>
    <img src="assets/readme/hero.png" width="960" alt="Grimoire figure reading a glowing code grimoire in a magical library">
  </p>
  <h1>Grimoire</h1>
  <p><strong>Codex harnessing assets for reusable agent workflows.</strong></p>
  <p><a href="README.ko.md">한국어</a></p>
</div>

Grimoire is the personal Codex harnessing repository maintained by `hon454`. It packages reusable Codex skills, a plugin, hooks, workflow instructions, and tool integration guidance for the owner's Codex environment.

## Status

This repository currently exposes one installable Grimoire plugin plus repository-local maintenance policy. It does not promise roadmap contents beyond the Codex assets and policy committed here.

## Plugin

Grimoire currently publishes one installable harness plugin:

| Icon | Plugin | Purpose |
| --- | :---: | --- |
| <img src="plugins/grimoire/assets/icon.png" width="72" alt="Grimoire icon"> | [**Grimoire**](plugins/grimoire/) | Workflow skills and hooks for Grimoire bootstrap, skill authoring, conversation handoff, current-work triage, issue preflight and readiness review, locale-grounded translation, review response, Git cleanup, and conflict resolution. |

## Contents

- `plugins/grimoire/`: the installable Grimoire plugin package.
- `plugins/grimoire/hooks/resolve_grimoire_config.py`: the SessionStart config resolver that merges user and project `.grimoire/config.toml` files into a validated session config cache.
- `plugins/grimoire/skills/using-grimoire/SKILL.md`: the bootstrap skill that requires Codex agents to check and load applicable Grimoire skills before acting.
- `plugins/grimoire/skills/report-grimoire-issue/SKILL.md`: the explicit-invocation issue-reporting skill that drafts upstream Grimoire GitHub issues and posts them only after confirmation.
- `plugins/grimoire/skills/writing-great-skills/SKILL.md`: the explicit-invocation reference for writing and editing predictable Codex skills.
- `plugins/grimoire/skills/handoff/SKILL.md`: the explicit-invocation skill that creates a self-contained prompt for copying selected conversation context into another task.
- `plugins/grimoire/skills/now-what/SKILL.md`: the explicit-invocation current-work triage skill that recommends what to do next.
- `plugins/grimoire/skills/issue-preflight/SKILL.md`: the explicit-invocation pre-implementation audit skill that validates tracker issues, linked changes, and branch-scoped work references without changing trackers.
- `plugins/grimoire/skills/issue-readiness-review/SKILL.md`: the explicit-invocation readiness review skill that drafts the appropriate tracker update without changing trackers.
- `plugins/grimoire/skills/magical-translation/SKILL.md`: the locale-grounded translation skill that reads the Grimoire session config cache before translating user-facing text.
- `plugins/grimoire/skills/magical-review-response/SKILL.md`: the review-response workflow that translates review feedback, interviews decision points, implements the confirmed plan, verifies changes, and handles reviewer follow-up.
- `plugins/grimoire/skills/git-workspace-cleanup/SKILL.md`: the explicit-invocation Git cleanup skill that prunes local worktrees and branches back to main, then updates main.
- `plugins/grimoire/skills/git-resolve-conflicts/SKILL.md`: the guarded Git conflict resolution skill for making conflicted branches or PRs mergeable against a fetched remote base.
- `assets/readme/`: README-specific visual assets.
- `docs/adr/0001-adopt-codex-only-harness-direction.md`: the decision record that defines Grimoire as a Codex harnessing repository.
- `docs/maintaining-grimoire.md`: repository-local policy for changing Grimoire skills, plugin packaging, Codex harness assets, documentation, and publishing checks.
- `.agents/plugins/marketplace.json`: the Codex marketplace catalog that exposes `plugins/grimoire/`.
- `AGENTS.md`: the source-of-truth agent protocol for this repository.

## Installation Notes

For Codex, add this repository as a plugin marketplace:

```bash
codex plugin marketplace add hon454/grimoire
```

Then open the Codex plugin directory and install `grimoire` from the Grimoire marketplace:

```text
codex
/plugins
```

The Codex marketplace catalog points to `./plugins/grimoire`. The plugin's `.codex-plugin/plugin.json` points to its installable skill directory and SessionStart hook.

Grimoire bundles a Codex SessionStart hook. After installing or updating the plugin, review and trust the hook in Codex before relying on its generated Grimoire session config.

Migration note: if you previously installed `archmage`, `book-of-engineering`, or `book-of-git`, install or update `grimoire`, trust the hook again, then remove the old local plugin installs if they still appear. Existing `$skill-name` triggers are preserved.

## Grimoire Config

The Grimoire plugin reads optional user and project config files, bootstraps a missing user `output.locale` from the OS preferred locale, then writes a validated session config cache when the SessionStart hook runs:

- user config: `~/.grimoire/config.toml`
- project config: `<repo>/.grimoire/config.toml`

Supported keys are intentionally narrow:

```toml
schema_version = 1

[output]
locale = "{locale}" # for example, "ko-KR"

[tracker]
primary = "github" # "github", "linear", or "none"

[tracker.linear]
team_identifier = "{TEAM}"
```

`output.locale` must be a valid locale tag such as `ko-KR`, `en-US`, or `zh-TW`. Natural-language names and host-style locale forms such as `ko_KR.UTF-8` are not accepted in config; OS preferred-locale detection may still normalize host and environment values into canonical tags.

`docs/maintaining-grimoire.md` is repo-local policy for contributors and Codex agents working in this repository. It is not an installable user workflow.

## License

MIT
