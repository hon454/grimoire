# grimoire 베이스라인 설계

작성일 2026-10-20. 이 문서는 레포의 구조와 운영 규약을 왜 이렇게 정했는지 기록합니다. 규약 자체의 단일 소스는 영문 [AGENTS.md](../AGENTS.md)이며, 이 문서는 그 배경 설명입니다.

## 1. 목표

- 레포 하나에 여러 플러그인(마도서)을 담고, 하나의 마켓플레이스 `grimoire`로 배포한다.
- 모든 플러그인은 Claude Code와 Codex에서 **같은 파일로** 동작한다. 하네스별 복사본이나 생성 레이어를 두지 않는다.
- 유지보수 비용을 낮춘다. 손으로 맞춰야 하는 중복은 도구가 검사하거나 생성한다.

## 2. 두 하네스의 사양 비교

| 항목 | Claude Code | Codex |
|---|---|---|
| 마켓플레이스 | `.claude-plugin/marketplace.json` | `.agents/plugins/marketplace.json` |
| 플러그인 매니페스트 | `.claude-plugin/plugin.json` | `.codex-plugin/plugin.json` |
| 스킬 | `skills/<name>/SKILL.md` 자동 탐색 | 동일 |
| 훅 | `hooks/hooks.json` | 동일 파일, 이벤트 이름과 stdin 계약이 거의 같음 |
| 훅 matcher 도구명 | `Bash`, `Edit`, `Write`, `Agent` | 같은 이름을 별칭으로 수용 |
| 플러그인 경로 변수 | `${CLAUDE_PLUGIN_ROOT}` | `PLUGIN_ROOT` 외에 `CLAUDE_PLUGIN_ROOT`도 호환용으로 제공 |
| 고유 요소 | `commands/`, `agents/`, `userConfig`, mods | `interface` 블록, `agents/openai.yaml` 사이드카 |

스킬, 훅, 스크립트는 공유 가능하고, 갈라지는 것은 얇은 매니페스트 두 장뿐입니다. 이것이 전체 구조의 전제입니다.

## 3. 레퍼런스 조사 요약

superpowers, pstack-claude, ECC, mattpocock/skills, gstack 다섯 레포를 조사했습니다.

- 다섯 곳 모두 플러그인 매니페스트를 손으로 작성합니다. 자동화는 버전 스탬프와 일치성 검사(`--check`)에 한정됩니다.
- pstack-claude는 `VERSION` 파일을 단일 소스로 두고 `tools/generate.mjs`가 매니페스트에 버전을 찍고 레이아웃 불변식을 CI에서 검사합니다. grimoire는 이 모델을 다권 구조에 맞게 축소했습니다.
- gstack만 하네스별 SKILL.md를 템플릿에서 렌더링하는데, 그것은 플러그인이 아니라 스킬 디렉토리 설치 방식이라 우리 문제와 다릅니다.

조사에서 드러난 Codex 함정은 다음과 같고, 모두 `check`의 규칙이 되었습니다.

- Agent Plugins 스키마의 **루트 `plugin.json`이 있으면 Codex가 플러그인 훅을 전혀 로드하지 않습니다** (pstack-claude 이슈 265). 그래서 공식 문서가 권하는 루트 매니페스트 대신 `.codex-plugin/plugin.json`을 씁니다.
- Codex는 매니페스트에 `hooks` 필드가 없으면 `hooks/hooks.json`을 자동 로드합니다. 의도를 드러내기 위해 훅이 있으면 경로를, 없으면 정확히 `{}`를 명시합니다. 빈 배열이나 생략은 다시 자동 탐색입니다.
- Codex는 플러그인을 캐시로 복사하면서 **심볼릭 링크를 버립니다**. 레포 어디에도 링크를 두지 않고 `CLAUDE.md`도 `AGENTS.md`를 가리키는 실제 파일로 둡니다.
- Codex 스킬 프론트매터 검증기는 `name`, `description`, `metadata`, `license`, `allowed-tools`만 허용한다고 ECC가 기록했습니다. Claude 전용 설정은 `metadata` 아래에 넣습니다. 이 허용 목록은 실제 설치로 재확인할 항목입니다.
- `bin/`이 있는 플러그인은 claude.ai와 Cowork에서 설치가 거부됩니다.

## 4. 결정 사항

