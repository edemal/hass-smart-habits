---
phase: 03-coordinator-wiring-storage
plan: 03
subsystem: coordinator
tags: [home-assistant, coordinator, websocket-api, dismissed-patterns, stale-automations, storage]

# Dependency graph
requires:
  - phase: 03-01
    provides: Configurable analysis schedule wired into coordinator (update_interval)
  - phase: 03-02
    provides: DismissedPatternsStore and StaleAutomation dataclass
provides:
  - Coordinator with dismissed pattern filtering (MGMT-02) via DismissedPatternsStore
  - Coordinator loads dismissed store before first scan (MGMT-01)
  - _async_detect_stale_automations reading from HA state machine (MGMT-03)
  - STALE_AUTOMATION_DAYS = 30 constant in const.py
  - WebSocket API with 3 namespaced commands: get_patterns, dismiss_pattern, trigger_scan
  - async_register_commands called from async_setup_entry
affects:
  - phase-04: UI panel consumes WebSocket commands for pattern display and dismissal
  - phase-05: Frontend panel data contract established via WebSocket schema

# Tech tracking
tech-stack:
  added: [voluptuous (stub for tests), homeassistant.components.websocket_api]
  patterns:
    - WebSocket commands decorated with @websocket_command schema + @callback or @async_response
    - Coordinator accessed via entries[0].runtime_data in WebSocket handlers (not hass.data[DOMAIN])
    - dataclasses.asdict for serializing DetectedPattern and StaleAutomation to JSON
    - DismissedPatternsStore loaded in _async_setup to guarantee data before first scan

key-files:
  created:
    - custom_components/smart_habits/websocket_api.py
    - tests/test_websocket.py
  modified:
    - custom_components/smart_habits/coordinator.py
    - custom_components/smart_habits/const.py
    - custom_components/smart_habits/__init__.py
    - tests/conftest.py
    - tests/test_integration.py
    - tests/test_stale_automation.py

key-decisions:
  - "dismissed_store.async_load() called in _async_setup (not __init__) — ensures dismissed patterns loaded before first _async_update_data call (avoids race condition)"
  - "ws_dismiss_pattern calls coordinator.async_refresh() after dismiss — keeps coordinator data immediately consistent with dismissed state"
  - "WebSocket handlers return send_error if no config entries found — guards against calling before integration setup"
  - "voluptuous stub added to conftest.py — avoids installing full HA dependency chain in pure-Python test environment"
  - "hass.states.async_all('automation') with TypeError fallback — supports both current and older HA versions"

patterns-established:
  - "WebSocket API pattern: @websocket_command schema + @callback for sync handlers, @async_response for async"
  - "Coordinator data contract: dict with 'patterns' and 'stale_automations' keys — both Phase 3 and future frontend rely on this"
  - "HA stub pattern in conftest.py: stub all direct HA dependencies transitively for pure-Python static analysis tests"

requirements-completed: [PDET-07, MGMT-01, MGMT-02, MGMT-03]

# Metrics
duration: 3min
completed: 2026-02-22
---

# Phase 3 Plan 03: Coordinator Wiring + Storage Summary

**Coordinator wired with dismissed pattern filtering (MGMT-02), stale automation detection from HA state machine (MGMT-03), and WebSocket API exposing 3 namespaced commands for the frontend panel**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-02-22T12:06:18Z
- **Completed:** 2026-02-22T12:09:33Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- Coordinator now filters dismissed patterns before returning results (MGMT-02), with dismissed store loaded before first scan (MGMT-01)
- `_async_detect_stale_automations` reads directly from HA state machine without any Recorder query (MGMT-03) and returns `list[StaleAutomation]` dataclasses
- WebSocket API with 3 namespaced commands (`smart_habits/get_patterns`, `smart_habits/dismiss_pattern`, `smart_habits/trigger_scan`) registered in `async_setup_entry`
- Test suite grew from 37 to 46 tests — all passing, zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire dismissed store + stale automation detection into coordinator** - `12cacbc` (feat)
2. **Task 2: Create WebSocket API and register in async_setup_entry** - `3693c21` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified

