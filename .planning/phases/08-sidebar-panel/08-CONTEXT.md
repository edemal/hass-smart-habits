# Phase 8: Sidebar Panel - Context

**Gathered:** 2026-03-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Dedicated sidebar panel accessible from HA navigation that displays pattern suggestions (from all three detectors) and stale automations. Users can accept, dismiss, or customize suggestions directly from the panel with immediate visual feedback. All WebSocket commands are already built and tested — this phase is purely frontend (LitElement web component).

</domain>

<decisions>
## Implementation Decisions

### Card Layout & Information Density
- Claude's discretion on all card layout decisions
- Confidence display: choose what looks best in HA's design language (bar, text, both)
- Information density: choose between compact, detailed, or progressive disclosure
- Automation preview description placement: choose visibility approach (always, on-hover, or in customize flow)
- Entity icons: choose appropriate icon usage based on HA conventions

### Category Grouping & Ordering
- Claude's discretion on grouping style (collapsible sections, flat list with headers, or tabs)
- Claude's discretion on sort order within groups (confidence, recency, alphabetical)
- Claude's discretion on category naming for the three pattern types (daily_routine, temporal_sequence, presence)
- Claude's discretion on empty state design (message + guidance, scan prompt, or combination)

### Accept/Dismiss/Customize Interaction
- Claude's discretion on action button presentation (icon buttons, action bar, swipe)
- Claude's discretion on customize UX (inline expansion, modal dialog, or detail view)
- Claude's discretion on post-accept feedback (toast + removal, success state, persistent card)
- Claude's discretion on whether accept requires confirmation step

### Stale Automations Section
- Claude's discretion on placement relative to suggestions
- Claude's discretion on available actions (informational only, disable, or disable + delete)
- Claude's discretion on information displayed per stale entry
- Claude's discretion on staleness threshold visibility/configurability

### Claude's Discretion
Full discretion on all visual and interaction design decisions for this phase. The user trusts Claude to make choices that align with HA's native design language and conventions. Key constraint: the panel must feel like a native HA panel, not a custom app embedded in HA.

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches. User deferred all design decisions to Claude's judgment with one implicit constraint: the panel should feel native to Home Assistant.

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `DetectedPattern` dataclass (models.py): entity_id, pattern_type, peak_hour, confidence, evidence, active_days, total_days, secondary_entity_id
- `StaleAutomation` dataclass (models.py): entity_id, friendly_name, last_triggered, days_since_triggered
- WebSocket API (websocket_api.py): All 5 commands ready — get_patterns, dismiss_pattern, accept_pattern, trigger_scan, preview_automation
- `AutomationCreator` (automation_creator.py): _generate_description for human-readable previews, _build_automation_dict for full automation data

### Established Patterns
- WebSocket commands use `smart_habits/` namespace (e.g., `smart_habits/get_patterns`)
- Coordinator accessed via `entries[0].runtime_data`
- Accept pattern returns `{accepted: true, automation_id, automation_alias}` or `{accepted: true, yaml_for_manual_copy}` on file write failure
- Dismiss pattern returns `{dismissed: true}` and triggers coordinator refresh
- Pattern fingerprint: entity_id + pattern_type + peak_hour + optional secondary_entity_id
- Customization overrides: trigger_hour and trigger_entities passed to accept/preview

### Integration Points
- Panel registration: Need `async_register_panel` in __init__.py or via manifest.json `panel` key
- Frontend JS bundle: Needs to be served from `custom_components/smart_habits/frontend/` (HACS convention)
- No existing frontend code — everything built from scratch
- manifest.json has no `panel` or `frontend_extra_module_url` yet

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 08-sidebar-panel*
*Context gathered: 2026-03-01*
