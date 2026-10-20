# archmage

그리모어의 필독서이자 메타 플러그인입니다. 다른 책(`book-of-*`)을 쓰는 법을 세션 시작 시 주입하고, 새 책을 제본하는 스킬을 제공합니다.

## 포함 내용

| 종류 | 이름 | 역할 |
|---|---|---|
| 스킬 | `required-reading` | 설치된 그리모어 책과 스킬을 어떻게 찾고 쓰는지 설명 |
| 스킬 | `book-binding` | 새 책 뼈대 생성, 스킬과 훅 작성 규약, 검증, 릴리스 절차 |
| 훅 | `SessionStart` | `required-reading` 본문을 세션 컨텍스트에 주입 (`scripts/session-start.mjs`) |

## 설치

```bash
claude plugin marketplace add hon454/grimoire
claude plugin install archmage@grimoire
```

```bash
codex plugin marketplace add hon454/grimoire
codex plugin add archmage@grimoire
```

Codex에서는 플러그인 훅을 처음 한 번 `/hooks`에서 신뢰해야 실행됩니다.
