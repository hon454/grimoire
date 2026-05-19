---
name: maintaining-grimoire
description: Use when modifying the Grimoire skill library itself, including adding or updating skills, plugin manifests, repository instructions, compatibility files, sidecar metadata, or publishing checks.
---

# Maintaining Grimoire

Use this skill only when changing the Grimoire repository itself.

## Repository Shape

Grimoire is a personal, public skill library for reusable coding-agent workflows.

Shared skill behavior belongs in `skills/<skill>/SKILL.md`. Client-specific packaging belongs in the matching plugin manifest directory.

## Skill Authoring

When adding or updating a skill:

1. Use a stable, literal skill directory name under `skills/`.
2. Put the complete shared instructions in `skills/<skill>/SKILL.md`.
3. Keep the frontmatter `name` stable and literal.
4. Make the `description` concrete enough for agents to decide when to use the skill.
5. Keep the body focused on operational instructions, not roadmap notes or promised future work.
6. Prefer platform-neutral capability names in shared instructions, such as "native shell", "native plan tool", or "host skill mechanism", instead of client-specific tool names.
7. Add bundled resources only when they directly support the skill.

## Sidecar Metadata

Skill behavior belongs in `skills/<skill>/SKILL.md`. Platform-specific metadata belongs in sidecar files.

- Keep shared `SKILL.md` frontmatter minimal and portable.
- Use `name` and `description` as the portable baseline.
- Add Codex sidecars such as `agents/openai.yaml` when they directly support the skill.
- Do not add platform-specific frontmatter fields to shared `SKILL.md` unless the repository has an explicit compatibility rule.

## Compatibility

Maintain Codex-first, Claude-compatible packaging:

- `AGENTS.md` is the source of truth for repository instructions.
- `CLAUDE.md` must remain a symbolic link to `AGENTS.md`.
- `.codex-plugin/plugin.json` points to `./skills/`.
- `.claude-plugin/plugin.json` describes the same package identity.
- Client-specific metadata belongs in sidecar files or client-specific plugin directories, not in shared skill bodies.

## Publishing Checks

Before publishing or handing off repository changes:

1. Verify JSON manifests are valid.
2. Verify `CLAUDE.md` is still a symlink to `AGENTS.md`.
3. Verify `.ephemeral/` is not part of committed changes.
4. Run the available skill validator for each changed skill folder. In Codex, use the `skill-creator` validator when available; otherwise verify equivalent basics manually: YAML frontmatter, required fields, and folder/name alignment.
5. If a sidecar such as `agents/openai.yaml` exists or changes, verify it still matches the shared `SKILL.md`; regenerate it when available tooling supports that.
6. Review skill descriptions for trigger clarity.
7. Use a Conventional Commit message, such as `{type}({scope}): {summary}`.
8. Use a branch name that exposes the Conventional Commit type, such as `{type}/{slug}`.