| 번호 | 항목 | 결정 | 근거 |
|---|---|---|---|
| 1 | 플러그인 디렉토리 | `plugins/` | 관례. 두 마켓플레이스 모두 임의 경로를 받으므로 비용 차이는 없음 |
| 2 | 매니페스트 관리 | 플러그인 매니페스트 2장은 손으로, 마켓플레이스 2장은 생성 | 매니페스트는 하네스 고유 내용을 담고, 마켓플레이스는 순수 파생물 |
| 3 | 훅 런타임 | 의존성 없는 Node `.mjs` | Windows에서 셸 스크립트는 하네스별 분기가 필요. Node 하나로 OS와 하네스 모두 동일 |
| 4 | 버전 | 플러그인별 독립 semver, `VERSION` 파일, 태그 `<plugin>/vX.Y.Z` | 사용자는 책을 골라 설치하므로 레포 단일 버전은 의미가 약함 |
| 5 | 라이선스와 author | MIT, `hon454` + GitHub URL, 이메일 없음 | 공개 레포 노출 최소화 |
| 6 | 언어 | 하네스가 읽는 파일은 영어, README와 docs는 한국어 | 모델이 읽는 텍스트는 영어가 안전 |
| 7 | 메타 플러그인 | `archmage`, `book-of-*` 규칙의 유일한 예외 | 알파벳순 최상단, 필독서로 눈에 띔 |
| 8 | 인큐베이터 | 두지 않음. 모든 도메인은 첫 스킬부터 자기 책 | 네임스페이스 변경 없음, archmage는 메타 스킬만 유지 |
| 9 | 부트스트랩 훅 | archmage가 SessionStart 훅을 베이스라인부터 포함 | 발동 안정성, Codex 훅 동작의 검증 수단 |
| 10 | `commands/` | 금지, 스킬만 | 슬래시 메뉴 중복, Codex에 대응 개념 없음 |
| 11 | 레포 | `hon454/grimoire` 공개, 기본 브랜치 `main` | 설치 명령이 가장 단순 |
| 12 | 런타임 하한 | Node 20 이상, `node --test`, 의존성 0 | 현재 LTS 하한, 공급망 위험 없음 |
| 13 | Codex `category` | 기본 `Developer Tools`, `.codex-plugin/plugin.json`의 `interface.category`로 덮어쓰기 | 단일 소스에서 두 마켓플레이스로 복사 |
| 14 | CHANGELOG | 플러그인별 Keep a Changelog, 최신 항목과 `VERSION` 일치를 `check`가 강제 | 버전만 올리고 기록을 빠뜨리는 실수 방지 |
| 15 | 스킬 이름 | 동명사형(`reading-the-grimoire`), 전 플러그인에서 유일 | 책의 장(章) 같은 서술형, 충돌 방지 |
| 16 | `bin/` | 금지 | claude.ai와 Cowork 설치 호환 |
| 17 | 로컬 개발 설치 | swap 모델(`dev-install`/`dev-refresh`/`dev-uninstall`)을 2차 커밋에서 구현 | 사용자 설정 파일을 다루므로 별도 리뷰 |
| 18 | 첫 커밋 | 문서, archmage, `tools/grimoire.mjs`(check/stamp/new-book), CI | `new-book` 없이는 두 번째 책을 규약대로 만들기 어려움 |

## 5. 공유 본체 작성 규약

- **SKILL.md 프론트매터**는 허용 키 5개만 씁니다. `name`은 디렉토리명과 같고 `description`은 "Use when ..."으로 시작하는 트리거 문장입니다.
- **훅**은 두 하네스 교집합 이벤트만 쓰고 matcher는 Claude 이름으로 씁니다. 명령은 `node "${CLAUDE_PLUGIN_ROOT}/scripts/x.mjs"` 형태이며, 스크립트는 stdin의 JSON을 읽고 내부 오류 시 출력 없이 0으로 종료합니다.
- **하네스 판별**은 환경변수로 합니다. Codex는 `PLUGIN_ROOT`를 함께 내보내고 Claude는 `CLAUDE_*`만 내보냅니다. archmage의 SessionStart 훅은 Claude에는 `hookSpecificOutput` JSON을, Codex에는 평문을 출력합니다.
- **스크립트 호출**은 항상 인터프리터 경유입니다. 일부 패키저가 실행 비트를 벗깁니다.
- **플러그인 간 의존 금지.** 플러그인 루트 밖 경로는 두 하네스 모두 거부합니다.

## 6. 운영 도구 `tools/grimoire.mjs`

- `check`: 4절과 5절의 규칙 전부와 마켓플레이스 신선도를 검사합니다. 오류가 하나라도 있으면 종료 코드 1입니다.
- `stamp [plugin] [--set X.Y.Z]`: `VERSION`을 두 매니페스트에 쓰고 마켓플레이스 2장을 재생성합니다.
- `new-book <name> [--description] [--category] [--skill]`: `tools/templates/`에서 새 책 뼈대를 만듭니다.
- `marketplaces`: 마켓플레이스만 재생성합니다.

도구가 플러그인 안이 아니라 레포 루트에 있는 이유는 세 가지입니다. 배포물에 섞이면 안 되고, 플러그인은 자기 루트 밖을 볼 수 없으며, CI는 하네스 없이 맨 Node로 돌아야 합니다. archmage의 `binding-a-book` 스킬이 이 도구를 호출하는 진입점 역할을 합니다.

## 7. CI

`.github/workflows/validate.yml`은 ubuntu와 windows, Node 20과 22 매트릭스에서 `check`와 테스트를 돌리고, 별도 잡에서 Claude Code CLI를 설치해 `claude plugin validate --strict`를 마켓플레이스 루트와 각 플러그인에 실행합니다. Codex에는 공식 검증 CLI가 없으므로 Codex 쪽 규칙은 `check`가 담당합니다.

## 8. 열린 위험과 확인 항목

- Codex CLI로 설치한 플러그인에서 번들 훅이 실제로 실행되는지 문서가 불명확합니다. archmage를 로컬 마켓플레이스로 Codex에 설치해 SessionStart 훅 출력이 컨텍스트에 들어가는지 확인해야 합니다.
- Codex SessionStart 훅의 평문 출력 처리와 `matcher` 값(`startup|resume|clear|compact`)은 문서 기반이며 실측 전입니다.
- Codex 스킬 프론트매터 허용 목록은 ECC의 기록에 의존합니다.
- CI의 `claude plugin validate` 잡은 CLI가 인증 없이 검증을 수행한다는 가정 아래 작성했습니다. 첫 실행에서 확인합니다.
- Windows에서 Claude Code가 셸 형식 훅 명령을 어떤 셸로 실행하든 `node "<경로>"` 형태는 동작해야 하지만, 실제 세션으로 확인해야 합니다.
