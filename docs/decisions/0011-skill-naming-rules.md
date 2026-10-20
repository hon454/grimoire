---
status: accepted
date: 2026-10-21
supersedes: [0007-skills-only-component-policy.md]
superseded-by: null
---
# 스킬 이름은 주제를 가리키는 가장 짧은 kebab-case 이름이며 관사와 긴 이름을 금지한다

> 책 이름이 이미 네임스페이스인 맥락에서, 동명사 강제가 긴 이름과 관사를 낳고 `tdd` 같은 도메인 용어의 정체성을 지우는 문제에 직면하여, 우리는 형태를 강제하지 않는 짧은 주제 이름(관사 금지, 4단어 상한, 전 플러그인 유일)을 택하고 동명사 유지, 동명사 권장, 완전 자유 형식을 배제했다. 호출이 짧고 도메인 용어가 그대로 보이게 하기 위해, 책마다 이름 양식이 조금씩 달라질 수 있음을 감수한다.

## 맥락과 문제

ADR 0007은 스킬 이름을 kebab-case 동명사구(`reading-the-grimoire`)로 정했다. 근거는 책의 장(章) 제목처럼 읽히고 동사+목적어라 충돌이 적다는 것이었다. `check`와 `new-book`은 첫 단어가 `ing`로 끝나는지만 정규식으로 검사했다.

첫 책 `book-of-engineering`의 첫 스킬 두 개(ADR 작성, TDD)의 이름을 짓자 문제가 드러났다.

- 동명사구는 길어진다(`recording-a-decision`, `developing-test-first`).
- 관사가 섞인다(`writing-an-adr`). 관사를 빼면 영어로 어색하다(`writing-adr`).
- TDD처럼 이름 자체가 정체성인 도메인 용어가 동명사 뒤에 숨는다. `writing-tests-first`는 "테스트 먼저"로만 읽히고 `red-green-refactoring`은 첫 단어가 동명사가 아니라 규칙에 걸린다.
- 검사가 겉핥기라 `string-theory`는 통과하고 `red-green-refactoring`은 막힌다.

두 하네스에서 스킬은 Claude Code에서 `<book>:<skill>`, Codex에서 `$<skill>`(실측상 플러그인 네임스페이스 포함)로 보인다. 책 이름이 이미 맥락을 주므로 스킬 이름이 서술형일 이유가 약하다. Claude 공식 플러그인은 `code-review`, `simplify`처럼 짧은 명사·명령형을 쓰고, mattpocock/skills는 `tdd`, `diagnosing-bugs`, `to-spec`을 혼용한다. 충돌 억제 효과도 0007의 주장만큼 크지 않다. `reviewing-code`가 두 책에 생기면 `code-review`와 똑같이 충돌하며, 충돌은 어차피 `check`의 유일성 검사가 잡는다.

## 고려한 선택지

1. 동명사 유지 + 관사 금지·길이 상한 추가: 변경이 적지만 규칙만 늘고 도메인 용어 문제는 남는다. `binding-a-book`이 관사를 써서 archmage 개명은 어차피 따라온다.
2. 동명사 권장, 검사는 kebab-case와 유일성만: 유연하지만 책이 늘수록 혼용으로 흘러간다(mattpocock/skills가 그 결과).
3. 짧은 주제 이름으로 전환, 형태 비강제, 기계 검사는 kebab-case·유일성·관사 금지·단어 수 상한: 공식 플러그인 관행과 같고 호출이 짧다. 일반어 충돌이 잦아질 수 있으나 유일성 검사가 잡는다.
4. 자유 형식, 유일성만 강제: 가장 자유롭지만 긴 이름과 관사를 막을 수 없다.

## 결정

3번을 택한다. 스킬 이름 규칙은 다음과 같다.

- 주제를 가리키는 가장 짧은 이름을 쓴다. 도메인 용어(`tdd`, `adr`)가 그 설명(`writing-tests-first`)보다 낫다. 동사가 필요하면 동명사(`reviewing-pull-requests`)도 허용한다.
- kebab-case이고, 관사(`a`, `an`, `the`)를 단어로 포함하지 않으며, 4단어 이하(권장 1~3단어)이고, 모든 플러그인을 통틀어 유일하다. `check`와 `new-book`이 네 가지를 모두 검사한다.
- archmage의 스킬은 이 규칙에 맞게 개명한다: `reading-the-grimoire` → `required-reading`, `binding-a-book` → `book-binding`. archmage는 0.2.0으로 올린다. SessionStart 훅이 읽는 스킬 경로도 함께 바꾼다.
- `book-of-engineering`의 첫 두 스킬은 `adr`과 `tdd`로 짓는다.

이 ADR은 0007의 이름 규칙만 대체한다. 0007의 나머지 정책, 즉 `commands/`·`bin/`·플러그인 루트 `CLAUDE.md` 금지, `SKILL.md` 프론트매터 허용 목록(`name`, `description`, `metadata`, `license`, `allowed-tools`), `name`과 폴더명 일치, "Use when ..." 트리거 설명, `agents/openai.yaml` 사이드카 필수, 실행 파일은 `scripts/`에 두고 인터프리터 경유 호출은 그대로 유효하다.

## 결과

- 좋음: `/book-of-engineering:tdd`, `$tdd`처럼 호출이 짧고 도메인 용어가 그대로 보인다. 관사와 긴 이름은 기계가 막는다. `red-green-refactoring`과 `code-review`가 모두 통과한다.
- 나쁨: 책마다 명사형과 동명사형이 섞일 수 있다. `review`, `setup` 같은 일반어는 먼저 쓴 책이 차지하고 뒤에 오는 책은 더 구체적인 이름을 써야 한다. archmage 설치자는 스킬 이름이 바뀐다(플러그인 갱신 시 캐시 전체가 다시 복사되므로 옛 이름은 남지 않는다).
- 재검토 조건: 일반어 충돌이 실제로 잦아지면 유일성 범위를 책 단위로 좁히는 안(네임스페이스에 의존)을 다시 본다. 4단어 상한이 실제 이름을 막으면 상한을 조정한다.
- 확인 수단: `check`와 `new-book`의 `skillNameProblem` 검사. `tests/check.test.mjs`, `tests/new-book.test.mjs`.
