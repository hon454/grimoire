# Changelog

All notable changes to the `archmage` plugin are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the version follows [Semantic Versioning](https://semver.org/).

## [0.2.0] - 2026-10-21

### Changed

- Skills renamed to short topic names (ADR 0011): `reading-the-grimoire` is now `required-reading` and `binding-a-book` is now `book-binding`. Invoke them as `archmage:required-reading` and `archmage:book-binding`.
- `required-reading` and `book-binding` describe the new skill naming rule: the shortest topic name, no articles, at most 4 words, unique across books.
- `book-binding` (formerly `binding-a-book`) now documents the `dev-install` / `dev-refresh` / `dev-uninstall` loop for trying a book locally.

## [0.1.0] - 2026-10-20

### Added

- `reading-the-grimoire` skill: how an agent discovers and uses grimoire plugins.
- `binding-a-book` skill: how to scaffold, validate and release a new `book-of-*` plugin.
- SessionStart hook that injects the required reading into the session context in both Claude Code and Codex.
