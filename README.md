# grimoire

Claude Code와 Codex에서 동시에 쓰는 플러그인 모음입니다. 플러그인 하나가 마도서 한 권이며, 레포 전체가 하나의 마켓플레이스(`grimoire`)입니다.

| 플러그인 | 역할 |
|---|---|
| `archmage` | 필독서. 그리모어 사용법을 세션 시작 시 주입하고, 새 책을 제본하는 스킬을 제공합니다. |
| `book-of-*` | 도메인별 책. 각 책은 자기 스킬과 훅만으로 자립하며 다른 책에 의존하지 않습니다. |
| `claude-code-mods/*` | Claude Code 전용 mod. 프롬프트 위 밴드 같은 인터페이스 확장이라 Codex에는 없고 Codex 마켓플레이스에도 실리지 않습니다. |
| `token-weather` | 첫 mod. 프롬프트 위 한 줄에 컨텍스트 날씨, 5시간·7일 한도, 캐시 남은 시간, 세션 비용, 에이전트를 보여 줍니다(en/ko). |

## 설치

Claude Code:

```bash
claude plugin marketplace add hon454/grimoire
claude plugin install archmage@grimoire
```

Codex:

```bash
codex plugin marketplace add hon454/grimoire
codex plugin add archmage@grimoire
```

다른 책도 같은 방식으로 `book-of-<domain>@grimoire`를 설치합니다. Codex에서는 플러그인이 포함한 훅을 처음 한 번 `/hooks`에서 신뢰해야 실행됩니다.

## 구조

```
.claude-plugin/marketplace.json     Claude Code 마켓플레이스 (생성물)
.agents/plugins/marketplace.json    Codex 마켓플레이스 (생성물)
plugins/<plugin>/                   플러그인 한 권
  VERSION, CHANGELOG.md             플러그인별 독립 semver와 변경 기록
  .claude-plugin/plugin.json        Claude 매니페스트
  .codex-plugin/plugin.json         Codex 매니페스트
  skills/<skill>/SKILL.md           두 하네스가 함께 읽는 스킬 본문
  skills/<skill>/agents/openai.yaml Codex UI 메타데이터
  hooks/hooks.json                  두 하네스가 함께 읽는 훅 (선택)
  scripts/*.mjs                     훅과 스킬이 호출하는 Node 스크립트
claude-code-mods/<mod>/             Claude Code 전용 mod (Codex에는 설치되지 않음)
tools/grimoire.mjs                  운영 도구: check, stamp, new-book, new-mod, dev-install
tests/                              node tools/run-tests.mjs
docs/ARCHITECTURE.md                현재 구조 개요 (살아있는 문서)
docs/PLUGIN-AUTHORING.md            새 책 만드는 절차
docs/decisions/                     결정 기록 (ADR, 불변)
docs/research/                      조사 노트 (불변)
```

구조 설명은 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), 새 책을 만드는 절차는 [docs/PLUGIN-AUTHORING.md](docs/PLUGIN-AUTHORING.md)에 있습니다. 에이전트와 기여자를 위한 규약은 영문 [AGENTS.md](AGENTS.md)가 단일 소스입니다.

## 개발

Node 20 이상만 필요하고 외부 의존성은 없습니다.

```bash
node tools/grimoire.mjs check     # 모든 플러그인과 마켓플레이스 검증
node tools/run-tests.mjs                       # 테스트
node tools/grimoire.mjs dev-install  # 두 하네스에 이 체크아웃을 마켓플레이스로 등록하고 설치 (확인 후 실행)
node tools/grimoire.mjs dev-refresh  # 플러그인을 고친 뒤 양쪽 캐시에 다시 복사
claude plugin validate . --strict # 공식 Claude 검증기
```

## 라이선스

MIT
