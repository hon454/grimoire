# Grimoire

[English](README.md)

Grimoire는 코딩 에이전트를 위한 재사용 가능한 워크플로우 skill을 모아 둔 개인 컬렉션입니다.

Grimoire는 `hon454`가 유지보수하는 source library입니다. 설치 가능한 plugin은 `plugins/` 아래에 있으며, Codex 우선 사용과 기본 skill 형식이 겹치는 범위의 Claude Code 호환 reader를 위해 packaging합니다.

## Status

이 저장소는 현재 Archmage와 Book of Engineering plugin 및 repository-local maintenance policy를 노출합니다. 여기 commit된 skill과 policy를 넘어선 roadmap content는 약속하지 않습니다.

## Contents

- `plugins/archmage/`: 설치 가능한 Archmage plugin package입니다.
- `plugins/archmage/skills/using-grimoire/SKILL.md`: 에이전트가 작업 전에 적용 가능한 Grimoire skill을 확인하고 로드하도록 요구하는 설치 가능한 bootstrap skill입니다.
- `plugins/book-of-engineering/`: 설치 가능한 Book of Engineering plugin package입니다.
- `plugins/book-of-engineering/skills/work-briefing/SKILL.md`: 현재 작업 상태 briefing을 작성하는 명시적 호출 handoff skill입니다.
- `docs/maintaining-grimoire.md`: Grimoire skill, plugin packaging, 호환성 파일, 문서, publishing check를 변경할 때 쓰는 repository-local policy입니다.
- `.agents/plugins/marketplace.json`: `./plugins/` 아래 local plugin을 노출하는 Codex marketplace catalog입니다.
- `.claude-plugin/marketplace.json`: `./plugins/` 아래 local plugin을 노출하는 local Claude-compatible marketplace catalog입니다.
- `AGENTS.md`: 이 저장소의 source-of-truth agent protocol입니다.
- `CLAUDE.md`: Claude Code 호환성을 위해 `AGENTS.md`를 가리키는 symbolic link입니다.

## Installation Notes

Codex 호환 클라이언트에서는 이 저장소를 plugin marketplace로 추가합니다.

```bash
codex plugin marketplace add hon454/grimoire
```

그다음 Codex plugin directory를 열고 Grimoire marketplace에서 `archmage` 또는 `book-of-engineering`을 설치합니다.

```text
codex
/plugins
```

Codex marketplace catalog는 `./plugins/` 아래 local plugin path들을 가리킵니다. 각 plugin의 `.codex-plugin/plugin.json`은 설치 가능한 skill directory를 가리킵니다.

Claude Code 호환 local marketplace reader에서는 `.claude-plugin/marketplace.json`이 `./plugins/` 아래 같은 local plugin package들을 노출하며, 각 plugin의 `.claude-plugin/plugin.json` metadata와 일치합니다.

`docs/maintaining-grimoire.md`는 이 저장소에서 작업하는 contributor와 agent를 위한 repo-local policy입니다. 설치 가능한 user workflow가 아닙니다.

## License

MIT
