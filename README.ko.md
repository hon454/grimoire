<div align="center">
  <p>
    <img src="assets/readme/hero.png" width="960" alt="Grimoire figure reading a glowing code grimoire in a magical library">
  </p>
  <h1>Grimoire</h1>
  <p><strong>재사용 가능한 에이전트 workflow를 위한 Codex harnessing asset입니다.</strong></p>
  <p><a href="README.md">English</a></p>
</div>

Grimoire는 `hon454`가 유지보수하는 개인 Codex harnessing repository입니다. 소유자의 Codex 환경을 위한 재사용 가능한 Codex skill, plugin, hook, workflow instruction, tool integration guidance를 packaging합니다.

## Status

이 저장소는 현재 설치 가능한 Grimoire plugin 하나와 repository-local maintenance policy를 노출합니다. 여기 commit된 Codex asset과 policy를 넘어선 roadmap content는 약속하지 않습니다.

## Plugin

Grimoire는 현재 설치 가능한 harness plugin 하나를 제공합니다.

| Icon | Plugin | 설명 |
| --- | :---: | --- |
| <img src="plugins/grimoire/assets/icon.png" width="72" alt="Grimoire icon"> | [**Grimoire**](plugins/grimoire/) | Grimoire bootstrap, skill authoring, handoff prompt 생성, 검증된 side-conversation handoff, current-work triage, issue preflight, readiness review와 Linear closeout, locale-grounded translation, evidence-bound review response, Git cleanup, conflict resolution을 위한 workflow skill과 hook입니다. |

## Contents

- `plugins/grimoire/`: 설치 가능한 Grimoire plugin package입니다.
- `plugins/grimoire/hooks/resolve_grimoire_config.py`: user/project `.grimoire/config.toml`을 병합해 검증된 session config cache를 만드는 SessionStart config resolver입니다.
- `plugins/grimoire/skills/using-grimoire/SKILL.md`: Codex agent가 작업 전에 적용 가능한 Grimoire skill을 확인하고 로드하도록 요구하는 bootstrap skill입니다.
- `plugins/grimoire/skills/report-grimoire-issue/SKILL.md`: upstream Grimoire GitHub issue를 초안화하고 확인 후에만 게시하는 명시적 호출 issue-reporting skill입니다.
- `plugins/grimoire/skills/writing-great-skills/SKILL.md`: 예측 가능한 Codex skill을 작성하고 편집하기 위한 명시적 호출 reference skill입니다.
- `plugins/grimoire/skills/create-handoff-prompt/SKILL.md`: 선택한 대화 맥락을 다른 작업에 복사할 수 있는 자기완결적 prompt로 만드는 명시적 호출 skill입니다.
- `plugins/grimoire/skills/handoff-to-main-task/SKILL.md`: host가 식별한 임시 side conversation에서 유일하게 검증된 main task로 guarded handoff를 preview하고 보내는 명시적 호출 skill입니다.
- `plugins/grimoire/references/handoff-composition.md`: 두 handoff skill이 공유하는 비노출 composition contract입니다.
- `plugins/grimoire/skills/now-what/SKILL.md`: 현재 작업 맥락을 triage하고 다음 행동을 추천하는 명시적 호출 skill입니다.
- `plugins/grimoire/skills/issue-preflight/SKILL.md`: tracker를 변경하지 않고 구현 전 tracker issue, linked change, branch-scoped work reference를 검증하는 명시적 호출 skill입니다.
- `plugins/grimoire/skills/issue-readiness-review/SKILL.md`: tracker를 변경하지 않고 readiness에 맞는 tracker update 초안을 만드는 명시적 호출 readiness review skill입니다.
- `plugins/grimoire/skills/linear-issue-closeout/SKILL.md`: 독립적인 읽기 전용 reviewer 검토 후 근거가 충분한 Linear issue를 완료 상태로 전환하고 comment를 작성하는 명시적 호출 closeout skill입니다.
- `plugins/grimoire/skills/magical-translation/SKILL.md`: user-facing text를 번역하기 전에 Grimoire session config cache에서 locale을 읽는 번역 skill입니다.
- `plugins/grimoire/skills/magical-review-response/SKILL.md`: GitHub PR review 또는 pasted feedback을 위한 Thread-owned Review Session을 하나 생성하거나 resume하고, 결정을 versioned Evidence와 Action Envelope에 결합하며, 승인된 작업의 검증과 reviewer follow-up journal까지 처리하는 명시적 호출 review-response workflow입니다.
- `plugins/grimoire/skills/git-workspace-cleanup/SKILL.md`: local worktree와 branch를 main만 남기도록 정리한 뒤 main을 최신화하는 명시적 호출 Git cleanup skill입니다.
- `plugins/grimoire/skills/git-resolve-conflicts/SKILL.md`: fetched remote base를 기준으로 conflict가 있는 branch나 PR을 merge 가능하게 만드는 guarded Git conflict resolution skill입니다.
- `assets/readme/`: README 전용 visual asset입니다.
- `docs/adr/0001-adopt-codex-only-harness-direction.md`: Grimoire를 Codex harnessing repository로 정의한 decision record입니다.
- `docs/maintaining-grimoire.md`: Grimoire skill, plugin packaging, Codex harness asset, 문서, publishing check를 변경할 때 쓰는 repository-local policy입니다.
- `.agents/plugins/marketplace.json`: `plugins/grimoire/`를 노출하는 Codex marketplace catalog입니다.
- `AGENTS.md`: 이 저장소의 source-of-truth agent protocol입니다.

