# Roadmap: Auto Pattern

## Overview

Build bottom-up: establish the HA integration scaffold and validated DB access layer first, then layer pattern detection, coordinator wiring, automation creation, and the full review panel on top. Each phase delivers a coherent, independently testable capability before the next begins. The core value — one-click automation creation from discovered habits — is complete at Phase 7. Phase 8 completes the review UX with the dedicated sidebar panel.

## Milestones

- ✅ **v1.0 MVP Backend** — Phases 1-3 (shipped 2026-02-22)
- 📋 **v1.1 Full Product** — Phases 4-8 (in progress)

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

<details>
<summary>✅ v1.0 MVP Backend (Phases 1-3) — SHIPPED 2026-02-22</summary>

- [x] **Phase 1: Foundation** - HACS-compatible integration scaffold, Recorder DB access layer, async execution patterns, HAOS dependency validation (completed 2026-02-22)
- [x] **Phase 2: Pattern Detection Engine** - Daily routine detector, confidence scoring, unit-tested against static fixtures, coordinator wired (completed 2026-02-22)
- [x] **Phase 3: Coordinator Wiring + Storage** - PatternCoordinator, WebSocket API, persistent storage, panel skeleton (completed 2026-02-22)

See: `.planning/milestones/v1.0-ROADMAP.md` for full phase details.

</details>

### v1.1 Full Product

- [ ] **Phase 4: Temporal Sequence Detector** - Sliding-window co-activation detector, detectors/ subpackage, DetectedPattern fingerprint extension
- [ ] **Phase 5: Presence Pattern Detector** - Arrival-correlation detector with dwell-time filter, person.* domain preference
- [ ] **Phase 6: Multi-Detector Coordinator + Acceptance Store** - All three detectors run in single executor job, AcceptedPatternsStore, coordinator filters accepted patterns
- [ ] **Phase 7: Automation Creator + Accept WebSocket** - File-write + reload automation creation, accept/customize WS commands, human-readable preview
- [ ] **Phase 8: Sidebar Panel** - LitElement web component, pattern cards with accept/dismiss/customize, stale automation list, category grouping

## Phase Details

### Phase 4: Temporal Sequence Detector
**Goal**: The system detects temporal sequences (Device A activates then Device B activates within a configurable window) and the detection code is fully unit-tested in isolation before any HA wiring
**Depends on**: Phase 3 (detectors/ subpackage introduced here, but inherits v1.0 codebase)
**Requirements**: PDET-09, PDET-11
**Success Criteria** (what must be TRUE):
  1. Given historical state data where entity A turns on and entity B turns on within 5 minutes repeatedly, the detector surfaces a temporal sequence pattern with a confidence score
  2. The detector processes 50 entities over 30 days of history in under 10 seconds (Pi 4 performance bar)
  3. User can configure the detection time window (default 5 minutes) in the options flow, and the detector respects the configured value
  4. Existing dismissed patterns continue to work correctly after the DetectedPattern fingerprint is extended with secondary_entity_id and the storage version is bumped
**Plans:** 1/2 plans executed

Plans:
- [ ] 04-01-PLAN.md — Structural refactor (detectors/ subpackage, model extension, storage v2, options flow, WS update)
- [ ] 04-02-PLAN.md — TDD: TemporalSequenceDetector implementation + coordinator wiring

### Phase 5: Presence Pattern Detector
**Goal**: The system detects presence-based patterns (a person arrives home and devices activate within a time window) and the detector is unit-tested in isolation with flap-noise fixtures
**Depends on**: Phase 4 (detectors/ subpackage, fingerprint extension)
**Requirements**: PDET-10
**Success Criteria** (what must be TRUE):
  1. Given state history where a person entity transitions to "home" and lights turn on within the configured window, the detector surfaces a presence pattern with a confidence score
  2. A person entity that transitions to "home" and back to "not_home" within 5 minutes (flap) is not counted as a genuine arrival
  3. When no person.* entities exist in HA state, the detector falls back to device_tracker.* entities without error
  4. The detector is independently unit-testable with static state fixtures requiring no live HA instance
