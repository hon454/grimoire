# 새 책 만들기

이 문서는 grimoire 체크아웃 안에서 새 플러그인(`book-of-*`)을 만들고 검증하고 릴리스하는 절차입니다. 에이전트에게 시키려면 archmage의 `book-binding` 스킬이 같은 절차를 영어로 담고 있습니다.

## 1. 뼈대 생성

```bash
node tools/grimoire.mjs new-book book-of-<domain> --description "<한 문장 설명>" [--category "<Codex 카테고리>"] [--skill <스킬명>]
```

생성되는 것:

- `plugins/book-of-<domain>/VERSION` (0.1.0), `CHANGELOG.md`, `README.md`
- `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json` (`hooks: {}` 상태)
- `--skill`을 주면 `skills/<skill>/SKILL.md`와 `skills/<skill>/agents/openai.yaml`
- 마켓플레이스 2장 재생성

이름은 kebab-case이고 `book-of-`로 시작해야 합니다. `archmage`만 예외입니다. `description`은 영어로 씁니다. 두 매니페스트와 마켓플레이스에 그대로 들어가기 때문입니다.

## 2. 스킬 작성

`skills/<name>/SKILL.md`:

```markdown
---
name: reviewing-a-pull-request
description: Use when the user asks to review a pull request or a diff. Walks through ...
metadata:
  plugin: book-of-engineering
---

# Reviewing a pull request
...
```

- 이름은 주제를 가리키는 가장 짧은 kebab-case 이름(`tdd`, `adr`, `code-review`)입니다. 관사(`a`, `an`, `the`)를 넣지 않고 4단어 이하이며 모든 플러그인을 통틀어 유일해야 합니다. 동사가 필요하면 동명사(`reviewing-pull-requests`)도 됩니다(ADR 0011).
- 프론트매터 키는 `name`, `description`, `metadata`, `license`, `allowed-tools`만 허용됩니다. Claude 전용 값은 `metadata` 아래에 둡니다.
- `description`은 두 하네스가 스킬을 고르는 근거입니다. "Use when ..."으로 시작하는 트리거 문장 뒤에 무엇을 하는지 한두 문장을 씁니다.
- 스크립트는 `node scripts/x.mjs`처럼 인터프리터 경유로 호출하도록 본문에 씁니다.
- 다른 책의 파일을 링크하지 않습니다.

`skills/<name>/agents/openai.yaml`은 Codex UI 메타데이터입니다. `display_name`, `short_description`, `policy.allow_implicit_invocation`을 채웁니다. 사용자가 명시적으로 불러야 하는 스킬이면 `allow_implicit_invocation: false`로 둡니다.

## 3. 훅 추가 (선택)

1. `hooks/hooks.json`을 만듭니다. 이벤트는 `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `PermissionRequest`, `Stop`, `SubagentStart`, `SubagentStop`, `PreCompact`, `SessionEnd`만 씁니다.
2. matcher는 Claude 이름(`Bash`, `Edit|Write`, `Agent`)으로 씁니다. Codex가 별칭으로 받아들입니다.
3. 명령은 `node "${CLAUDE_PLUGIN_ROOT}/scripts/x.mjs"` 형태로 씁니다.
4. `.codex-plugin/plugin.json`의 `hooks`를 `{}`에서 `"./hooks/hooks.json"`으로 바꿉니다.
5. 스크립트는 `plugins/archmage/scripts/session-start.mjs`를 참고합니다. stdin JSON을 읽고, 하네스를 환경변수로 판별하고, 실패하면 출력 없이 0으로 종료합니다.

## 4. 검증

```bash
node tools/grimoire.mjs check
node tools/run-tests.mjs
claude plugin validate . --strict
claude plugin validate ./plugins/book-of-<domain> --strict
```

`check`가 "stale"을 보고하면 `node tools/grimoire.mjs stamp`로 마켓플레이스를 재생성합니다.

## 5. 로컬 설치로 확인

두 하네스 모두 플러그인을 캐시에 **복사**해 설치하므로, 체크아웃을 고쳐도 재설치 전에는 반영되지 않습니다. 이 반복을 `tools/grimoire.mjs`의 dev 명령이 맡습니다(ADR 0009, swap 모델).

```bash
node tools/grimoire.mjs dev-status      # 두 하네스의 grimoire 등록 상태와 설치된 플러그인
node tools/grimoire.mjs dev-install     # 처음 한 번: 마켓플레이스 grimoire를 이 체크아웃으로 교체하고 플러그인 설치
node tools/grimoire.mjs dev-refresh     # 고칠 때마다: 양쪽 캐시에 플러그인을 다시 복사
node tools/grimoire.mjs dev-uninstall   # 끝나면: 마켓플레이스를 GitHub(hon454/grimoire)로 되돌림
```

동작 규칙:

- 마켓플레이스 이름은 `grimoire` 하나만 씁니다. `grimoire-dev` 같은 두 번째 이름이나 `--plugin-dir` 동시 로드는 스킬이 두 번 보이고 훅이 두 번 돌기 때문에 쓰지 않습니다.
- 모든 명령은 현재 상태와 실행할 단계를 먼저 출력하고, `--yes`가 없으면 확인을 받습니다. `--dry-run`은 계획만 보여 줍니다. 비대화형 셸에서는 `--yes`가 필요합니다.
- Claude에서 마켓플레이스를 제거하면 그 마켓플레이스 플러그인들의 데이터·옵션·시크릿이 삭제됩니다. `dev-install`(GitHub에서 교체할 때)과 `dev-uninstall`은 이 단계에 경고를 붙입니다. `dev-refresh`는 `uninstall --keep-data`를 써서 데이터를 보존합니다.
- 플러그인 ID(`archmage@grimoire`)는 교체 전후로 같아서 `enabledPlugins`를 건드리지 않습니다. 교체 전에 설치되어 있던 플러그인만 다시 설치하고, 아무것도 없었다면 레포의 모든 플러그인을 설치합니다.
- Codex의 훅 신뢰는 플러그인 ID와 `hooks.json` 해시 기준으로 `config.toml`에 남으므로 `dev-refresh` 뒤에도 유지됩니다. `hooks.json`을 고치면 Codex 대화형 화면의 `/hooks`에서 다시 신뢰해야 합니다.

도구 없이 손으로 할 때의 명령은 다음과 같습니다. Claude는 `claude plugin marketplace add <체크아웃 경로>` 뒤 `claude plugin install <plugin>@grimoire`, Codex는 `codex plugin marketplace add <체크아웃 경로>` 뒤 `codex plugin add <plugin>@grimoire`입니다. 같은 이름의 GitHub 등록이 이미 있으면 먼저 `marketplace remove grimoire`를 해야 합니다.

## 6. 릴리스

1. `plugins/<book>/VERSION`을 새 버전으로 수정합니다.
2. `CHANGELOG.md`의 `[Unreleased]` 내용을 `## [<version>] - <날짜>` 아래로 옮깁니다.
3. `node tools/grimoire.mjs stamp <book>`으로 두 매니페스트와 마켓플레이스에 버전을 반영합니다.
4. `check`와 테스트를 돌리고 커밋한 뒤 `<book>/v<version>` 태그를 붙입니다.

`stamp --set X.Y.Z`를 쓰면 1번과 3번을 한 번에 할 수 있지만, CHANGELOG를 쓰기 전까지 `check`는 실패합니다. 의도된 동작입니다.
