---
status: accepted
date: 2026-10-21
supersedes: []
superseded-by: null
---
# Claude Code 전용 mod는 `claude-code-mods/` 아래 별도 계열로 두고 Codex 마켓플레이스에서 제외한다

> Claude Code의 함수 훅 mod(프롬프트 위 밴드, 패널, 상태줄 같은 인터페이스 확장)를 그리모어에서도 배포하려는 맥락에서, mod는 인프로세스 모듈과 엔진 API에 의존해 Codex로 옮길 수 없고 기존 규약(ADR 0003의 공유 본체, ADR 0007의 스킬 전용)과 `check`가 그것을 받아들이지 않는 문제에 직면하여, 우리는 `plugins/`와 나란한 `claude-code-mods/<name>/` 디렉토리를 Claude 전용 계열로 신설하고 별도 레포와 `book-of-*` 안에 섞는 방안을 배제했다. 마켓플레이스와 운영 도구를 하나로 유지하기 위해, "같은 파일이 두 하네스에서 돈다"는 원칙에 디렉토리 단위의 명시적 예외를 감수한다.

## 맥락과 문제

Claude Code의 mod는 `hooks/hooks.json`이 `{"modules": ["./x.mjs"]}`로 함수 훅 모듈을 가리키고, 모듈이 `register(on, options)`를 내보내 엔진 인터페이스 `$`(세션 사용량, 저장소, 시계, UI 렌더링)에 붙는 구조다. 조사한 `augiefra/claude-mods`의 `token-weather-usage`는 이 방식으로 컨텍스트, 한도 게이지, 캐시 카운트다운, 비용을 프롬프트 위 한 줄에 그린다. Codex에는 인프로세스 플러그인 런타임도 UI 밴드도 `$.session.usage()` 같은 데이터 피드도 없어, 전달 수단 전체가 이식 불가능하다. 또 Codex는 플러그인의 `hooks/hooks.json`을 명령 훅 설정으로 읽으므로 `modules` 형식의 파일이 Codex 쪽에 설치되면 해석 불가 상태가 된다. 현재 `check`는 모든 플러그인에 Codex 매니페스트와 교집합 훅 이벤트를 요구한다.

## 고려한 선택지

1. `claude-code-mods/<name>/` 별도 계열: Claude 매니페스트만, Codex 마켓플레이스에서 제외, `check`가 계열별 규칙 적용, CI에 `claude plugin test`.
2. 별도 레포(예: `hon454/claude-mods`): 그리모어는 순수 양하네스로 남지만 마켓플레이스와 설치가 둘로 갈리고 운영 도구와 CI를 복제해야 한다.
3. `book-of-engineering` 같은 책 안에 Claude 전용 구성 요소로 포함: Codex 사용자가 그 책을 설치하면 해석 불가한 `hooks.json`이 따라간다.
4. 접두사(`charm-of-*` 등)로 구분해 `plugins/` 안에 둠: 디렉토리 하나로 끝나지만 `check`가 이름으로 종류를 추론해야 하고, "`plugins/`의 모든 것은 양하네스"라는 단순한 규칙이 깨진다.

## 결정

1번을 택한다. 종류는 디렉토리가 말한다. `plugins/`는 양하네스 플러그인, `claude-code-mods/`는 Claude 전용 mod이며, mod의 이름은 접두사 없는 보통 이름(`token-weather`)을 쓴다. 두 계열은 마켓플레이스 하나를 공유하므로 이름은 두 계열을 통틀어 유일해야 한다.

mod 한 개의 규약은 다음과 같다.

- `VERSION`, `CHANGELOG.md`, `README.md`(한국어), `.claude-plugin/plugin.json`을 둔다. 버전과 변경 기록 규칙은 ADR 0008과 같다.
- `hooks/hooks.json`은 `modules` 배열만 가지며 명령 훅 `hooks` 키를 함께 쓰지 않는다. 명령 훅이 필요하면 `plugins/`의 플러그인으로 만든다. 모듈은 `register`를 내보내고 허용 확장자(`.ts .tsx .jsx .js .mjs .cjs .mts .cts`)를 쓴다.
- `.codex-plugin/`을 두지 않는다. 마켓플레이스 생성기는 mod를 Claude 마켓플레이스에만 싣고(`tags`에 `claude-code-mod` 추가) Codex 마켓플레이스에서 제외한다. `dev-install`도 mod를 Claude에만 설치한다.
- `commands/`, `bin/`, 루트 `plugin.json`, 심볼릭 링크, 플러그인 루트 `CLAUDE.md` 금지와 개인 경로 검사는 플러그인과 같다. `skills/`와 `agents/openai.yaml`은 요구하지 않는다.
- 다른 프로젝트의 mod를 채용하거나 코드를 adapt한 mod는 그 프로젝트의 라이선스를 자기 디렉토리의 `LICENSE`와 `NOTICE`로 함께 싣고 `plugin.json`의 `license`에 적는다. 레포 전체 라이선스(MIT)는 mod 디렉토리의 라이선스로 덮어쓰인다. 아이디어만 빌린 경우에도 `NOTICE`에 출처를 적는다.
- 테스트는 `tests/*.test.ts`로 두고 `claude plugin test`로 돌린다. CI는 각 mod에 `claude plugin validate --strict`와 `claude plugin test`를 실행한다.
- 개발 중 핫 리로드는 `claude --plugin-dir claude-code-mods/<name>`이나 `CLAUDE_CODE_PLUGIN_DIRS`로 한다. 같은 mod가 마켓플레이스로도 설치되어 있으면 둘 다 로드되어 훅이 두 번 돌므로, 그때는 `dev-refresh`만 쓴다.

## 결과

- 좋음: 레포, 마켓플레이스, 운영 도구, CI가 하나로 유지된다. 디렉토리만 보면 어느 하네스용인지 안다. Codex 사용자는 mod를 볼 수 없어 깨진 설치가 생기지 않는다.
- 나쁨: 양하네스 원칙에 예외 디렉토리가 생기고 `check`와 생성기가 두 종류를 안다. mod는 Claude Code의 비공개 mod API(이벤트 이름, `$` 형태, 요소 props)에 묶여 버전 변화에 깨질 수 있다.
- 재검토 조건: Codex가 인프로세스 확장이나 UI 밴드에 해당하는 기능을 얻으면 mod를 양하네스 플러그인으로 옮길 수 있는지 다시 본다. mod가 많아져 별도 마켓플레이스 분류가 필요해지면 2번을 다시 본다.
- 확인 수단: `check`의 mod 규칙(`tests/mods.test.mjs`), 마켓플레이스 생성기의 제외 규칙, `dev-install`의 하네스별 목록(`tests/dev-install.test.mjs`), CI의 `claude plugin test`. 조사 근거는 `docs/research/2026-10-21-claude-mods.md`.
