# 조사 노트: 스펙 주도 개발 도구와 결정 기록 프레임워크의 문서 구조

- 날짜: 2026-10-20
- 목적: grimoire 레포의 자기 문서화 체계(개요 문서, 결정 기록, 조사 노트)를 정하기 위해, 에이전트 지향 SDD 도구와 ADR 규격이 문서를 어떻게 나누고 동기화하는지 조사한다.
- 방법: 서브에이전트 2개가 공식 문서와 레포(raw 파일, API 디렉토리 목록)를 직접 읽었고, Claude 공식 마켓플레이스 캐시의 `feature-dev`, `plugin-dev`, `claude-md-management` 플러그인과 superpowers 클론은 로컬에서 직접 확인했다. 확인하지 못한 항목은 마지막 절에 적었다.
- 결과 반영: 이 노트의 결론은 문서 체계 결정 기록(ADR)의 입력이다. 노트 자체는 불변이며, 이후 상황 변화는 새 노트로 남긴다.

## 1. 조사 대상 요약

### GitHub spec-kit (main, 1.2.2 기준)

- 기능별 폴더 `specs/<NNN|YYYYMMDD-HHMMSS>-<short-name>/`에 `spec.md`(WHAT/WHY), `plan.md`(HOW), `research.md`, `data-model.md`, `contracts/`, `quickstart.md`, `tasks.md`, `checklists/`가 쌓인다. `spec.md`만 `/speckit.plan`의 필수 입력이다.
- 프로젝트 전역 문서는 `.specify/memory/constitution.md` 하나다. 원칙 5개 + 자유 섹션 2개 + 거버넌스로 구성되고, semver 버전과 `Ratified`/`Last Amended` 날짜를 가진다. 거버넌스 조항: "개정은 의존 템플릿과 명령 지침에 같은 변경 안에서 전파되어야 하며, 파일 상단의 Sync Impact Report에 기록한다."
- 자동 전파 기능은 v0.14.4에서 제거됐다. 이유는 "단일 소스를 복제하고 프리셋/오버라이드 합성과 충돌한다"는 것이고, 대신 `plan`, `tasks`, `analyze`가 실행 시점에 constitution을 읽는다. 템플릿은 `[Gates determined based on constitution file]`이라는 포인터만 갖는다.
- 결정 기록은 `research.md`의 `Decision / Rationale / Alternatives considered` 삼항과 `plan.md`의 Complexity Tracking 표뿐이다. ADR 메커니즘은 코어에 없고 커뮤니티 카탈로그 확장으로만 존재한다.
- `[NEEDS CLARIFICATION]` 정책이 바뀌었다. 원문 철학은 "추측하지 말라"였지만 현행 명령은 "합리적 기본값을 택하고 범위·보안·UX에 큰 영향을 주는 것만 최대 3개 표시"다. 나머지는 `## Assumptions`에 적는다.
- 스펙 유지보수 모델은 CLI 설정이 아니라 팀 규약이다. `docs/concepts/spec-persistence.md`는 Flow-back(산출물에 반영 후 재조정), Flow-forward(완료 산출물은 불변, 변경은 새 폴더), Living spec(`spec.md` 수정 후 파생물 재생성) 셋을 제시하고 "코어에는 `spec.md`, `plan.md`, `tasks.md`를 자동으로 재조정하는 명령이 없다"고 명시한다.
- 에이전트 컨텍스트 파일(CLAUDE.md, AGENTS.md 등)은 옵트인 확장 `agent-context`만 다룬다. 관리 블록은 `<!-- SPECKIT START/END -->` 마커 사이이며 현재 내용은 "현재 plan.md를 읽어라"는 포인터 한 문단뿐이다.
- 다중 에이전트: `templates/commands/*.md`가 단일 소스이고, 통합 클래스(Markdown/TOML/YAML/Skills)가 에이전트별 디렉토리(`.claude/skills`, `.agents/skills`, `.gemini/commands` 등)로 렌더링한다. `__SPECKIT_COMMAND_PLAN__` 같은 플레이스홀더가 `/speckit.plan`, `$speckit-plan` 등으로 치환된다.

### AWS Kiro

- `.kiro/specs/<feature>/`에 `requirements.md`(EARS: `WHEN ... THE SYSTEM SHALL ...`), `design.md`, `tasks.md` 삼종. 버그는 `bugfix.md`(현재 동작 / 기대 동작 / 회귀 방지 동작).
- 전역은 `.kiro/steering/`의 `product.md`, `tech.md`, `structure.md`. 프론트매터 `inclusion: always | fileMatch | manual | auto`로 로드 조건을 건다. 모범 사례: "표준의 이유를 설명하라", "steering 변경은 코드 변경처럼 리뷰하라".
- 결정 기록 전용 문서 없음. 동기화는 IDE의 Refine / Sync Files 버튼으로 수동 보조.

