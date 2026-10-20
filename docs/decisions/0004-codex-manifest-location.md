---
status: accepted
date: 2026-10-20
supersedes: []
superseded-by: null
---
# Codex 매니페스트는 `.codex-plugin/plugin.json`에 두고 루트 `plugin.json`을 금지한다

> archmage의 SessionStart 훅이 Codex에서 실행되어야 하는 맥락에서, 루트 `plugin.json`이 있으면 Codex가 플러그인 훅을 로드하지 않는 문제에 직면하여, 우리는 `.codex-plugin/plugin.json`을 택하고 루트 매니페스트와 이중 매니페스트를 배제했다. 훅 실행과 검증된 설치 경로를 얻기 위해, 공식 스키마의 확장 구조를 쓰지 못하는 단점을 감수한다.

## 맥락과 문제

Codex 공식 문서는 Agent Plugins 스키마(`$schema: https://agent-plugins.org/schemas/1.0.0/plugin.schema.json`)의 루트 `plugin.json`을 새 표준으로 권장하고, `.codex-plugin/plugin.json`은 "루트의 `extensions."com.openai"` 객체가 없을 때의 호환 폴백"으로 설명한다. 그런데 pstack-claude는 이슈 265에서 "Codex는 루트 `plugin.json`을 `.codex-plugin/plugin.json`보다 먼저 읽고, 그 경우 플러그인 훅을 전혀 로드하지 않는다"고 기록하고, 루트 `plugin.json`의 존재를 CI 불변식으로 금지한다. archmage는 SessionStart 훅을 쓴다.

관련 사실 하나 더: Codex는 매니페스트에 `hooks` 필드가 없으면 `hooks/hooks.json`을 자동 로드한다. superpowers는 `"hooks": {}`로 이를 억제하며, 빈 배열이나 필드 생략은 다시 자동 탐색으로 떨어진다고 테스트에 적어 두었다.

## 고려한 선택지

1. 루트 `plugin.json`(공식 권장 포맷): 훅이 로드되지 않는다.
2. `.codex-plugin/plugin.json`(호환 포맷): 훅이 로드된다. `interface`를 최상위에 둔다.
3. 둘 다 두고 내용 동기화: 1번과 같은 훅 문제를 그대로 가지며 드리프트 위험이 추가된다.

## 결정

2번을 택한다. 훅이 실행되는 것이 공식 포맷 준수보다 중요하다. 함께 정한 것:

- `check`는 플러그인 루트의 `plugin.json` 존재를 오류로 처리한다.
- Codex 매니페스트는 `hooks` 필드를 항상 명시한다. `hooks/hooks.json`이 있으면 `"./hooks/hooks.json"`, 없으면 정확히 `{}`다. 의도를 파일에 드러내고 자동 탐색에 기대지 않는다.
- `skills`는 `"./skills/"`로 명시한다(번들 플러그인과 레퍼런스가 모두 그렇게 한다).

## 결과

- 좋음: 훅이 로드된다. pstack-claude와 ECC가 실제 배포에 쓰는 경로다.
- 나쁨: 공식 스키마의 `extensions."com.openai"` 구조와 `onboardingSkill` 같은 새 필드가 폴백 포맷에서도 동작하는지는 개별 확인이 필요하다.
- 재검토 조건: Codex가 루트 매니페스트에서도 플러그인 훅을 로드하도록 고치면(pstack-claude 이슈 265 추적) 이 ADR을 superseded 처리하고 루트 포맷으로 옮기는 새 ADR을 쓴다.
- 확인 수단: `tools/grimoire.mjs check`의 금지 규칙과 `hooks` 필드 검사, `tests/check.test.mjs`. 2026-10-20 Codex CLI 로컬 설치에서 매니페스트와 스킬 발견은 확인했고, 훅 실행은 `/hooks` 신뢰 절차 뒤에 확인할 예정이다.
