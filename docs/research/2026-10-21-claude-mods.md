# 조사: augiefra/claude-mods의 구조와 이식 가능성

- 날짜: 2026-10-21
- 대상: https://github.com/augiefra/claude-mods (HEAD `cfa7d3f`, 2026-10-20)
- 방법: GitHub API 메타데이터 + 얕은 클론을 읽음. 실행하지 않음.
- 쓰임: ADR 0010(Claude 전용 mod 계열)의 근거. 첫 mod `token-weather` 재작성의 설계 참조.

## 1. 정체

Eric Cologni의 마켓플레이스 `augiefra-mods`. 플러그인은 `token-weather-usage` 하나(v3.17.4). 2026-10-02 시작, 별 21, 포크 4, 커밋 약 34, 외부 PR 2건 병합(밴드 아래에 다른 mod 출력 쌓기, 러시아어 라벨). 열린 이슈는 좁은 폭에서 밴드가 잘리는 문제(#2) 하나.

프롬프트 위 한 줄 밴드에 다음을 그린다. 컨텍스트 토큰과 날씨 글리프(25/50/75/90% 임계), 최근 5턴 막대, 추세, 5시간·7일 한도 게이지(경과 시간 대비 페이스로 초록/노랑/빨강, `PACE_ALERT = 15`, `USED_ALERT = 90`), 7일 소진 예측, 프롬프트 캐시 카운트다운(1시간/5분 TTL 추론)과 만료·미스·압축 상태와 재작성 비용, 세션 비용, 실행 중 에이전트 수와 호버 카드. 터미널 예: `☂ 634k ▃▄▂█▆ ▲ +6.3k │ 5h ━━━━╍─ 74% · 24 min │ 7d ━━━━── 65% · 2d20h │ cache 52 min │ ≈ $41.07 (+$0.58 · +1.5% 5h) │ 2 agents`.

## 2. 구조

```
.claude-plugin/marketplace.json            name: augiefra-mods, plugins[0].source: ./plugins/token-weather-usage
LICENSE                                    Apache-2.0
NOTICE                                     출처와 adapt한 코드의 고지
plugins/token-weather-usage/
  .claude-plugin/plugin.json               version, userConfig.language (auto|en|fr|ru), license Apache-2.0
  .claude-plugin/icon.png
  hooks/hooks.json                         { "modules": ["./token-weather-usage.mjs"] }
  hooks/token-weather-usage.mjs            1,689줄, mod 전체
  tests/token-weather-usage.test.ts        1,312줄, claude plugin test
  README.md
```

`commands/`, `skills/`, `agents/`, MCP, 상태줄 스크립트, `types` 필드, 셸 훅 모두 없음. npm 의존성 0, `package.json` 없음. 모듈 안에 `import`, `require`, `process`, `fs`, `fetch` 없음. 모든 것은 `$`로 접근한다.

## 3. 사용하는 mod 메커니즘

| 이벤트 | 용도 |
|---|---|
| `session.start` | 상태 초기화, 언어 결정, 환경변수 읽기, `$.session.usage()`, `$.agent.list()`, `$.store` 복원, `$.clock.every` 두 개(60초 한도 갱신, 10초 캐시 카운트다운과 에이전트 폴링) |
| `session.end` | `prompt_input_exit`/`other`일 때만 타이머 해제 (/clear, /resume은 유지) |
| `turn.step` | 제너레이터. `yield* next(e)` 결과의 `usage`(input, cache_read, cache_creation, output, model), `toolUses`, `stopReason`을 읽음 |
| `turn.complete` | `$.session.usage()` 재조회 → 컨텍스트, `cost.usd`, `rateLimits[]`(`kind`, `percentUsed`, `resetsAt`) |
| `session.compact` | `tokensAfter`. `trigger === "precompute"`와 `skip`은 무시 |
| `session.measure` | `changed`에 `rateLimits`가 있으면 갱신 |
| `ui.render` `{component: "AbovePrompt"}` | `e.props.bodyColumns`, `e.surface`, `$.ui.resolve(e)` → `Box`, `Text`, `Svg` |

`$` 사용: `clock.now`, `clock.every`, `ui.invalidate`, `ui.resolve`, `env.get`(LC_ALL, LC_MESSAGES, LANG, 캐시 관련 4개), `store.get/set/keys/delete`, `session.usage`, `session.id`, `agent.list`.

호스트가 소스를 정적으로 읽어 `on(...)`, `$.x.y(...)`, 환경변수 이름을 수집하므로, 이름을 동적으로 만들거나 `$`를 받는 함수를 최상위 밖으로 옮기면 조용히 깨진다. 원본 헤더 주석이 이를 명시한다.

## 4. 가져갈 설계

- **순수 관찰자.** 모든 훅이 `next(e)` 결과를 그대로 돌려준다. 도구 호출을 가로채지 않고 응답의 `toolUses`를 읽어 에이전트 활동을 추적한다. README가 "아무것도 바꾸거나 지연시키거나 거부하지 않는다"고 약속한다.
- **fail-soft.** 저장소, 환경변수, 에이전트 목록 호출을 전부 try/catch로 감싸고 실패 시 이전 값을 유지한다. 그릴 것이 없거나 설문(`hasSurvey`)이 떠 있으면 `next(e)`만 돌려준다.
- **합성 가능.** `ui.render`에서 `next(e)`를 기다린 뒤 그 아래에 자기 출력을 쌓는다(PR #1).
- **상태 모델.** 모듈 변수는 `session.start`에서 초기화. `$.store` 키 셋: `limits`(계정 전체 최신 한도, 세션 간 공유, 1분마다 채택), `week`(7일 % 기록, 30분당 1개, 2일 보관), `turns:<sessionId>`(세션별 기록, 8일 유휴 후 삭제). 도구 이름 같은 활동 정보는 프라이버시를 위해 메모리에만 둔다.
- **재그리기 절제.** 10초 타이머는 렌더 텍스트의 키가 바뀌었을 때만 `invalidate`.
- **반응형.** 텍스트 폭을 재서 `svg` → `text` → `none`으로 줄인다. 데스크톱은 `flexWrap`, `borderStyle: "round"` 필, 호버 카드는 absolute Box에 `hover: {display: "flex"}`.
- **글리프.** 이모지 없이 단일 폭 유니코드만: `☀ ☁ ☂ ☇ ↯`, 막대 `▁▂▃▄▅▆▇█`, 게이지 `━ ╍ ─`, 구분자 `│`.
- **캐시 TTL 추론.** 직전 요청 5분 뒤 히트면 1시간, 1시간 내 같은 모델에서 프롬프트가 줄지 않았는데 미스면 5분, 아니면 환경변수, 아니면 구독이면 1시간·API 키면 5분. 미스는 읽기 <50%이고 쓰기 >1000.
- **페이스와 소진.** 페이스 = 사용% − 경과%. 소진 예측은 주 전체 속도(Claude 사용량 페이지와 일치) + 최근 하루 속도.
- **i18n.** 언어별 라벨 함수 테이블 하나. 로케일은 환경변수, 그다음 `Intl`.
- **추정치 표기.** 달러에 `≈`, 가격표에 없는 모델은 토큰만, TTL 툴팁에 "assumed"/"observed".

## 5. 깨지기 쉬운 곳

- Claude Code 비공개 mod API 전체(이벤트 이름, `$.session.usage()` 형태, `$.agent.list()`, 요소 props). 테스트 주석에 "test(name, {options}, body)는 2.1.286에서 register에 닿지 않는다"는 버전 메모.
- 날짜가 박힌 가격표 `PRICES`(2026-10-08 기준). 구독 요금은 "API 가격 환산이지 청구서가 아님".
- 5h/7d 윈도우, `rateLimits[].kind` 값, 압축 이벤트, Anthropic 캐시 TTL 규칙과 환경변수 4개, 데스크톱 surface 등 Claude 고유 의미론.
- 에이전트 상태는 이벤트가 아니라 10초 폴링(에이전트 스폰 훅은 플러그인 디렉토리가 받지 않는다고 README가 설명). 백그라운드 셸과 Workflow 에이전트는 보이지 않음.
- 미사용 코드 `KNOWN_TOKENS` 정규식 목록.

## 6. Codex 이식 불가 지점

인프로세스 모듈 로딩, `ui.render` 컴포넌트 트리, `$.session.usage()`의 한도·비용·캐시 수치, `session.compact`/`session.measure`, `$.agent.list()`, `$.store`, `$.clock`, `userConfig`, `claude plugin test` 전부. 하네스 중립으로 재사용 가능한 것은 모델 ID 정규화(`modelId`), 도구명 축약(`toolText`), 묶음 계산(`batchesOf`), 포맷터, 페이스·소진 계산, 텍스트 게이지 렌더링, 보관 정책처럼 `$` 없는 순수 함수뿐이다.

## 7. 라이선스

Apache-2.0. `NOTICE`가 Anthropic의 Token Weather 예제(Apache-2.0, 컨텍스트 날씨·토큰·최근 턴 차트)와 Anji Xu의 agentpane(MIT, `latestBatch`, `batchReceipt`, `toolParts`)에서 adapt한 코드를 밝히고, usage-meter(HolyGrail)와 prompt-cache-control(Daniel San)은 코드 없이 아이디어만 썼다고 적는다. 설계를 채용해 재작성할 때의 의무: 코드 일부라도 가져오면 해당 mod 디렉토리에 Apache-2.0 LICENSE와 NOTICE(Cologni, Anthropic PBC, 해당 시 Anji Xu)를 싣고 `plugin.json`의 `license`를 Apache-2.0으로 적는다. 아이디어만 빌려도 NOTICE에 출처를 적는 것이 원저자가 보인 관례다.

## 8. 미확인

- Claude Code mod API의 공식 문서. 이벤트 payload 형태는 원본 소스와 테스트, 그리고 설치된 Claude Code 2.1.299의 `claude-code.d.ts` 선언에서 확인해야 한다.
- 플러그인 디렉토리 사본이 몇 버전 뒤처지는지(README 주장).
