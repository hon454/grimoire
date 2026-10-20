---
status: accepted
date: 2026-10-20
supersedes: []
superseded-by: null
---
# 레포 자기 문서화는 규약, 개요, 결정 기록, 조사 노트의 네 종류로 나눈다

> 베이스라인 설계 결정 18개를 `DESIGN.md` 한 장에 적어 둔 상황에서, 결정이 번복될 때 이력과 근거가 사라지는 문제에 직면하여, 우리는 항상 로드되는 규약(`AGENTS.md`), 살아있는 개요(`ARCHITECTURE.md`), 불변 결정 기록(`docs/decisions/`), 불변 조사 노트(`docs/research/`)의 분리를 택하고 단일 문서 유지와 spec-kit식 기능별 문서 폴더를 배제했다. 현재 상태를 한 장으로 읽으면서도 번복 이력을 추적하기 위해, 변경마다 문서 두세 곳을 함께 갱신하는 비용을 감수한다.

## 맥락과 문제

첫 커밋의 `docs/DESIGN.md`는 결정표와 근거, 레퍼런스 조사 요약, 열린 위험을 모두 담고 있었다. 이 구조는 결정이 뒤집힐 때 "왜 전에는 그렇게 했는가"가 git 이력에만 남고, 조사 자료와 결정과 현재 상태가 한 파일에서 섞인다. [조사 노트](../research/2026-10-20-sdd-doc-structures.md)에서 spec-kit, Kiro, OpenSpec, BMAD, Anthropic feature-dev, superpowers, ADR 규격을 비교했다.

조사에서 드러난 공통 패턴은 다음과 같다. 항상 로드되는 전역 문서는 작고 분리되어 있다. 결정은 어디서나 Decision / Rationale / Alternatives 삼항으로 기록된다. 설계 문서는 조건부로만 쓴다. 코드와 문서는 같은 커밋에서 맞춘다. 에이전트 프레임워크 중 ADR을 기본 탑재한 곳은 없다.

## 고려한 선택지

1. `DESIGN.md` 단일 파일을 제자리 수정: 가장 단순하지만 번복 이유가 커밋 메시지에만 남고 파일이 비대해진다.
2. 개요 문서 + `docs/decisions/` ADR: 현재 상태는 한 장, 이력은 결정 단위로 남는다. 파일이 늘고 두 곳을 함께 갱신해야 한다.
3. ADR만, 개요 없음: 현재 상태를 알려면 ADR을 전부 읽어야 한다.
4. 주제별 분할(`ARCHITECTURE`, `CONVENTIONS`, `HARNESS-NOTES`): 결정 이력은 여전히 없고 규약은 `AGENTS.md`와 중복된다.
5. spec-kit식 기능별 폴더(`spec`, `plan`, `research`, `tasks`): grimoire의 "기능"은 스킬이나 책 한 권이고 산출물이 마크다운이라 스펙과 구현의 거리가 거의 없다. 과하다.

## 결정

2번을 택하고, 다음을 함께 정한다.

- 개요 문서 이름은 `ARCHITECTURE.md`다. `DESIGN`은 구현 전 설계 문서를, `STATUS`는 진행 대시보드를, `CONTEXT`는 에이전트 주입 컨텍스트(`AGENTS.md`의 역할)를 연상시켜 배제했다.
- ADR 형식은 MADR 최소형(맥락과 문제 / 고려한 선택지 / 결정 / 결과)에 `status`, `date`, `supersedes`, `superseded-by` 프론트매터와 제목 아래 Y-statement 요약 한 문장을 더한다. 선택지 비교란이 있어 설계 논의에서 쓴 선택지 표를 그대로 옮길 수 있다.
- 한 ADR은 독립적으로 번복될 수 있는 결정 하나다. 질문 하나에 하나가 아니다. 사소한 규약(author 표기, 라이선스, Node 하한, category 기본값)은 `AGENTS.md`에 적는다.
- 조사 노트는 `docs/research/YYYY-MM-DD-slug.md`로 날짜 접두, 결정은 `NNNN-slug.md`로 순번이다. 조사는 시간순 자료이고 결정은 참조 안정성이 중요하다.
- 규약을 바꾸는 변경은 ADR, `AGENTS.md`, `ARCHITECTURE.md` 갱신을 같은 커밋에 담는다.
- 언어는 하네스가 읽는 파일(`AGENTS.md`, SKILL.md, 훅, 매니페스트, 스크립트)은 영어, 사람이 읽는 문서(README, `docs/`)는 한국어다.
- 계획 문서는 커밋하지 않는다. 계획은 세션 안에서 소비하고 결과만 CHANGELOG와 ADR에 남긴다.

## 결과

- 좋음: 현재 상태는 `ARCHITECTURE.md` 한 장으로 읽히고, 번복은 `superseded-by` 링크로 추적된다. 조사 자료가 결정의 입력으로 보존된다.
- 나쁨: 규약 변경마다 세 문서를 함께 손봐야 한다. ADR이 많아지면 색인이 길어진다.
- 재검토 조건: ADR이 수십 개를 넘어 색인이 읽히지 않게 되거나, 기여자가 늘어 번호 충돌이 생기면 날짜 접두나 범주 하위 디렉토리를 검토한다.
- 확인 수단: `tools/grimoire.mjs check`가 `docs/decisions/` 파일명 순번과 프론트매터, `ARCHITECTURE.md`가 참조하는 ADR의 존재를 검사한다.