### OpenSpec (Fission-AI)

- `openspec/specs/<capability>/spec.md`가 살아있는 진실이고, 변경은 `openspec/changes/<change>/`에 `proposal.md`(WHY), 선택적 `design.md`, `tasks.md`, 델타 스펙(`## ADDED | MODIFIED | REMOVED | RENAMED Requirements`)으로 쌓인 뒤 `changes/archive/YYYY-MM-DD-<change>/`로 아카이브되며 델타가 본 스펙에 병합된다.
- `design.md`는 조건부다. "횡단 변경, 새 외부 의존성, 보안·성능·마이그레이션 복잡도, 모호성" 중 하나라도 해당할 때만 만든다. 섹션에 `## Decisions`("왜 X를 Y 대신 택했는가, 고려한 대안 포함")가 있다.
- 조사한 도구 중 유일하게 기계 검증이 있다. `openspec validate --strict`, 시나리오 제목은 정확히 `####`, 체크박스는 `[x]`만 완료로 인정.
- 전역 컨텍스트는 `openspec/config.yaml`의 `context`(모든 프롬프트에 주입)와 `rules`(산출물별). 과거의 `project.md`는 "에이전트가 읽을 수도 안 읽을 수도 있는 수동적 문서"라는 이유로 폐기됐다.

### BMAD-METHOD (요약)

- 역할 에이전트가 문서를 소유한다. v4: PM이 `docs/prd.md`, Architect가 `docs/architecture.md`, PO가 샤딩, QA가 `docs/qa/gates/*.yml`(PASS/CONCERNS/FAIL/WAIVED). v7: 스킬 기반으로 `_bmad-output/<type>-<slug>/`에 산출하고 요구사항 변경은 노트의 날짜 달린 `Decision:` 줄로 남긴다. ADR 없음.

### ADR 규격

- Nygard(2011): `doc/arch/adr-NNN.md`, Title / Context / Decision / Status / Consequences. "번호는 재사용하지 않는다", "번복되면 옛 것을 superseded로 남긴다".
- MADR: `docs/decisions/NNNN-title-with-dashes.md`. 프론트매터 `status`, `date`, `decision-makers`. 전체형은 Context and Problem Statement / Decision Drivers / Considered Options / Decision Outcome(Consequences, Confirmation) / Pros and Cons of the Options / More Information. 최소형은 Context and Problem Statement / Considered Options / Decision Outcome(+Consequences).
- log4brains: `docs/adr/yyyymmdd-title.md`로 날짜 접두를 써서 번호 충돌을 피한다. "ADR은 불변이고 status만 바뀐다."
- Y-statement: "In the context of <u>, facing <c>, we decided for <o> and neglected <others>, to achieve <q>, accepting <d>." 한 문장형.
- 공통 조언: "템플릿은 하나 골라 고수하라", "100개 넘는 결정 로그는 아무도 안 읽는다".

### Anthropic / Claude Code

- 공식 `feature-dev` 플러그인(Discovery → Codebase Exploration → Clarifying Questions → Architecture Design → Implementation → Quality Review → Summary)과 `plugin-dev`(8단계)는 **영속 문서를 하나도 만들지 않는다.** 산출물은 TodoWrite 목록과 채팅 요약뿐이다.
- 모범 사례 문서: Explore → Plan → Implement → Commit. "diff를 한 문장으로 설명할 수 있으면 계획을 생략하라." 스펙이 필요하면 인터뷰 후 `SPEC.md`에 쓰고 새 세션에서 실행. CLAUDE.md는 "각 줄에 대해 '이 줄을 지우면 Claude가 실수하는가'를 물어라", 200줄 이하 권고, `@경로` 임포트(깊이 4), `.claude/rules/*.md`에 `paths:` 프론트매터로 경로 범위 지정. `AGENTS.md`는 CLAUDE.md가 없을 때 네이티브로 읽는다(v2.1.277+).
- Anthropic Academy 플레이북: 승인된 계획을 `plan.md`로 커밋하고 "구현이 계획에서 벗어나면 같은 커밋에서 `plan.md`를 갱신하라, 훅으로 동기화 강제를 고려하라."
- `claude-md-management` 플러그인의 품질 기준: 명령(20점), 아키텍처 명료성(20), 비자명 패턴과 "왜 이렇게 하는가"(15), 간결성(15), 최신성(15), 실행 가능성(15). 적신호: 템플릿 복사, 일반론, 끝내지 않은 TODO, 여러 CLAUDE.md 간 중복.

