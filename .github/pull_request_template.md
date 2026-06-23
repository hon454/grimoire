<!-- PR title: use Conventional Commit style with the narrowest durable scope that describes the affected responsibility. -->

## Summary

<!-- Briefly explain what changed and why. -->

## Changes

<!-- List the concrete changes reviewers should understand first. -->

## Validation

<!-- These checks come from AGENTS.md and docs/maintaining-grimoire.md. Delete items that do not apply, and add any PR-specific checks you ran. -->

- JSON manifests, if changed:
- Plugin assets or Codex plugin manifests, if changed: `python3 scripts/validate-plugin-assets.py`
- Skill validation, if skill content changed:
- README parity, if docs changed:
- `git diff --check`:

## Risk

<!-- Note breaking changes, plugin or marketplace impact, Codex workflow impact, or required follow-up. -->

- Breaking change:
- Plugin or marketplace impact:
- Follow-up required:

## Related Issues (optional)

<!-- Delete this section when there are no closing or related issues. Example: Closes #123 -->
