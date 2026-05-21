# Maintaining Grimoire

This document is repository policy for maintaining Grimoire. `AGENTS.md` remains the top-level protocol; this document owns detailed maintenance rules for skills, plugin packaging, compatibility, documentation, and publishing checks.

## Repository Shape

Grimoire is a personal, public skill library for reusable coding-agent workflows.

Source-owned shared skill behavior belongs in `skills/<skill>/SKILL.md` unless that workflow has been moved into a packaged plugin. Client-specific packaging belongs under the matching plugin directory, such as `plugins/<plugin>/.codex-plugin/`, `plugins/<plugin>/.claude-plugin/`, `plugins/<plugin>/skills/`, and plugin assets.

Repository-only policy belongs in `AGENTS.md` or `docs/`, not in `skills/`, because installed users should not receive repository maintenance instructions as an installable workflow.

## Skill Authoring

When adding or updating a source-owned skill:

1. Use a stable, literal skill directory name under the appropriate `skills/` directory.
2. Put complete shared instructions in `SKILL.md`.
3. Keep frontmatter `name` stable and literal.
4. Make `description` concrete enough for agents to decide when to use the skill.
5. Keep the body focused on operational instructions, not roadmap notes or promised future work.
6. Prefer platform-neutral capability names in shared instructions, such as "native shell", "native plan tool", or "host skill mechanism", instead of client-specific tool names.
7. Add bundled resources only when they directly support the skill.

Keep skills small and readable. Split broad catch-all instructions into narrower workflows when separate trigger criteria or proof obligations would make them easier to use correctly.

## Sidecar Metadata

Skill behavior belongs in `SKILL.md`. Platform-specific metadata belongs in sidecar files or client-specific plugin directories.

- Keep shared `SKILL.md` frontmatter minimal and portable.
- Use `name` and `description` as the portable baseline.
- Add Codex sidecars such as `agents/openai.yaml` only when they directly support a skill.
- Do not add platform-specific frontmatter fields to shared `SKILL.md` unless the repository has an explicit compatibility rule.
- If sidecar metadata exists or changes, verify it still matches the shared `SKILL.md`; regenerate it when available tooling supports that.

## Compatibility

Maintain Codex-first, Claude-compatible packaging:

- `AGENTS.md` is the source of truth for repository instructions.
- `CLAUDE.md` exists as a symbolic link to `AGENTS.md` for Claude Code compatibility.
- Shared instructions should stay Markdown-first so Codex and Claude Code can consume the same source material.
- Client-specific metadata belongs in sidecar files or client-specific plugin directories, not in shared skill bodies.
- Plugin manifests should describe package identity and installation behavior for their client without duplicating repository policy.

## Instruction And Archmage Placement

Use this boundary when deciding where new maintenance material belongs:

- Put always-on repository rules in `AGENTS.md` when every agent working in this repository must see them before doing anything else.
- Put detailed repository maintenance policy in `docs/maintaining-grimoire.md` when the material governs source ownership, packaging, compatibility, publishing, or documentation maintenance.
- Put reusable agent workflows in Archmage when installed users should be able to invoke the workflow outside this repository.
- Keep repository-only operational policy out of Archmage and out of installable `skills/` paths.
- Move a workflow into Archmage only when it is reusable across repositories and does not depend on Grimoire's local governance, repository layout, or publishing responsibilities.

## README Maintenance

Keep `README.md` as the canonical English README and `README.ko.md` as its Korean companion.

When changing repository purpose, contents, installation, compatibility, or license details, update both READMEs in the same change. Keep commands, paths, product names, and language-switch links consistent across both files.

Do not modify README files for maintenance-policy-only changes unless the repository purpose, contents, installation, compatibility, or license details visible to readers are changing.

## Plugin Visual Assets

Do not create plugin visual assets automatically during scaffolding or maintenance. Add `logo` and `composerIcon` only after a human has supplied or approved the assets.

When manually adding or updating plugin images:

- Use only source images with clear usage rights, or manually approved original assets.
- Do not directly clean up watermarked stock images into repository assets. If a reference image has a watermark, use a separately supplied or approved original mark that avoids copying the protected source.
- If both are present, keep `logo` and `composerIcon` visually related, but optimize the icon for small-size recognition.
- Use transparent PNG assets by default, with no text, watermark, decorative floating particles, shadows, or background fill.
- Center the subject and leave enough transparent padding so the mark is not clipped in rounded or masked client surfaces.
- Store plugin visual assets under the plugin's `./assets/` directory and reference them from the Codex manifest with `./assets/...` paths.
- Treat copyright clearance, brand fit, and small-size legibility as manual review items; do not rely on automation for those judgments.

For Codex plugin assets, keep the current repository convention unless the upstream client requirement changes. These manifest fields are optional, but if present they must point to matching assets:

- `interface.logo`: 512 by 512 pixel RGBA PNG.
- `interface.composerIcon`: 256 by 256 pixel RGBA PNG.

## Publishing Checks

Before publishing, handing off, or committing repository changes:

1. Verify JSON manifests are valid.
2. If plugin visual assets or Codex plugin manifest asset references changed, run `python3 scripts/validate-plugin-assets.py`.
3. Run the available skill validator for each changed skill folder. In Codex, use the `skill-creator` validator when available; otherwise verify equivalent basics manually: YAML frontmatter, required fields, and folder/name alignment.
4. Review skill descriptions for trigger clarity.
5. Use a Conventional Commit message, such as `{type}({scope}): {summary}`.
6. Use a branch name that exposes the Conventional Commit type, such as `{type}/{slug}`.

For documentation-only policy changes, inspect the changed policy directly for drift against `AGENTS.md`, READMEs, and plugin packaging. Do not expose repository-only maintenance policy as an installable skill.
