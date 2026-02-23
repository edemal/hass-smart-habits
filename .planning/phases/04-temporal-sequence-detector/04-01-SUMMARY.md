---
phase: 04-temporal-sequence-detector
plan: 01
subsystem: detectors-subpackage-and-data-model
tags: [refactoring, data-model, storage, config-flow, websocket]
dependency_graph:
  requires: []
  provides:
    - detectors/ subpackage with DailyRoutineDetector
    - DetectedPattern.secondary_entity_id field
    - DismissedPatternsStore v2 with 4-element fingerprints
    - CONF_SEQUENCE_WINDOW option and coordinator attribute
    - dismiss_pattern WS command with optional secondary_entity_id
  affects:
    - custom_components/smart_habits/coordinator.py
    - custom_components/smart_habits/__init__.py
    - custom_components/smart_habits/storage.py
    - custom_components/smart_habits/models.py
    - tests/test_storage.py
    - tests/test_integration.py
tech_stack:
  added: []
  patterns:
    - Subpackage extraction with backward-compat shim
    - Optional field placement on dataclass (last field with default)
    - Inline v1-to-v2 migration via d.get() with fallback
key_files:
  created:
    - custom_components/smart_habits/detectors/__init__.py
    - custom_components/smart_habits/detectors/_utils.py
    - custom_components/smart_habits/detectors/daily_routine.py
  modified:
    - custom_components/smart_habits/pattern_detector.py (now backward-compat shim)
    - custom_components/smart_habits/models.py (secondary_entity_id added)
    - custom_components/smart_habits/const.py (CONF_SEQUENCE_WINDOW added)
    - custom_components/smart_habits/storage.py (v2 with 4-element fingerprints)
    - custom_components/smart_habits/config_flow.py (sequence_window dropdown)
    - custom_components/smart_habits/strings.json (sequence_window labels)
    - custom_components/smart_habits/websocket_api.py (optional secondary_entity_id)
    - custom_components/smart_habits/coordinator.py (sequence_window attr, updated dismiss filter)
    - custom_components/smart_habits/__init__.py (propagate sequence_window on options update)
    - tests/conftest.py (SelectSelectorMode stub, vol.Optional/vol.Any stubs)
    - tests/test_storage.py (v2 migration and fingerprint tests)
    - tests/test_integration.py (updated coordinator import assertion)
decisions:
  - pattern_detector.py kept as backward-compat shim re-exporting from detectors/
  - secondary_entity_id placed last in DetectedPattern to satisfy dataclass default-field ordering
  - v1 storage migration handled inline via d.get() — no separate migration step needed
  - Storage version bumped to 2 to signal schema change; HA Store does not auto-migrate
metrics:
  duration: 6 min
  tasks_completed: 2
  files_created: 3
  files_modified: 11
  tests_added: 5
  tests_total: 50
  completed_date: 2026-02-23
---

# Phase 4 Plan 01: Detectors Subpackage and Multi-Detector Data Model Foundation Summary

**One-liner:** Restructured codebase for multi-detector support: extracted detectors/ subpackage, extended DetectedPattern with secondary_entity_id, storage v2 with 4-element fingerprints and v1 migration, sequence_window option in config/coordinator/WS API.

## What Was Built

### Task 1: Create detectors/ subpackage and move DailyRoutineDetector (commit: 5327a55)

Created `custom_components/smart_habits/detectors/` as a proper Python subpackage:

- `detectors/_utils.py`: Contains `ACTIVE_STATES`, `SKIP_STATES`, and `extract_record()` (formerly `DailyRoutineDetector._extract_record` static method, now a module-level public function)
- `detectors/daily_routine.py`: Full `DailyRoutineDetector` class, now importing from `._utils`
- `detectors/__init__.py`: Package entry point exporting `DailyRoutineDetector`
- `pattern_detector.py`: Replaced with a backward-compatibility shim re-exporting from the new subpackage
- `coordinator.py`: Updated import to `from .detectors import DailyRoutineDetector`
- `tests/test_daily_routine_detector.py`: Updated imports to canonical `custom_components.smart_habits.detectors` paths

