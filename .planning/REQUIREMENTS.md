# Requirements: Auto Pattern

**Defined:** 2026-02-22
**Core Value:** Automatically discover the user's real habits from their smart home data and turn them into one-click automations — no manual rule-writing required.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Pattern Detection

- [ ] **PDET-01**: User can trigger pattern analysis on historical Recorder DB states
- [ ] **PDET-02**: System detects daily time-based routines (e.g. light on every morning at ~7:00)
- [ ] **PDET-03**: System detects presence-based patterns (person arrives → devices activate)
- [ ] **PDET-04**: System detects temporal sequences (device A on → device B shortly after)
- [ ] **PDET-05**: Each pattern has a confidence score with evidence (e.g. "8/10 mornings")
- [x] **PDET-06**: User can configure lookback period (7/14/30/90 days)
- [ ] **PDET-07**: User can configure analysis schedule + trigger manual scan
- [x] **PDET-08**: Pattern analysis uses lightweight ML, runs on RPi 4 class hardware

### Suggestion Management

- [ ] **MGMT-01**: User can dismiss suggestions persistently (survives restart)
- [ ] **MGMT-02**: Dismissed patterns train future analysis (reduces similar suggestions)
- [ ] **MGMT-03**: System detects stale automations (not fired in 30+ days)

### User Interface

- [ ] **UI-01**: Dedicated sidebar panel for pattern review and management
- [ ] **UI-02**: User can accept suggestion → creates real HA automation entity
- [ ] **UI-03**: User can preview suggestion in human-readable form before accepting
- [ ] **UI-04**: User can customize suggestion (time, entities, conditions) before accepting
- [ ] **UI-05**: Suggestions grouped by category ("Morning Routines", "Arrival Sequences")

### Integration

- [x] **INTG-01**: HACS-compatible custom integration with config flow
- [x] **INTG-02**: All processing runs locally, no external API calls
- [x] **INTG-03**: Analysis runs as background task, does not block HA

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Suggestion Management

- **MGMT-04**: Filter suggestions by entity domain (lights, switches, covers...)
- **MGMT-05**: Exclude specific users/personas from analysis
- **MGMT-06**: Skip patterns already covered by existing automations (dedup)

### User Interface

- **UI-06**: Lovelace dashboard card for quick-view notifications

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Cloud/external ML processing | Privacy — all processing must be local |
| Auto-create automations without user review | Destroys trust per UX research; always require explicit accept |
| Real-time streaming pattern detection | RPi 4 can't sustain continuous inference; batch is correct architecture |
| Mobile push notifications for new patterns | Notification fatigue; sidebar panel is primary UI |
| Per-user pattern profiles | Massive complexity; HA user model doesn't map cleanly to per-person analysis |
| Energy optimization suggestions | Different problem domain — behavioral patterns, not energy analysis |
| Natural language automation input | LLM territory; scope creep away from pattern mining |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| PDET-01 | Phase 2 | Pending |
| PDET-02 | Phase 2 | Pending |
| PDET-03 | Phase 5 | Pending |
| PDET-04 | Phase 5 | Pending |
| PDET-05 | Phase 2 | Pending |
| PDET-06 | Phase 1 | Complete |
| PDET-07 | Phase 3 | Pending |
| PDET-08 | Phase 1 | Complete |
| MGMT-01 | Phase 3 | Pending |
| MGMT-02 | Phase 3 | Pending |
| MGMT-03 | Phase 3 | Pending |
| UI-01 | Phase 5 | Pending |
| UI-02 | Phase 4 | Pending |
| UI-03 | Phase 5 | Pending |
| UI-04 | Phase 5 | Pending |
| UI-05 | Phase 5 | Pending |
| INTG-01 | Phase 1 | Complete |
| INTG-02 | Phase 1 | Complete |
| INTG-03 | Phase 1 | Complete |

**Coverage:**
- v1 requirements: 19 total
- Mapped to phases: 19
- Unmapped: 0 ✓

---
*Requirements defined: 2026-02-22*
*Last updated: 2026-02-22 after roadmap creation — all requirements mapped*