### superpowers

- 브레인스토밍 결과를 `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`, 실행 계획을 `docs/superpowers/plans/YYYY-MM-DD-<feature>.md`에 날짜 접두로 커밋한다. 선택은 "당신의 결정으로" 설계 문서에 기록된다. 별도 결정 로그는 없다.

## 2. 공통 패턴

1. 항상 로드되는 전역 문서는 작고 분리되어 있다(Kiro steering, OpenSpec `config.yaml context`, spec-kit constitution, CLAUDE.md 200줄).
2. 버전이 붙는 문서는 constitution뿐이고, 나머지 문서는 constitution을 복제하지 않고 가리킨다.
3. 결정은 어디서나 Decision / Rationale / Alternatives 삼항이다.
4. 설계 문서는 조건부로만 쓴다(OpenSpec의 네 조건).
5. 코드와 문서는 같은 커밋에서 맞춘다(spec-kit 거버넌스, Anthropic 플레이북).
6. 기계 검증이 있는 곳은 OpenSpec뿐이며, 나머지는 사람의 리뷰에 의존한다.
7. 다중 에이전트 지원은 단일 소스에서 에이전트별 디렉토리를 생성하는 방식이고, `AGENTS.md`가 공통 폴백이다.

## 3. grimoire에 대한 함의

- grimoire의 "기능"은 스킬 하나나 책 한 권이고 산출물이 마크다운이라 스펙과 구현의 거리가 거의 없다. 스킬 `description`과 책 README가 이미 살아있는 스펙이다. 기능별 `spec/plan/tasks` 폴더는 과하다.
- 필요한 것은 세 층이다. 항상 로드되는 규약(`AGENTS.md`), 현재 상태 개요(살아있는 문서), 불변 결정 기록(ADR). 여기에 조사 노트(날짜 접두, 불변)를 ADR의 입력으로 둔다.
- 규약을 바꾸는 변경은 ADR + 규약 + 개요 갱신을 같은 커밋에 담는다.
- ADR은 MADR 최소형에 `status`, `date`, `supersedes` 프론트매터를 붙이면 이번 설계 논의에서 쓴 "선택지 / 근거 / 장단점" 표를 그대로 옮길 수 있다.
- 조사 노트는 날짜 접두(시간순 자료), 결정은 순번(참조 안정성). 단독 유지보수라 번호 충돌 걱정은 없다.
- spec-kit과 OpenSpec의 워크플로우 자체는 나중에 `book-of-*` 한 권의 소재가 될 수 있으나, 이번 결정 범위는 레포 자기 문서화에 한정한다.

## 4. 확인하지 못한 것

- Kiro `requirements.md`와 `tasks.md`의 정확한 섹션 제목은 공식 페이지가 404라 서드파티 사본에 의존했다.
- OpenSpec의 CI 레시피는 문서에서 찾지 못했다.
- spec-kit의 `spec-driven.md` 철학 문서는 현행 템플릿보다 오래되어 일부 내용(Phase -1 게이트, "추측하지 말라")이 현행과 다르다.
- BMAD v6의 디렉토리 구조는 문서 404로 검증하지 못했다.
- Anthropic에 "spec-driven"이라는 제목의 공식 글은 없다. 스펙 관련 지침은 Claude Code 모범 사례 문서와 Academy 플레이북에서 왔다.

## 5. 출처

- https://github.com/github/spec-kit (templates/, docs/concepts/, docs/upgrade.md, design/integration.md, extensions/agent-context/)
- https://kiro.dev/docs/specs/ , https://kiro.dev/docs/steering/
- https://github.com/Fission-AI/OpenSpec (schemas/spec-driven/schema.yaml, 템플릿), https://openspec.dev/docs/
- https://github.com/bmad-code-org/BMAD-METHOD (V4 docs/user-guide.md), https://docs.bmad-method.org
- https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions , https://adr.github.io/madr/ , https://github.com/npryce/adr-tools , https://github.com/thomvaill/log4brains , https://ozimmer.ch (Y-statement)
- https://code.claude.com/docs/en/best-practices , https://code.claude.com/docs/en/memory , https://www.anthropic.com/engineering (effective context engineering)
- 로컬: `~/.claude/plugins/marketplaces/claude-plugins-official/plugins/{feature-dev,plugin-dev,claude-md-management}`, superpowers 클론의 `skills/{brainstorming,writing-plans}/SKILL.md`
