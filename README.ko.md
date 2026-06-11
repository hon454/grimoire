<div align="center">
  <p>
    <img src="assets/readme/hero.png" width="960" alt="Archmage reading a glowing code grimoire in a magical library">
  </p>
  <h1>Grimoire</h1>
  <p><strong>코딩 에이전트를 위한 재사용 가능한 워크플로우 skill 모음입니다.</strong></p>
  <p><a href="README.md">English</a></p>
</div>

Grimoire는 `hon454`가 유지보수하는 source library입니다. 설치 가능한 plugin은 `plugins/` 아래에 있으며, Codex 우선 사용과 기본 skill 형식이 겹치는 범위의 Claude Code 호환 reader를 위해 packaging합니다.

## Status

이 저장소는 현재 Archmage, Book of Engineering, Book of Git plugin 및 repository-local maintenance policy를 노출합니다. 여기 commit된 skill과 policy를 넘어선 roadmap content는 약속하지 않습니다.

## Plugins

Grimoire는 현재 다음 설치 가능한 plugin을 제공합니다.

| Icon | Plugin | 설명 |
| --- | :---: | --- |
| <img src="plugins/archmage/assets/icon.png" width="72" alt="Archmage icon"> | [**Archmage**](plugins/archmage/) | 코딩 에이전트가 Grimoire를 일관되게 사용하고 유지보수하도록 돕는 운영 workflow입니다. 적용 가능한 workflow 선택, 필요한 맥락 로딩, 재사용 가능한 Grimoire 이슈의 upstream 보고에 초점을 둡니다. |
| <img src="plugins/book-of-engineering/assets/icon.png" width="72" alt="Book of Engineering icon"> | [**Book&nbsp;of&nbsp;Engineering**](plugins/book-of-engineering/) | 현재 작업 맥락을 이해하고 다음 행동을 고르며, 구현 전 work item 유효성을 감사하는 engineering workflow입니다. |
| <img src="plugins/book-of-git/assets/icon.png" width="72" alt="Book of Git icon"> | [**Book&nbsp;of&nbsp;Git**](plugins/book-of-git/) | local repository를 이해 가능하고 복구 가능한 상태로 유지하기 위한 Git workflow입니다. workspace hygiene, branch discipline, guarded repository cleanup에 초점을 둡니다. |

## Contents

- `plugins/archmage/`: 설치 가능한 Archmage plugin package입니다.
- `plugins/archmage/skills/using-grimoire/SKILL.md`: 에이전트가 작업 전에 적용 가능한 Grimoire skill을 확인하고 로드하도록 요구하는 설치 가능한 bootstrap skill입니다.
- `plugins/archmage/skills/report-grimoire-issue/SKILL.md`: upstream Grimoire GitHub issue를 초안화하고 확인 후에만 게시하는 명시적 호출 issue-reporting skill입니다.
- Archmage `0.2.0`은 재사용 가능한 Grimoire 문서, skill, plugin packaging, 호환성, workflow 보고를 위한 `$report-grimoire-issue`를 추가합니다.
- `plugins/book-of-engineering/`: 설치 가능한 Book of Engineering plugin package입니다.
- `plugins/book-of-engineering/skills/now-what/SKILL.md`: 현재 작업 맥락을 triage하고 다음 행동을 추천하는 명시적 호출 skill입니다.
- `plugins/book-of-engineering/skills/issue-preflight/SKILL.md`: tracker를 변경하지 않고 구현 전 tracker issue, linked change, branch-scoped work reference를 검증하는 명시적 호출 skill입니다.
- Book of Engineering `0.3.0`은 구현 전 tracker issue, linked change, branch-scoped work reference의 유효성을 확인하는 `$issue-preflight`를 추가합니다.
- `plugins/book-of-git/`: 설치 가능한 Book of Git plugin package입니다.
- `plugins/book-of-git/skills/git-workspace-cleanup/SKILL.md`: local worktree와 branch를 main만 남기도록 정리한 뒤 main을 최신화하는 명시적 호출 Git cleanup skill입니다.
- `assets/readme/`: README 전용 visual asset입니다.
- `assets/book-of/`: `book-of-*` plugin scaffolding에 쓰는 승인된 기본 book-family visual asset입니다.
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

그다음 Codex plugin directory를 열고 Grimoire marketplace에서 `archmage`, `book-of-engineering`, 또는 `book-of-git`을 설치합니다.

```text
codex
/plugins
```

Codex marketplace catalog는 `./plugins/` 아래 local plugin path들을 가리킵니다. 각 plugin의 `.codex-plugin/plugin.json`은 설치 가능한 skill directory를 가리킵니다.

Claude Code 호환 local marketplace reader에서는 `.claude-plugin/marketplace.json`이 `./plugins/` 아래 같은 local plugin package들을 노출하며, 각 plugin의 `.claude-plugin/plugin.json` metadata와 일치합니다.

`docs/maintaining-grimoire.md`는 이 저장소에서 작업하는 contributor와 agent를 위한 repo-local policy입니다. 설치 가능한 user workflow가 아닙니다.

## License

MIT