## Review Response Session

GitHub PR review locator 또는 한 batch의 pasted review feedback과 함께 `$magical-review-response`를 명시적으로 호출합니다. 이 skill은 현재 Codex task에 Review Session 하나를 생성하거나 resume하고, authoritative state와 deterministic read-only detail view를 다음 경로에 저장합니다.

```text
<GRIMOIRE_HOME>/review-response/threads/<thread-id>/
├── state.json
└── review.html
```

Session은 중단 이후에도 Source snapshot, Review Item, versioned Evidence, 결정, active authorization, local progress와 remote mutation attempt를 보존합니다. 산출물은 기본적으로 유지됩니다. 같은 task에서 다른 PR로 전환하려면 먼저 remote 상태를 조정하고, 현재 Session 폐기에 대한 명시적 승인을 받은 뒤, state-last purge가 성공해야 새 PR Session을 시작할 수 있습니다.

## Installation Notes

Codex에서는 이 저장소를 plugin marketplace로 추가합니다.

```bash
codex plugin marketplace add hon454/grimoire
```

그다음 Codex plugin directory를 열고 Grimoire marketplace에서 `grimoire`를 설치합니다.

```text
codex
/plugins
```

Codex marketplace catalog는 `./plugins/grimoire`를 가리킵니다. plugin manifest는 설치 가능한 skill directory를 가리키며, Codex는 번들된 SessionStart hook을 기본 `hooks/hooks.json` 경로에서 탐색합니다.

Grimoire는 Codex SessionStart hook을 포함합니다. plugin을 설치하거나 업데이트한 뒤, 생성되는 Grimoire session config를 사용하기 전에 Codex에서 해당 hook을 검토하고 신뢰 처리해야 합니다.

Migration note: 기존에 `archmage`, `book-of-engineering`, `book-of-git`을 설치했다면 `grimoire`를 설치하거나 업데이트하고 hook을 다시 신뢰 처리한 뒤, 이전 local plugin install이 아직 보이면 제거하면 됩니다. 기존 `$skill-name` trigger는 유지되지만 `$handoff`는 이제 `$create-handoff-prompt`입니다.

## Grimoire Config

Grimoire plugin은 선택적인 user/project config 파일을 읽고, user `output.locale`이 없으면 OS 선호 locale로 bootstrap한 뒤, SessionStart hook 실행 시 검증된 session config cache를 작성합니다.

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
