<div align="center">
  <p>
    <img src="assets/readme/hero.png" width="960" alt="Archmage reading a glowing code grimoire in a magical library">
  </p>
  <h1>Grimoire</h1>
  <p><strong>재사용 가능한 에이전트 workflow를 위한 Codex harnessing asset입니다.</strong></p>
  <p><a href="README.md">English</a></p>
</div>

Grimoire는 `hon454`가 유지보수하는 개인 Codex harnessing repository입니다. 소유자의 Codex 환경을 위한 재사용 가능한 Codex skill, plugin, hook, workflow instruction, tool integration guidance를 packaging합니다.

## Status

이 저장소는 현재 Archmage, Book of Engineering, Book of Git plugin 및 repository-local maintenance policy를 노출합니다. 여기 commit된 Codex asset과 policy를 넘어선 roadmap content는 약속하지 않습니다.

## Plugins

Grimoire는 현재 다음 설치 가능한 plugin을 제공합니다.

| Icon | Plugin | 설명 |
| --- | :---: | --- |
| <img src="plugins/archmage/assets/icon.png" width="72" alt="Archmage icon"> | [**Archmage**](plugins/archmage/) | Codex agent가 Grimoire를 일관되게 사용하고 유지보수하도록 돕는 운영 workflow와 hook입니다. 적용 가능한 workflow 선택, Grimoire config 로딩, 재사용 가능한 Grimoire 이슈의 upstream 보고, skill 개선에 초점을 둡니다. |
| <img src="plugins/book-of-engineering/assets/icon.png" width="72" alt="Book of Engineering icon"> | [**Book&nbsp;of&nbsp;Engineering**](plugins/book-of-engineering/) | 현재 작업 맥락을 이해하고 다음 행동을 고르며, 구현 전 work item 유효성 감사와 issue readiness review를 수행하는 engineering workflow입니다. |
| <img src="plugins/book-of-git/assets/icon.png" width="72" alt="Book of Git icon"> | [**Book&nbsp;of&nbsp;Git**](plugins/book-of-git/) | local repository를 이해 가능하고 복구 가능한 상태로 유지하기 위한 Git workflow입니다. workspace hygiene, branch discipline, guarded repository cleanup, conflict resolution에 초점을 둡니다. |

## Contents

