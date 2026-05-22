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

When a skill writes user-facing narrative output, such as reports, briefings, summaries, handoffs, or generated documents, include a `## Language` section near the top of that skill, before workflow steps or source inspection rules. Use this baseline unless the skill needs narrower wording:

```markdown
## Language

Write user-facing prose in the clearest user language. For bare skill invocations, use the host OS preferred language when readable; otherwise use English.

Ignore triggers, default prompts, commands, paths, identifiers, URLs, templates, logs, and quotes as language signals. Preserve technical text as-is.
```

## Sidecar Metadata

Skill behavior belongs in `SKILL.md`. Platform-specific metadata belongs in sidecar files or client-specific plugin directories.

- Keep shared `SKILL.md` frontmatter minimal and portable.
- Use `name` and `description` as the portable baseline.
- Add Codex sidecars such as `agents/openai.yaml` only when they directly support a skill.
- Do not add platform-specific frontmatter fields to shared `SKILL.md` unless the repository has an explicit compatibility rule.
- If sidecar metadata exists or changes, verify it still matches the shared `SKILL.md`; regenerate it when available tooling supports that.

## Explicit Invocation Skills

Some task-oriented skills should run only when a user explicitly calls them. When adding or updating one of these skills:

1. Say in the skill description that it is explicit-invocation-only and name the expected trigger, such as `$work-briefing`.
2. Add Codex sidecar metadata at `agents/openai.yaml` with `policy.allow_implicit_invocation: false`.
3. Add a Codex `interface.default_prompt` that includes the `$skill-name` trigger.
4. Add `disable-model-invocation: true` to `SKILL.md` frontmatter for Claude Code-compatible readers.
5. Document the Claude Code explicit invocation form in the skill body when the skill is packaged in a plugin, such as `/plugin-name:skill-name`.

This is an explicit compatibility exception to the minimal shared frontmatter rule. Keep the exception limited to skills that are intentionally user-invoked workflows.

## Compatibility

Maintain Codex-first, Claude-compatible packaging:

- `AGENTS.md` is the source of truth for repository instructions.
- `CLAUDE.md` exists as a symbolic link to `AGENTS.md` for Claude Code compatibility.
- Shared instructions should stay Markdown-first so Codex and Claude Code can consume the same source material.
- Client-specific metadata belongs in sidecar files or client-specific plugin directories, not in shared skill bodies.
- Plugin manifests should describe package identity and installation behavior for their client without duplicating repository policy.

## Instruction And Plugin Placement

Use this boundary when deciding where new maintenance material belongs:

- Put always-on repository rules in `AGENTS.md` when every agent working in this repository must see them before doing anything else.
- Put detailed repository maintenance policy in `docs/maintaining-grimoire.md` when the material governs source ownership, packaging, compatibility, publishing, or documentation maintenance.
- Put reusable agent workflows in an installable plugin when installed users should be able to invoke the workflow outside this repository.
- Use Archmage for Grimoire bootstrap, repository-library orientation, skill selection, and other workflows that help agents use or maintain Grimoire as a skill library.
- Use Book of Engineering for current-work engineering context, handoff, briefing, planning, and execution-support workflows.
- Add a separate plugin only when the workflow has a durable user-facing domain boundary that would make Archmage's responsibility unclear.
- Keep repository-only operational policy out of installable plugin `skills/` paths.

## README Maintenance

Keep `README.md` as the canonical English README and `README.ko.md` as its Korean companion.

When changing repository purpose, contents, installation, compatibility, or license details, update both READMEs in the same change. Keep commands, paths, product names, and language-switch links consistent across both files.

Do not modify README files for maintenance-policy-only changes unless the repository purpose, contents, installation, compatibility, or license details visible to readers are changing.

## Plugin Visual Assets

When creating a new `book-of-*` plugin, copy the approved default book assets into the plugin instead of generating new images:

1. Copy `assets/book-of/default-logo.png` to `plugins/<plugin>/assets/logo.png`.
2. Copy `assets/book-of/default-icon.png` to `plugins/<plugin>/assets/icon.png`.
3. Reference them from the Codex manifest as `./assets/logo.png` and `./assets/icon.png`.

Keep the copied default book assets until a human approves a plugin-specific variant in the same family, such as a changed central emblem or cover color. Treat plugin-specific `book-of-*` variants as manual visual asset updates, not as part of initial plugin scaffolding.

When creating an approved plugin-specific `book-of-*` variant:

- Use `assets/book-of/default-logo.png` as the family baseline for the book silhouette, centered placement, transparent padding, and approximate visual footprint.
- Keep the book shape in the same family as the default asset. Limit plugin-specific differentiation to the central emblem, cover color, and a small number of ornamental accent colors.
- Keep the bottom page block in the same warm parchment beige/tan family as the approved default assets. Do not tint pages with the plugin theme color.
- Keep the cover body and left spine in one cohesive color family. Reserve strong accent colors for the central emblem and optional right-side corner or edge ornaments.
- Prefer cel-shaded or hard-faceted painted shading that matches the existing icon family. Avoid smooth gradients, center glows, airbrush shading, vignettes, mottled color noise, and broad color-grading passes.
- If a generated variant misses the approved art direction, regenerate or redraw the image instead of relying on color correction. Limit post-processing to transparency extraction, footprint alignment, small-fringe cleanup, and icon resizing.
- Keep the central emblem simple enough to remain legible in the 256 by 256 composer icon and smaller client surfaces.

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

Text-only plugins may omit visual asset fields until a reviewed asset is available. If any visual asset field is present, keep `interface.logo` and `interface.composerIcon` as a validated pair.

## Publishing Checks

Before publishing, handing off, or committing repository changes:

1. Verify JSON manifests are valid.
2. If plugin visual assets or Codex plugin manifest asset references changed, run `python3 scripts/validate-plugin-assets.py`.
3. Run the available skill validator for each changed skill folder. In Codex, use the `skill-creator` validator when available; otherwise verify equivalent basics manually: YAML frontmatter, required fields, and folder/name alignment. For explicit invocation skills, manually verify `disable-model-invocation: true` if the available validator does not recognize that compatibility field.
4. Review skill descriptions for trigger clarity.
5. Use a Conventional Commit message, such as `{type}({scope}): {summary}`.
6. Use a branch name that exposes the Conventional Commit type, such as `{type}/{slug}`.

For documentation-only policy changes, inspect the changed policy directly for drift against `AGENTS.md`, READMEs, and plugin packaging. Do not expose repository-only maintenance policy as an installable skill.
