# Feature Research

**Domain:** Home Assistant custom integration — automation creation, sidebar panel, temporal sequence detection, presence-based pattern detection
**Researched:** 2026-02-23
**Confidence:** MEDIUM-HIGH — prior v1.0 research confirmed most integration patterns; v1.1 features extend known-working architecture. Automation creation endpoint (LOW-MEDIUM: undocumented officially). Temporal/presence detection algorithms (MEDIUM: no HA-specific standard, pure algorithm design). Panel/WebSocket patterns (HIGH: well-documented, already proven in design).

---

## Context: What Already Exists (v1.0)

The following are complete and should NOT be re-researched:
- `DailyRoutineDetector` — hour-of-day frequency binning, confidence scoring
- `RecorderReader` — async DB access via Recorder executor thread
- `SmartHabitsCoordinator` — DataUpdateCoordinator, schedule, dismissed filter, stale automation detection
- `DismissedPatternsStore` — persistent storage via `helpers.storage.Store`
- WebSocket API — 3 commands: `get_patterns`, `dismiss_pattern`, `trigger_scan`
- Config flow — lookback period, analysis interval

This research covers ONLY what is needed for v1.1 new features.

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features users will assume exist once they see the pattern suggestion list. Missing these makes v1.1 feel incomplete or broken.

| Feature | Why Expected | Complexity | Dependencies on Existing |
|---------|--------------|------------|--------------------------|
| **Accept suggestion → create real HA automation** | Core promise of the product: "one-click automation." If accepting produces a dismissable notification or YAML to paste, the feature feels fake. Users will not install a second time. | HIGH | Needs: new `AutomationBuilder`, new `smart_habits/accept_pattern` WS command, new acceptance state in `DismissedPatternsStore` (or separate `AcceptedPatternsStore`). Coordinator must post-filter accepted patterns the same way it filters dismissed ones. |
| **Accepted patterns removed from suggestion list** | Once the user accepts a pattern, it must stop appearing as a "suggestion." Seeing it again is confusing and erodes trust. | LOW | Needs: acceptance persistence (IDs stored in `.storage/smart_habits`). Coordinator already post-filters dismissed patterns — same mechanism extended for accepted. |
| **Sidebar panel for pattern review** | A WebSocket API is not a UI. Users expect a visual interface, not DevTools. The panel is the only user-facing surface for v1.1. Without it the integration is invisible. | HIGH | Needs: `panel_custom.async_register_panel()` in `__init__.py`, `frontend` + `panel_custom` in `manifest.json` dependencies, a served JS web component, `hass.http.register_static_path` or `hass.http.async_register_static_paths`. Existing WS API is the data layer. |
| **Temporal sequence detection (Device A → Device B within N minutes)** | Advertised as a core v1.1 capability. Without it the milestone is not complete. | HIGH | Needs: new `TemporalSequenceDetector` class (pure Python, no external deps). Must run via `hass.async_add_executor_job` same as `DailyRoutineDetector`. Output must produce `DetectedPattern` or a new `SequencePattern` dataclass. RecorderReader already returns state history — same input format. |
| **Presence-based pattern detection (arrive → devices activate)** | Advertised as a core v1.1 capability. Users with `person.*` entities expect the system to detect arrival sequences. | HIGH | Needs: new `PresencePatternDetector` class. Requires `person.*` or `device_tracker.*` entity states from RecorderReader — existing reader already handles these entity domains (ACTIVE_STATES includes `"home"`). Must produce `DetectedPattern` compatible output. |
| **Customize suggestion before accepting** | Users will want to adjust the time offset, affected entities, or trigger before committing to an automation. Accepting without preview often leads to broken or wrong automations. Creates trust that the system is not acting without them. | HIGH | Needs: panel UI form pre-populated from pattern data. New WS command to "preview" or "customize and accept" with modifications. AutomationBuilder must accept overridden fields. |

### Differentiators (Competitive Advantage)

