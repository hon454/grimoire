---
status: accepted
date: 2026-10-20
supersedes: []
superseded-by: null
---
# 플러그인 매니페스트는 손으로 쓰고 마켓플레이스는 생성하며 `VERSION`을 도구가 스탬프한다

> 플러그인마다 매니페스트 2장과 마켓플레이스 2장에 같은 이름·버전·설명이 들어가는 맥락에서, 손으로 맞추면 드리프트가 나고 전부 생성하면 하네스 고유 내용까지 추상화해야 하는 문제에 직면하여, 우리는 매니페스트는 손 작성·마켓플레이스는 생성·버전은 `VERSION` 파일에서 스탬프하는 방식을 택하고 `book.yaml` 전체 생성기와 전수 수동 관리를 배제했다. 중복은 도구가 맡고 하네스 고유 내용은 사람이 쓰게 하기 위해, `stamp`를 잊으면 `check`가 실패하는 절차 비용을 감수한다.

## 맥락과 문제

레퍼런스 다섯 곳 모두 플러그인 매니페스트를 손으로 쓴다. 자동화는 버전 스탬프(superpowers `.version-bump.json`, pstack-claude `tools/generate.mjs`, ECC `release.sh`, mattpocock `sync-plugin-version.mjs`)와 일치성 검사(`--check`, 매니페스트 테스트)에 한정된다. pstack-claude는 `VERSION` 파일을 단일 소스로 두고 생성기가 5개 매니페스트에 버전을 찍은 뒤 CI와 pre-commit에서 `--check`를 돌린다. grimoire는 플러그인이 여럿이라 마켓플레이스 2장이 플러그인 수만큼 항목을 가진다.

## 고려한 선택지

1. 전부 손으로 쓰고 검증 스크립트로 일치성만 검사: 책이 늘수록 마켓플레이스 2장을 손으로 맞추는 비용이 커진다.
2. `book.yaml` 단일 소스에서 매니페스트 2장과 마켓플레이스 2장을 전부 생성: Codex `interface`, Claude `userConfig` 같은 하네스 고유 필드까지 추상 스키마로 감싸야 하고, 생성물과 소스가 둘 다 커밋된다.
3. 매니페스트는 손 작성, 마켓플레이스는 생성, 버전은 `VERSION`에서 스탬프: 마켓플레이스는 순수 파생물이고 매니페스트는 고유 내용을 담는다는 성격 차이를 그대로 따른다.

## 결정

3번을 택한다.

- 플러그인마다 `VERSION` 파일이 버전의 단일 소스다. `tools/grimoire.mjs stamp`가 두 매니페스트의 `version`에 쓴다.
- `.claude-plugin/marketplace.json`과 `.agents/plugins/marketplace.json`은 각 플러그인의 매니페스트에서 생성한다. Codex `category`는 `.codex-plugin/plugin.json`의 `interface.category`를 단일 소스로 삼아 두 마켓플레이스에 복사하고, 없으면 `Developer Tools`다.
- `check`는 두 매니페스트의 `name`, `version`, `description` 일치, `VERSION`과의 일치, 마켓플레이스 신선도를 검사한다. `check`는 아무것도 고치지 않는다.
- `new-book`이 `tools/templates/`에서 새 플러그인 뼈대를 만든다.
- 도구는 플러그인 안이 아니라 레포 루트 `tools/`에 둔다. 배포물에 섞이면 안 되고, 플러그인은 자기 루트 밖을 볼 수 없으며, CI는 하네스 없이 맨 Node로 돌아야 한다. archmage의 `binding-a-book` 스킬이 이 도구를 호출하는 진입점이다.

## 결과

- 좋음: 중복은 생성과 검사로 막히고, 하네스 고유 내용은 해당 매니페스트에서 직접 편집한다. 생성기 스키마를 설계하지 않아도 된다.
- 나쁨: 버전을 올린 뒤 `stamp`를 잊으면 `check`가 실패한다(의도된 동작). 마켓플레이스 파일을 손으로 고치면 다음 `stamp`에서 덮어써진다.
- 재검토 조건: 하네스별 매니페스트 필드가 늘어 두 장의 공통 부분이 커지면 2번(전체 생성)을 다시 본다.
- 확인 수단: `tests/check.test.mjs`, `tests/new-book.test.mjs`, CI의 `check`와 `claude plugin validate --strict`.
