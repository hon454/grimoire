# grimoire 아키텍처

이 문서는 레포가 지금 어떻게 생겼고 각 부분이 어떻게 맞물리는지 설명하는 살아있는 문서입니다. 규칙 자체는 영문 [AGENTS.md](../AGENTS.md)가 단일 소스이고, 왜 이렇게 정했는지는 [docs/decisions/](decisions/README.md)의 결정 기록에 있습니다. 구조가 바뀌면 이 문서와 해당 ADR, `AGENTS.md`를 같은 커밋에서 갱신합니다.

## 1. 목적

- 레포 하나에 여러 플러그인(마도서)을 담고 마켓플레이스 `grimoire` 하나로 배포한다.
- 모든 플러그인은 Claude Code와 Codex에서 같은 파일로 동작한다. 하네스별 복사본이나 생성 레이어를 두지 않는다.
- 손으로 맞춰야 하는 중복은 도구가 검사하거나 생성한다.

## 2. 레포 지도

```
.claude-plugin/marketplace.json     Claude 마켓플레이스 (생성물, 손대지 않음)
.agents/plugins/marketplace.json    Codex 마켓플레이스 (생성물, 손대지 않음)
AGENTS.md                           에이전트와 기여자 규약 (영어, 단일 소스)
CLAUDE.md                           AGENTS.md를 가리키는 실제 파일
plugins/<plugin>/                   플러그인 한 권
  VERSION                           버전의 단일 소스
  CHANGELOG.md                      Keep a Changelog, 최신 항목 = VERSION
  .claude-plugin/plugin.json        Claude 매니페스트 (손 작성)
  .codex-plugin/plugin.json         Codex 매니페스트 (손 작성, interface 포함)
  skills/<skill>/SKILL.md           두 하네스가 함께 읽는 스킬
  skills/<skill>/agents/openai.yaml Codex UI 메타데이터 사이드카
  hooks/hooks.json                  두 하네스가 함께 읽는 훅 (선택)
  scripts/*.mjs                     훅과 스킬이 호출하는 Node 스크립트
  README.md                         플러그인의 살아있는 스펙 (한국어)
tools/grimoire.mjs                  운영 도구: check, stamp, new-book, dev-install, marketplaces
tools/templates/                    new-book이 쓰는 뼈대
tests/*.test.mjs                    node --test
docs/ARCHITECTURE.md                이 문서
docs/PLUGIN-AUTHORING.md            새 책 만드는 절차
docs/decisions/NNNN-*.md            결정 기록 (불변)
docs/research/YYYY-MM-DD-*.md       조사 노트 (불변)
.github/workflows/validate.yml      CI
```

현재 플러그인은 `archmage` 하나다. 메타 플러그인이며 `reading-the-grimoire`(세션 시작 시 주입되는 필독서)와 `binding-a-book`(새 책 제본 절차) 스킬, SessionStart 훅을 담는다. 다른 모든 도메인은 `book-of-<domain>` 플러그인으로 첫 스킬부터 분리된다.

## 3. 동작 흐름

**설치.** 사용자는 `claude plugin marketplace add hon454/grimoire` 또는 `codex plugin marketplace add hon454/grimoire`로 마켓플레이스를 등록하고 `archmage@grimoire`처럼 플러그인을 고른다. Claude는 디렉토리 마켓플레이스를 제자리에서 읽고, Codex는 플러그인 디렉토리를 `~/.codex/plugins/cache/grimoire/<plugin>/<version>/`로 통째로 복사한다.

**매니페스트에서 마켓플레이스로.** `tools/grimoire.mjs stamp`가 각 플러그인의 `VERSION`을 두 매니페스트의 `version`에 쓰고, 매니페스트의 이름·설명·키워드·`interface.category`를 읽어 마켓플레이스 2장을 다시 생성한다. `check`는 생성물이 최신인지 비교만 한다.