**Plans**: TBD

### Phase 6: Multi-Detector Coordinator + Acceptance Store
**Goal**: All three detectors run together in a single background job, accepted patterns are persisted and filtered from the suggestion list, and the data model supports the automation creation flow in Phase 7
**Depends on**: Phase 5 (all three detectors exist)
**Requirements**: (none direct — enables AUTO-01, AUTO-02, AUTO-05 in Phase 7)
**Success Criteria** (what must be TRUE):
  1. After a coordinator refresh, coordinator.data contains patterns from all three detectors (daily routine, temporal sequence, presence) merged into a single list
  2. Accepting a pattern via the new AcceptedPatternsStore removes it from the suggestion list returned by get_patterns
  3. Accepted patterns persist across HA restart (coordinator.data["accepted_patterns"] survives config entry reload)
  4. The coordinator runs all three detectors in a single executor job, not three separate jobs
**Plans**: TBD

### Phase 7: Automation Creator + Accept WebSocket
**Goal**: A user can accept a pattern suggestion and a real HA automation entity is created, visible in Settings > Automations — the complete core value is delivered end-to-end
**Depends on**: Phase 6 (AcceptedPatternsStore, merged detector output)
**Requirements**: AUTO-01, AUTO-02, AUTO-03, AUTO-04, AUTO-05
**Success Criteria** (what must be TRUE):
  1. Accepting a pattern creates a real HA automation entity visible in Settings > Automations, and the automation persists after HA restart
  2. Before accepting, the user sees a plain-language description of what the automation will do (e.g. "Turns on kitchen lights every weekday at 07:05")
  3. The user can adjust the trigger time, entities, or conditions on a suggestion before accepting, and the created automation reflects the customized values
  4. Accepting a pattern that already has a corresponding automation does not create a duplicate
  5. If automations.yaml is not writable at runtime, the integration warns the user and surfaces the generated YAML for manual copy rather than silently failing
**Plans**: TBD

### Phase 8: Sidebar Panel
**Goal**: Users can review, act on, and manage all pattern types from a dedicated sidebar panel — accept, dismiss, and customize suggestions without leaving the panel, with immediate visual feedback after every action
**Depends on**: Phase 7 (all WebSocket commands stable and tested)
**Requirements**: PANEL-01, PANEL-02, PANEL-03, PANEL-04, PANEL-05
**Success Criteria** (what must be TRUE):
  1. A dedicated sidebar panel is accessible from the HA navigation sidebar and displays pattern suggestions with confidence scores
  2. User can accept, dismiss, or open a customize form for any suggestion directly from the panel — no page reload required after any action
  3. Patterns are grouped by category ("Morning Routines", "Arrival Sequences", "Device Chains") within the panel
  4. The panel displays the list of stale automations (those not fired in 30+ days) alongside pattern suggestions
  5. Panel state updates immediately after accept or dismiss — the acted-on pattern disappears from the list without requiring a page reload
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Foundation | v1.0 | 3/3 | Complete | 2026-02-22 |
| 2. Pattern Detection Engine | v1.0 | 2/2 | Complete | 2026-02-22 |
| 3. Coordinator Wiring + Storage | v1.0 | 3/3 | Complete | 2026-02-22 |
| 4. Temporal Sequence Detector | 1/2 | In Progress|  | - |
| 5. Presence Pattern Detector | v1.1 | 0/TBD | Not started | - |
| 6. Multi-Detector Coordinator + Acceptance Store | v1.1 | 0/TBD | Not started | - |
| 7. Automation Creator + Accept WebSocket | v1.1 | 0/TBD | Not started | - |
| 8. Sidebar Panel | v1.1 | 0/TBD | Not started | - |
