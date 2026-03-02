---
phase: 08-sidebar-panel
plan: 01
subsystem: ui
tags: [panel_custom, StaticPathConfig, web-component, home-assistant, frontend, javascript]

# Dependency graph
requires:
  - phase: 07-automation-creator-accept-websocket
    provides: WebSocket commands (accept_pattern, dismiss_pattern, get_patterns, preview_automation, trigger_scan) that the panel will call

provides:
  - Panel registration infrastructure in __init__.py (async_setup_entry + async_unload_entry)
  - StaticPathConfig serving frontend/ at /smart_habits_frontend
  - Minimal smart-habits-panel.js stub loadable by HA
  - manifest.json dependencies: http, frontend, panel_custom
  - 6 panel registration tests in tests/test_panel_registration.py
  - conftest.py stubs for StaticPathConfig, frontend, panel_custom

affects:
  - 08-02 (full panel UI — extends the stub JS created here)

# Tech tracking
tech-stack:
  added:
    - homeassistant.components.panel_custom.async_register_panel (Python panel registration)
    - homeassistant.components.http.StaticPathConfig (static file serving since HA 2024.8)
    - homeassistant.components.frontend.async_remove_panel (panel cleanup on unload)
    - Vanilla HTMLElement web component (no build tooling)
  patterns:
    - Panel registered in async_setup_entry, removed in async_unload_entry
    - Duplicate registration guard via hass.data.get("frontend_panels", {}) check + try/except
    - Static path served from integration's frontend/ subdirectory
    - conftest.py stub pattern extended for new HA module imports

key-files:
  created:
    - custom_components/smart_habits/frontend/smart-habits-panel.js
    - tests/test_panel_registration.py
  modified:
    - custom_components/smart_habits/__init__.py
    - custom_components/smart_habits/manifest.json
    - tests/conftest.py

key-decisions:
  - "cache_headers=False used for StaticPathConfig — prevents stale JS during development; can be set True for production"
  - "Duplicate registration guard: primary defense is hass.data['frontend_panels'] dict check; try/except around async_register_panel as secondary safety net"
  - "frontend.async_remove_panel called in async_unload_entry — enables clean re-registration on config entry reload without RuntimeError"
  - "autospec=False in test mocks — SmartHabitsCoordinator autospec interferes with AsyncMock return_value setup; plain return_value=mock_coord is sufficient"
  - "Stub JS panel (Plan 01) will be fully replaced in Plan 02 — stub exists only to allow panel registration to be verified end-to-end"

patterns-established:
  - "Panel registration pattern: StaticPathConfig + async_register_panel in async_setup_entry + async_remove_panel in async_unload_entry"
  - "Test pattern for __init__.py integration: patch SmartHabitsCoordinator with return_value, patch _async_register_panel as AsyncMock, use asyncio.run()"

requirements-completed: [PANEL-01]

# Metrics
duration: 3min
completed: 2026-03-02
---

# Phase 8 Plan 01: Sidebar Panel Registration Summary

**Panel registration infrastructure via panel_custom.async_register_panel + StaticPathConfig serving vanilla HTMLElement stub JS at /smart_habits_frontend/smart-habits-panel.js**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-02T08:19:25Z
- **Completed:** 2026-03-02T08:22:42Z
- **Tasks:** 1
- **Files modified:** 5 (3 modified, 2 created)

## Accomplishments
- Panel registration in async_setup_entry: StaticPathConfig serving frontend/, async_register_panel with sidebar_icon=mdi:brain, sidebar_title=Smart Habits, frontend_url_path=smart_habits
- Duplicate registration guard (frontend_panels dict check + try/except) prevents RuntimeError on config entry reload
- frontend.async_remove_panel in async_unload_entry enables clean re-registration lifecycle
- manifest.json updated with dependencies: [http, frontend, panel_custom] per HA integration requirements
- Minimal HTMLElement web component stub created — enough for HA to load the panel, to be replaced in Plan 02
- 6 tests verifying all behaviors pass; full suite of 138 tests green with no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Panel registration + manifest + frontend stub + tests** - `c6df676` (feat)

**Plan metadata:** (docs commit to follow)

## Files Created/Modified
- `custom_components/smart_habits/__init__.py` - Added panel imports, PANEL_URL_BASE/PANEL_WEBCOMPONENT constants, StaticPathConfig registration + async_register_panel call in async_setup_entry, async_remove_panel in async_unload_entry
- `custom_components/smart_habits/manifest.json` - Added "dependencies": ["http", "frontend", "panel_custom"]
- `custom_components/smart_habits/frontend/smart-habits-panel.js` - Minimal HTMLElement stub with shadow DOM, set hass() setter, customElements.define("smart-habits-panel")
- `tests/test_panel_registration.py` - 6 tests: panel kwargs, static path config, duplicate guard, unload cleanup, manifest dependencies, JS file existence
- `tests/conftest.py` - Added stubs for homeassistant.components.http.StaticPathConfig, homeassistant.components.frontend, homeassistant.components.panel_custom

## Decisions Made
- `cache_headers=False` for StaticPathConfig — prevents browser caching of the JS stub during development
- Primary duplicate registration defense: `hass.data.get("frontend_panels", {})` dict check before calling async_register_panel; secondary defense: try/except catches any remaining edge cases
- `async_remove_panel` called in unload so re-setup of the config entry doesn't hit "Route already registered" error
- Tests use `asyncio.run()` pattern (consistent with existing project) rather than `@pytest.mark.asyncio` (not installed)
- Test mocks use `return_value=mock_coord` (not `autospec=True`) — autospec on SmartHabitsCoordinator creates mismatched mock hierarchy that breaks AsyncMock for async_config_entry_first_refresh

## Deviations from Plan

None - plan executed exactly as written. The only minor adaptation was using `asyncio.run()` for async tests (consistent with existing project test pattern) instead of `@pytest.mark.asyncio` (which requires pytest-asyncio, not installed). This was anticipated by the conftest.py inspection before writing tests.

## Issues Encountered
- `autospec=True` on SmartHabitsCoordinator caused `TypeError: 'MagicMock' object can't be awaited` because the mock created by autospec didn't inherit the AsyncMock setup for `async_config_entry_first_refresh`. Fixed by switching to `return_value=mock_coord` (Rule 1 auto-fix, inline).

## Next Phase Readiness
- Panel registration infrastructure is complete and tested
- Plan 02 can now build the full feature panel (pattern list, accept/dismiss/customize actions, stale automations) by replacing the stub JS file
- All 138 existing tests continue to pass — no regression risk

---
*Phase: 08-sidebar-panel*
*Completed: 2026-03-02*
