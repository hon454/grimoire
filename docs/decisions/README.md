# 결정 기록 (ADR)

grimoire의 구조와 규약을 바꾼 결정을 한 건씩 불변 문서로 남깁니다. 형식은 MADR 최소형에 프론트매터와 한 문장 요약(Y-statement)을 더한 것입니다. 템플릿은 [template.md](template.md)입니다.

## 규칙

- 파일명은 `NNNN-kebab-title.md`, 번호는 0001부터 순번이며 재사용하지 않습니다.
- 한 ADR은 독립적으로 번복될 수 있는 결정 하나를 다룹니다. 사소한 규약(표기, 기본값)은 ADR이 아니라 `AGENTS.md`에 적습니다.
- ADR은 쓴 뒤 본문을 고치지 않습니다. 바뀌는 것은 프론트매터의 `status`와 `superseded-by`뿐입니다. 결정을 뒤집을 때는 새 ADR을 쓰고 옛 ADR을 `superseded`로 표시합니다.
- 규약을 바꾸는 변경은 ADR, `AGENTS.md`, `ARCHITECTURE.md` 갱신을 같은 커밋에 담습니다.
- `status`는 `proposed`, `accepted`, `deprecated`, `superseded` 중 하나입니다. `node tools/grimoire.mjs check`가 파일명, 순번, 프론트매터를 검사합니다.

## 색인

| 번호 | 제목 | 상태 |
|---|---|---|
| [0001](0001-repository-documentation-layers.md) | 레포 자기 문서화 체계 | accepted |
| [0002](0002-multi-plugin-single-marketplace.md) | 다중 플러그인 단일 마켓플레이스 | accepted |
| [0003](0003-shared-body-with-thin-manifests.md) | 하네스 공유 본체와 얇은 매니페스트 2장 | accepted |
| [0004](0004-codex-manifest-location.md) | Codex 매니페스트 위치 | accepted |
| [0005](0005-manifest-management.md) | 매니페스트 관리 방식 | accepted |
| [0006](0006-hook-runtime.md) | 훅 런타임 | accepted |
| [0007](0007-skills-only-component-policy.md) | 스킬 전용 컴포넌트 정책 | accepted |
| [0008](0008-versioning-and-changelog.md) | 버전과 변경 기록 | accepted |
| [0009](0009-dev-install-swap-model.md) | 개발용 로컬 설치 swap 모델 | accepted |
