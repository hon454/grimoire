# book-of-engineering

소프트웨어 엔지니어링 실천 스킬을 담는 책입니다. 첫 판은 테스트 주도 개발과 아키텍처 결정 기록 두 가지를 다룹니다.

## 포함 내용

| 종류 | 이름 | 역할 |
|---|---|---|
| 스킬 | `tdd` | red-green-refactor 순환을 합의한 seam에서 돌리고, 테스트가 정직한지(독립 기대값, 경계에서만 mock, 변이 검사) 지킨다. 기능 구현·버그 수정 전에 자동으로 적용된다. |
| 스킬 | `adr` | 결정이 기록할 가치가 있는지(되돌리기 어려움, 맥락 없이는 의아함, 실제 trade-off) 판단하고, 레포의 결정 로그를 찾아 MADR 최소형 + Y-statement로 불변 기록 한 건을 쓴다. 기존 기록을 뒤집을 때는 새 기록으로 supersede한다. |

Claude Code에서는 `book-of-engineering:tdd`, `book-of-engineering:adr`로, Codex에서는 `$tdd`, `$adr`로 보입니다.

## 출처

- `tdd`는 Jesse Vincent의 [superpowers](https://github.com/obra/superpowers) `test-driven-development` 스킬을 뼈대로 하고, Matt Pocock의 [skills](https://github.com/mattpocock/skills) `tdd` 스킬에서 seam·안티패턴·수직 슬라이스·경계 mock 기준을 합쳤습니다.
- `adr`의 "기록할 가치" 세 조건과 기록 대상 목록은 Matt Pocock의 `domain-modeling` 스킬에서 가져왔고, 기록 형식은 grimoire 자체가 쓰는 MADR 최소형 + Y-statement입니다.
- 두 원본 모두 MIT이며 고지는 [NOTICE](NOTICE)에 있습니다.

## 설치

```bash
claude plugin marketplace add hon454/grimoire
claude plugin install book-of-engineering@grimoire
```

```bash
codex plugin marketplace add hon454/grimoire
codex plugin add book-of-engineering@grimoire
```
