# 새 책 만들기

이 문서는 grimoire 체크아웃 안에서 새 플러그인(`book-of-*`)을 만들고 검증하고 릴리스하는 절차입니다. 에이전트에게 시키려면 archmage의 `binding-a-book` 스킬이 같은 절차를 영어로 담고 있습니다.

## 1. 뼈대 생성

```bash
node tools/grimoire.mjs new-book book-of-<domain> --description "<한 문장 설명>" [--category "<Codex 카테고리>"] [--skill <동명사형-스킬명>]
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

- 이름은 동명사형(`doing-something`)이고 모든 플러그인을 통틀어 유일해야 합니다.
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
node --test
claude plugin validate . --strict
claude plugin validate ./plugins/book-of-<domain> --strict
```

`check`가 "stale"을 보고하면 `node tools/grimoire.mjs stamp`로 마켓플레이스를 재생성합니다.

## 5. 로컬 설치로 확인

`dev-install` 도구는 2차 커밋에서 추가됩니다. 그 전까지는 아래 수동 절차를 씁니다.

Claude Code: 디렉토리 마켓플레이스는 파일을 제자리에서 읽으므로 수정이 바로 반영됩니다.

```bash
claude plugin marketplace add G:/grimoire
claude plugin install book-of-<domain>@grimoire
```

Codex: `~/.codex/config.toml`에 로컬 마켓플레이스를 등록한 뒤 설치합니다. Codex는 플러그인을 캐시로 복사하므로 수정 후에는 `codex plugin remove` 후 다시 `add` 해야 반영됩니다.

```toml
[marketplaces.grimoire]
source_type = "local"
source = 'G:\grimoire'
```

```bash
codex plugin add book-of-<domain>@grimoire
```

같은 이름 `grimoire`로 GitHub 마켓플레이스가 이미 등록되어 있으면 충돌합니다. Claude는 등록을 거부하고 Codex는 TOML 테이블을 덮어씁니다. 개발 중에는 GitHub 등록을 제거하고 로컬을 등록했다가 끝나면 되돌리는 방식(swap)을 쓰며, 이것이 `dev-install`/`dev-uninstall`이 자동화할 절차입니다. Claude에서 마켓플레이스를 제거하면 그 마켓플레이스 플러그인의 데이터와 설정도 함께 삭제되니 주의합니다.

## 6. 릴리스

1. `plugins/<book>/VERSION`을 새 버전으로 수정합니다.
2. `CHANGELOG.md`의 `[Unreleased]` 내용을 `## [<version>] - <날짜>` 아래로 옮깁니다.
3. `node tools/grimoire.mjs stamp <book>`으로 두 매니페스트와 마켓플레이스에 버전을 반영합니다.
4. `check`와 테스트를 돌리고 커밋한 뒤 `<book>/v<version>` 태그를 붙입니다.

`stamp --set X.Y.Z`를 쓰면 1번과 3번을 한 번에 할 수 있지만, CHANGELOG를 쓰기 전까지 `check`는 실패합니다. 의도된 동작입니다.