**개발용 로컬 설치 (swap 모델, ADR 0009).** `tools/grimoire.mjs dev-install`은 두 하네스에서 마켓플레이스 `grimoire`의 등록 상태를 읽어 출력하고, GitHub 등록이면 제거한 뒤 이 체크아웃을 디렉토리 마켓플레이스로 등록하고, 전과 같은 플러그인 ID(`archmage@grimoire` 등)를 다시 설치한다. 이미 이 체크아웃이면 교체 없이 재설치만 한다. 두 하네스 모두 플러그인을 캐시에 복사하므로 수정 뒤에는 `dev-refresh`(Claude는 `uninstall --keep-data` 후 `install`, Codex는 `remove` 후 `add`)로 다시 복사한다. `dev-uninstall`은 로컬 등록을 제거하고 GitHub 소스로 되돌린다. 계획을 먼저 출력하고 `--yes`가 없으면 확인을 받으며, Claude 마켓플레이스 제거가 그 플러그인들의 데이터·옵션·시크릿을 지운다는 경고를 해당 단계에 붙인다. `dev-status`는 상태만 보여 준다. `tools/dev.mjs`의 계획 생성은 순수 함수라 `tests/dev-install.test.mjs`가 ID 불변식을 검사한다.

**검증.** `check`는 플러그인마다 이름 규칙, `VERSION`과 CHANGELOG와 매니페스트의 일치, 금지 항목(루트 `plugin.json`, `commands/`, `bin/`, 심볼릭 링크, `CLAUDE.md`), Codex `hooks` 필드 명시, 스킬 이름·프론트매터·사이드카, 훅 이벤트와 참조 경로, 개인 경로 유출, 마켓플레이스 신선도를 검사한다. 레포 수준에서는 `docs/decisions/`의 순번과 프론트매터, 이 문서가 참조하는 ADR의 존재를 검사한다. CI는 ubuntu와 windows, Node 20과 22에서 `check`와 테스트를 돌리고 `claude plugin validate --strict`를 별도 잡으로 실행한다.

**훅 실행.** 두 하네스 모두 `hooks/hooks.json`을 읽고 `node "${CLAUDE_PLUGIN_ROOT}/scripts/session-start.mjs"`를 실행한다. 스크립트는 `PLUGIN_ROOT` 유무로 하네스를 판별해 Claude에는 `hookSpecificOutput` JSON을, Codex에는 평문을 출력한다. Codex는 플러그인 훅을 비관리 훅으로 취급해 사용자가 `/hooks`에서 한 번 신뢰하기 전까지 건너뛴다.

## 4. 두 하네스 비교

| 항목 | Claude Code | Codex |
|---|---|---|
| 마켓플레이스 | `.claude-plugin/marketplace.json` | `.agents/plugins/marketplace.json` (`category`, `policy` 필수) |
| 플러그인 매니페스트 | `.claude-plugin/plugin.json` | `.codex-plugin/plugin.json` (루트 `plugin.json`은 금지, ADR 0004) |
| 스킬 | `skills/<name>/SKILL.md` 자동 탐색, `플러그인:스킬` 네임스페이스 | 동일. 실측에서 `archmage:reading-the-grimoire`로 노출 |
| 훅 | `hooks/hooks.json` | 동일 파일. 이벤트 이름과 stdin 계약 거의 동일. 비관리 훅은 `/hooks` 신뢰 필요 |
| 훅 matcher 도구명 | `Bash`, `Edit`, `Write`, `Agent` | 같은 이름을 별칭으로 수용 (`tool_name`은 `apply_patch` 등으로 옴) |
| 플러그인 경로 변수 | `${CLAUDE_PLUGIN_ROOT}`, `${CLAUDE_PLUGIN_DATA}`, `${CLAUDE_PROJECT_DIR}` | `PLUGIN_ROOT`, `PLUGIN_DATA` 외에 `CLAUDE_PLUGIN_ROOT`, `CLAUDE_PLUGIN_DATA`도 제공 |
| 전용 요소 | `commands/`(금지), `agents/`, `userConfig`, mods | `interface` 블록, `agents/openai.yaml`, `onboardingSkill` |
| 설치 | `claude plugin marketplace add owner/repo` | `codex plugin marketplace add owner/repo` (로컬 경로도 가능) |

## 5. 규약 요약

규칙의 전문은 `AGENTS.md`에 있고, ADR로 다루지 않은 사소한 규약은 다음과 같다.

- author는 `{ "name": "hon454", "url": "https://github.com/hon454" }`, 이메일 없음. 라이선스 MIT.
- Node 20 이상, 외부 의존성 0, 테스트는 `node --test` 기본 탐색.
- Codex `category` 기본값은 `Developer Tools`, 플러그인별로 `interface.category`에서 덮어쓴다.
- 하네스가 읽는 파일은 영어, 사람이 읽는 문서는 한국어.
- 줄 끝은 LF(`.gitattributes`).