Features that create meaningful advantage over existing community tools (Danm72/automation-suggestions, ai_automation_suggester, TaraHome).

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Human-readable automation preview before accepting** | Show "Turns on kitchen lights every weekday at 07:05" — not raw YAML, not "pattern_type: daily_routine." Builds user confidence in the system. No competitor does this. | MEDIUM | Needs: `AutomationBuilder.to_description()` method producing natural language from pattern fields (entity_id, pattern_type, peak_hour, sequence participants). Pure Python string formatting — no external deps. |
| **Sequence detection with configurable window** | User can set "within 5 minutes" vs "within 15 minutes" as the correlation window for A → B detection. Allows tuning to household tempo. | LOW | Window parameter added to `TemporalSequenceDetector.__init__`. Exposed in OptionsFlow or as detector config. Low cost, high user control payoff. |
| **Presence-based patterns with multiple entities** | "When person arrives → kitchen lights on AND TV on within 3 minutes" — detecting compound arrival activations, not just one entity. Competitors do not do this. | HIGH | Requires joining arrival events with multiple downstream entity state changes within a window. Extension of presence detector. High complexity but high value for users with standard arrival routines. |
| **Pattern category labeling** | Display patterns grouped by type: "Morning Routines," "Arrival Sequences," "Evening Wind-Down." Users understand the pattern in domain language, not technical type names. | MEDIUM | Classification from `pattern_type` field: `daily_routine` → time-of-day binning, `temporal_sequence` → label based on trigger entity domain, `presence_based` → label based on presence entity. Panel-layer feature, no backend changes needed. |
| **Stale automation review in sidebar panel** | Already detected in v1.0 coordinator — just needs to be displayed in the new panel. No competitor surfaces unused automations proactively. | LOW | Stale automations already in `coordinator.data["stale_automations"]`. WebSocket API already returns them. Panel just needs a second tab or section. Zero backend cost — pure UI work. |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Auto-accept all high-confidence patterns** | Reduce friction to zero — "just handle it" | Creates automations without consent. Users lose trust the moment something unexpected fires. Smart home context: wrong automation = lights on at 3am, TV blasting at 6am. Not recoverable. | Always require one explicit accept click per suggestion. Make it one click — not zero clicks. |
| **YAML export / paste workflow** | Seems like less complexity; avoids the unstable internal API | Friction is unacceptable. Pasting YAML requires users to know where `automations.yaml` lives, how YAML syntax works, and how to reload. Defeats the core value proposition. Competitors like ai_automation_suggester already do this poorly. | Use the internal REST API (`POST /api/config/automation/config/<id>`). It is undocumented but community-verified and stable since HA 2024+. |
| **Lovelace card variant of the panel** | "I want to add it to my dashboard" | Duplicates the sidebar panel lifecycle and increases maintenance surface. Cards require separate registration, different component lifecycle, and potentially separate build pipeline. No additive UX value — the sidebar is dedicated space. | Sidebar panel only for v1.1. Defer card to v2+ if demand is confirmed. |
| **Real-time pattern update on every state change** | "Why do I have to click Scan?" | Running pattern analysis on every state change event would fire hundreds of times per minute on a busy instance. Pi 4 cannot sustain this. Patterns form over days — real-time is architecturally wrong. | Keep scheduled background analysis + on-demand scan button. Panel can show "last scanned: 2 hours ago" to manage expectations. |
| **Notification push when new patterns found** | "Tell me when there's something new" | HA's notify system requires per-platform setup. Patterns are discovered in batch jobs — timing doesn't match user context. Notification fatigue is real. | Persistent badge/count in the sidebar panel title. User checks when curious. Opt-in notify deferred to v2 if demand is confirmed. |
| **Direct `automations.yaml` file writes** | Seems direct and obvious since automations are YAML | Corrupts user config if they use `!include_dir_merge_list` or custom YAML structures. Race conditions with HA's own file management. Can brick automation config. | Use `POST /api/config/automation/config/<id>` exclusively. Never touch `automations.yaml` directly. |

---

## Feature Dependencies

```
[DailyRoutineDetector] (existing, v1.0)
    ├──produces──> [DetectedPattern dataclass] (existing)
    └──extends to──> [TemporalSequenceDetector] (new)
                         └──produces──> [SequencePattern or extended DetectedPattern] (new)

[RecorderReader] (existing, v1.0)
    └──feeds──> [PresencePatternDetector] (new)
                    └──requires──> [person.* / device_tracker.* states in Recorder]
                    └──produces──> [DetectedPattern with pattern_type="presence_based"] (new)

[SmartHabitsCoordinator] (existing, v1.0)
    └──must aggregate──> [DailyRoutineDetector + TemporalSequenceDetector + PresencePatternDetector]
    └──must filter──> [DismissedPatternsStore + AcceptedPatternsStore] (acceptance store: new)

[WebSocket API] (existing, v1.0 — 3 commands)
    └──must extend with──> [smart_habits/accept_pattern] (new)
    └──must extend with──> [smart_habits/accept_pattern_customized] (new, for customize flow)

[AutomationBuilder] (new)
    └──requires──> [accept_pattern WS command]
    └──requires──> [DetectedPattern / SequencePattern]
    └──calls──> [POST /api/config/automation/config/<id>] (HA internal REST, undocumented)
    └──produces──> [human-readable description] for preview UI

[Sidebar Panel JS] (new)
    └──requires──> [panel_custom.async_register_panel() in __init__.py]
    └──requires──> [frontend + panel_custom in manifest.json dependencies]
    └──requires──> [all WS commands: get_patterns, dismiss_pattern, trigger_scan, accept_pattern]
    └──reads──> [stale_automations from get_patterns response] (already in WS response)

[AcceptedPatternsStore] (new, or extend DismissedPatternsStore)
    └──requires──> [accept_pattern WS command]
    └──feeds──> [Coordinator post-filter] (same mechanism as dismissed filter)
```

