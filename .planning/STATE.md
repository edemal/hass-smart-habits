# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-22)

**Core value:** Automatically discover the user's real habits from their smart home data and turn them into one-click automations — no manual rule-writing required.
**Current focus:** Phase 4 — UI Panel (next phase)

## Current Position

Phase: 3 of 5 (Coordinator Wiring + Storage) — COMPLETE
Plan: 3 of 3 in phase (all complete)
Status: Phase 3 complete — coordinator wired with dismissed filtering, stale detection, WebSocket API, 46 tests passing
Last activity: 2026-02-22 — Completed Plan 03-03 (coordinator wiring, WebSocket API, 46 tests)

Progress: [███████████████░] 68%

## Performance Metrics

**Velocity:**
- Total plans completed: 8
- Average duration: 2.6 min
- Total execution time: 21 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1. Foundation | 3/3 | 6 min | 2 min |
| 2. Pattern Detection Engine | 2/2 | 9 min | 4.5 min |
| 3. Coordinator Wiring + Storage | 3/3 | ~8 min | ~2.7 min |

**Recent Trend:**
- Last 5 plans: 2 min, 5 min, 4 min, 3 min, 3 min
- Trend: Phase 3 complete — all wiring done, clean baseline for Phase 4

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Roadmap creation: Build bottom-up — DB access and async patterns validated in Phase 1 before any ML code is written
- Roadmap creation: PDET-03 (presence) and PDET-04 (sequences) deferred to Phase 5 — different algorithm paths that would complicate Phase 2 delivery
- 01-01: Used modern ConfigFlow class syntax (ConfigFlow, domain=DOMAIN) not deprecated HANDLERS dict pattern
- 01-01: single_config_entry in manifest enforces one-instance-only declaratively — no code check needed
- 01-01: after_dependencies=[recorder] ensures Recorder DB loads before smart_habits
- 01-01: No translations/en.json — English-only strings.json per locked v1 decision
- 01-01: DEFAULT_ENTITY_DOMAINS = light/switch/binary_sensor/input_boolean/person/device_tracker as analysis whitelist
- 01-02: All Recorder DB queries use get_instance(hass).async_add_executor_job — routes to Recorder's dedicated DB thread pool, not generic executor
- 01-02: dt_util.utcnow() used everywhere (timezone-aware, not deprecated datetime.utcnow())
- 01-02: PDET-08 risk resolved — static analysis tests prove zero external ML dependencies; HAOS compatibility confirmed
- 01-03: entry.runtime_data used instead of hass.data[DOMAIN] — modern HA pattern, avoids deprecated coordinator-dict approach
- 01-03: entry.async_create_background_task instead of asyncio.create_task — HA manages task cancellation on entry unload
- 01-03: update_interval=None on DataUpdateCoordinator — Phase 1 no polling schedule; INTG-03 fulfilled
- 02-01: lookback_days used as confidence denominator — simpler, known limitation for new entities documented
- 02-01: One pattern per entity max — return only the highest-confidence hour to avoid duplicate entity patterns
- 02-01: MIN_EVENTS_THRESHOLD=5 early-exit guard — sparse entities cannot form meaningful patterns
- 02-01: HA stub injection via sys.modules in conftest.py — enables pure-Python detector tests without HA install
- 02-01: pytest.ini with pythonpath=. added — required for custom_components import resolution in test environment
- 02-02: hass.async_add_executor_job (not recorder executor) for CPU-bound detector work — prevents deadlocks under DB load
- 02-02: async_trigger_scan delegates to async_refresh() — single code path for data retrieval, no duplication
- 02-02: coordinator.data["patterns"] as stable data contract for Phase 3 WebSocket API
- 03-01: entry.options.get() with entry.data fallback in coordinator — options always take priority over initial config data
- 03-01: coordinator.update_interval mutated directly in _async_options_updated — DataUpdateCoordinator supports live attribute update without reinstantiation
- 03-01: entry.async_on_unload wraps add_update_listener — automatic deregistration on unload, no manual cleanup code
- 03-01: ANALYSIS_INTERVAL_OPTIONS as string list ["1","3","7"] — SelectSelector returns strings; int() cast applied at save time (MC-02)
- 03-02: DismissedPatternsStore wraps helpers.storage.Store (no custom file I/O) with namespaced key "smart_habits.dismissed"
- 03-02: Dismissed fingerprint = tuple(entity_id, pattern_type, peak_hour) for MGMT-02 set-membership filter
- 03-02: StaleAutomation dataclass defined in models.py — coordinator wires _async_detect_stale_automations in Plan 03
- 03-03: dismissed_store.async_load() in _async_setup (not __init__) — guarantees dismissed patterns loaded before first scan
- 03-03: ws_dismiss_pattern calls coordinator.async_refresh() after persist — keeps data consistent with dismissed state immediately
- 03-03: WebSocket command handlers guard with async_entries empty check — avoids AttributeError before integration setup
- 03-03: hass.states.async_all("automation") with TypeError fallback — supports current and older HA versions
- 03-03: coordinator.data contract expanded to {"patterns": [...], "stale_automations": [...]} — stable for Phase 4 frontend

### Pending Todos

None yet.

### Blockers/Concerns

- **Phase 1 risk RESOLVED:** scikit-learn/numpy confirmed broken on HAOS musl-Linux. Static analysis tests in Plan 01-02 prove zero external ML dependencies. Pure-Python stdlib approach is now the committed path — no fallback needed, it IS the implementation.
- **Phase 4 risk:** Automation creation uses undocumented REST endpoint (`POST /api/config/automation/config/<id>`). Inspect HA DevTools network traffic during Phase 4 planning to confirm current payload structure before implementing AutomationBuilder.

## Session Continuity

Last session: 2026-02-22
Stopped at: Completed 03-03-PLAN.md — coordinator wiring, WebSocket API, 46 tests passing
Resume file: None
