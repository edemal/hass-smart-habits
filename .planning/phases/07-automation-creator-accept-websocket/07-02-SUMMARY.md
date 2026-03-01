---
phase: 07-automation-creator-accept-websocket
plan: 02
subsystem: websocket
tags: [websocket, automation-creator, tdd, yaml-fallback, preview, auto-04, auto-05]

# Dependency graph
requires:
  - phase: 07-01
    provides: AutomationCreator class, AutomationCreationError, async_create_automation entry point
  - phase: 06-multi-detector-coordinator-acceptance-store
    provides: AcceptedPatternsStore, ws_accept_pattern handler, coordinator with accepted_store

provides:
  - Extended ws_accept_pattern with AutomationCreator call + trigger_hour/trigger_entities schema
  - AutomationCreationError handling with yaml_for_manual_copy fallback (AUTO-05)
  - ws_preview_automation @callback handler returning description + automation_dict (AUTO-03)
  - 5-command async_register_commands registration

affects:
  - Phase 8 (panel UI: can now call ws_preview_automation to display human-readable descriptions before accept)
  - Frontend accept flow: automation_id/automation_alias now returned on success

# Tech tracking
tech-stack:
  added: []
  patterns:
    - TDD with RED/GREEN commits
    - Lazy import inside handler body to avoid circular imports (AutomationCreator imported inside ws_accept_pattern and ws_preview_automation)
    - @callback for pure-computation handler (ws_preview_automation), @async_response for I/O handlers

key-files:
  created: []
  modified:
    - custom_components/smart_habits/websocket_api.py
    - tests/test_acceptance.py
    - tests/test_websocket.py

key-decisions:
  - "AutomationCreator imported lazily inside handler body (not at module top) to prevent circular import between websocket_api.py and automation_creator.py"
  - "ws_preview_automation uses @callback not @async_response — purely synchronous computation (_build_automation_dict + _generate_description have no I/O)"
  - "accepted_store.async_accept called before AutomationCreator.async_create_automation — pattern acceptance persisted even if file write fails"
  - "On AutomationCreationError, coordinator.async_refresh still called and accepted:True returned — pattern IS accepted, automation file write is best-effort"
  - "test_register_commands_has_four_commands updated to >= 4 (from == 4) as forward-compatible assertion when 5th command was added"

requirements-completed: [AUTO-01, AUTO-02, AUTO-03, AUTO-04, AUTO-05]

# Metrics
duration: 3min
completed: 2026-03-01
---

# Phase 7 Plan 02: WebSocket Extension + Preview Summary

**ws_accept_pattern wired to AutomationCreator with trigger_hour/trigger_entities customization, AutomationCreationError fallback returning yaml_for_manual_copy, and new ws_preview_automation @callback handler for side-effect-free previews**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-03-01T19:45:26Z
- **Completed:** 2026-03-01T19:48:12Z
- **Tasks:** 1 (TDD: RED + GREEN commits)
- **Files modified:** 3 (websocket_api.py modified, 2 test files modified)

## Accomplishments
- ws_accept_pattern extended: AutomationCreator imported lazily, async_create_automation called after accepted_store.async_accept, automation_id + automation_alias returned on success
- AutomationCreationError caught: yaml_for_manual_copy fallback computed via _build_automation_dict + yaml.dump, returned with accepted:True and warning string
- trigger_hour + trigger_entities optional schema fields added to ws_accept_pattern (AUTO-04)
- ws_preview_automation: new @callback handler, schema with 3 required + 3 optional fields, returns {description, automation_dict} without side effects
- async_register_commands updated to 5 calls: ws_preview_automation registered as 5th command
- 27/27 tests in test_acceptance.py + test_websocket.py pass; 132/132 full suite green

## Task Commits

Each task committed atomically (TDD: RED then GREEN):

1. **RED — Failing tests for ws_accept_pattern automation creation + ws_preview_automation** - `27d318e` (test)
2. **GREEN — Extended websocket_api.py + test fix** - `bb33185` (feat)

## Files Created/Modified
- `custom_components/smart_habits/websocket_api.py` - Extended ws_accept_pattern + new ws_preview_automation handler + 5th command registration
- `tests/test_acceptance.py` - 7 new tests for AutomationCreator integration; test_register_commands_has_four_commands updated to >= 4
- `tests/test_websocket.py` - 7 new tests for ws_preview_automation (handler existence, @callback, schema fields, response keys, 5-command count)

## Decisions Made
- Lazy import of AutomationCreator inside handler body rather than module-level import — prevents circular import between websocket_api.py and automation_creator.py (same pattern used by HA core for late-bound integrations)
- ws_preview_automation decorated with @callback (not @async_response) because both _build_automation_dict and _generate_description are pure Python computation — no file I/O, no executor, no await needed
- Pattern acceptance (accepted_store.async_accept) called unconditionally before automation creation — the acceptance must persist even if the YAML write fails

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_register_commands_has_four_commands stale assertion**
- **Found during:** GREEN phase
- **Issue:** test_acceptance.py had `assert count == 4` which broke when 5th command was added, blocking the full test run
- **Fix:** Changed assertion to `assert count >= 4` with updated docstring explaining the 5-command reality. The exact 5-count is verified separately in `test_register_commands_has_five_commands` (test_websocket.py)
- **Files modified:** tests/test_acceptance.py
- **Commit:** bb33185

## Self-Check: PASSED

All files exist and commits present:
- custom_components/smart_habits/websocket_api.py — FOUND
- tests/test_acceptance.py — FOUND
- tests/test_websocket.py — FOUND
- Commit 27d318e (RED) — FOUND
- Commit bb33185 (GREEN) — FOUND
- 132/132 tests green — VERIFIED

---
*Phase: 07-automation-creator-accept-websocket*
*Completed: 2026-03-01*
