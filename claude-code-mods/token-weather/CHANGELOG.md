# Changelog

All notable changes to the `token-weather` mod are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the version follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.0] - 2026-10-21

### Removed

- The language option. Labels are English only: the Korean table, the `auto` detection from `LC_ALL`, `LC_MESSAGES`, `LANG` and the runtime locale, and the `language` user config are gone.
- Every cost figure. Gone are the session-cost pill (the total, the last prompt's dollars and its 5-hour points), the cache block's stake, rewrite price, miss surcharge and savings, the agents card's cost split by model and effort, the last batch's cost and the delegating savings, the price table and every use of the session usage's `cost` field. The cache block keeps the time left, the share read, misses, expiry and the `/compact` or new-thread advice; the agents card keeps the agents running with their latest tool call and the last batch's wall time, parallelism and tool calls.

## [0.1.0] - 2026-10-21

### Added

- Port of `token-weather-usage` 3.17.4 by Eric Cologni (Apache-2.0, see `NOTICE`): context weather and recent-prompt bars, 5-hour and 7-day gauges against elapsed time with the 7-day run-out estimate, prompt cache countdown with missed/expired/compacted states and costs, session and last-prompt cost, agents pill with its cost split, running agents and last-batch receipt.
- Labels in English or Korean (`language` option: `auto`, `en`, `ko`); French and Russian are not carried over.
- Terminal width measured in cells so wide (Hangul, CJK) labels do not push the band past the line.
