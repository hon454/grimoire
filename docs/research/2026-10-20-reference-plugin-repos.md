# 조사 노트: 레퍼런스 플러그인 레포 다섯 곳의 구조와 매니페스트 관리

- 날짜: 2026-10-20
- 목적: grimoire의 매니페스트 관리 방식(손 작성 대 생성)과 하네스 호환 규칙을 정하기 위해 superpowers, pstack-claude, ECC, mattpocock/skills, gstack을 조사했다.
- 방법: 서브에이전트 3개가 GitHub API와 얕은 클론으로 각 레포의 매니페스트, 스크립트, 테스트, CI를 읽었다.
- 결과 반영: [ADR 0003](../decisions/0003-shared-body-with-thin-manifests.md), [0004](../decisions/0004-codex-manifest-location.md), [0005](../decisions/0005-manifest-management.md), [0006](../decisions/0006-hook-runtime.md), [0007](../decisions/0007-skills-only-component-policy.md).

## 1. 요약표

| 레포 | 플러그인 수 | Claude/Codex 매니페스트 | 자동화 범위 | 일치성 강제 수단 |
|---|---|---|---|---|
| obra/superpowers | 1 (하네스 11종) | 손으로 작성, 설명문까지 서로 다름 | `.version-bump.json` + `bump-version.sh`로 버전만 스탬프 | 셸 테스트가 매니페스트 필드 비교. CI 없음 |
| michael-denyer/pstack-claude | 1 | 손으로 작성 | `VERSION` → `tools/generate.mjs`가 5개 매니페스트에 버전 스탬프, Codex 프롬프트 스텁 생성 | `generate.mjs --check`를 CI와 pre-commit에서 실행, 레이아웃 불변식 검사 |
| affaan-m/everything-claude-code (ECC) | 1 | 손으로 작성 | `release.sh`가 21개 파일 버전 치환 | 매니페스트 테스트 + CI 검증기 12종, 3 OS 매트릭스 |
| mattpocock/skills | 1 | Claude 매니페스트만 작성, Codex는 폴백으로 그것을 읽음 | changesets가 `package.json` 버전을 plugin.json에 복사 | 문서상 규칙, CI 검증 없음 |
| garrytan/gstack | 플러그인 아님 (skills 디렉토리 + `./setup`) | 해당 없음 | `.tmpl`에서 하네스별 SKILL.md 렌더링, Claude 렌더만 커밋 | "생성물 신선도" CI 게이트, 26개 워크플로우 |

다섯 곳 모두 Claude와 Codex 매니페스트를 단일 소스에서 생성하지 않는다.

## 2. 하네스 호환에서 드러난 사실

- **루트 `plugin.json`과 Codex 훅.** pstack-claude 이슈 265: Agent Plugins 스키마의 루트 `plugin.json`이 있으면 Codex가 그것을 우선 읽고 플러그인 훅을 로드하지 않는다. pstack은 루트 `plugin.json`의 존재를 CI에서 금지한다.
- **Codex 훅 자동 탐색.** 매니페스트에 `hooks` 필드가 없으면 `hooks/hooks.json`을 자동 로드한다. superpowers는 `"hooks": {}`로 억제하며, 빈 배열이나 생략은 다시 자동 탐색으로 떨어진다고 테스트 주석에 적었다.
- **심볼릭 링크.** Codex는 플러그인을 캐시로 복사하며 링크를 버린다. mattpocock은 이 때문에 Codex용 큐레이션 디렉토리를 포기했다(ADR 0002). ECC는 레포에 링크가 0개다.
- **Codex 프론트매터 허용 목록.** ECC CONTRIBUTING: Codex 검증기는 `name`, `description`, `metadata`, `license`, `allowed-tools`만 허용한다.
- **`agents/openai.yaml` 사이드카.** mattpocock(모든 스킬), ECC(Codex 부분집합), gstack(루트)이 Codex UI 메타데이터(`interface.display_name`, `short_description`, `policy.allow_implicit_invocation`)를 이 파일로 제공한다.
- **`commands/` 금지.** pstack-claude는 커맨드와 스킬이 슬래시 메뉴에 이중 노출된다는 이유로 금지한다. ECC는 커맨드를 레거시 심으로만 유지한다.
- **`bin/`.** Claude 공식 문서: `bin/`이 있는 플러그인은 claude.ai와 Cowork에서 설치가 거부된다.
- **스크립트 호출.** superpowers `writing-skills`: 일부 패키저가 실행 비트를 벗기므로 `bash scripts/x.sh`, `node scripts/x.js`처럼 인터프리터 경유로 호출하라.
- **Windows.** superpowers는 cmd/bash 폴리글랏 `run-hook.cmd`와 확장자 없는 훅 파일(Claude가 `.sh`에 `bash`를 자동으로 붙이는 동작 회피), pstack은 POSIX sh + PowerShell 쌍둥이 + `commandWindows`, ECC는 Node 통일. 세 곳 모두 `.gitattributes`로 LF 강제.
- **Codex 전용 훅 파일.** pstack과 ECC는 `hooks/codex-hooks.json`을 따로 두는데 이유는 `commandWindows`와 `PLUGIN_ROOT` → `CLAUDE_PLUGIN_ROOT` 매핑이다.
- **마켓플레이스 `policy.products`.** pstack의 Codex 마켓플레이스 항목은 `"products": ["CODEX"]`를 둔다(선택 필드).

