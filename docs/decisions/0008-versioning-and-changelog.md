---
status: accepted
date: 2026-10-20
supersedes: []
superseded-by: null
---
# 버전은 플러그인별 독립 semver, 변경 기록은 플러그인별 `CHANGELOG.md`로 관리한다

> 사용자가 책을 골라 설치하는 맥락에서, 레포 단일 버전은 어느 책이 바뀌었는지 말해 주지 않고 변경 기록 도구는 의존성 0 원칙과 충돌하는 문제에 직면하여, 우리는 플러그인별 `VERSION`과 손으로 쓰는 Keep a Changelog 형식의 `CHANGELOG.md`를 택하고 레포 단일 버전, changesets, 레포 단일 CHANGELOG, 태그 전용 기록을 배제했다. 설치된 플러그인 안에서 자기 이력을 읽을 수 있게 하기 위해, 릴리스마다 사람이 기록을 쓰는 비용을 감수한다.

## 맥락과 문제

두 하네스 모두 플러그인 매니페스트의 `version`으로 업데이트를 판단한다. mattpocock은 changesets로 `package.json` 버전을 매니페스트에 복사하고, pstack-claude는 `VERSION`과 `CHANGES.md`의 최신 제목이 같아야 생성기가 통과하며, superpowers와 ECC는 손으로 릴리스 노트를 쓴다. grimoire는 npm 배포가 없고 의존성 0이다.

## 고려한 선택지

버전 단위: 플러그인별 독립 semver 대 레포 단일 버전. 사용자는 보통 책 하나만 설치하므로 레포 버전은 의미가 약하다.

변경 기록: (1) 플러그인별 `CHANGELOG.md` 손 작성 + `check`가 최신 항목과 `VERSION` 일치를 강제, (2) changesets 도입, (3) 레포 단일 `CHANGELOG.md`에 플러그인별 섹션, (4) 기록 파일 없이 git 태그와 GitHub Releases만.

## 결정

플러그인별 독립 semver와 선택지 1을 택한다.

- `plugins/<p>/VERSION`이 단일 소스이고 `MAJOR.MINOR.PATCH`다.
- 릴리스 태그는 `<plugin>/v<version>` 형식이다.
- `plugins/<p>/CHANGELOG.md`는 Keep a Changelog 형식이며 `[Unreleased]` 절을 유지한다. `check`는 가장 위의 버전 제목이 `VERSION`과 같은지 검사한다.
- 릴리스 절차는 `VERSION` 수정, CHANGELOG 항목 이동, `stamp`, 커밋, 태그다. `stamp --set`은 앞의 두 단계를 묶지만 CHANGELOG를 쓰기 전까지 `check`가 실패한다.
- changesets는 도입하지 않는다. npm 배포가 없어 이득이 없고 `node_modules`와 봇 설정이 필요하다.

## 결과

- 좋음: 버전만 올리고 기록을 빠뜨리는 실수를 CI가 잡는다. 설치된 플러그인 디렉토리에 이력이 함께 들어간다.
- 나쁨: 여러 PR의 변경을 모으는 것은 수동이다. 플러그인이 많아지면 릴리스가 잦아진다.
- 재검토 조건: 기여자가 늘어 변경 조각을 PR 단위로 모을 필요가 생기면 changesets를 다시 본다.
- 확인 수단: `check`의 CHANGELOG 검사, `tests/new-book.test.mjs`의 `stamp --set` 시나리오.