### Task 2: Extend model, storage v2, const, config flow, WS API, coordinator (commit: d2dea12)

Extended the entire data pipeline for temporal sequence pattern support:

- **models.py**: `DetectedPattern.secondary_entity_id: str | None = None` added as the last field
- **const.py**: `CONF_SEQUENCE_WINDOW = "sequence_window"`, `DEFAULT_SEQUENCE_WINDOW = 300`, `SEQUENCE_WINDOW_OPTIONS = ["60", "120", "300", "600", "900"]`
- **storage.py**: STORAGE_VERSION bumped to 2, `_dismissed` type changed to `set[tuple[str, str, int, str | None]]`, async_load/async_dismiss/is_dismissed updated to 4-element tuples with backward-compat v1 migration
- **config_flow.py**: `sequence_window` SelectSelector dropdown added to options flow
- **strings.json**: sequence_window data and data_description entries added
- **websocket_api.py**: `vol.Optional("secondary_entity_id", default=None)` added to dismiss_pattern command
- **coordinator.py**: `self.sequence_window` attribute; dismiss filter passes `p.secondary_entity_id`
- **__init__.py**: `_async_options_updated` propagates `sequence_window` changes
- **tests/conftest.py**: SelectSelectorMode/Config/Selector stubs; vol.Optional/vol.Any stubs
- **tests/test_storage.py**: Added `test_storage_version_is_2`, `test_storage_contains_secondary_entity_id`, `test_v1_data_migrates_secondary_entity_id_to_none`, `test_secondary_entity_id_creates_distinct_fingerprint`

## Test Results

```
50 passed in 1.00s
```

All 50 tests pass: 13 daily routine detector tests, 6 integration tests, 4 recorder reader tests, 5 stale automation tests, 9 storage tests (7 existing + 2 new structural + 2 new functional), 6 websocket tests.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test_coordinator_imports_detector asserting stale import path**
- **Found during:** Task 1
- **Issue:** `test_integration.py::test_coordinator_imports_detector` checked for `from .pattern_detector import DailyRoutineDetector` which was intentionally changed to `from .detectors import DailyRoutineDetector`
- **Fix:** Updated test assertion to expect the new canonical path with explanatory comment
- **Files modified:** `tests/test_integration.py`
- **Commit:** d2dea12

**2. [Rule 1 - Bug] Fixed storage functional tests failing due to MagicMock spec issue**
- **Found during:** Task 2
- **Issue:** Python 3.14's unittest.mock raises `InvalidSpecError: Cannot spec a Mock object` when `Store(mock_hass, ...)` is called with a MagicMock hass argument. The stub `Store = MagicMock` class tried to use `mock_hass` as a spec.
- **Fix:** Used `unittest.mock.patch` on `custom_components.smart_habits.storage.Store` in `_make_store_instance` helper; used `MagicMock(spec=[])` for hass
- **Files modified:** `tests/test_storage.py`
- **Commit:** d2dea12

**3. [Rule 2 - Missing functionality] Added vol.Optional and vol.Any to voluptuous stub**
- **Found during:** Task 2
- **Issue:** `websocket_api.py` now uses `vol.Optional` and `vol.Any` which were not stubbed in conftest.py
- **Fix:** Added stubs for both in the conftest.py voluptuous block
- **Files modified:** `tests/conftest.py`
- **Commit:** d2dea12

## Self-Check: PASSED

- FOUND: custom_components/smart_habits/detectors/__init__.py
- FOUND: custom_components/smart_habits/detectors/_utils.py
- FOUND: custom_components/smart_habits/detectors/daily_routine.py
- FOUND: commit 5327a55 (Task 1)
- FOUND: commit d2dea12 (Task 2)
