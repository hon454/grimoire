# Changelog

All notable changes to the `book-of-engineering` plugin are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the version follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-10-21

### Added

- `tdd` skill: the red-green-refactor loop at agreed seams, with the rules that keep tests honest (independent expectations, mocks only at system boundaries, the mutation check). Adapted from superpowers `test-driven-development` and mattpocock/skills `tdd` (both MIT, see NOTICE).
- `adr` skill: decides whether a decision deserves a record, finds or creates the repository's decision log, and writes one immutable MADR-style record with a Y-statement; supersedes instead of editing. The "worth recording" gate is adapted from mattpocock/skills `domain-modeling` (MIT, see NOTICE).
