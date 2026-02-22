---
phase: 03-coordinator-wiring-storage
plan: 01
subsystem: coordinator
tags: [schedule, options-flow, mc-01, mc-02, pdet-07]
dependency_graph:
  requires: [02-02-SUMMARY.md]
  provides: [configurable-analysis-schedule, options-update-listener, analysis-interval-option]
  affects: [coordinator.py, __init__.py, config_flow.py, const.py, strings.json]
tech_stack:
  added: [datetime.timedelta]
  patterns: [options-update-listener, options-before-data-fallback, int-cast-selectselector]
key_files:
  created: []
  modified:
    - custom_components/smart_habits/const.py
    - custom_components/smart_habits/coordinator.py
    - custom_components/smart_habits/__init__.py
    - custom_components/smart_habits/config_flow.py
    - custom_components/smart_habits/strings.json
    - tests/test_integration.py
decisions:
  - "entry.options.get() with entry.data fallback used in coordinator for both CONF_LOOKBACK_DAYS and CONF_ANALYSIS_INTERVAL — options always take priority over initial config data"
  - "update_interval mutated directly on coordinator instance in _async_options_updated — DataUpdateCoordinator supports live attribute update without reinstantiation"
  - "entry.async_on_unload wraps add_update_listener — ensures listener deregistration on config entry unload with no manual cleanup code needed"
  - "ANALYSIS_INTERVAL_OPTIONS as string list ['1','3','7'] — matches SelectSelector contract (always returns strings); int() cast applied at save time (MC-02 pattern)"
metrics:
  duration: 3 min
  completed: 2026-02-22
  tasks_completed: 2
  files_changed: 6
---

# Phase 3 Plan 01: Configurable Analysis Schedule + MC-01/MC-02 Fixes Summary

Configurable analysis schedule via timedelta update_interval, options update listener (MC-01), int()-cast options storage (MC-02), and analysis interval selector in options flow — all backed by 37 passing tests.

## What Was Built

### Task 1 — Add schedule constants, update coordinator to use timedelta, fix MC-01/MC-02

**const.py:** Added three new constants:
- `CONF_ANALYSIS_INTERVAL = "analysis_interval"`
- `DEFAULT_ANALYSIS_INTERVAL = 1`
- `ANALYSIS_INTERVAL_OPTIONS = ["1", "3", "7"]`

**coordinator.py:** Replaced `update_interval=None` with `update_interval=timedelta(days=analysis_interval_days)`. Both `CONF_ANALYSIS_INTERVAL` and `CONF_LOOKBACK_DAYS` are now read from `entry.options` first, falling back to `entry.data`, then the default constant. Updated class docstring to reflect Phase 3 scheduled polling.

**__init__.py (MC-01):** Added `entry.async_on_unload(entry.add_update_listener(_async_options_updated))` after coordinator setup. Added `_async_options_updated` module-level coroutine that updates `coordinator.lookback_days`, `coordinator.update_interval`, and calls `coordinator.async_refresh()` so options changes propagate immediately without restart.

**config_flow.py (MC-02):** Options flow `async_step_init` now casts both `CONF_LOOKBACK_DAYS` and `CONF_ANALYSIS_INTERVAL` with `int()` before `async_create_entry`. Added `CONF_ANALYSIS_INTERVAL` dropdown field using `SelectSelector(SelectSelectorConfig(options=ANALYSIS_INTERVAL_OPTIONS, mode=SelectSelectorMode.DROPDOWN))`. Added `current_interval` pre-population from options/data fallback.

**strings.json:** Added `analysis_interval` to both `data` and `data_description` under `options.step.init`.

### Task 2 — Update integration tests for Phase 3 schedule + options wiring

- Renamed `test_coordinator_has_no_poll_interval` → `test_coordinator_has_scheduled_poll_interval`; updated assertion from `update_interval=None` to `update_interval=timedelta`
- Added `test_init_registers_update_listener`: asserts `add_update_listener` and `async_on_unload` both present in `__init__.py` (MC-01)
- Added `test_options_flow_casts_to_int`: asserts `int(user_input[` pattern in `config_flow.py` (MC-02)
- Added `test_coordinator_reads_options_first`: asserts `entry.options.get(` in `coordinator.py`
- Updated module docstring to reflect Phase 3 test coverage

**Result:** 37/37 tests pass — all Phase 1/2/3 tests green.

## Deviations from Plan

None — plan executed exactly as written.

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| `entry.options.get()` with `entry.data` fallback in coordinator | Options always override initial config; existing entries without options key fall back to config data gracefully |
| `coordinator.update_interval` mutated directly in `_async_options_updated` | `DataUpdateCoordinator` supports live attribute mutation; no reinstantiation or HA restart needed |
| `entry.async_on_unload` wraps `add_update_listener` | Automatic deregistration on unload; zero manual cleanup code; consistent with HA lifecycle patterns |
| `ANALYSIS_INTERVAL_OPTIONS` as `["1","3","7"]` strings | `SelectSelector` always returns strings; `int()` cast at save time (MC-02) rather than trying to coerce the selector itself |

## Verification Results

| Check | Result |
|-------|--------|
| Python syntax (all 4 .py files) | PASSED |
| strings.json JSON validity | PASSED |
| `update_interval=None` count in coordinator.py | 0 (removed) |
| `add_update_listener` count in `__init__.py` | 1 |
| pytest tests/ -v (37 tests) | 37 passed |

## Self-Check: PASSED

- FOUND: `.planning/phases/03-coordinator-wiring-storage/03-01-SUMMARY.md`
- FOUND: commit `c352e8c` (feat: add configurable analysis schedule + MC-01/MC-02 fixes)
- FOUND: commit `a938172` (test: update integration tests for Phase 3 schedule + options wiring)