### Dependency Notes

- **TemporalSequenceDetector requires same RecorderReader output format:** No changes needed to RecorderReader — it already returns `dict[entity_id -> list[State | dict]]`. Sequence detector needs to consume multiple entities in a single pass.
- **AutomationBuilder is the highest-risk dependency:** `POST /api/config/automation/config/<id>` is community-verified but officially undocumented. The payload format must be reverse-engineered from HA's own automation editor. This is Phase 4's primary research risk (flagged in PROJECT.md).
- **Panel depends on stable WebSocket API:** Build the panel AFTER the WebSocket API is extended with `accept_pattern`. The panel must not be built against a WS API that will change.
- **Acceptance state must filter patterns before they reach panel:** Same post-hoc filter pattern as dismissed. Coordinator must exclude accepted pattern IDs from `data["patterns"]`. Do not send "accepted" patterns to the panel — they belong in a separate "your automations" view if needed, not mixed with pending suggestions.
- **Presence detector conflicts with simple entity_id-based analysis:** Presence patterns are multi-entity joins (presence entity + N downstream entities). The existing `DailyRoutineDetector` works per-entity. Presence detector requires a different algorithm: group by arrival event, then correlate downstream changes within a window. Cannot reuse `DailyRoutineDetector._detect_entity()`.
- **Customize-before-accept depends on AutomationBuilder being complete:** The customization UI renders editable fields based on what AutomationBuilder accepts. Build AutomationBuilder first, then expose its input fields in the panel.

---

## MVP Definition

### Launch With (v1.1)

Complete the v1.1 milestone — core product loop closed.

- [ ] **TemporalSequenceDetector** — detects Device A → Device B patterns within configurable window; produces `DetectedPattern` with `pattern_type="temporal_sequence"`
- [ ] **PresencePatternDetector** — detects arrival + downstream activation patterns; produces `DetectedPattern` with `pattern_type="presence_based"`
- [ ] **AutomationBuilder** — converts `DetectedPattern` to a valid HA automation dict; creates real automation via `POST /api/config/automation/config/<id>`
- [ ] **`smart_habits/accept_pattern` WS command** — triggers AutomationBuilder, persists acceptance, refreshes coordinator
- [ ] **AcceptedPatternsStore** (or extend existing Store) — persists accepted pattern IDs so coordinator filters them on every scan
- [ ] **Human-readable preview** — `AutomationBuilder.to_description()` — shown in panel before accept; short natural language string
- [ ] **Customize before accept** — panel form lets user modify time/entities/window; WS command accepts overrides
- [ ] **Sidebar Panel JS** — LitElement web component; displays suggestions with confidence + evidence; dismiss/accept/customize actions; stale automation list; manual scan trigger; registered via `panel_custom.async_register_panel()`

### Add After Validation (v1.x)

Features to add once v1.1 core is shipped and users are actively using it.

- [ ] **Pattern category grouping in panel** — group by type ("Morning Routines," "Arrival Sequences"); display-layer only; add when suggestion volume grows
- [ ] **Notification opt-in for new patterns** — add when users report they want proactive alerts; HA notify service; opt-in only
- [ ] **Accepted automation quick view** — panel section showing automations created by this integration; add when users ask "what did I already accept?"

### Future Consideration (v2+)

Defer until v1.1 is shipped and product-market fit is confirmed.

- [ ] **Multi-entity routine clustering** ("morning routine" as one block) — high complexity; only worth building if users explicitly request it
- [ ] **Learn from dismissals (implicit training)** — pattern fingerprinting + blacklist weighting; needs meaningful dismiss volume to validate
- [ ] **State correlation patterns** (temperature → heater) — different data model needed; explicitly out of scope in PROJECT.md

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Accept → create real HA automation | HIGH | HIGH | P1 |
| Sidebar panel | HIGH | HIGH | P1 |
| Temporal sequence detection | HIGH | HIGH | P1 |
| Presence-based detection | HIGH | HIGH | P1 |
| Accepted patterns filtered from list | HIGH | LOW | P1 (fast follow on acceptance) |
| Human-readable automation preview | HIGH | LOW | P1 (AutomationBuilder method, small delta) |
| Customize before accept | MEDIUM | HIGH | P1 (in scope per PROJECT.md) |
| Stale automation display in panel | MEDIUM | LOW | P1 (data already available, UI only) |
| Sequence window configuration | MEDIUM | LOW | P2 |
| Pattern category labeling | MEDIUM | MEDIUM | P2 |
| Notification opt-in | LOW | MEDIUM | P3 |
| Multi-entity routine clustering | MEDIUM | HIGH | P3 |

