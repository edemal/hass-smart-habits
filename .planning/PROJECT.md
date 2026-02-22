# Auto Pattern

## What This Is

A Home Assistant custom integration that analyzes historical device states from the Recorder database to identify behavioral patterns — time-based sequences, daily routines, and presence-based habits. It suggests automations based on discovered patterns, which users can accept, customize, or dismiss directly from a dedicated HA panel.

## Core Value

Automatically discover the user's real habits from their smart home data and turn them into one-click automations — no manual rule-writing required.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Analyze historical states from HA Recorder DB
- [ ] Detect temporal sequences (Device A on → Device B shortly after)
- [ ] Detect daily time-based routines (light on every morning at ~7:00)
- [ ] Detect presence-based patterns (person arrives → devices activate)
- [ ] Use lightweight ML models for pattern detection
- [ ] Show discovered patterns with confidence scores
- [ ] Suggest HA automations from discovered patterns
- [ ] User can accept a suggestion → creates real HA automation entity
- [ ] User can customize a suggestion before accepting
- [ ] User can dismiss/reject suggestions
- [ ] Filter out patterns already covered by existing automations
- [ ] Configurable lookback period (7/14/30/90 days)
- [ ] Dedicated sidebar panel for pattern review and automation management

### Out of Scope

- State correlations (temperature → heater) — not in v1, can add later
- Lovelace dashboard card — panel-only for v1
- Mobile app notifications for new patterns
- Cloud/external ML processing — everything runs locally

## Context

- Home Assistant custom integration (HACS-compatible)
- Data source: HA Recorder database (SQLite or MariaDB)
- ML must run on typical HA hardware (Raspberry Pi 4, NUC, etc.) — lightweight is critical
- Pattern analysis should be a background job, not blocking HA
- Generated automations follow standard HA automation YAML format
- Must handle HA's entity naming and state conventions
- Existing automations check via HA's automation registry

## Constraints

- **Platform**: Home Assistant custom integration (Python, async)
- **Hardware**: Must run on Raspberry Pi 4 class hardware — models and analysis must be lightweight
- **Dependencies**: Minimal external dependencies, compatible with HA's Python environment
- **Data Access**: Recorder DB only — no external API calls for data
- **Privacy**: All processing local, no data leaves the instance

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Custom Integration over Add-on | Tighter HA integration, direct DB access, native panel support | — Pending |
| Recorder DB as sole data source | Most reliable historical data, already available in every HA install | — Pending |
| Real automation creation (not just YAML display) | Lower friction for users, one-click value | — Pending |
| Sidebar panel for UI | Dedicated space for reviewing patterns, not cramped in a card | — Pending |
| Confidence score display | Users can judge pattern quality themselves, configurable threshold | — Pending |
| Filter existing automations | Avoid duplicate/redundant suggestions | — Pending |
| ML approach | To be determined during research phase | — Pending |

---
*Last updated: 2026-02-22 after initialization*
