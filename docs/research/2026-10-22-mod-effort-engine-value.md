# 조사: 데스크톱 세션에서 mod의 `/effort`는 다음 요청의 effort를 바꾸는가

- 날짜: 2026-10-22
- 대상: Claude Code v2.1.305(mod API 타입은 2.1.299 plugin-authoring 스킬 동봉본 `claude-code.d.ts`), 데스크톱 앱(Code 탭) 세션에서의 실측. 모델 `claude-opus-5-5`.
- 방법: 프롬프트 위 밴드에 `low`·`high`·`max` 버튼을 그리는 probe mod `effort-probe`를 dev-mods 폴더에 만들고 hot reload로 띄움. 버튼은 `$.command.run({ command: "effort", args })`를 부르고, `turn.step` 훅은 요청마다 `e.effort`를, `command.run` 훅(`{ command: "effort" }`)은 그 체인을 지나는 실행을 mod 폴더의 jsonl에 남김. 같은 턴에 Bash로 `CLAUDE_EFFORT`도 읽음. probe는 실측 뒤 지웠고 커밋하지 않았다.
- 쓰임: [2026-10-21 model/effort 조사](2026-10-21-mod-model-effort-control.md)의 데스크톱 결론을 고쳐 읽는 근거. effort를 다루는 mod를 다시 기획할 때의 전제.

## 1. 결론

- **mod가 엔진에 건 `/effort`는 엔진의 effort를 실제로 바꾼다.** 다음 모델 요청부터 그 값으로 나가고, 앱이 매 턴 자기 값을 다시 보내 덮어쓰지는 않는다.
- **바뀌지 않는 것은 앱의 표시뿐이다.** 앱의 effort 표시는 mod가 바꾸기 전 값에 머문다. 사용자가 보는 값과 실제로 나가는 값이 어긋난다.
- **앱의 effort 선택기는 엔진 값을 직접 덮어쓴다.** 엔진의 `command.run` 체인을 지나지 않아 mod의 훅은 이를 보지 못하지만, 바뀐 값은 다음 요청부터 적용된다. 마지막에 바꾼 쪽이 이긴다.

따라서 2026-10-21 노트의 "데스크톱에서는 mod가 effort를 바꿀 수 없다"는 효과가 아니라 표시에 대한 판단이었다. 데스크톱에서도 mod로 effort를 바꿀 수는 있다. 다만 앱 표시가 따라오지 않으므로, 사용자가 볼 수 있는 표시는 mod가 직접 그려야 하고 앱 선택기와 따로 논다는 점은 그대로다.

## 2. 근거

### 2.1 probe 로그

시각은 `$.clock.now()`의 밀리초 뒷자리만 적었다.

```
…755642  session.start
…763232  button.pressed     level: low
…763253  button.resolved    text: "Set effort level to low (this session only): Quick,
                            straightforward implementation with minimal overhead"
…808381  turn.step          turn 11838e08, index 0, effort: low
…812161  turn.step          turn 11838e08, index 1, effort: low
                            (이 사이에 사용자가 앱 선택기로 max를 고름)
…855714  turn.step          turn 2c5d35ca, index 0, effort: max
```

`command.run` 훅의 줄은 한 번도 남지 않았다.

### 2.2 단계별 대조

| 단계 | 앱 표시 | `turn.step`의 `e.effort` | `CLAUDE_EFFORT` |
| --- | --- | --- | --- |
| probe 로드 전 | 높음 | — | `high` |
| mod 버튼 `low` 뒤 | 높음(그대로) | `low` (step 2개) | `low` |
| 앱 선택기 `max` 뒤 | max | `max` | `max` |

- 버튼의 `$.command.run`은 약 20ms 만에 resolve됐고 채팅에 사람이 친 것과 같은 `/effort low` 줄과 출력이 남았다.
- `CLAUDE_EFFORT`는 엔진이 Bash와 훅 명령에 넘기는 "현재 턴의 effort"다. `turn.step`과 같은 값을 보여 엔진 쪽 값이 바뀌었다는 두 번째 근거가 된다.

### 2.3 `command.run` 훅이 비어 있던 이유

- 버튼의 실행: `$.command.run`은 호출한 mod 자신의 `command.run` 훅을 건너뛴다(API 문서). 같은 mod의 훅에 안 잡힌 것은 예상대로다.
- 앱 선택기: 2026-10-21 노트대로 `/effort`는 `thinClientDispatch: "control-request"` 명령이라 앱이 처리하고, 엔진의 명령 체인으로 흘러오지 않는다. 그런데도 엔진 값은 바뀌었으므로, 앱은 명령 체인 밖의 control request로 엔진 설정을 직접 바꾼다.

## 3. 2026-10-21 노트에서 고쳐 읽을 곳

- §1 둘째 항목 "mod가 엔진에 실행시킨 `/effort`는 채팅 줄만 남기고 앱의 값은 바꾸지 않는다": 앱의 *표시*에 대해서만 맞다. 엔진 값과 실제 요청은 바뀐다.
- §2.3 표 "effort 바꾸기 | `$.command.run(...)` | 터미널만": 데스크톱에서도 효과가 있다. 표시만 안 따라온다.
- §2.3 표 "사용자의 `/effort` 감지 | 터미널만": 그대로다. 데스크톱 앱의 선택은 `command.run`으로 오지 않는다. 다만 다음 `turn.step`의 `e.effort`로 사후에 알 수 있다.

## 4. 확인하지 않은 것

- `/model`도 같은지. 같은 `control-request` 계열이라 엔진 값은 바뀌고 표시만 낡을 것으로 보이나 시험하지 않았다.
- `turn.step`에서 `next({ ...e, effort })`로 요청 단위로 덮어쓰는 경로. 타입 문서는 허용한다.
- 저장 여부. 채팅 줄은 "this session only"였다. 공식 문서는 `/effort <level>`이 `modelSettings`에 저장된다고 하므로, 데스크톱 엔진에서 다른 경로를 타는지, 다음 세션에 이어지는지는 보지 않았다.
- 앱이 나중에(예: 세션 재개, 모델 전환) 자기 표시 값을 엔진에 다시 보내는지.

## 5. 다시 볼 조건

- 앱이 엔진의 effort를 읽어 표시하게 되면 2026-10-21 노트의 `model-dial` 설계를 데스크톱에서도 되살릴 수 있다.
- mod API에 세션 effort를 읽거나 바뀜을 알리는 noun·이벤트가 생기면 `turn.step` 사후 관측 대신 그것을 쓴다.
