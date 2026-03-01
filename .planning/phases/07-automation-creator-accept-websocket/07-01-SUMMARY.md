---
phase: 07-automation-creator-accept-websocket
plan: 01
subsystem: automation
tags: [yaml, hashlib, homeassistant, tdd, file-io, automation-creation]

# Dependency graph
requires:
  - phase: 06-multi-detector-coordinator-acceptance-store
    provides: AcceptedPatternsStore, ws_accept_pattern handler, coordinator with accepted_patterns
  - phase: 07-RESEARCH.md
    provides: AutomationCreator architecture pattern, pitfall list, file-write + reload mechanism

provides:
  - AutomationCreator class in automation_creator.py
  - AutomationCreationError typed exception
  - AUTOMATION_ID_PREFIX constant in const.py
  - Deterministic MD5-based automation ID generation (AUTO-05)
  - Human-readable description generator for all 3 pattern types (AUTO-03)
  - Synchronous file I/O with yaml.dump sort_keys=False (AUTO-01, AUTO-02)
  - Async wrapper with executor + automation.reload (AUTO-01)

affects:
  - 07-02 (WebSocket extension: ws_accept_pattern will import and call AutomationCreator)
  - Phase 8 (panel UI: will display automation previews via _generate_description)

# Tech tracking
tech-stack:
  added: [pyyaml (installed for test environment), hashlib (stdlib), os.access (stdlib)]
  patterns:
    - TDD with RED/GREEN commits
    - Executor-based file I/O to avoid blocking HA event loop
    - Deterministic automation IDs via hashlib.md5 fingerprint hash

key-files:
  created:
    - custom_components/smart_habits/automation_creator.py
    - tests/test_automation_creator.py
  modified:
    - custom_components/smart_habits/const.py

key-decisions:
  - "hashlib.md5 used for deterministic automation IDs — same pattern fingerprint always maps to same ID, enabling AUTO-05 dedup without external state"
  - "create_automation_sync is synchronous and must always be called via hass.async_add_executor_job — async_create_automation is the primary entry point for WebSocket handlers"
  - "os.access(path, os.W_OK) checked before write attempt — if file missing, parent dir checked instead; AutomationCreationError surfaced to WS handler for graceful fallback"
  - "HA 2024.9+ plural triggers/actions syntax used throughout — triggers[0].trigger not trigger.platform"

patterns-established:
  - "AutomationCreator: single-responsibility class for all YAML file operations, instantiated at call site by WS handler"
  - "Writability check before write: os.access(path, os.W_OK) to distinguish permission error from IOError"
  - "Dedup guard: any(a.get('id') == automation_id for a in existing) before appending to list"

requirements-completed: [AUTO-01, AUTO-02, AUTO-03, AUTO-05]

# Metrics
duration: 6min
completed: 2026-03-01
---

# Phase 7 Plan 01: AutomationCreator Summary

**AutomationCreator class that builds valid HA automation dicts via MD5 fingerprint IDs, writes YAML with sort_keys=False, deduplicates by deterministic ID, and reloads via automation.reload service**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-03-01T19:40:26Z
- **Completed:** 2026-03-01T19:46:30Z
- **Tasks:** 1 (TDD: RED + GREEN commits)
- **Files modified:** 3 (created 2, modified 1)

## Accomplishments
- AutomationCreator class with all methods: _get_automation_id, _build_automation_dict, _generate_description, create_automation_sync, async_create_automation
- 29 TDD tests covering all behavior: ID determinism, all 3 pattern types, description generation, file I/O create/append/dedup/error
- AUTOMATION_ID_PREFIX constant added to const.py
- Full test suite 117/117 green, no regressions

## Task Commits

Each task committed atomically (TDD: RED then GREEN):

1. **RED — Failing tests + const.py** - `aba19af` (test)
2. **GREEN — AutomationCreator implementation** - `b3368ae` (feat)

## Files Created/Modified
- `custom_components/smart_habits/automation_creator.py` - AutomationCreator class, AutomationCreationError, full file I/O and reload logic
- `tests/test_automation_creator.py` - 29 TDD tests across 4 test classes
- `custom_components/smart_habits/const.py` - Added AUTOMATION_ID_PREFIX = "smart_habits_"

## Decisions Made
- Used hashlib.md5 (not uuid4) for automation IDs — determinism is the key property needed for AUTO-05 dedup; random UUIDs would create duplicates on re-accept
- Writability check for missing files checks parent dir (not file itself) since os.access on a non-existent path returns False even when the directory is writable
- PyYAML installed for test environment (already bundled with HA in production)

## Deviations from Plan

None — plan executed exactly as written. Implementation followed 07-RESEARCH.md Pattern 1 code examples faithfully.

## Issues Encountered
- PyYAML not installed in test environment (Rule 3 auto-fix): installed `pyyaml` via pip for test runner. Not a production concern — HA bundles PyYAML.

## Next Phase Readiness
- AutomationCreator is ready to be imported by ws_accept_pattern in Phase 7-02
- async_create_automation(entity_id, pattern_type, peak_hour, secondary_entity_id, trigger_hour, trigger_entities) is the call signature for WebSocket integration
- AutomationCreationError must be caught in WS handler for graceful YAML fallback (surfaced to frontend as yaml_for_manual_copy)

---
*Phase: 07-automation-creator-accept-websocket*
*Completed: 2026-03-01*