**Priority key:**
- P1: Required for v1.1 milestone completion
- P2: Should have, low cost add-on to v1.1
- P3: Defer to v1.x / v2+

---

## Implementation Notes by Feature

### Temporal Sequence Detection

**Algorithm approach (MEDIUM confidence — standard pattern, HA-specific application):**

The standard approach for A → B co-occurrence detection:
1. Build event list: `[(timestamp, entity_id, state)] sorted by timestamp`
2. For each "trigger" entity state change to active state, open a time window of N minutes
3. Within that window, collect all other entity state changes to active
4. For each trigger→target pair, count occurrences across the lookback window
5. Confidence = co-occurrence count / trigger event count
6. Emit pattern if confidence >= min_confidence AND co-occurrence count >= min_events

**Key constraints:**
- Must be single-pass or near-linear; O(n²) nested loops will time out on Pi 4 with large datasets
- Window size matters: 5 minutes catches "turn on TV → dim lights," 15 minutes catches "arrive home → devices activate"
- Minimum sequence events threshold prevents spurious patterns from one-off coincidences (use same `MIN_EVENTS_THRESHOLD` as `DailyRoutineDetector`)
- Needs a new `SequencePattern` dataclass or extend `DetectedPattern` with `trigger_entity_id` and `target_entity_id` fields

**Complexity: HIGH** — algorithm is straightforward but must be carefully bounded for memory and CPU on Pi 4.

### Presence-Based Pattern Detection

**Algorithm approach (MEDIUM confidence):**

Presence detection is a variant of temporal sequence detection where the trigger is specifically a `person.*` or `device_tracker.*` entity changing to `"home"` state:
1. Extract arrival events: `person.*` or `device_tracker.*` → `"home"` state transitions
2. For each arrival event, open a window of N minutes
3. Collect downstream entity activations within window
4. Count per entity: how many arrivals were followed by this entity becoming active within the window
5. Confidence = activation_count / arrival_count
6. Emit `DetectedPattern` with `pattern_type="presence_based"`, where `entity_id` is the activated entity, and a new field (or evidence string) identifies the presence trigger

**Key constraints:**
- RecorderReader already handles `person.*` states (ACTIVE_STATES contains `"home"`)
- Must distinguish "already on when person arrived" from "turned on after arrival" — check if entity was already active at arrival time
- Default window: 10 minutes for presence-based patterns (longer than sequence detection) since arrival routines can be slower
- Needs access to both person entity history AND downstream entity history in the same analysis call

**Complexity: HIGH** — multi-entity join with temporal correlation; more complex than per-entity analysis.

### AutomationBuilder and Automation Creation

**Risk: MEDIUM-HIGH** — the `POST /api/config/automation/config/<id>` endpoint is community-verified but not officially documented. This is the highest-risk feature in v1.1.

**What the payload looks like (MEDIUM confidence — inferred from HA source + community reports):**
```python
{
    "id": "<generated_uuid>",
    "alias": "Smart Habits: kitchen light morning routine",
    "description": "Created by Smart Habits on 2026-02-23",
    "trigger": [
        {
            "platform": "time",
            "at": "07:05:00"
        }
    ],
    "condition": [],
    "action": [
        {
            "service": "homeassistant.turn_on",
            "target": {"entity_id": "light.kitchen"}
        }
    ],
    "mode": "single"
}
```

For temporal sequence pattern, trigger must use state-change platform:
```python
{
    "trigger": [
        {
            "platform": "state",
            "entity_id": "media_player.tv",
            "to": "on"
        }
    ]
}
```

For presence-based pattern:
```python
{
    "trigger": [
        {
            "platform": "state",
            "entity_id": "person.john",
            "to": "home"
        }
    ]
}
```