## 3. 운영 패턴

- **버전 단일 소스.** superpowers는 `.version-bump.json`에 12개 파일 경로와 필드를 선언하고 `bump-version.sh --check`로 드리프트를 검출한다. pstack은 `VERSION` 파일과 `CHANGES.md` 최신 제목 일치를 생성기가 강제한다. mattpocock은 `marketplace.json`에 `version`을 아예 두지 않아 드리프트 가능성을 없앴다.
- **공용 코드.** superpowers는 `lib/`가 없고 스킬 헬퍼는 스킬 디렉토리 안에 둔다. 형제 스킬 참조는 상대 경로(`../subagent-driven-development/scripts/...`). mattpocock은 파일 링크 대신 "Skill 도구로 호출"로 스킬 간 의존을 표현한다. ECC는 `scripts/lib/` 112개를 훅과 CLI가 공유하되 플러그인 배포물에 포함한다.
- **배포 제외.** superpowers의 Codex 패키징 스크립트는 `hooks/`, `scripts/`, `tests/`, `docs/`, `.claude*`가 아카이브에 들어가면 실패한다.
- **CI.** superpowers와 mattpocock은 검증 CI가 없다. pstack은 생성기 `--check`, Windows 훅 테스트, shellcheck, 링크 검사. ECC는 3 OS × 3 Node × 4 패키지 매니저 매트릭스. 조사한 곳 중 `claude plugin validate`를 CI에서 쓰는 곳은 없었다.
- **mattpocock의 Codex 전략.** ADR 0002: Codex는 `.codex-plugin/`이 없으면 `.claude-plugin/`으로 폴백하므로 Claude 매니페스트만 유지한다. 공식 Claude 디렉토리 등재는 `plugin.json`을 직접 읽어 `marketplace.json`에 의존하지 않는다.

## 4. 확인하지 못한 것

- Claude Code가 `hooks.json`의 `commandWindows` 키를 지원하는지(pstack은 Codex 파일에서만 쓴다).
- ECC가 "Claude 검증기가 `agents` 필드를 지원하지 않는다"고 적은 것은 현행 공식 문서(`agents` 필드 존재)와 다르다. 오래된 기록일 가능성이 높다.
- superpowers가 참조하는 릴리스 절차 문서 `CLAUDE.md`는 레포에 없다(유지보수자 로컬 파일로 추정).

## 5. 출처

- https://github.com/obra/superpowers , https://github.com/obra/superpowers-marketplace
- https://github.com/michael-denyer/pstack-claude (상류: https://github.com/cursor/plugins/tree/main/pstack)
- https://github.com/affaan-m/everything-claude-code
- https://github.com/mattpocock/skills
- https://github.com/garrytan/gstack
