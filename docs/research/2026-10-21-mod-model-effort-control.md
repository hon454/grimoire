# 조사: mod에서 세션의 모델과 추론 레벨(effort)을 바꿀 수 있는가

- 날짜: 2026-10-21
- 대상: Claude Code v2.1.304의 mod API(`claude-code.d.ts`, plugin-authoring 스킬 동봉본), 바이너리의 명령 정의, 공식 문서(model-config, settings-reference), 데스크톱 앱(Code 탭)과 터미널에서의 실측.
- 방법: 프롬프트 위 밴드에 모델·effort 세그먼트를 그리는 mod `model-dial`을 만들어 `claude plugin test`와 실제 세션에서 돌려 봄. 결과가 데스크톱 앱에서 요구를 충족하지 못해 mod는 폐기했고 커밋하지 않았다.
- 쓰임: 세션 설정을 건드리는 mod를 다시 기획할 때의 전제. ADR 0010(mod 계열)의 한계 보강.

## 1. 결론

- **터미널**에서는 된다. mod가 `$.command.run({ command: "model", args })`와 `$.command.run({ command: "effort", args })`를 부르면 사용자가 친 것과 같이 동작하고, 사용자가 친 `/model`·`/effort`도 `command.run` 훅으로 들어온다.
- **데스크톱 앱(Code 탭)** 에서는 안 된다. 앱이 세션의 모델과 effort를 자기 쪽에서 관리한다. 앱의 선택은 엔진의 명령 체인을 거치지 않아 mod가 보지 못하고, mod가 엔진에 실행시킨 `/effort`는 채팅 줄("Set effort level to …")만 남기고 앱의 값은 바꾸지 않는다. 앱의 값을 바꾸는 API는 mod에 없다.
- 요청 단위로는 어느 surface에서든 `turn.step` 훅이 `effort`와 `model`을 고쳐 보낼 수 있다. 그러나 앱의 표시(`◐ medium · /effort`)는 따라오지 않아 사용자가 확인할 길이 없고, 앱 설정과 mod 선택이 따로 놀게 된다.

따라서 "데스크톱에서 클릭으로 모델·effort를 바꾸는 밴드"는 현재 mod API로 만들 수 없다. 터미널 전용이라면 가능하다.

## 2. 근거

### 2.1 명령 정의(바이너리)

`/effort`는 `{ type: "local-jsx", name: "effort", immediate: true, requires: { ink: true }, thinClientDispatch: "control-request" }`로 정의된다. 인자 힌트는 `[low|medium|high|xhigh|max|auto]`이고, 모델이 지원하면 `|ultracode [on|off]`가 붙는다. `thinClientDispatch: "control-request"`가 데스크톱 앱(thin client)에서 호스트가 직접 처리한다는 표시다. `/model`도 같은 계열이다.

`/model`이 받는 별칭 목록: `sonnet, opus, haiku, fable, best, sonnet[1m], opus[1m], fable[1m], opusplan`. `ultracode`는 settings.json의 불리언 키이자 `/config` 행이고, 모델이 지원하지 않거나 dynamic workflows가 꺼져 있으면 거부된다.

### 2.2 공식 문서

- `/effort <level>`은 모델별 설정(`modelSettings`)에 저장되어 다음 세션에도 이어진다. 슬라이더에서 `s`를 누르면 이 세션에만 적용된다. `/effort auto`가 저장된 값을 지우는 유일한 방법이고 `default`는 문서에 없다.
- `/effort status`가 적용 중인 레벨을 보여 준다. 인자 없는 `/effort`는 슬라이더를 연다.
- 모델 기본 effort: Opus 5.5·Sonnet 5.5·Haiku 5.5는 `medium`, 그 밖에 지원 모델은 `high`, Opus 4.7은 `xhigh`.

### 2.3 mod API에서 쓸 수 있는 것

| 목적 | 수단 | 비고 |
| --- | --- | --- |
| 현재 모델 읽기 | `$.session.model()` | `/model`이 보이는 그대로 |
| 모델 전환 감지 | `on("classic.PostModelSwitch")` | `source`가 `command`/`picker`/`sdk`/`auto`/`resume` |
| 모델 바꾸기 | `$.command.run({ command: "model", args })` | 터미널에서 확인. 데스크톱은 미확인 |
| 현재 effort 읽기 | `turn.step`의 `e.effort` | 요청이 나갈 때만 안다. 세션 설정을 직접 읽는 noun은 없다 |
| effort 바꾸기 | `$.command.run({ command: "effort", args })` | 터미널만 |
| 요청 단위 덮어쓰기 | `turn.step`에서 `next({ ...e, effort })` 또는 `model` | 모든 surface. 표시는 안 따라옴 |
| 사용자의 `/effort` 감지 | `on("command.run", { command: "effort" })` | 터미널만 |
| ultracode 상태 | `$.config.list()`의 `ultracode` 행, `$.settings.read().ultracode` | 세션 단위 토글은 settings에 안 남는다 |
| 데스크톱 세션 설정 변경 | MCP `set_session_effort` / `set_session_model` | "자기 세션에는 거부". 다른 세션에만 쓸 수 있다 |
| 전역 단축키 | 없음 | Button `hotkey`는 밴드 포커스 중에만, Button `action`은 터미널 키바인딩 코드만, `Client`의 `onKey`는 그 영역 포커스 중에만 |

### 2.4 실측

- 터미널(앱의 터미널 패널에서 띄운 `claude`): 밴드가 그려지고, 세그먼트로 `/effort`가 실행되며, 사용자가 친 `/effort xhigh`가 밴드에 반영됨.
- 데스크톱 세션: 앱의 effort 선택은 채팅 줄 없이 바뀌고 mod는 이를 못 봄. mod의 세그먼트는 채팅 줄만 남기고 앱의 값은 그대로. 사용자 확인.
- `claude plugin test`에서 Button `action: "pane:next"`는 통과했으나 실제 코드 바인딩은 시험하지 않음.

## 3. 만들었던 것(폐기)

`claude-code-mods/model-dial`: token-weather와 같은 알약 레이아웃, 모델 세그먼트(`Haiku · Sonnet · Opus · Fable`, 캐시 재작성 비용을 보여 주고 yes를 받은 뒤 `/model`), effort 세그먼트(`low … max`, 적용 중인 레벨은 색, 엔진이 실제로 쓴 레벨은 밑줄), ultracode 토글. `$.state` 계약(`types/index.d.ts`)과 `claude plugin test` 28건. 데스크톱 한계 때문에 폐기.

## 4. 다시 볼 조건

- mod API에 세션 effort를 읽고 쓰는 noun이 생기거나, `set_session_effort`가 자기 세션을 허용하면.
- 데스크톱 앱이 `control-request` 명령을 엔진의 `command.run` 체인에도 흘려보내면.
- 터미널 전용 mod로 범위를 줄여도 괜찮다고 판단되면 `model-dial` 설계를 그대로 되살릴 수 있다.
