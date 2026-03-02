---
phase: 10-add-integration-and-device-type-filters-for-pattern-exclusion
plan: "02"
subsystem: coordinator
tags: [entity_registry, pattern_filtering, exclusion, tdd]

# Dependency graph
requires:
  - phase: 10-01
    provides: CONF_EXCLUDED_INTEGRATIONS, CONF_EXCLUDED_DOMAINS, DEFAULT_EXCLUDED_INTEGRATIONS, DEFAULT_EXCLUDED_DOMAINS constants and options flow UI
provides:
  - _is_pattern_excluded method on SmartHabitsCoordinator filtering by integration (registry.platform) or entity domain prefix
  - Exclusion filter step in _async_update_data applied before dismissed/accepted split
  - 9-test TDD suite covering all exclusion scenarios
affects: [coordinator, pattern analysis pipeline]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "_is_pattern_excluded takes registry as parameter (obtained once in _async_update_data, passed to each call) to avoid repeated er.async_get(hass) calls"
    - "Domain check uses entity_id.split('.')[0] prefix — O(1), no registry needed"
    - "Integration check guarded by 'if excluded_integrations:' — empty list skips registry lookup entirely"
    - "Exclusion filter runs BEFORE dismissed/accepted split so excluded patterns vanish from both lists"

key-files:
  created:
    - tests/test_coordinator_filters.py
  modified:
    - custom_components/smart_habits/coordinator.py

key-decisions:
  - "Registry obtained once in _async_update_data and passed to _is_pattern_excluded to avoid repeated er.async_get(hass) calls per pattern"
  - "Domain check via entity_id prefix runs before integration check (no I/O) for performance"
  - "Unregistered entities (registry returns None) are NOT excluded — avoids false-positive filtering for non-registry entities"
  - "Fast path: if excluded_integrations or excluded_domains is falsy, skip registry lookup and list comprehension entirely"

patterns-established:
  - "TDD RED-GREEN flow: failing tests committed first, then implementation"

requirements-completed: []

# Metrics
duration: 2min
completed: 2026-03-02
---

# Phase 10 Plan 02: Coordinator Exclusion Filter Summary

**`_is_pattern_excluded` method on SmartHabitsCoordinator filters patterns by integration (via entity registry platform) or entity domain prefix, applied before dismissed/accepted split, with 9 TDD tests covering all scenarios**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-02T09:14:42Z
- **Completed:** 2026-03-02T09:16:17Z
- **Tasks:** 1 (TDD: RED commit + GREEN commit)
- **Files modified:** 2

## Accomplishments
- `_is_pattern_excluded` method added to `SmartHabitsCoordinator` with domain prefix check and registry integration check
- Exclusion filter integrated into `_async_update_data` BEFORE dismissed/accepted split — excluded patterns vanish from both lists
- `excluded_integrations` and `excluded_domains` initialized from `entry.options` in `__init__` with defaults
- Fast path: empty exclusion lists skip all registry lookups
- 9 TDD unit tests pass covering primary entity, secondary entity, domain, integration, unregistered, empty lists, combined filters, and non-matching patterns
- All 147 tests pass (no regressions)

## Task Commits

Each task was committed atomically:

1. **RED: Failing tests for exclusion filter** - `29ec05e` (test)
2. **GREEN: Implement exclusion filter in coordinator** - `c10cc15` (feat)

_TDD plan: test commit then implementation commit_

## Files Created/Modified
- `tests/test_coordinator_filters.py` - 9 unit tests for `_is_pattern_excluded` using bare coordinator instance and mock registry
- `custom_components/smart_habits/coordinator.py` - Added `er` import, exclusion constants, `__init__` attributes, `_is_pattern_excluded` method, and filter step in `_async_update_data`

## Decisions Made
- Registry obtained once in `_async_update_data` and passed to `_is_pattern_excluded` as parameter, avoiding repeated `er.async_get(hass)` calls per pattern
- Domain check uses `entity_id.split(".")[0]` prefix — runs first (no I/O) before integration check
- Unregistered entities are NOT excluded (registry returns None) — prevents false-positive filtering for entities not in the registry
- Fast path: `if excluded_integrations or excluded_domains:` guard skips registry lookup entirely when no filters configured

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 10 complete: filter constants, options flow UI, coordinator exclusion filter with full TDD coverage
- The integration now silently drops patterns from excluded integrations/domains before they appear in any suggestion list
- No further work required for this feature unless new exclusion criteria are needed

---
*Phase: 10-add-integration-and-device-type-filters-for-pattern-exclusion*
*Completed: 2026-03-02*
