---
status: accepted
date: 2026-10-20
supersedes: []
superseded-by: null
---
# 스킬, 훅, 스크립트는 두 하네스가 같은 파일을 읽고 매니페스트만 두 장을 둔다

> Claude Code와 Codex를 동시에 지원해야 하는 맥락에서, 하네스별 복사본이 생기면 드리프트가 나는 문제에 직면하여, 우리는 공유 본체 + 얇은 매니페스트 2장을 택하고 단일 소스에서 하네스별 파일을 렌더링하는 생성 레이어(gstack 방식)와 하네스별 디렉토리 복제(ECC의 `.agents/skills` 부분집합 방식)를 배제했다. 변환 없이 같은 파일이 양쪽에서 돌게 하기 위해, 두 하네스의 교집합 기능만 쓰는 제약을 감수한다.

## 맥락과 문제

두 하네스의 사양을 비교한 결과, 스킬(`skills/<name>/SKILL.md`), 훅(`hooks/hooks.json`, 이벤트 이름과 stdin 계약), MCP 설정은 포맷과 경로가 사실상 같다. 갈라지는 것은 매니페스트 위치(`.claude-plugin/plugin.json` 대 `.codex-plugin/plugin.json`)와 하네스 고유 요소(Claude의 `commands/`, `agents/`, `userConfig`, Codex의 `interface`, `agents/openai.yaml`)뿐이다. Codex는 훅 matcher에서 Claude의 도구 이름(`Bash`, `Edit|Write`, `Agent`)을 별칭으로 받고 `CLAUDE_PLUGIN_ROOT`도 호환용으로 내보낸다. superpowers와 pstack-claude가 같은 전략을 쓴다.

## 고려한 선택지

1. 공유 본체 + 얇은 매니페스트 2장: 변환 없음. 교집합 기능만 사용.
2. 단일 소스에서 하네스별 파일 생성: 하네스별 최적화가 가능하지만 생성기 유지와 "생성물 신선도" 검사가 필요하다. gstack이 이 방식인데 그것은 플러그인이 아니라 스킬 디렉토리 설치다.
3. 하네스별 디렉토리에 복사본 유지: ECC가 Codex와 Cursor용 스킬 부분집합을 손으로 복사하며 "동기화는 수동"이라고 명시한다. 드리프트가 실제로 발생한다(ECC 매니페스트의 스킬 수가 세 곳에서 다르다).

## 결정

1번을 택하고, 다음을 함께 정한다.

- 플러그인 루트에 `skills/`, `hooks/hooks.json`, `scripts/`, 선택적 `.mcp.json`을 두고 두 하네스가 그대로 읽는다.
- Claude 전용 요소는 `.claude-plugin/plugin.json`과 Claude 전용 폴더에만, Codex 전용 메타데이터(`interface`)는 `.codex-plugin/plugin.json`에만 둔다. Codex는 모르는 폴더를 무시한다.
- 스킬마다 `agents/openai.yaml` 사이드카를 둔다. Codex UI 메타데이터를 싣는 관례이며 Claude는 무시한다.
- 심볼릭 링크는 레포 어디에도 두지 않는다. Codex는 플러그인을 캐시로 복사하며 링크를 버리고, Windows 체크아웃도 링크를 지원하지 않을 수 있다. `CLAUDE.md`도 `AGENTS.md`를 가리키는 실제 파일이다.
- 플러그인 경로 변수는 `${CLAUDE_PLUGIN_ROOT}` 하나만 쓴다.
- 훅 이벤트는 두 하네스 교집합만 쓰고 matcher는 Claude 이름으로 쓴다.

## 결과

- 좋음: 생성기도 복사본도 없다. 스킬 본문은 한 번만 쓴다. pstack-claude의 Codex 설치 경로가 실측으로 검증되어 있다.
- 나쁨: 한 하네스에만 있는 기능(Claude의 `context: fork`, Codex의 `onboardingSkill`)을 쓰려면 매니페스트 쪽에서만 선언해야 하고 본문은 그 기능 없이도 동작하게 써야 한다.
- 재검토 조건: 두 하네스의 스킬 포맷이 갈라지거나(프론트매터 허용 키 변경 등), 하네스 전용 기능 의존이 커지면 2번(생성 레이어)을 다시 본다.
- 확인 수단: `check`가 심볼릭 링크, 사이드카 존재, 훅 이벤트 집합, `${CLAUDE_PLUGIN_ROOT}` 참조 경로를 검사한다. Codex 로컬 설치에서 스킬이 `archmage:reading-the-grimoire`로 발견됨을 실측했다(2026-10-20).
