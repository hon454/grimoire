<div align="center">
  <p>
    <img src="assets/readme/hero.png" width="960" alt="Archmage reading a glowing code grimoire in a magical library">
  </p>
  <h1>Grimoire</h1>
  <p><strong>Codex harnessing assets for reusable agent workflows.</strong></p>
  <p><a href="README.ko.md">한국어</a></p>
</div>

Grimoire is the personal Codex harnessing repository maintained by `hon454`. It packages reusable Codex skills, plugins, hooks, workflow instructions, and tool integration guidance for the owner's Codex environment.

## Status

This repository currently exposes the Archmage, Book of Engineering, and Book of Git plugins plus repository-local maintenance policy. It does not promise roadmap contents beyond the Codex assets and policy committed here.

## Plugins

Grimoire currently publishes these installable plugins:

| Icon | Plugin | Purpose |
| --- | :---: | --- |
| <img src="plugins/archmage/assets/icon.png" width="72" alt="Archmage icon"> | [**Archmage**](plugins/archmage/) | Operational workflows for helping Codex agents use and maintain Grimoire consistently: choosing applicable workflows, loading the right context, reporting reusable Grimoire issues upstream, and improving skills. |
| <img src="plugins/book-of-engineering/assets/icon.png" width="72" alt="Book of Engineering icon"> | [**Book&nbsp;of&nbsp;Engineering**](plugins/book-of-engineering/) | Engineering workflows for understanding current work context, choosing the next action, auditing work-item validity before implementation, and reconciling merge-ready change requests with tracker context. |
| <img src="plugins/book-of-git/assets/icon.png" width="72" alt="Book of Git icon"> | [**Book&nbsp;of&nbsp;Git**](plugins/book-of-git/) | Git workflows for keeping local repositories understandable and recoverable, with guarded support for workspace hygiene, branch discipline, repository cleanup, and conflict resolution. |

## Contents

- `plugins/archmage/`: the installable Archmage plugin package.
- `plugins/archmage/skills/using-grimoire/SKILL.md`: the installable bootstrap skill that requires Codex agents to check and load applicable Grimoire skills before acting.
- `plugins/archmage/skills/report-grimoire-issue/SKILL.md`: the explicit-invocation issue-reporting skill that drafts upstream Grimoire GitHub issues and posts them only after confirmation.
- `plugins/archmage/skills/writing-great-skills/SKILL.md`: the explicit-invocation reference for writing and editing predictable Codex skills.
- Archmage `0.2.0` adds `$report-grimoire-issue` for reusable Grimoire documentation, skill, plugin packaging, Codex harness, and workflow reports.
- `plugins/book-of-engineering/`: the installable Book of Engineering plugin package.
- `plugins/book-of-engineering/skills/now-what/SKILL.md`: the explicit-invocation current-work triage skill that recommends what to do next.
- `plugins/book-of-engineering/skills/issue-preflight/SKILL.md`: the explicit-invocation pre-implementation audit skill that validates tracker issues, linked changes, and branch-scoped work references without changing trackers.
- `plugins/book-of-engineering/skills/merge-readiness-sync/SKILL.md`: the explicit-invocation pre-merge workflow that reconciles merge-ready git-hosted change requests with issue tracker context without merging the change.
- Book of Engineering `0.3.0` adds `$issue-preflight` for validating tracker issues, linked changes, and branch-scoped work references before implementation.
- Book of Engineering `0.4.0` adds `$merge-readiness-sync` for reconciling merge-ready change requests with tracker context before merge.
- `plugins/book-of-git/`: the installable Book of Git plugin package.
- `plugins/book-of-git/skills/git-workspace-cleanup/SKILL.md`: the explicit-invocation Git cleanup skill that prunes local worktrees and branches back to main, then updates main.
- `plugins/book-of-git/skills/git-resolve-conflicts/SKILL.md`: the guarded Git conflict resolution skill for making conflicted branches or PRs mergeable against a fetched remote base.
- Book of Git `0.2.0` adds `$git-resolve-conflicts` for resolving merge, rebase, cherry-pick, and PR branch conflicts without pushing automatically.
- `assets/readme/`: README-specific visual assets.
- `assets/book-of/`: approved default book-family visual assets for `book-of-*` plugin scaffolding.
- `docs/adr/0001-adopt-codex-only-harness-direction.md`: the decision record that defines Grimoire as a Codex harnessing repository.
- `docs/maintaining-grimoire.md`: repository-local policy for changing Grimoire skills, plugin packaging, Codex harness assets, documentation, and publishing checks.
- `.agents/plugins/marketplace.json`: the Codex marketplace catalog that exposes local plugins from `./plugins/`.
- `AGENTS.md`: the source-of-truth agent protocol for this repository.

## Installation Notes

For Codex, add this repository as a plugin marketplace:

```bash
codex plugin marketplace add hon454/grimoire
```

Then open the Codex plugin directory and install `archmage`, `book-of-engineering`, or `book-of-git` from the Grimoire marketplace:

```text
codex
/plugins
```

The Codex marketplace catalog points to local plugin paths under `./plugins/`. Each plugin's `.codex-plugin/plugin.json` points to its installable skill directory.

`docs/maintaining-grimoire.md` is repo-local policy for contributors and Codex agents working in this repository. It is not an installable user workflow.

## License

MIT
