---
phase: 04-temporal-sequence-detector
plan: 02
subsystem: temporal-sequence-detector
tags: [tdd, detector, pattern-detection, coordinator]
dependency_graph:
  requires:
    - 04-01 (detectors/ subpackage, DetectedPattern.secondary_entity_id, sequence_window attr)
  provides:
    - TemporalSequenceDetector class with two-pointer sliding-window algorithm
    - temporal_sequence patterns merged in coordinator.data alongside daily_routine
    - 10 unit tests covering all detection behaviors and performance
  affects:
    - custom_components/smart_habits/detectors/temporal_sequence.py
    - custom_components/smart_habits/detectors/__init__.py
    - custom_components/smart_habits/coordinator.py
    - tests/test_temporal_sequence_detector.py
    - tests/conftest.py
tech_stack:
  added: []
  patterns:
    - Two-pointer sliding-window scan for O(n+m) co-activation counting per pair
    - Sentinel peak_hour=0 to distinguish sequence patterns from hour-based routines
    - Merge detector outputs before dismissed-pattern filter in coordinator
key_files:
  created:
    - custom_components/smart_habits/detectors/temporal_sequence.py
    - tests/test_temporal_sequence_detector.py
  modified:
    - custom_components/smart_habits/detectors/__init__.py
    - custom_components/smart_habits/coordinator.py
    - tests/conftest.py
decisions:
  - two-pointer scan chosen over nested loops for O(n+m) per pair vs O(n*m)
  - peak_hour=0 as sentinel for temporal_sequence patterns (not hour-based)
  - test_no_ha_imports uses regex matching import statements rather than substring scan to allow docstring mentions
metrics:
  duration: 3 min
  tasks_completed: 2
  files_created: 2
  files_modified: 3
  tests_added: 10
  tests_total: 60
  completed_date: 2026-02-23
---

# Phase 4 Plan 02: TemporalSequenceDetector Summary

**One-liner:** Sliding-window co-activation detector finding A->B entity pairs with configurable time window and confidence threshold, wired into coordinator alongside DailyRoutineDetector.

## What Was Built

### Task 1: RED — Failing tests for TemporalSequenceDetector (commit: c6083d0)

Created `tests/test_temporal_sequence_detector.py` with 10 test functions, all failing via ImportError before implementation:

1. `test_detects_known_sequence` — hallway->kitchen 20/30 days, confidence >= 0.5
2. `test_detects_high_confidence_sequence` — door_sensor->porch 25/30 days, confidence >= 0.7
3. `test_no_pattern_outside_window` — B at 10min: no pattern at 5-min window, detected at 15-min window
4. `test_min_occurrences_gate` — entity with 3 activations (< MIN_PAIR_OCCURRENCES=5): no patterns
5. `test_self_pair_excluded` — no pattern with entity_id == secondary_entity_id
6. `test_pattern_fields` — pattern_type="temporal_sequence", peak_hour=0, secondary_entity_id set, evidence contains "activates within"
7. `test_performance_50_entities_30_days` — 50 entities / 30 days under 10 seconds
8. `test_no_ha_imports` — no `import homeassistant` / `from homeassistant` in module
9. `test_empty_input` — `detect({}, 30)` returns `[]`
10. `test_sorted_by_confidence_desc` — patterns sorted by confidence descending

Added `temporal_states_30d` fixture to `tests/conftest.py`: 50 entities / 30 days with two known A->B sequences embedded plus 46 noise entities (seeded RNG=99).

### Task 2: GREEN — Implementation and coordinator wiring (commit: 19b6ffa)

Created `custom_components/smart_habits/detectors/temporal_sequence.py`:

- `TemporalSequenceDetector(window_seconds=300, min_confidence=0.6)`
- `detect(states, lookback_days)`: Phase 1 collects sorted activations per entity (skip < 5), Phase 2 evaluates all ordered pairs, Phase 3 returns sorted by confidence
- `_collect_activations()`: uses `extract_record` from `_utils`, filters `ACTIVE_STATES`/`SKIP_STATES`
- `_count_followed_by()`: two-pointer scan — b_idx monotonically advances past B-activations before a_ts; local `j` copy scans the window per A-activation
- `_detect_pair()`: computes confidence, emits `DetectedPattern` with `peak_hour=0` sentinel
- ZERO homeassistant imports — only stdlib + relative imports from `..const`, `..models`, `._utils`

Updated `detectors/__init__.py` to export `TemporalSequenceDetector`.

Updated `coordinator.py`:
- Import: `from .detectors import DailyRoutineDetector, TemporalSequenceDetector`
- After daily routine detection, runs `TemporalSequenceDetector(window_seconds=self.sequence_window, min_confidence=self.min_confidence)` via `async_add_executor_job`
- Merges `all_patterns = patterns + seq_patterns` before dismissed-pattern filter
- Logging updated to show daily_routine and temporal_sequence counts separately

## Test Results

```
60 passed in 1.16s
```

All 60 tests pass: 13 daily routine detector tests, 16 integration/recorder/stale tests, 9 storage tests, 6 websocket tests, 10 temporal sequence detector tests (new), plus 6 integration tests.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test_no_ha_imports matching docstring content**
- **Found during:** Task 2 (GREEN)
- **Issue:** `test_no_ha_imports` used `assert "homeassistant" not in src` which fails because the temporal_sequence.py module docstring says "No homeassistant imports". The intent was to verify zero actual import statements, not the absence of the word in docstrings.
- **Fix:** Changed assertion to use `re.findall(r"^\s*(import|from)\s+homeassistant", src, re.MULTILINE)` — matches actual import statements only
- **Files modified:** `tests/test_temporal_sequence_detector.py`
- **Commit:** 19b6ffa

## Self-Check: PASSED

- FOUND: custom_components/smart_habits/detectors/temporal_sequence.py
- FOUND: tests/test_temporal_sequence_detector.py
- FOUND: commit c6083d0 (Task 1 RED)
- FOUND: commit 19b6ffa (Task 2 GREEN)
