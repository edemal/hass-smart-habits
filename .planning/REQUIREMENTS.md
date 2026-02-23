# Requirements: Auto Pattern (Smart Habits)

**Defined:** 2026-02-23
**Core Value:** Automatically discover the user's real habits from their smart home data and turn them into one-click automations — no manual rule-writing required.

## v1.1 Requirements

Requirements for milestone v1.1 (Full Product). Each maps to roadmap phases.

### Detection

- [x] **PDET-09**: System detects temporal sequences where Device A activates and Device B activates within a configurable time window
- [ ] **PDET-10**: System detects presence-based patterns where a person's arrival correlates with device activations within a time window
- [x] **PDET-11**: User can configure the sequence detection time window (default 5 minutes) via options flow

### Automation Creation

- [ ] **AUTO-01**: User can accept a pattern suggestion and a real HA automation entity is created, visible in Settings > Automations
- [ ] **AUTO-02**: Created automation persists across HA restart
- [ ] **AUTO-03**: User sees a human-readable preview of the automation before accepting (e.g. "Turns on kitchen lights every weekday at 07:05")
- [ ] **AUTO-04**: User can customize trigger time, entities, or conditions before accepting a suggestion
- [ ] **AUTO-05**: Accepting a pattern that already has a corresponding automation does not create a duplicate

### Panel

- [ ] **PANEL-01**: Dedicated sidebar panel accessible from HA navigation displays pattern suggestions with confidence scores
- [ ] **PANEL-02**: User can accept, dismiss, or customize suggestions directly from the panel
- [ ] **PANEL-03**: Patterns are grouped by category (e.g. "Morning Routines", "Arrival Sequences", "Device Chains")
- [ ] **PANEL-04**: Panel displays stale automations that haven't fired recently
- [ ] **PANEL-05**: Panel state updates immediately after accept/dismiss actions without requiring page reload

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Advanced Detection

- **PDET-12**: System detects multi-entity routine clusters ("morning routine" as one block)
- **PDET-13**: System learns from dismissals to improve future suggestions (implicit training)
- **PDET-14**: System detects state correlation patterns (temperature → heater activation)

### Notifications

- **NOTIF-01**: User receives notification when new patterns are discovered

### UI

- **UI-06**: Lovelace dashboard card variant of the sidebar panel

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Auto-accept high-confidence patterns | Wrong automations firing at 3am destroys user trust — all patterns require explicit acceptance |
| YAML export / paste workflow | Defeats the one-click value proposition; competitors already do this poorly |
| Real-time pattern update on every state change | Fires hundreds of times per minute; Pi 4 cannot sustain; scheduled analysis is correct |
| Cloud/external ML processing | Privacy constraint — everything runs locally |
| Mobile app notifications for new patterns | Deferred to v2+ |
| Per-user pattern profiles | HA user model doesn't map cleanly to per-person analysis |
| Energy optimization suggestions | Different problem domain |
| Natural language automation input | LLM territory, scope creep |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| PDET-09 | Phase 4 | Pending |
| PDET-11 | Phase 4 | Complete |
| PDET-10 | Phase 5 | Pending |
| AUTO-01 | Phase 7 | Pending |
| AUTO-02 | Phase 7 | Pending |
| AUTO-03 | Phase 7 | Pending |
| AUTO-04 | Phase 7 | Pending |
| AUTO-05 | Phase 7 | Pending |
| PANEL-01 | Phase 8 | Pending |
| PANEL-02 | Phase 8 | Pending |
| PANEL-03 | Phase 8 | Pending |
| PANEL-04 | Phase 8 | Pending |
| PANEL-05 | Phase 8 | Pending |

**Coverage:**
- v1.1 requirements: 13 total
- Mapped to phases: 13
- Unmapped: 0 ✓

---
*Requirements defined: 2026-02-23*
*Last updated: 2026-02-23 — traceability mapped during v1.1 roadmap creation*
