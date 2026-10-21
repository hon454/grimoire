# 조사: mod가 버튼으로 세션 컴팩션을 실행할 수 있는가

- 날짜: 2026-10-22
- 대상: Claude Code v2.1.305(mod API 타입은 2.1.299 plugin-authoring 스킬 동봉본 `claude-code.d.ts`), 데스크톱 앱(Code 탭) 세션에서의 실측.
- 방법: 프롬프트 위 밴드에 버튼 세 개를 그리는 probe mod `compact-probe`를 dev-mods 폴더에 만들고 hot reload로 띄워, 각 경로를 눌러 본 결과와 `session.compact` 훅의 입력·결과를 mod 폴더의 jsonl에 남김. probe는 커밋하지 않았다.
- 쓰임: 밴드에서 세션에 명령을 거는 mod를 기획할 때의 전제. 2026-10-21 model/effort 조사의 짝. token-weather에 컴팩션 버튼을 넣어 보았으나 폐기했다(4절).

## 1. 결론

- **`$.command.run({ command: "compact", args })`는 데스크톱 세션에서 실제로 컴팩션한다.** 사람이 `/compact args`를 친 것과 같다. `args`는 요약 지시문이 된다.
- **`$.session.compact()`는 데스크톱 세션에서 쓸 수 없다.** 데스크톱 앱이 띄운 엔진은 headless(SDK) 세션이라 호출이 곧바로 reject된다.
- `/effort`·`/model`과 갈리는 이유: 그 둘은 앱이 처리하는 `control-request` 명령이고, `/compact`는 엔진이 처리하는 `post-text` 명령이다. mod가 엔진에 건 `/compact`는 엔진 안에서 끝나므로 앱이 가로챌 일이 없다.

따라서 "컴팩션이 필요할 때 밴드에 버튼을 띄우고, 누르면 컴팩션"은 데스크톱에서 지금 API로 만들 수 있다. 수단은 `command.run`이다.

## 2. 근거

### 2.1 API 문서(`claude-code.d.ts`)

| 수단 | 문서의 동작 |
| --- | --- |
| `$.session.compact({ instructions? })` | `session.compact` 이벤트를 `trigger: "plugin"`으로. 턴 중에는 reject, 훅이 막으면 `{ skip }` |
| `$.command.run({ command, args })` | 사람이 친 slash command처럼 `command.run` 이벤트를 큐에 넣고 세션이 idle일 때 실행. 호출한 훅 자신은 건너뛰고 `e.origin`은 `{ kind: "plugin", name }`. 모르는 이름, 턴이 기다리는 훅 안, Stop 이후에는 reject |
| `$.prompt.submit({ text })` | 프롬프트 제출. 이번에는 시험하지 않음 |

바이너리의 명령 정의에서 `/compact`의 `thinClientDispatch`는 `"post-text"`, `/effort`·`/model`은 `"control-request"`다.

### 2.2 실측(데스크톱 세션, surface `desktop`)

probe 로그(시각은 UTC):

```
17:04:52.862  pressed            A: $.session.compact
17:04:52.868  rejected           HooksError: $.session.compact: not available in a headless (-p / SDK)
                                 session yet: compaction here runs inside a turn (a /compact prompt);
                                 catch it and carry on
17:05:49.268  pressed-command    B: $.command.run({ command: "compact", args })
17:05:49.284  compact-hook       trigger: manual, messages: 89
17:06:38.495  compact-hook-result skip: null, messages 89 → 3, tokens 129,203 → 14,268
17:06:38.503  command-resolved   result: {}
```

- 채팅에는 사람이 친 것과 같은 `/compact` 명령 줄과 `Compacted`가 남았고, 다음 세션 요약의 추가 지시문이 버튼에 넣은 `args` 문자열 그대로였다.
- `session.compact` 훅의 `trigger`는 `plugin`이 아니라 `manual`이다. 다른 mod는 버튼 컴팩션과 사람이 친 `/compact`를 trigger로 구분할 수 없다.
- `command.run`의 promise는 컴팩션이 끝난 뒤 resolve됐다(약 49초, 컨텍스트 129k). 버튼 쪽에서 "컴팩션 중" 상태를 그렸다가 끝나면 지울 수 있다.
- C(`prompt.submit`)는 B가 동작해 시험하지 않았다.

## 3. 확인하지 않은 것

- 응답이 도는 중에 B를 누르면 어떻게 되는가. 문서대로라면 큐에 들어갔다가 idle일 때 실행된다.
- 터미널 surface에서 같은 경로. 터미널 엔진은 headless가 아니므로 `$.session.compact()`도 될 것으로 보인다.
- `prompt.submit`으로 `/compact`를 보내면 slash command로 처리되는가.

## 4. 만들었던 것(폐기)

token-weather 0.3.0 후보로 컴팩션 버튼을 구현했다. 커밋하지 않았다.

- 표시 조건은 밴드가 이미 컴팩션을 권하는 경우와 같다. 날씨가 "Compact soon"(90% 초과)일 때, 또는 캐시가 만료됐고 컨텍스트가 100k~300k일 때다. 캐시가 만료됐어도 300k 이상이면 새 스레드를 권하므로 버튼을 띄우지 않는다.
- 동작은 `Compact` → `Compact 129k?` 아래 Yes·No → Yes를 누르면 `$.command.run({ command: "compact" })` → 끝날 때까지 `Compacting…` 순서다. 터미널에서는 밴드에 포커스가 있을 때 `c`, `y`, `n` 키로도 누른다. 실행이 reject되면 토스트를 띄우고 버튼을 원래대로 돌린다.
- 위치는 처음에 날씨 pill 안에 두었다. 그다음 줄 끝의 별도 빨간 pill로 옮기고, 어느 조건으로 떴는지를 hover 카드에 적었다.
- `claude plugin test` 7건을 추가해 전체 56건이 통과했다. 실제 세션에서는 확인하지 않았다.
- token-weather에는 넣지 않기로 하고 폐기했다. 다시 만든다면 위 설계와 이 노트의 실측을 출발점으로 삼으면 된다.

## 5. 다시 볼 조건

- `$.session.compact()`의 headless 제한("not available … yet")이 풀리면 `trigger: "plugin"`으로 구분되는 그 경로가 낫다.
- `/compact`의 `thinClientDispatch`가 `control-request`로 바뀌면 `command.run` 경로도 막힐 수 있다. 그때는 model/effort와 같은 처지가 된다.
