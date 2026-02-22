# Roadmap: Auto Pattern

## Overview

Build bottom-up: establish the HA integration scaffold and validated DB access layer first, then layer pattern detection, coordinator wiring, automation creation, and the full review panel on top. Each phase delivers a coherent, independently testable capability before the next begins. The core value — one-click automation creation from discovered habits — is complete at Phase 4. Phase 5 completes the review UX and adds the advanced detectors that make the product a true differentiator.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Foundation** - HACS-compatible integration scaffold, Recorder DB access layer, async execution patterns, HAOS dependency validation (completed 2026-02-22)
- [x] **Phase 2: Pattern Detection Engine** - Daily routine detector, confidence scoring, unit-tested against static fixtures, coordinator wired (completed 2026-02-22)
- [x] **Phase 3: Coordinator Wiring + Storage** - PatternCoordinator, WebSocket API, persistent storage, panel skeleton (completed 2026-02-22)
- [ ] **Phase 4: Automation Creation** - AutomationBuilder, accept-to-create flow, full core user journey complete
- [ ] **Phase 5: Review Panel + Advanced Detectors** - Full LitElement sidebar panel, presence-based detection, temporal sequence detection

## Phase Details

### Phase 1: Foundation
**Goal**: A loadable HA custom integration with confirmed async patterns, working Recorder DB access, and validated HAOS dependency compatibility — so every phase above it builds on proven ground
**Depends on**: Nothing (first phase)
**Requirements**: INTG-01, INTG-02, INTG-03, PDET-06, PDET-08
**Success Criteria** (what must be TRUE):
  1. Integration installs and loads in Home Assistant via HACS without errors
  2. Config flow completes and creates a config entry with lookback period selection (7/14/30/90 days)
  3. RecorderReader queries the Recorder DB in an executor job and returns state rows scoped to the configured lookback window — no event loop blocking
  4. scikit-learn and numpy install successfully on HAOS, or pure-Python fallback is confirmed and documented as the algorithm path
  5. All processing runs locally — no network calls leave the HA instance
**Plans:** 3/3 plans complete

Plans:
- [ ] 01-01-PLAN.md — Integration scaffold with config flow and HACS metadata
- [ ] 01-02-PLAN.md — RecorderReader DB access layer and HAOS dependency validation
- [ ] 01-03-PLAN.md — Coordinator wiring with background scan trigger

### Phase 2: Pattern Detection Engine
**Goal**: A tested daily routine detector that produces confidence-scored pattern objects from Recorder state data — pure Python, validated against real-shape fixtures, ready to wire into HA
**Depends on**: Phase 1
**Requirements**: PDET-01, PDET-02, PDET-05
**Success Criteria** (what must be TRUE):
  1. User can trigger pattern analysis (manually or via coordinator) and receive a list of detected patterns
  2. Each detected pattern includes a confidence score with human-readable evidence (e.g. "happened 8 of last 10 mornings")
  3. DailyRoutineDetector correctly identifies a time-based routine from a 90-day fixture with 500 entities within 30 seconds on Pi 4 class hardware
  4. Analysis runs in an executor job and does not block the HA event loop
**Plans:** 2/2 plans complete

Plans:
- [x] 02-01-PLAN.md — DailyRoutineDetector with TDD: models, algorithm, test suite
- [x] 02-02-PLAN.md — Coordinator wiring: connect detector to HA lifecycle

### Phase 3: Coordinator Wiring + Storage
**Goal**: The pattern detection engine is wired into HA's lifecycle — scheduled analysis, on-demand scans, persistent dismissed/accepted state, and a WebSocket API with a thin panel that proves the data contract end-to-end
**Depends on**: Phase 2
**Requirements**: PDET-07, MGMT-01, MGMT-02, MGMT-03
**Audit Fixes** (from v1.0 audit):
  - MC-01: Register `entry.add_update_listener` so options flow reconfiguration updates the running coordinator
  - MC-02: Add `int()` cast in options flow `async_step_init` to match config flow behavior
**Success Criteria** (what must be TRUE):
  1. User can trigger a manual analysis scan from the integration and see updated results
  2. Analysis runs automatically on the configured schedule without blocking HA startup
  3. A dismissed pattern stays dismissed across HA restarts
  4. Dismissing a pattern type reduces the frequency of similar suggestions in subsequent analysis runs
  5. Stale automations (not triggered in 30+ days) are surfaced separately in the data the panel can display
  6. Changing lookback period via options flow takes effect immediately without restart (MC-01/MC-02)
**Plans:** 3/3 plans complete

Plans:
- [x] 03-01-PLAN.md — Configurable analysis schedule + MC-01/MC-02 audit fixes
- [x] 03-02-PLAN.md — DismissedPatternsStore + StaleAutomation model
- [x] 03-03-PLAN.md — Coordinator wiring + WebSocket API

### Phase 4: Automation Creation
**Goal**: A user can click accept on a suggestion and a real, working HA automation entity is created — the complete core value is delivered end-to-end
**Depends on**: Phase 3
**Requirements**: UI-02
**Success Criteria** (what must be TRUE):
  1. Accepting a suggestion creates a real HA automation entity visible in Settings > Automations
  2. The created automation persists across HA restart
  3. Accepting a suggestion that already has a corresponding automation does not create a duplicate
  4. The accept flow updates the panel state (pattern moves from pending to accepted) without requiring a page reload
**Plans**: TBD

### Phase 5: Review Panel + Advanced Detectors
**Goal**: Users can review, preview, customize, and act on all pattern types through a polished sidebar panel — including presence-based and temporal sequence patterns that no competitor detects
**Depends on**: Phase 4
**Requirements**: UI-01, UI-03, UI-04, UI-05, PDET-03, PDET-04
**Success Criteria** (what must be TRUE):
  1. Dedicated sidebar panel is accessible from the HA navigation and displays suggestions grouped by category (e.g. "Morning Routines", "Arrival Sequences")
  2. User can preview any suggestion in plain language before accepting (e.g. "Turns on kitchen lights every weekday at 07:05")
  3. User can edit the time, entities, or conditions of a suggestion before accepting it
  4. System detects patterns where a person's arrival triggers device activation and surfaces them as suggestions
  5. System detects temporal sequences (device A on → device B shortly after) and surfaces them as suggestions
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 3/3 | Complete   | 2026-02-22 |
| 2. Pattern Detection Engine | 2/2 | Complete    | 2026-02-22 |
| 3. Coordinator Wiring + Storage | 3/3 | Complete    | 2026-02-22 |
| 4. Automation Creation | 0/TBD | Not started | - |
| 5. Review Panel + Advanced Detectors | 0/TBD | Not started | - |
