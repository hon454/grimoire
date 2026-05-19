# Grimoire

[English](README.md)

Grimoire는 코딩 에이전트를 위한 재사용 가능한 워크플로우 skill을 모아 둔 개인 컬렉션입니다.

이 저장소는 Codex 우선으로 시작하며, 기본 skill 형식이 겹치는 범위에서 Claude Code와의 호환성을 유지합니다. 공유되는 진짜 원본은 `skills/<skill>/SKILL.md`이고, 클라이언트별 메타데이터는 `.codex-plugin/`과 `.claude-plugin/`에 둡니다.

## Status

이 저장소는 새 공개 skeleton입니다. 현재는 bootstrap과 repository-maintenance skill만 의도적으로 포함합니다.

## Contents

- `skills/using-grimoire/SKILL.md`: 에이전트가 작업 전에 적용 가능한 Grimoire skill을 확인하고 로드하도록 요구하는 bootstrap skill입니다.
- `skills/maintaining-grimoire/SKILL.md`: Grimoire skill, manifest, 호환성 파일, publishing check를 변경할 때 쓰는 repository-maintenance skill입니다.
- `AGENTS.md`: 이 저장소의 source-of-truth agent protocol입니다.
- `CLAUDE.md`: Claude Code 호환성을 위해 `AGENTS.md`를 가리키는 symbolic link입니다.

## Installation Notes

Codex 호환 클라이언트에서는 이 저장소를 plugin marketplace로 추가합니다.

```bash
codex plugin marketplace add hon454/grimoire
```

그다음 Codex plugin directory를 열고 Grimoire marketplace에서 `grimoire`를 설치합니다.

```text
codex
/plugins
```

Codex plugin manifest는 `.codex-plugin/plugin.json`에 있으며 `./skills/`를 가리킵니다.

Claude Code 호환 클라이언트에서는 이 저장소를 plugin으로 설치하거나 참조하고 `.claude-plugin/plugin.json` manifest를 사용합니다. `.claude-plugin/marketplace.json`의 local Claude marketplace catalog는 이 저장소를 `./`에서 노출합니다.

## License

MIT
