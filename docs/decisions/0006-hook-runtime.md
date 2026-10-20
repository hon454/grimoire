---
status: accepted
date: 2026-10-20
supersedes: []
superseded-by: null
---
# 훅 스크립트는 의존성 없는 Node 20+ 단일 파일로 쓰고 `hooks.json`은 한 장만 둔다

> 유지보수자가 Windows를 쓰고 훅이 두 하네스에서 같은 파일로 돌아야 하는 맥락에서, 셸 스크립트는 OS와 하네스마다 분기가 필요한 문제에 직면하여, 우리는 의존성 없는 Node `.mjs`와 단일 `hooks/hooks.json`을 택하고 sh + `commandWindows` 이중 작성, Bun, 외부 테스트 러너를 배제했다. OS와 하네스 어디서나 같은 파일이 돌게 하기 위해, 사용자 머신에 Node 20 이상을 요구하는 설치 조건을 감수한다.

## 맥락과 문제

superpowers는 cmd/bash 폴리글랏 `run-hook.cmd`로 Windows에서 Git Bash를 찾고, pstack-claude는 POSIX sh 훅에 Codex용 PowerShell 쌍둥이와 `commandWindows`를 두며, ECC는 Node로 통일하고 "Windows, macOS, Linux에서 같은 동작을 위해"라고 적었다. Claude Code는 Windows에서 `.sh`가 들어간 명령에 `bash`를 자동으로 붙이는 동작이 있어 superpowers는 훅 파일을 확장자 없이 둔다. 일부 패키저는 실행 비트를 벗긴다. Node 18은 2025년 4월 지원 종료, 20은 2026년 4월, 22는 2027년 4월까지다. `node --test`는 20부터 안정이다.

## 고려한 선택지

1. Node 20 이상, `node --test`, 의존성 0: 설치 조건이 넓고 공급망 위험이 없다. 22 전용 API(`fs.glob`)는 못 쓴다.
2. Node 22 이상: 최신 API를 쓰지만 20에 머문 머신에서 훅이 실패한다.
3. Bun: TypeScript 직접 실행. 사용자에게 Bun 설치를 요구하고 Windows 지원이 약하며 하네스가 보장하지 않는다.
4. Node 20 + vitest 같은 외부 러너: `node_modules`가 생겨 배포물 제외 규칙이 필요하고 의존성 0 원칙을 포기한다.
5. 훅 파일 분리(`hooks.json` + `codex-hooks.json`): pstack과 ECC의 분리 이유는 `commandWindows`와 환경변수 매핑인데, Node 명령에는 둘 다 필요 없다.

## 결정

1번을 택하고 훅 파일은 한 장으로 시작한다.

- 훅 명령은 `node "${CLAUDE_PLUGIN_ROOT}/scripts/x.mjs"` 형태다. 스킬 본문에서도 스크립트는 인터프리터 경유로 호출한다.
- 스크립트는 stdin의 JSON을 읽고(읽지 않더라도 비워서 파이프를 막지 않고), 하네스는 환경변수로 판별한다. Codex는 `PLUGIN_ROOT`를 함께 내보내고 Claude는 `CLAUDE_*`만 내보낸다. `GRIMOIRE_HARNESS`로 강제할 수 있다.
- 내부 오류 시 출력 없이 0으로 종료해 세션을 막지 않는다.
- SessionStart 출력은 Claude에는 `hookSpecificOutput` JSON, Codex에는 평문이다.
- `.gitattributes`로 LF를 강제한다.
- 테스트는 `node --test`의 기본 탐색을 쓴다(디렉토리 인자는 Node 20에서 받지 않는다).

## 결과

- 좋음: 하네스와 OS 네 조합에서 파일 하나. 폴리글랏 래퍼나 PowerShell 쌍둥이가 없다. 테스트도 같은 런타임이다.
- 나쁨: Node가 없는 머신에서는 훅이 실패한다(README에 명시). 디렉토리 순회 같은 편의 API를 직접 쓴다.
- 재검토 조건: Codex의 Windows 실행에서 `commandWindows` 없이 `node "<경로>"`가 실패하는 것이 확인되면 `codex-hooks.json` 분리를 검토한다. Node 20 지원 종료(2026-04) 이후 하한을 22로 올리는 것을 검토한다.
- 확인 수단: `tests/session-start.test.mjs`가 두 하네스 출력 형식과 실패 시 침묵을 검증한다. `check`는 `.sh` 훅 명령에 경고한다.
