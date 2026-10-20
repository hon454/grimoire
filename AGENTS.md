# grimoire: agent and contributor instructions

grimoire is a multi-plugin repository (a "spellbook") that ships the same plugins to Claude Code and Codex at the same time. Every plugin under `plugins/` is a book. `archmage` is the required reading: it carries the meta skills that teach an agent how to use and extend the grimoire.

Human-facing docs (README, `docs/`) are written in Korean. Everything a harness reads (SKILL.md, hooks, manifests, scripts, this file) is written in English.

## Layout

```
.claude-plugin/marketplace.json     generated: Claude Code marketplace (name: grimoire)
.agents/plugins/marketplace.json    generated: Codex marketplace (same plugin list)
plugins/<plugin>/                   one plugin per directory
  VERSION                           single source of the plugin version (semver)
  CHANGELOG.md                      Keep a Changelog; newest entry must equal VERSION
  .claude-plugin/plugin.json        Claude Code manifest
  .codex-plugin/plugin.json         Codex manifest (never a root plugin.json, see rules)
  skills/<skill>/SKILL.md           shared body, read by both harnesses
  skills/<skill>/agents/openai.yaml Codex UI metadata sidecar
  hooks/hooks.json                  shared body, read by both harnesses (optional)
  scripts/*.mjs                     Node scripts called by hooks and skills
tools/grimoire.mjs                  maintainer tool: check, stamp, new-book
tests/                              node --test suites for the tool, templates and hooks
docs/                               design and authoring docs (Korean)
```

## Commands

```bash
node tools/grimoire.mjs check              # validate every plugin and both marketplaces
node tools/grimoire.mjs stamp [plugin]     # write VERSION into manifests, regenerate marketplaces
node tools/grimoire.mjs new-book <name>    # scaffold plugins/<name> (name must be book-of-*)
node --test                         # run the test suites
claude plugin validate . --strict          # official Claude Code validator (marketplace root)
```

Run `check` before every commit. CI runs `check`, the tests, and `claude plugin validate --strict`.

## Rules that `check` enforces

- Plugin names are kebab-case. Only `archmage` may skip the `book-of-` prefix.
- `VERSION`, both manifests' `version`, and the newest `CHANGELOG.md` heading agree.
- Both manifests share `name` and `description`. `name` equals the directory name.
- No root `plugin.json` in a plugin: Codex reads it ahead of `.codex-plugin/plugin.json` and then loads no plugin hooks.
- The Codex manifest always sets `hooks`: `"./hooks/hooks.json"` when that file exists, `{}` otherwise. Omitting the key makes Codex auto-load `hooks/hooks.json`.
- No `commands/` (skills only), no `bin/` (claude.ai and Cowork refuse plugins that have one), no symlinks (Codex drops them), no `CLAUDE.md` inside a plugin root.
- Every skill directory holds `SKILL.md` whose frontmatter `name` equals the directory name, has a `description`, and uses only `name`, `description`, `metadata`, `license`, `allowed-tools`. Every skill also has `agents/openai.yaml`.
- Skill names are gerund phrases (`reading-the-grimoire`) and unique across all plugins.
- `hooks/hooks.json` uses only events both harnesses support and matchers in Claude's names (`Bash`, `Edit|Write`, `Agent`), which Codex aliases. Every `${CLAUDE_PLUGIN_ROOT}/...` path it references must exist.
- No personal absolute paths (`C:\Users\...`, `/Users/...`, `/home/...`) inside `plugins/`.
- Both marketplace files are up to date with the plugins on disk.

## Conventions

- Hook and helper scripts are dependency-free Node (`.mjs`), Node 20 or newer. No Bun, no `node_modules`.
- Invoke scripts through the interpreter in prose and hooks (`node "${CLAUDE_PLUGIN_ROOT}/scripts/x.mjs"`), never by bare path: some packagers strip executable bits.
- Use `${CLAUDE_PLUGIN_ROOT}` for plugin-relative paths. Codex sets the same variable for compatibility.
- Plugins never reference files outside their own root and never depend on another plugin.
- Claude-only components (`agents/`, `userConfig`) go only in the Claude manifest. Codex-only metadata (`interface`) goes only in the Codex manifest.
- Line endings are LF everywhere (`.gitattributes`).

## Adding a plugin

1. `node tools/grimoire.mjs new-book book-of-<domain> --description "..." [--category "..."] [--skill <gerund-name>]`
2. Write the skills. Keep `SKILL.md` frontmatter to the allowed keys; put anything else under `metadata`.
3. `node tools/grimoire.mjs check`, then `node --test`.
4. Add a `CHANGELOG.md` entry, commit, and tag `<plugin>/v<version>` when releasing.
