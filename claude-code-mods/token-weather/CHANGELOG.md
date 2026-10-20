# Changelog

All notable changes to the `token-weather` mod are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the version follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-10-21

### Added

- Port of `token-weather-usage` 3.17.4 by Eric Cologni (Apache-2.0, see `NOTICE`): context weather and recent-prompt bars, 5-hour and 7-day gauges against elapsed time with the 7-day run-out estimate, prompt cache countdown with missed/expired/compacted states and costs, session and last-prompt cost, agents pill with its cost split, running agents and last-batch receipt.
- Labels in English or Korean (`language` option: `auto`, `en`, `ko`); French and Russian are not carried over.
- Terminal width measured in cells so wide (Hangul, CJK) labels do not push the band past the line.