- `custom_components/smart_habits/coordinator.py` - Added DismissedPatternsStore wiring, dismissed filtering, stale automation detection
- `custom_components/smart_habits/const.py` - Added `STALE_AUTOMATION_DAYS = 30`
- `custom_components/smart_habits/websocket_api.py` - New file: 3 WebSocket commands with namespaced types
- `custom_components/smart_habits/__init__.py` - Added `async_register_commands(hass)` call
- `tests/conftest.py` - Added stubs for homeassistant.helpers.storage, websocket_api, voluptuous, callback
- `tests/test_websocket.py` - New file: 6 static analysis tests for WebSocket API
- `tests/test_integration.py` - Added WebSocket registration test
- `tests/test_stale_automation.py` - Flipped preparatory test, added coordinator stale detection tests

## Decisions Made

- `dismissed_store.async_load()` called in `_async_setup` (not `__init__`) — guarantees storage is loaded before first `_async_update_data` call, avoiding RESEARCH pitfall 3 (dismissed patterns visible at first scan)
- `ws_dismiss_pattern` calls `coordinator.async_refresh()` after persist — coordinator data stays consistent with dismissed state immediately, no stale data visible in subsequent `get_patterns` calls
- WebSocket handlers guard with `async_entries("smart_habits")` empty check — avoids AttributeError if handler called before integration is set up
- `hass.states.async_all("automation")` with `TypeError` fallback for older HA versions — defensive compatibility without breaking current path
- Added voluptuous stub to conftest.py rather than installing it — test suite remains zero-dependency on HA install

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added homeassistant.helpers.storage stub to conftest.py**
- **Found during:** Task 1 verification (pytest run)
- **Issue:** Adding `from .storage import DismissedPatternsStore` to coordinator.py created a new import chain through `homeassistant.helpers.storage` — not stubbed, causing `ModuleNotFoundError` in tests
- **Fix:** Added `homeassistant.helpers.storage` stub with `Store = MagicMock` to conftest.py
- **Files modified:** tests/conftest.py
- **Verification:** All 37 existing tests pass after stub addition
- **Committed in:** 12cacbc (Task 1 commit)

**2. [Rule 2 - Missing Critical] Added websocket_api, voluptuous, and callback stubs to conftest.py**
- **Found during:** Task 2 verification (pytest run)
- **Issue:** websocket_api.py imports voluptuous and homeassistant.core.callback — neither stubbed; tests failed on collection with `ModuleNotFoundError`
- **Fix:** Added stubs for `voluptuous`, `homeassistant.components.websocket_api`, and `homeassistant.core.callback` to conftest.py
- **Files modified:** tests/conftest.py
- **Verification:** 46 tests pass including all 6 new test_websocket.py tests
- **Committed in:** 3693c21 (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 2 — missing critical stubs for test isolation)
**Impact on plan:** Both fixes required to maintain the project's pure-Python test environment. No scope creep — stub pattern already established in conftest.py.

## Issues Encountered

None beyond the stub additions documented above as deviations.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 3 complete: all coordinator wiring, storage integration, and WebSocket API implemented
- WebSocket data contract (`patterns` + `stale_automations`) stable for Phase 4 frontend panel
- All MGMT-01/02/03 and PDET-07 requirements satisfied
- 46 tests passing, zero regressions — clean baseline for Phase 4

## Self-Check: PASSED

- FOUND: custom_components/smart_habits/websocket_api.py
- FOUND: custom_components/smart_habits/coordinator.py
- FOUND: tests/test_websocket.py
- FOUND: .planning/phases/03-coordinator-wiring-storage/03-03-SUMMARY.md
- FOUND: commit 12cacbc (Task 1)
- FOUND: commit 3693c21 (Task 2)

---
*Phase: 03-coordinator-wiring-storage*
*Completed: 2026-02-22*
