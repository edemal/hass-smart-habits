# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-23)

**Core value:** Automatically discover the user's real habits from their smart home data and turn them into one-click automations — no manual rule-writing required.
**Current focus:** Milestone v1.1 — Full Product (Phases 4-8)

## Current Position

Phase: 4 — Temporal Sequence Detector
Plan: 1 of 2 complete
Status: In Progress
Last activity: 2026-02-23 — 04-01 complete: detectors/ subpackage + data model foundation

```
Progress: [░░░░░░░░░░░░░░░░░░░░] 0% (0/5 phases complete)
v1.0:     [████████████████████] 100% (3/3 phases complete, shipped)
```

## Performance Metrics

**Velocity:**
- Total plans completed: 8
- Average duration: 2.6 min
- Total execution time: 21 min

**By Phase (v1.0):**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1. Foundation | 3/3 | 6 min | 2 min |
| 2. Pattern Detection Engine | 2/2 | 9 min | 4.5 min |
| 3. Coordinator Wiring + Storage | 3/3 | ~8 min | ~2.7 min |

**By Phase (v1.1 — in progress):**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 4. Temporal Sequence Detector | 1/2 | 6 min | 6 min |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
- [Phase 04-temporal-sequence-detector]: detectors/ subpackage with backward-compat shim in pattern_detector.py for existing external imports
- [Phase 04-temporal-sequence-detector]: secondary_entity_id field placed last in DetectedPattern dataclass to satisfy Python default-field ordering rules
- [Phase 04-temporal-sequence-detector]: Storage v2 migration handled inline via d.get() fallback — no separate migration step, HA Store does not auto-migrate across versions

### Pending Todos

None.

### Blockers/Concerns

- **Phase 7 risk (automation creation):** Option A (file-write + `automation.reload`) is the chosen mechanism. Needs live HA testing during Phase 7 planning to confirm: (a) `hass.config.path("automations.yaml")` resolves correctly, (b) YAML dict structure is accepted without schema error, (c) automation appears in `hass.states` within timeout, (d) automation persists through restart. If `automations.yaml` is not writable (e.g. `!include_dir_merge_list` config), fallback is to display generated YAML for manual copy — NOT Option B (undocumented REST endpoint).
- **Phase 8 risk (panel registration):** `StaticPathConfig` requires HA 2024.11+. Verify minimum HA version declaration in manifest.json before writing panel UI. Establish a non-blank stub panel test before any feature work.

## Session Continuity

Last session: 2026-02-23
Stopped at: Completed 04-temporal-sequence-detector/04-01-PLAN.md
Resume file: None