## 6. 결정 색인

| ADR | 결정 | 상태 |
|---|---|---|
| [0001](decisions/0001-repository-documentation-layers.md) | 레포 자기 문서화는 규약, 개요, 결정 기록, 조사 노트 네 종류 | accepted |
| [0002](decisions/0002-multi-plugin-single-marketplace.md) | `plugins/` 아래 다중 플러그인, 마켓플레이스 하나, `archmage` 메타, 인큐베이터 없음 | accepted |
| [0003](decisions/0003-shared-body-with-thin-manifests.md) | 공유 본체 + 얇은 매니페스트 2장, 심볼릭 링크 금지 | accepted |
| [0004](decisions/0004-codex-manifest-location.md) | Codex 매니페스트는 `.codex-plugin/`, 루트 `plugin.json` 금지, `hooks` 명시 | accepted |
| [0005](decisions/0005-manifest-management.md) | 매니페스트 손 작성, 마켓플레이스 생성, `VERSION` 스탬프, 도구는 레포 루트 | accepted |
| [0006](decisions/0006-hook-runtime.md) | Node 20+ 의존성 0, 단일 `hooks.json`, 환경변수로 하네스 판별 | accepted |
| [0007](decisions/0007-skills-only-component-policy.md) | 스킬만, `commands/`와 `bin/` 금지, 동명사 이름, 프론트매터 허용 목록, 사이드카 | accepted |
| [0008](decisions/0008-versioning-and-changelog.md) | 플러그인별 semver와 `CHANGELOG.md`, `check`가 일치 강제 | accepted |
| [0009](decisions/0009-dev-install-swap-model.md) | 개발용 로컬 설치는 swap 모델 (`dev-install`/`dev-refresh`/`dev-uninstall`) | accepted |

조사 노트: [SDD 도구와 ADR 규격의 문서 구조](research/2026-10-20-sdd-doc-structures.md), [레퍼런스 플러그인 레포 다섯 곳](research/2026-10-20-reference-plugin-repos.md).

## 7. 열린 위험과 확인 항목

- **Codex 훅 실행 (해소, 2026-10-21).** 로컬 마켓플레이스로 설치한 archmage의 SessionStart 훅이 `/hooks` 신뢰 후 `codex exec`에서 실행되어, 스크립트의 평문 출력이 `developer` 역할 메시지로 컨텍스트에 들어가는 것을 확인했다. 플러그인 훅은 비관리 훅이라 사용자가 한 번 신뢰해야 하며, `hooks.json`이 바뀌면 해시가 달라져 다시 신뢰해야 한다. Codex `/hooks` 화면에는 이름 없는 훅으로 표시되므로, 두 하네스가 모두 받아들이는 표시용 필드가 확인되면 추가한다.
- **Codex SessionStart 세부.** 평문 출력은 실측으로 확인했다. `matcher` 값(`startup|resume|clear|compact`)이 Codex에서 어떤 소스 이름과 대응하는지는 아직 문서 기반이다.
- **Codex 프론트매터 허용 목록**은 ECC의 기록에 의존한다.
- **CI의 `claude plugin validate` 잡 (해소, 2026-10-20).** 첫 푸시의 워크플로우에서 인증 없이 통과했다.
- **Windows의 Claude 훅 (해소, 2026-10-21).** 로컬 디렉토리 마켓플레이스로 설치한 archmage의 SessionStart 훅이 Windows의 Claude Code 데스크톱 세션에서 실행되어 `<grimoire_required_reading>` 블록이 컨텍스트에 들어가고 스킬이 `archmage:<skill>`로 노출되는 것을 확인했다. 훅 오류나 경고는 없었다.
- **`dev-install` (해소, 2026-10-21).** ADR 0009를 `tools/dev.mjs`로 구현했고 실제 머신에서 `dev-refresh`가 두 하네스를 갱신하는 것을 확인했다. Codex 훅 신뢰(`config.toml`의 `[hooks.state]`, 플러그인 ID와 훅 해시 기준)는 remove/add 뒤에도 유지되었고, Claude 플러그인 데이터 디렉토리는 `--keep-data`로 보존되었다. GitHub 등록에서 로컬로의 교체 경로는 계획 출력(dry-run)과 단위 테스트로만 검증했다.
