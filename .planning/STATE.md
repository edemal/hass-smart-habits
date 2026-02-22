# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-22)

**Core value:** Automatically discover the user's real habits from their smart home data and turn them into one-click automations — no manual rule-writing required.
**Current focus:** Phase 1 — Foundation

## Current Position

Phase: 1 of 5 (Foundation)
Plan: 3 of 3 in current phase
Status: In progress
Last activity: 2026-02-22 — Completed Plan 01-03 (coordinator wired into integration entry point)

Progress: [████░░░░░░] 20%

## Performance Metrics

**Velocity:**
- Total plans completed: 3
- Average duration: 2 min
- Total execution time: 6 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1. Foundation | 3/3 | 6 min | 2 min |

**Recent Trend:**
- Last 5 plans: 2 min, 2 min, 2 min
- Trend: Stable

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

### Pending Todos

None yet.

### Blockers/Concerns

- **Phase 1 risk RESOLVED:** scikit-learn/numpy confirmed broken on HAOS musl-Linux. Static analysis tests in Plan 01-02 prove zero external ML dependencies. Pure-Python stdlib approach is now the committed path — no fallback needed, it IS the implementation.
- **Phase 4 risk:** Automation creation uses undocumented REST endpoint (`POST /api/config/automation/config/<id>`). Inspect HA DevTools network traffic during Phase 4 planning to confirm current payload structure before implementing AutomationBuilder.

## Session Continuity

Last session: 2026-02-22
Stopped at: Completed 01-03-PLAN.md — coordinator wired into integration entry point with background scan
Resume file: None
