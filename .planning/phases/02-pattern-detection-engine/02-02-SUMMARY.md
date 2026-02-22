---
phase: 02-pattern-detection-engine
plan: 02
subsystem: coordinator-wiring
tags: [homeassistant, python, coordinator, executor, pattern-detection, integration-tests, ast]

# Dependency graph
requires:
  - phase: 02-01
    provides: DailyRoutineDetector.detect(states, lookback_days) -> list[DetectedPattern]
  - phase: 01-03
    provides: SmartHabitsCoordinator with async_trigger_scan stub and RecorderReader

provides:
  - SmartHabitsCoordinator._async_update_data fetching states via RecorderReader then running DailyRoutineDetector via hass.async_add_executor_job
  - async_trigger_scan delegating to async_refresh() (no duplicated DB logic)
  - 4 AST-based integration tests validating coordinator-detector wiring contract

affects: [03-websocket-api, 05-ui-panel]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "hass.async_add_executor_job for CPU-bound detector work (generic executor, not recorder executor)"
    - "async_trigger_scan delegates to async_refresh() — single code path for data retrieval"
    - "AST ast.walk + ast.unparse for static analysis of async function bodies"
    - "Return contract: _async_update_data returns {'patterns': list[DetectedPattern]}"

key-files:
  created: []
  modified:
    - custom_components/smart_habits/coordinator.py
    - tests/test_integration.py

key-decisions:
  - "Use hass.async_add_executor_job (not recorder executor) for CPU-bound detector work — prevents deadlocks under DB load"
  - "async_trigger_scan delegates entirely to async_refresh() — no duplicated state-fetching logic"
  - "Return dict with 'patterns' key as stable data contract for Phase 3 WebSocket API"

# Metrics
duration: 4min
completed: 2026-02-22
---

# Phase 2 Plan 02: Coordinator-Detector Wiring Summary

**SmartHabitsCoordinator wired to DailyRoutineDetector via hass.async_add_executor_job, with async_trigger_scan delegating to async_refresh(), validated by 4 AST-based integration tests and 26 total tests passing**

## Performance

- **Duration:** ~4 min
- **Completed:** 2026-02-22T10:34:11Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- `SmartHabitsCoordinator._async_update_data` replaced Phase 1 stub with real implementation: fetches states via `RecorderReader.async_get_states`, runs `DailyRoutineDetector.detect` via `self.hass.async_add_executor_job` (generic executor), returns `{"patterns": list[DetectedPattern]}`
- `async_trigger_scan` simplified to delegate to `async_refresh()` — no duplicated DB access logic
- Added `self.min_confidence = DEFAULT_MIN_CONFIDENCE` to coordinator `__init__`
- 4 new AST-based integration tests: import verification, generic executor guard, refresh delegation check, patterns key contract
- 26/26 tests pass — zero regressions against Phase 1 (9 tests) + Phase 2 Plan 01 (13 + 4 tests)

## Task Commits

1. **Task 1: Wire DailyRoutineDetector into coordinator** - `08fa64c` (feat)
2. **Task 2: Add integration tests for coordinator-detector wiring** - `3d2e080` (feat)

## Files Created/Modified

- `custom_components/smart_habits/coordinator.py` — imports DailyRoutineDetector + DEFAULT_MIN_CONFIDENCE, implements real _async_update_data, simplifies async_trigger_scan to delegate to async_refresh()
- `tests/test_integration.py` — 4 new AST-based wiring tests appended to existing Phase 1 tests

## Decisions Made

- Used `self.hass.async_add_executor_job` for CPU-bound `detector.detect()` call. The Recorder's dedicated DB executor (`get_instance(hass).async_add_executor_job`) is reserved for DB I/O only — using it for CPU work can cause deadlocks under high DB load (RESEARCH.md Anti-Pattern 2).
- `async_trigger_scan` now calls `self.async_refresh()` instead of duplicating the DB access + detection logic. Single code path ensures consistency and reduces maintenance surface.
- Return type `{"patterns": list[DetectedPattern]}` established as the coordinator data contract for Phase 3 WebSocket API serialization via `dataclasses.asdict`.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None.

## Next Phase Readiness

- `coordinator.data["patterns"]` contains `list[DetectedPattern]` after any scan
- Phase 3 WebSocket API can call `coordinator.async_refresh()` and read `coordinator.data["patterns"]`
- `DetectedPattern` dataclass serializes cleanly via `dataclasses.asdict` (stdlib, no external deps)
- PDET-01 fulfilled: user triggering a scan gets real pattern results via coordinator
- No blockers

## Self-Check: PASSED

Files verified present:
- FOUND: `custom_components/smart_habits/coordinator.py`
- FOUND: `tests/test_integration.py`

Commits verified:
- FOUND: `08fa64c` (feat(02-02): wire DailyRoutineDetector into SmartHabitsCoordinator)
- FOUND: `3d2e080` (feat(02-02): add integration tests for coordinator-detector wiring)

---
*Phase: 02-pattern-detection-engine*
*Completed: 2026-02-22*