**The POST endpoint** (MEDIUM confidence — community-verified, flagged in PROJECT.md):
```python
# AutomationBuilder async method — runs in event loop (aiohttp, not executor)
async def async_create_automation(self, hass: HomeAssistant, automation_dict: dict) -> str:
    automation_id = str(uuid.uuid4())
    automation_dict["id"] = automation_id

    result = await hass.auth.async_create_access_token(hass.auth.async_get_users()[0])
    # OR use hass.http directly since we're inside HA

    async with aiohttp.ClientSession() as session:
        resp = await session.post(
            f"http://localhost:{hass.config.api.port}/api/config/automation/config/{automation_id}",
            json=automation_dict,
            headers={"Authorization": f"Bearer {hass.auth...}"}
        )
    return automation_id
```

**NOTE:** The exact auth token acquisition pattern inside a running integration needs investigation during Phase 4. The prior ARCHITECTURE.md notes this endpoint and flags it as a research risk. Using `hass.auth` directly inside the integration may be possible without HTTP — check if `automations.async_create_automation()` service or `EntityRegistry` provides a cleaner path.

### Sidebar Panel

**Registration approach (HIGH confidence — official HA docs confirmed in prior research):**

```python
# In async_setup_entry:
from homeassistant.components import panel_custom

await panel_custom.async_register_panel(
    hass,
    webcomponent_name="smart-habits-panel",
    frontend_url_path="smart-habits",
    sidebar_title="Smart Habits",
    sidebar_icon="mdi:brain",
    module_url="/smart_habits_static/smart-habits-panel.js",
    require_admin=False,
)
```

**Static file serving** — the JS file must be served. Options:
1. Register a static path: `hass.http.async_register_static_paths([StaticPathConfig(url_path="/smart_habits_static", path=PANEL_DIR, cache_headers=False)])`
2. Place in `www/` — but that's outside the integration directory, not HACS-compatible

Use option 1. `PANEL_DIR` = `pathlib.Path(__file__).parent / "panel"`.

**Panel JS must be a proper custom element:**
- Framework: plain JS (no build step) or LitElement (small, no external CDN)
- Must define `customElements.define("smart-habits-panel", SmartHabitsPanel)`
- HA passes `hass` object and `narrow` (mobile) as properties
- All backend calls via `this.hass.connection.sendMessagePromise({type: "smart_habits/get_patterns"})`

**Manifest.json must declare dependencies:**
```json
{
    "dependencies": ["frontend", "recorder"],
    "after_dependencies": ["panel_custom"]
}
```

Note: `panel_custom` should be in `after_dependencies` not `dependencies` in modern HA — verify against current HA source.

---

## Competitor Feature Analysis

| Feature | Danm72 (automation-suggestions) | ai_automation_suggester | TaraHome / Sherrin | Our v1.1 |
|---------|----------------------------------|--------------------------|-------------------|----------|
| One-click create automation | No (redirects to Settings) | No (generates YAML) | Yes (YAML auto-write) | Yes (REST API, real automation) |
| Temporal sequence detection | No | No | No | Yes |
| Presence-based detection | No | No | No | Yes |
| Customize before accept | No | No | No | Yes |
| Sidebar panel | Lovelace card only | No (notifications) | Not documented | Yes (dedicated sidebar) |
| Human-readable preview | No | No | Not documented | Yes |
| Stale automation detection | Yes | No | No | Yes (v1.0 carryover) |
| Local processing only | Yes | No (cloud AI) | Yes | Yes |

---

## Sources

- `.planning/research/ARCHITECTURE.md` — panel registration, WebSocket API patterns, AutomationBuilder design, data flows (HIGH confidence — confirmed in prior research)
- `.planning/research/FEATURES.md` (v1.0) — competitor analysis, table stakes / differentiators baseline (MEDIUM confidence)
- `.planning/research/PITFALLS.md` — automation creation risks, YAML write anti-pattern, blocking event loop (HIGH confidence)
- `PROJECT.md` — v1.1 requirements, tech stack constraints, Phase 4 risk flag for automation creation API (HIGH confidence — primary source)
- `custom_components/smart_habits/` — existing code confirming architecture, data model, WS API surface (HIGH confidence — verified)
- [HA Developer Docs: Creating Custom Panels](https://developers.home-assistant.io/docs/frontend/custom-ui/creating-custom-panels/) — HIGH confidence (official)
- [HA Developer Docs: WebSocket API](https://developers.home-assistant.io/docs/frontend/extending/websocket-api/) — HIGH confidence (official)
- [HA Community: REST API for automations](https://community.home-assistant.io/t/rest-api-docs-for-automations/119997) — MEDIUM confidence (community, undocumented endpoint)
- Temporal sequence detection algorithm — standard co-occurrence window algorithm, MEDIUM confidence (general algorithm, no HA-specific standard)

---

*Feature research for: Home Assistant Smart Habits integration — v1.1 milestone features*
*Researched: 2026-02-23*
