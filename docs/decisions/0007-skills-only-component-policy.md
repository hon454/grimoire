---
status: superseded
date: 2026-10-20
supersedes: []
superseded-by: 0011-skill-naming-rules.md
---
# 플러그인은 스킬만 제공하고 `commands/`와 `bin/`을 금지하며 스킬 이름과 프론트매터를 제한한다

> 두 하네스가 같은 플러그인을 읽는 맥락에서, Claude 전용 컴포넌트와 하네스마다 다른 스킬 메타데이터 규칙이 호환성을 깨는 문제에 직면하여, 우리는 스킬 전용 정책(`commands/` 금지, `bin/` 금지, 동명사 이름, 프론트매터 허용 목록, 사이드카 필수)을 택하고 커맨드 허용과 하네스별 예외를 배제했다. 어느 하네스와 배포 채널에서도 같은 플러그인이 설치되게 하기 위해, Claude 커맨드의 인자 편의 기능을 포기한다.

## 맥락과 문제

Claude Code의 `commands/*.md`는 슬래시 커맨드가 되지만 사용자 호출 가능한 스킬도 같은 메뉴에 뜬다. pstack-claude는 "커맨드 트램펄린이 메뉴에 두 번 보인다"는 이유로 `commands/`를 CI에서 금지했고, ECC는 커맨드를 레거시 심으로만 남기며, Anthropic 문서도 새 플러그인은 `skills/`를 쓰라고 권한다. Codex에는 플러그인 수준 커맨드가 없어 커맨드를 쓰면 pstack처럼 Codex용 프롬프트 스텁 생성기가 필요하다. 플러그인에 `bin/`이 있으면 claude.ai와 Cowork가 설치를 거부한다. Codex 스킬 프론트매터 검증기는 `name`, `description`, `metadata`, `license`, `allowed-tools`만 허용한다고 ECC가 기록했다. mattpocock, ECC, gstack은 스킬마다 `agents/openai.yaml` 사이드카로 Codex UI 메타데이터를 제공한다.

## 고려한 선택지

1. 스킬만, `commands/`와 `bin/` 금지: 하네스 간 1:1 대응, 생성 레이어 불필요.
2. 커맨드 허용: Claude 전용 편의(`argumentHint`, `$ARGUMENTS`)를 얻지만 Codex 스텁 생성기와 메뉴 중복이 생긴다.
3. Claude 전용 책에서만 커맨드 허용: 동시 지원 원칙에 예외가 생기고 `check` 규칙이 책마다 달라진다.

스킬 이름은 동명사형(`reading-the-grimoire`), 명령형(`read-grimoire`), 명사 하나(`grimoire`), 호출 주체별 혼용 중 동명사형을 택했다. 책의 장(章) 같은 서술형이고 동사+목적어라 충돌이 적다.

## 결정

1번을 택하고 스킬 규약을 다음과 같이 정한다.

- `commands/`, `bin/`, 플러그인 루트 `CLAUDE.md`는 `check`가 오류로 막는다.
- 스킬 폴더명은 kebab-case 동명사형이며 모든 플러그인을 통틀어 유일하다. Codex의 네임스페이스 규칙이 확인되기 전까지 충돌을 원천 차단한다(이후 실측에서 Codex도 `플러그인:스킬`로 네임스페이스함을 확인했지만 규칙은 유지한다).
- `SKILL.md` 프론트매터는 `name`, `description`, `metadata`, `license`, `allowed-tools`만 쓴다. `name`은 폴더명과 같고 `description`은 "Use when ..."으로 시작하는 트리거 문장이다. Claude 전용 설정은 `metadata` 아래에 둔다.
- 스킬마다 `agents/openai.yaml`에 `interface.display_name`, `interface.short_description`, `policy.allow_implicit_invocation`을 둔다.
- 실행 파일은 `scripts/`에 두고 인터프리터 경유로 호출한다.

## 결과

- 좋음: claude.ai, Cowork, Claude Code CLI, Codex CLI와 앱 어디서나 같은 플러그인이 설치된다. 슬래시 메뉴 중복이 없다.
- 나쁨: 인자를 받는 명령형 워크플로우는 스킬 본문에서 사용자 입력을 해석하는 방식으로 써야 한다.
- 재검토 조건: Codex가 플러그인 커맨드를 지원하거나 Claude가 커맨드와 스킬의 메뉴 중복을 해소하면 2번을 다시 본다. Codex 프론트매터 허용 목록은 실측으로 재확인한다.
- 확인 수단: `check`의 금지 규칙, 이름 규칙, 프론트매터 키 검사, 사이드카 검사. `tests/check.test.mjs`.
