---
phase: 03-coordinator-wiring-storage
plan: 02
subsystem: storage-models
tags: [storage, persistence, dismissed-patterns, stale-automation, static-analysis-tests]
dependency_graph:
  requires: []
  provides:
    - DismissedPatternsStore (storage.py) — used by coordinator in Plan 03
    - StaleAutomation dataclass (models.py) — returned by coordinator._async_detect_stale_automations in Plan 03
  affects:
    - coordinator.py (Plan 03 wires DismissedPatternsStore and _async_detect_stale_automations)
    - websocket_api.py (Plan 03 serializes StaleAutomation via dataclasses.asdict)
tech_stack:
  added:
    - homeassistant.helpers.storage.Store (JSON persistence to .storage/)
  patterns:
    - Store(hass, version, key) wrapping pattern for dismissed state persistence
    - STORAGE_KEY namespacing: "smart_habits.dismissed" avoids key collisions (Pitfall 5)
    - Dismissed fingerprint as tuple(entity_id, pattern_type, peak_hour) stored as list of dicts
    - _async_setup() pattern for loading storage before first coordinator refresh (Pitfall 3)
key_files:
  created:
    - custom_components/smart_habits/storage.py
    - tests/test_storage.py
    - tests/test_stale_automation.py
  modified:
    - custom_components/smart_habits/models.py (added StaleAutomation dataclass)
    - tests/test_integration.py (updated test_coordinator_has_no_poll_interval for Phase 3)
decisions:
  - "DismissedPatternsStore wraps helpers.storage.Store — no custom file I/O (per RESEARCH.md Don't Hand-Roll table)"
  - "STORAGE_KEY='smart_habits.dismissed' namespaced to avoid future key collision when 'smart_habits.accepted' is added in Phase 4"
  - "Dismissed fingerprint = tuple(entity_id, pattern_type, peak_hour) — sufficient identity for MGMT-02 filter"
  - "test_coordinator_has_no_poll_interval updated to assert timedelta interval — coordinator was already updated in prior session per Phase 3 plan, test was stale (RESEARCH.md Pitfall 1)"
metrics:
  duration: "~2 min"
  completed: "2026-02-22"
  tasks_completed: 2
  files_modified: 5
---

# Phase 3 Plan 02: Dismissed Patterns Storage and Stale Automation Model Summary

**One-liner:** `DismissedPatternsStore` wrapping `helpers.storage.Store` for JSON-persisted dismissed-pattern fingerprints, plus `StaleAutomation` dataclass and 8 static-analysis tests.

## What Was Built

### Task 1: DismissedPatternsStore and StaleAutomation model

**`custom_components/smart_habits/storage.py`** — New module implementing `DismissedPatternsStore`:

- Wraps `homeassistant.helpers.storage.Store` with `STORAGE_KEY = "smart_habits.dismissed"` and `STORAGE_VERSION = 1`
- `async_load()` — called from coordinator `_async_setup()` before first refresh, loads dismissed set from `.storage/smart_habits.dismissed.json`
- `async_dismiss(entity_id, pattern_type, peak_hour)` — adds fingerprint tuple to in-memory set and immediately persists via `async_save()`
- `is_dismissed(entity_id, pattern_type, peak_hour)` — O(1) set membership check used by coordinator MGMT-02 filter
- `dismissed_count` property — exposes set size

**`custom_components/smart_habits/models.py`** — Added `StaleAutomation` dataclass:

```python
@dataclass
class StaleAutomation:
    entity_id: str
    friendly_name: str
    last_triggered: str | None
    days_since_triggered: int | None
```

Returned by `coordinator._async_detect_stale_automations` (wired in Plan 03).

### Task 2: Static analysis tests (8 new tests, 34 total)

**`tests/test_storage.py`** (5 tests):
- `test_storage_module_exists` — file exists at expected path
- `test_storage_uses_ha_store` — imports `Store` from `homeassistant.helpers.storage`
- `test_storage_key_is_namespaced` — STORAGE_KEY is `"smart_habits.dismissed"`
- `test_storage_has_required_methods` — AST confirms `async_load`, `async_dismiss`, `is_dismissed`
- `test_storage_dismiss_is_async` — AST confirms `async_dismiss` is `AsyncFunctionDef` (must await Store.async_save)

**`tests/test_stale_automation.py`** (3 tests):
- `test_stale_automation_model_exists` — `StaleAutomation` class exists with `@dataclass`
- `test_stale_automation_has_required_fields` — all 4 required fields present
- `test_stale_automation_threshold_constant` — `STALE_AUTOMATION_DAYS` not yet in `const.py` (preparatory; Plan 03 adds it)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated stale `test_coordinator_has_no_poll_interval` test**
- **Found during:** Task 2 (first pytest run revealed 1 failure)
- **Issue:** `test_coordinator_has_no_poll_interval` in `test_integration.py` asserted `update_interval=None` (Phase 1/2 behavior). The `coordinator.py` was already updated in a prior session to use `update_interval=timedelta(...)` (the Phase 3 change). This test stale state was explicitly anticipated in RESEARCH.md Pitfall 1: "This test must be updated in Phase 3 to check for a non-None timedelta."
- **Fix:** Updated test assertion to `"update_interval=timedelta" in source or "update_interval = timedelta" in source` with updated docstring reflecting Phase 3 scheduled scan behavior (PDET-07).
- **Files modified:** `tests/test_integration.py`
- **Commit:** e0c2181

## Test Results

```
34 passed in 1.05s
```

Zero regressions. All Phase 1/2 tests continue to pass alongside the 8 new tests.

## Self-Check: PASSED

Files confirmed present:
- `custom_components/smart_habits/storage.py` — FOUND
- `custom_components/smart_habits/models.py` (StaleAutomation added) — FOUND
- `tests/test_storage.py` — FOUND
- `tests/test_stale_automation.py` — FOUND

Commits confirmed:
- `9c72376` — feat(03-02): add DismissedPatternsStore and StaleAutomation model
- `e0c2181` — feat(03-02): add static analysis tests for storage and stale automation