- `plugins/archmage/`: 설치 가능한 Archmage plugin package입니다.
- `plugins/archmage/skills/using-grimoire/SKILL.md`: Codex agent가 작업 전에 적용 가능한 Grimoire skill을 확인하고 로드하도록 요구하는 설치 가능한 bootstrap skill입니다.
- `plugins/archmage/skills/report-grimoire-issue/SKILL.md`: upstream Grimoire GitHub issue를 초안화하고 확인 후에만 게시하는 명시적 호출 issue-reporting skill입니다.
- `plugins/archmage/skills/writing-great-skills/SKILL.md`: 예측 가능한 Codex skill을 작성하고 편집하기 위한 명시적 호출 reference skill입니다.
- `plugins/archmage/hooks/resolve_grimoire_config.py`: user/project `.grimoire/config.toml`을 병합해 검증된 session config cache를 만드는 SessionStart config resolver입니다.
- Archmage `0.3.0`은 출력 현지화와 issue tracker 기본값을 위한 Grimoire session config hook을 추가합니다.
- `plugins/book-of-engineering/`: 설치 가능한 Book of Engineering plugin package입니다.
- `plugins/book-of-engineering/skills/now-what/SKILL.md`: 현재 작업 맥락을 triage하고 다음 행동을 추천하는 명시적 호출 skill입니다.
- `plugins/book-of-engineering/skills/issue-preflight/SKILL.md`: tracker를 변경하지 않고 구현 전 tracker issue, linked change, branch-scoped work reference를 검증하는 명시적 호출 skill입니다.
- `plugins/book-of-engineering/skills/issue-readiness-review/SKILL.md`: tracker를 변경하지 않고 구현 가능한 issue body와 변경사항 요약 comment 초안을 만드는 명시적 호출 readiness review skill입니다.
- Book of Engineering `0.4.0`은 구현 전 in-boundary open question을 해소하고 tracker-ready issue update 초안을 만드는 `$issue-readiness-review`를 추가합니다.
- `plugins/book-of-git/`: 설치 가능한 Book of Git plugin package입니다.
- `plugins/book-of-git/skills/git-workspace-cleanup/SKILL.md`: local worktree와 branch를 main만 남기도록 정리한 뒤 main을 최신화하는 명시적 호출 Git cleanup skill입니다.
- `plugins/book-of-git/skills/git-resolve-conflicts/SKILL.md`: fetched remote base를 기준으로 conflict가 있는 branch나 PR을 merge 가능하게 만드는 guarded Git conflict resolution skill입니다.
- Book of Git `0.2.0`은 자동 push 없이 merge, rebase, cherry-pick, PR branch conflict를 해결하기 위한 `$git-resolve-conflicts`를 추가합니다.
- `assets/readme/`: README 전용 visual asset입니다.
- `assets/book-of/`: `book-of-*` plugin scaffolding에 쓰는 승인된 기본 book-family visual asset입니다.
- `docs/adr/0001-adopt-codex-only-harness-direction.md`: Grimoire를 Codex harnessing repository로 정의한 decision record입니다.
- `docs/maintaining-grimoire.md`: Grimoire skill, plugin packaging, Codex harness asset, 문서, publishing check를 변경할 때 쓰는 repository-local policy입니다.
- `.agents/plugins/marketplace.json`: `./plugins/` 아래 local plugin을 노출하는 Codex marketplace catalog입니다.
- `AGENTS.md`: 이 저장소의 source-of-truth agent protocol입니다.

## Installation Notes

Codex에서는 이 저장소를 plugin marketplace로 추가합니다.

```bash
codex plugin marketplace add hon454/grimoire
```

그다음 Codex plugin directory를 열고 Grimoire marketplace에서 `archmage`, `book-of-engineering`, 또는 `book-of-git`을 설치합니다.

```text
codex
/plugins
```

Codex marketplace catalog는 `./plugins/` 아래 local plugin path들을 가리킵니다. 각 plugin의 `.codex-plugin/plugin.json`은 설치 가능한 skill directory를 가리킵니다.

Archmage는 Codex SessionStart hook을 포함합니다. plugin을 설치하거나 업데이트한 뒤, 생성되는 Grimoire session config를 사용하기 전에 Codex에서 해당 hook을 검토하고 신뢰 처리해야 합니다.

## Grimoire Config

Archmage는 선택적인 user/project config 파일을 읽고, user `output.locale`이 없으면 OS 선호 locale로 bootstrap한 뒤, SessionStart hook 실행 시 검증된 session config cache를 작성합니다.

- user config: `~/.grimoire/config.toml`
- project config: `<repo>/.grimoire/config.toml`

지원하는 key는 의도적으로 좁게 유지합니다.

```toml
schema_version = 1

[output]
locale = "{locale}" # 예: "ko-KR"

[tracker]
primary = "github" # "github", "linear", "none" 중 하나

[tracker.linear]
team_identifier = "{TEAM}"
```

`output.locale`은 `ko-KR`, `en-US`, `zh-TW` 같은 valid locale tag여야 합니다. 자연어 이름이나 `ko_KR.UTF-8` 같은 host-style locale 형식은 config에서 허용하지 않지만, OS preferred-locale detection은 host/env 값을 canonical tag로 normalize할 수 있습니다.

`docs/maintaining-grimoire.md`는 이 저장소에서 작업하는 contributor와 Codex agent를 위한 repo-local policy입니다. 설치 가능한 user workflow가 아닙니다.

## License

MIT
