# Architecture Research

**Domain:** Home Assistant custom integration — ML pattern mining with frontend panel
**Researched:** 2026-02-23 (updated for v1.1 milestone)
**Confidence:** HIGH for Python integration patterns (verified in v1.0); MEDIUM for automation creation API (undocumented endpoint); MEDIUM for panel registration (official docs but no live verification)

---

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                          Home Assistant Runtime                               │
│                                                                               │
│  ┌──────────────────────────────────────────────────────────────────────────┐ │
│  │                       Frontend Layer (Browser)                            │ │
│  │                                                                            │ │
│  │  ┌────────────────────────────────────────────────────────────────────┐   │ │
│  │  │          Smart Habits Sidebar Panel (LitElement Web Component)      │   │ │
│  │  │  - Pattern cards: pending / accepted / dismissed tabs              │   │ │
│  │  │  - Confidence scores + evidence strings                            │   │ │
│  │  │  - Accept (with optional customize) / Dismiss actions              │   │ │
│  │  │  - Stale automation warnings                                       │   │ │
│  │  └────────────────────────────┬───────────────────────────────────────┘   │ │
│  └───────────────────────────────┼───────────────────────────────────────────┘ │
│                                  │ WebSocket (hass.connection.sendMessagePromise)
│  ┌───────────────────────────────┼───────────────────────────────────────────┐ │
│  │                    Python Integration Layer                                │ │
│  │                                                                            │ │
│  │  ┌──────────────┐  ┌──────────────────┐  ┌───────────────────────────┐   │ │
│  │  │  __init__.py │  │ websocket_api.py │  │     config_flow.py        │   │ │
│  │  │  (setup,     │  │ (5 commands:     │  │  (config + options flow:  │   │ │
│  │  │   teardown,  │  │  get_patterns,   │  │   lookback, interval,     │   │ │
│  │  │   panel reg) │  │  dismiss,        │  │   threshold)              │   │ │
│  │  │              │  │  trigger_scan,   │  └───────────────────────────┘   │ │
│  │  │              │  │  accept_pattern, │                                  │ │
│  │  │              │  │  get_accepted)   │                                  │ │
│  │  └──────┬───────┘  └────────┬─────────┘                                  │ │
│  │         │                   │                                             │ │
│  │  ┌──────▼───────────────────▼────────────────────────────────────────┐   │ │
│  │  │                   SmartHabitsCoordinator                           │   │ │
│  │  │  (DataUpdateCoordinator subclass — EXISTING, extended)             │   │ │
│  │  │  - Schedules periodic analysis runs                               │   │ │
│  │  │  - Runs all detectors, merges results                             │   │ │
│  │  │  - Filters dismissed patterns                                     │   │ │
│  │  │  - Detects stale automations                                      │   │ │
│  │  │  - NEW: tracks accepted patterns via AcceptedPatternsStore        │   │ │
│  │  └──────────────────────────┬─────────────────────────────────────────┘   │ │
│  │                              │ async_add_executor_job (generic executor)   │ │
│  │  ┌───────────────────────────▼─────────────────────────────────────────┐  │ │
│  │  │            Detector Layer (sync, CPU-bound, pure Python)             │  │ │
│  │  │                                                                      │  │ │
│  │  │  ┌──────────────────────┐  ┌──────────────────────────────────────┐ │  │ │
│  │  │  │ DailyRoutineDetector │  │ TemporalSequenceDetector (NEW)       │ │  │ │
│  │  │  │ (EXISTING)           │  │ - Sliding-window co-activation       │ │  │ │
│  │  │  │ hour-of-day binning  │  │ - Device A on → Device B within N s  │ │  │ │
│  │  │  │ confidence scoring   │  │ - Outputs TemporalPattern            │ │  │ │
│  │  │  └──────────────────────┘  └──────────────────────────────────────┘ │  │ │
│  │  │                                                                      │  │ │
│  │  │  ┌──────────────────────────────────────────────────────────────┐   │  │ │
│  │  │  │ PresencePatternDetector (NEW)                                 │   │  │ │
│  │  │  │ - person/device_tracker → other entity state changes         │   │  │ │
│  │  │  │ - Arrival/departure correlation within time window           │   │  │ │
│  │  │  │ - Outputs PresencePattern                                     │   │  │ │
│  │  │  └──────────────────────────────────────────────────────────────┘   │  │ │
│  │  └──────────────────────────────────────────────────────────────────────┘  │ │
│  │                              │                                             │ │
│  │  ┌───────────────────────────▼─────────────────────────────────────────┐  │ │
│  │  │                      RecorderReader (EXISTING)                       │  │ │
│  │  │  - get_significant_states via recorder executor                     │  │ │
│  │  │  - Domain-filtered entity selection                                 │  │ │
│  │  └──────────────────────────────────────────────────────────────────────┘  │ │
│  │                                                                             │ │
│  │  ┌──────────────────────────────────────────────────────────────────────┐  │ │
│  │  │                    AutomationCreator (NEW)                            │  │ │
│  │  │  - Translates DetectedPattern → HA automation dict                  │  │ │
│  │  │  - POST /api/config/automation/config/<uuid> via hass.auth session  │  │ │
│  │  │  - Returns created entity_id for tracking                           │  │ │
│  │  └──────────────────────────────────────────────────────────────────────┘  │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │                           Storage Layer                                      │ │
│  │  ┌───────────────────────┐  ┌──────────────────┐  ┌──────────────────────┐  │ │
│  │  │ Recorder DB           │  │ HA Automation    │  │ .storage/            │  │ │
│  │  │ (SQLite/MariaDB)      │  │ Registry         │  │ smart_habits.*       │  │ │
│  │  │ states, states_meta   │  │ (existing        │  │ .dismissed (exists)  │  │ │
│  │  │ (read-only via API)   │  │  automations)    │  │ .accepted  (NEW)     │  │ │
│  │  └───────────────────────┘  └──────────────────┘  └──────────────────────┘  │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Status | Responsibility |
|-----------|--------|----------------|
| `__init__.py` | MODIFY | Add panel registration in `async_setup_entry`; add `frontend`/`panel_custom` dependencies |
| `manifest.json` | MODIFY | Add `frontend`, `panel_custom` to `after_dependencies`; bump version |
| `coordinator.py` | MODIFY | Load `AcceptedPatternsStore` in `_async_setup`; filter accepted patterns; add detectors |
| `pattern_detector.py` | RENAME/REFACTOR | Rename to `detectors/daily_routine.py`; extract base class |
| `detectors/temporal.py` | NEW | `TemporalSequenceDetector` — sliding-window pair detection |
| `detectors/presence.py` | NEW | `PresencePatternDetector` — arrival/departure correlation |
| `automation_creator.py` | NEW | Pattern → HA automation dict; REST POST to create; entity validation |
| `websocket_api.py` | MODIFY | Add `accept_pattern` and `get_accepted` commands |
| `storage.py` | MODIFY | Add `AcceptedPatternsStore` (new storage key `smart_habits.accepted`) |
| `models.py` | MODIFY | Add `TemporalPattern`, `PresencePattern`, `AcceptedPattern` dataclasses |
| `panel/smart-habits-panel.js` | NEW | LitElement web component; pattern cards; accept/dismiss/customize actions |
| `DismissedPatternsStore` | UNCHANGED | Existing dismissed pattern persistence |
| `RecorderReader` | UNCHANGED | Recorder DB query layer |

---

## Recommended Project Structure

The v1.0 flat structure works for the existing code. The new detectors justify a `detectors/` subpackage to avoid a sprawling flat module list.

```
custom_components/smart_habits/
├── __init__.py                  # MODIFY: add panel registration
├── manifest.json                # MODIFY: add frontend, panel_custom deps
├── const.py                     # MODIFY: add new pattern_type constants
├── config_flow.py               # UNCHANGED
├── coordinator.py               # MODIFY: multi-detector, accepted store
├── models.py                    # MODIFY: add TemporalPattern, PresencePattern, AcceptedPattern
├── recorder_reader.py           # UNCHANGED
├── storage.py                   # MODIFY: add AcceptedPatternsStore
├── websocket_api.py             # MODIFY: add accept_pattern, get_accepted commands
├── automation_creator.py        # NEW
├── strings.json                 # UNCHANGED
├── detectors/
│   ├── __init__.py              # NEW: exports all detector classes
│   ├── daily_routine.py         # MOVE from pattern_detector.py (import alias in old path)
│   ├── temporal.py              # NEW: TemporalSequenceDetector
│   └── presence.py              # NEW: PresencePatternDetector
└── panel/
    └── smart-habits-panel.js    # NEW: LitElement web component

tests/
├── conftest.py                  # UNCHANGED
├── test_daily_routine_detector.py  # UNCHANGED
├── test_integration.py             # MODIFY: add panel registration test
├── test_recorder_reader.py         # UNCHANGED
├── test_stale_automation.py        # UNCHANGED
├── test_storage.py                 # MODIFY: add AcceptedPatternsStore tests
├── test_websocket.py               # MODIFY: add accept_pattern, get_accepted tests
├── test_temporal_detector.py       # NEW
├── test_presence_detector.py       # NEW
└── test_automation_creator.py      # NEW
```

### Structure Rationale

- **`detectors/`:** Three detectors sharing the same call contract (`detect(states, lookback_days) -> list[Pattern]`) belong together. Keeps `coordinator.py` imports clean and each detector independently testable.
- **`automation_creator.py`:** The REST API interaction is isolated here. If HA changes the endpoint, only this file needs updating.
- **`panel/`:** Frontend assets co-located with Python integration ensures HACS installs the JS without a separate step. HA serves the file via `panel_custom`.
- **Import alias:** `pattern_detector.py` can re-export from `detectors/daily_routine.py` to avoid breaking the existing test import path — avoids a disruptive rename across 46 tests.

---

## Architectural Patterns

### Pattern 1: Unified Detector Interface (New)

**What:** All three detectors share the same synchronous call contract. The coordinator calls them all in one executor job via a list, merging results.

**When to use:** `_async_update_data` in the coordinator. Pass the same `states` dict to all detectors; each inspects only the entity types it cares about.

**Trade-offs:** One executor job for all detectors (efficient — one thread context switch). Each detector must be stateless — reads `states` dict, returns `list[Pattern]`, no side effects.

**Example:**
```python
# coordinator.py
from .detectors import DailyRoutineDetector, TemporalSequenceDetector, PresencePatternDetector

def _run_all_detectors(states: dict, lookback_days: int, min_confidence: float) -> list:
    """Synchronous — called via hass.async_add_executor_job."""
    detectors = [
        DailyRoutineDetector(min_confidence=min_confidence),
        TemporalSequenceDetector(min_confidence=min_confidence),
        PresencePatternDetector(min_confidence=min_confidence),
    ]
    results = []
    for detector in detectors:
        results.extend(detector.detect(states, lookback_days))
    return sorted(results, key=lambda p: p.confidence, reverse=True)

# In _async_update_data:
patterns = await self.hass.async_add_executor_job(
    _run_all_detectors, states, self.lookback_days, self.min_confidence
)
```

### Pattern 2: Temporal Sequence Detection Algorithm

**What:** Sliding-window co-activation detection. For each entity pair (A, B), look for events where A transitions to active, followed by B transitioning to active within a configurable window (default: 5 minutes). Count such co-activations across distinct days; compute confidence as co_activation_days / total_days.

**When to use:** `TemporalSequenceDetector.detect()`. Only meaningful for binary-ish entities (lights, switches). Skip continuous sensors.

**Trade-offs:** O(n * m) for n A-events and m B-events per entity pair per day. Pair explosion risk: 100 entities = ~5000 pairs. Mitigation: only consider entity pairs that have both appeared in ACTIVE_STATES on the same calendar day before testing the within-window condition. This pre-filter dramatically reduces the candidate pair set.

**Example:**
```python
# detectors/temporal.py (algorithm sketch)
from collections import defaultdict

SEQUENCE_WINDOW_SECONDS = 300  # 5 minutes, configurable

def detect(self, states: dict, lookback_days: int) -> list:
    # Build per-entity activation event lists: {entity_id: [(date, ts_float), ...]}
    activations: dict[str, list[tuple]] = defaultdict(list)
    for entity_id, state_list in states.items():
        for record in state_list:
            ts, state_val = self._extract_record(record)
            if ts and state_val in ACTIVE_STATES:
                activations[entity_id].append((ts.date(), ts.timestamp()))

    # For each ordered pair (A, B) where A != B:
    #   Find days where A activation is followed by B activation within window
    entity_ids = list(activations.keys())
    patterns = []
    for i, entity_a in enumerate(entity_ids):
        for entity_b in entity_ids[i+1:]:
            # Count co-activation days for A → B and B → A independently
            patterns.extend(self._detect_pair(
                entity_a, activations[entity_a],
                entity_b, activations[entity_b],
                lookback_days,
            ))
    return patterns
```

### Pattern 3: Presence-Based Pattern Detection

**What:** Detect correlations between person/device_tracker entity arriving (transitioning to `home`) and other entities activating within a time window.

**When to use:** `PresencePatternDetector.detect()`. Only triggered by entities whose domain is `person` or `device_tracker` and whose state transitions to `home`.

**Trade-offs:** Presence events are sparse (typically 1-4 arrivals/day). Low total event count means low denominator — need at least MIN_EVENTS_THRESHOLD arrival events to form a pattern.

**Example:**
```python
# detectors/presence.py (algorithm sketch)
ARRIVAL_STATE = "home"
PRESENCE_WINDOW_SECONDS = 300  # 5 minutes after arrival

def detect(self, states: dict, lookback_days: int) -> list:
    # Step 1: Extract arrival events for person/device_tracker entities
    arrivals: list[tuple] = []  # (date, ts_float, person_entity_id)
    for entity_id, state_list in states.items():
        if entity_id.split(".")[0] not in ("person", "device_tracker"):
            continue
        prev_state = None
        for record in state_list:
            ts, state_val = self._extract_record(record)
            if ts and prev_state != ARRIVAL_STATE and state_val == ARRIVAL_STATE:
                arrivals.append((ts.date(), ts.timestamp(), entity_id))
            prev_state = state_val

    if len(arrivals) < MIN_EVENTS_THRESHOLD:
        return []

    # Step 2: For each non-presence entity, count activations within window of any arrival
    patterns = []
    for entity_id, state_list in states.items():
        if entity_id.split(".")[0] in ("person", "device_tracker"):
            continue
        patterns.extend(self._detect_entity_on_arrival(
            entity_id, state_list, arrivals, lookback_days
        ))
    return patterns
```

### Pattern 4: Automation Creation via HA Internal REST API

**What:** Convert a `DetectedPattern` to an HA automation configuration dict and create it via `POST /api/config/automation/config/<uuid>`. Use `hass.auth` for the Bearer token — specifically the trusted internal token available during integration setup.

**When to use:** `ws_accept_pattern` WebSocket handler, after optional user customization of trigger time/entities.

**Trade-offs:** The `/api/config/automation/config/<id>` endpoint is NOT in HA's public API docs. It is the endpoint the HA frontend's automation editor uses internally and has been stable across HA versions since 2021, but could change without notice. MEDIUM confidence — monitor across HA releases.

**Critical detail:** The integration cannot use a raw `aiohttp.ClientSession` for this call because it needs HA's auth token. Use `hass.auth.async_get_or_create_access_token()` or, better, use the HA-provided `async_get_clientsession(hass)` with a long-lived access token created via `hass.auth.async_create_long_lived_access_token()`. An even cleaner approach is to use HA's internal `homeassistant.components.automation` service calls if they expose a create action.

**Example:**
```python
# automation_creator.py
import uuid
import aiohttp
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .models import DetectedPattern

AUTOMATION_CONFIG_URL = "/api/config/automation/config/{automation_id}"

async def async_create_automation(
    hass,
    pattern: DetectedPattern,
    access_token: str,
) -> str | None:
    """Create a HA automation from a detected pattern. Returns new automation entity_id or None."""
    automation_id = str(uuid.uuid4())
    automation_dict = _build_automation_dict(pattern, automation_id)

    session = async_get_clientsession(hass)
    url = f"http://localhost:{hass.config.api.port}{AUTOMATION_CONFIG_URL.format(automation_id=automation_id)}"

    async with session.post(
        url,
        json=automation_dict,
        headers={"Authorization": f"Bearer {access_token}"},
    ) as resp:
        if resp.status in (200, 201):
            return f"automation.{automation_dict['alias'].lower().replace(' ', '_')}"
        return None


def _build_automation_dict(pattern: DetectedPattern, automation_id: str) -> dict:
    """Convert DetectedPattern to HA automation config dict."""
    if pattern.pattern_type == "daily_routine":
        return {
            "id": automation_id,
            "alias": f"Smart Habits: {pattern.entity_id} at {pattern.peak_hour:02d}:00",
            "description": f"Auto-generated from pattern: {pattern.evidence}",
            "trigger": [{
                "platform": "time",
                "at": f"{pattern.peak_hour:02d}:00:00",
            }],
            "condition": [],
            "action": [{
                "service": "homeassistant.turn_on",
                "target": {"entity_id": pattern.entity_id},
            }],
            "mode": "single",
        }
    # temporal_sequence and presence_based patterns use different trigger shapes
    # (see models.py for TemporalPattern and PresencePattern fields)
    raise NotImplementedError(f"Automation builder not implemented for {pattern.pattern_type}")
```

### Pattern 5: LitElement Sidebar Panel Registration

**What:** Register a custom panel programmatically in `async_setup_entry` via `homeassistant.components.panel_custom.async_register_panel`. The panel JS file is served from `custom_components/smart_habits/panel/` via HA's static file serving.

**When to use:** `async_setup_entry` in `__init__.py` after coordinator is initialized.

**Trade-offs:** Requires adding `frontend` and `panel_custom` to `after_dependencies` in `manifest.json`. The panel JS must be a proper custom element — a bare `customElements.define(...)` call registering a `LitElement` class. Panel registration must be idempotent (guard against double-registration on config reload).

**Example:**
```python
# __init__.py
from homeassistant.components import panel_custom
from homeassistant.components.frontend import async_remove_panel

PANEL_URL = "smart-habits"
PANEL_COMPONENT_NAME = "smart-habits-panel"

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # ... coordinator setup, websocket registration (existing) ...

    # Register panel (idempotent guard)
    hass.http.register_static_path(
        "/smart_habits_static",
        hass.config.path("custom_components/smart_habits/panel"),
        cache_headers=False,
    )
    await panel_custom.async_register_panel(
        hass,
        webcomponent_name=PANEL_COMPONENT_NAME,
        frontend_url_path=PANEL_URL,
        sidebar_title="Smart Habits",
        sidebar_icon="mdi:brain",
        module_url=f"/smart_habits_static/{PANEL_COMPONENT_NAME}.js",
        require_admin=False,
        config_panel_domain=DOMAIN,
    )
    entry.async_on_unload(lambda: async_remove_panel(hass, PANEL_URL))
    return True
```

**Panel JS minimum structure:**
```javascript
// panel/smart-habits-panel.js
import { LitElement, html, css } from "https://unpkg.com/lit@2/index.js?module";
// IMPORTANT: In production, bundle LitElement — do not load from CDN in user installs.
// Use a self-contained bundle (rollup/esbuild output) placed in panel/ directory.

class SmartHabitsPanel extends LitElement {
    static get properties() {
        return { hass: { type: Object }, narrow: { type: Boolean } };
    }

    async connectedCallback() {
        super.connectedCallback();
        const result = await this.hass.connection.sendMessagePromise({
            type: "smart_habits/get_patterns",
        });
        this._patterns = result.patterns;
        this.requestUpdate();
    }

    render() {
        return html`<div>${JSON.stringify(this._patterns)}</div>`;
    }
}
customElements.define("smart-habits-panel", SmartHabitsPanel);
```

---

## Data Flow

### Analysis Trigger Flow

```
HA Startup / Schedule Timer / ws trigger_scan command
    ↓
SmartHabitsCoordinator._async_update_data() [async, event loop]
    ↓
RecorderReader.async_get_states(entity_ids, lookback_days)
    → get_instance(hass).async_add_executor_job(get_significant_states, ...)
    ↓ returns dict[entity_id → list[State|dict]]
hass.async_add_executor_job(_run_all_detectors, states, lookback_days, min_confidence)
    → DailyRoutineDetector.detect(states, lookback_days) → list[DetectedPattern]
    → TemporalSequenceDetector.detect(states, lookback_days) → list[TemporalPattern]
    → PresencePatternDetector.detect(states, lookback_days) → list[PresencePattern]
    ↓ returns merged list, sorted by confidence
Filter dismissed (existing DismissedPatternsStore)
Filter accepted (new AcceptedPatternsStore) [do NOT re-suggest accepted patterns]
_async_detect_stale_automations() [hass.states.async_all("automation")]
    ↓
coordinator.data = {"patterns": [...], "stale_automations": [...], "accepted_patterns": [...]}
    ↓
All WebSocket subscribers notified; panel re-renders
```

### User Accepts Pattern Flow

```
User clicks "Accept" in Panel JS
    ↓
hass.connection.sendMessagePromise({
    type: "smart_habits/accept_pattern",
    entity_id: "...", pattern_type: "...", peak_hour: 7,
    customizations: { trigger_time: "07:15", action: "turn_on" }   # optional
})
    ↓ WebSocket message → ws_accept_pattern() handler [async]
    ↓
AutomationCreator.async_create_automation(hass, pattern, access_token)
    → Builds automation dict from pattern + customizations
    → POST /api/config/automation/config/<uuid>
    → Returns new automation entity_id (e.g. "automation.smart_habits_light_bedroom_0700")
    ↓ on success:
AcceptedPatternsStore.async_accept(entity_id, pattern_type, peak_hour, automation_entity_id)
    → persists to .storage/smart_habits.accepted
    ↓
coordinator.async_refresh()
    → accepted pattern removed from suggestions list
    ↓
connection.send_result({
    "accepted": True,
    "automation_entity_id": "automation.smart_habits_light_bedroom_0700"
})
    ↓
Panel moves pattern card to "Accepted" tab
```

### User Customizes Before Accepting

```
User clicks "Customize" in Panel
    ↓
Panel shows inline edit form (time picker, entity selector, action selector)
User edits → clicks "Save & Accept"
    ↓
hass.connection.sendMessagePromise({
    type: "smart_habits/accept_pattern",
    ..., customizations: { trigger_time: "07:30" }  # overrides pattern defaults
})
    ↓ same accept flow above, customizations merged into automation dict
```

### User Dismisses Pattern Flow

```
User clicks "Dismiss" in Panel
    ↓
hass.connection.sendMessagePromise({type: "smart_habits/dismiss_pattern", ...})
    ↓ EXISTING ws_dismiss_pattern() handler — no changes needed
DismissedPatternsStore.async_dismiss(...)
coordinator.async_refresh()
    ↓
Panel removes pattern card from pending view
```

### State Management

```
SmartHabitsCoordinator.data (in-memory, refreshed on each analysis run)
├── "patterns": list[DetectedPattern | TemporalPattern | PresencePattern]
│    (filtered: dismissed and accepted removed)
├── "stale_automations": list[StaleAutomation]
└── "accepted_patterns": list[AcceptedPattern]   # NEW: for "Accepted" tab display

.storage/smart_habits.dismissed  (EXISTING)
    Set[tuple(entity_id, pattern_type, peak_hour)]

.storage/smart_habits.accepted   (NEW)
    List[{"entity_id": ..., "pattern_type": ..., "peak_hour": ...,
           "automation_entity_id": ..., "accepted_at": ISO8601}]
```

---

## New Components Detail

### TemporalPattern Model (new `models.py` dataclass)

```python
@dataclass
class TemporalPattern:
    trigger_entity_id: str   # Device A (the one that fires first)
    response_entity_id: str  # Device B (follows within window)
    pattern_type: str        # "temporal_sequence"
    window_seconds: int      # Observed typical gap
    confidence: float
    evidence: str            # "A turned on, then B turned on within 5m on 8 of 14 days"
    active_days: int
    total_days: int
```

### PresencePattern Model (new `models.py` dataclass)

```python
@dataclass
class PresencePattern:
    presence_entity_id: str  # person.alice or device_tracker.phone
    response_entity_id: str  # light.hallway, etc.
    pattern_type: str        # "presence_based"
    window_seconds: int      # Observed activation gap after arrival
    confidence: float
    evidence: str            # "light.hallway turned on within 5m of arrival on 9 of 12 arrivals"
    active_days: int
    total_days: int
```

### AcceptedPattern Model (new `models.py` dataclass)

```python
@dataclass
class AcceptedPattern:
    entity_id: str
    pattern_type: str
    peak_hour: int           # For daily_routine; -1 for non-time-based patterns
    automation_entity_id: str
    accepted_at: str         # ISO 8601
```

### AcceptedPatternsStore (`storage.py` addition)

Same structure as `DismissedPatternsStore` but stores richer dict (includes `automation_entity_id` for the "Accepted" tab to link to the automation).

Storage key: `smart_habits.accepted` (namespaced to avoid collision with existing `smart_habits.dismissed`).

---

## Integration Points

### HA Internal APIs

| Service | Integration Pattern | Confidence | Notes |
|---------|---------------------|------------|-------|
| Recorder DB | `get_instance(hass).async_add_executor_job(get_significant_states, ...)` | HIGH | EXISTING — proven in v1.0 |
| WebSocket API | `@websocket_command` + `async_register_command` | HIGH | EXISTING — 3 commands; adding 2 more |
| helpers.storage.Store | `Store(hass, version, key)` | HIGH | EXISTING for dismissed; new key for accepted |
| panel_custom | `panel_custom.async_register_panel(...)` | MEDIUM | NEW — documented official API; not yet implemented |
| HA Automation REST | `POST /api/config/automation/config/<id>` | MEDIUM-LOW | NEW — undocumented endpoint; stable in practice; requires live testing |
| hass.http.register_static_path | Static file serving for panel JS | MEDIUM | NEW — official but check for deprecation in current HA version |

### New WebSocket Commands

| Command | Direction | Handler | Description |
|---------|-----------|---------|-------------|
| `smart_habits/accept_pattern` | Panel → Backend | `ws_accept_pattern` | Create HA automation from pattern; persist to AcceptedPatternsStore |
| `smart_habits/get_accepted` | Panel → Backend | `ws_get_accepted` | Return list of accepted patterns with automation links |

### Internal Module Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Coordinator ↔ Detectors | Direct Python call in executor job | Single function `_run_all_detectors(states, lookback_days, min_confidence)` — stateless, no shared mutable state |
| `ws_accept_pattern` ↔ AutomationCreator | Direct async call: `await automation_creator.async_create_automation(hass, pattern, token)` | AutomationCreator is a standalone async function, not a class |
| `ws_accept_pattern` ↔ AcceptedPatternsStore | Direct: `await coordinator.accepted_store.async_accept(...)` | Coordinator holds the store reference; handlers access via `entries[0].runtime_data` |
| Panel JS ↔ All WS handlers | WebSocket messages typed by `type` field | HA auth is enforced automatically for all WS connections |
| AutomationCreator ↔ HA REST | `aiohttp` via `async_get_clientsession(hass)` with long-lived or access token | Async HTTP — runs on event loop, NOT in executor |

---

## Build Order (Phase Dependencies)

Build bottom-up: each layer is independently testable before wiring the next.

```
Phase 1: TemporalSequenceDetector
  └── Pure Python, no HA dependencies
  └── Input: same dict[entity_id → list[State|dict]] as DailyRoutineDetector
  └── Output: list[TemporalPattern]
  └── Test: unit tests with static state history fixtures (same pattern as test_daily_routine_detector.py)
  └── No coordinator changes yet

Phase 2: PresencePatternDetector
  └── Same contract as Phase 1
  └── Depends on: person/device_tracker state records (already in RecorderReader domain filter)
  └── Test: unit tests — mock arrivals + subsequent activations

Phase 3: Coordinator Multi-Detector Wiring
  └── Depends on: Phase 1 + 2 (detectors exist)
  └── Changes: coordinator._async_update_data runs all detectors via single executor job
  └── Changes: coordinator._async_setup loads AcceptedPatternsStore
  └── Changes: coordinator.data gains "accepted_patterns" key
  └── Test: integration test — scan returns mixed pattern types; accepted patterns filtered

Phase 4: AutomationCreator + accept_pattern WS command
  └── Depends on: Phase 3 (coordinator has accepted store)
  └── Files: automation_creator.py (new), websocket_api.py (add 2 commands)
  └── Risk: REST endpoint needs live HA testing — verify before building panel
  └── Test: unit test builder dict generation; integration test with mocked HTTP call

Phase 5: Sidebar Panel (LitElement)
  └── Depends on: Phase 4 (all WS commands stable)
  └── Files: panel/smart-habits-panel.js (new), __init__.py + manifest.json (modified)
  └── Test: panel loads, connects WS, renders patterns, accept/dismiss actions work
```

**Why this order:**
- Detectors (phases 1-2) are pure Python and have no HA lifecycle coupling — fastest to build and test.
- Coordinator wiring (phase 3) is needed before any WS command can return mixed pattern types.
- AutomationCreator (phase 4) is isolated from the panel — the REST endpoint risk must be resolved before building any UI that depends on it. Verify accept flow with DevTools WS debugger before writing panel JS.
- Panel (phase 5) is last because it depends on all backend commands being stable. Frontend changes are the slowest to test and iterate on.

---

## Anti-Patterns

### Anti-Pattern 1: Adding All Detectors to One File

**What people do:** Extend `pattern_detector.py` with all three detectors in one 600-line file.

**Why it's wrong:** Makes each detector harder to test in isolation. A failure in temporal detection breaks the entire module import. Merge conflicts when working on different detectors.

**Do this instead:** One file per detector in `detectors/`. Each detector is a class with `detect(states, lookback_days) -> list` — independently importable and testable.

### Anti-Pattern 2: Running Each Detector in a Separate Executor Job

**What people do:** Call `async_add_executor_job` three times — once per detector — and `asyncio.gather` the results.

**Why it's wrong:** Each executor job acquires the GIL independently. Three jobs for pure-Python CPU work provides no parallelism (GIL). Adds three thread switches and three result futures for no gain.

**Do this instead:** One executor job that calls all detectors sequentially. `_run_all_detectors(states, lookback_days, min_confidence)` — single function, single thread switch, merged output list.

### Anti-Pattern 3: Using hass.auth.async_create_long_lived_access_token in the WS Handler

**What people do:** Generate a new long-lived access token every time a pattern is accepted, to authenticate the automation creation REST call.

**Why it's wrong:** Long-lived tokens persist in HA's auth store indefinitely. Creating one per accept action leaks tokens and pollutes the user's auth list.

**Do this instead:** Use the short-lived connection token from the WebSocket session context (`connection.refresh_token_id`) or use HA's internal service call mechanism if available. Alternatively, create ONE long-lived token at integration setup time and store it (not ideal). The cleanest path: call HA's `automation` integration service directly via `hass.services.async_call("automation", "reload")` after writing config — investigate whether `homeassistant.components.automation` exposes a Python-callable create path.

### Anti-Pattern 4: Inlining Automation Building Logic in the WS Handler

**What people do:** Build the automation dict inline inside `ws_accept_pattern`.

**Why it's wrong:** The endpoint is the riskiest part of the system. Isolating it in `AutomationCreator` means it can be tested without WebSocket scaffolding and updated without touching the WS layer.

**Do this instead:** `AutomationCreator` is a separate module with pure functions: `build_automation_dict(pattern) -> dict` (synchronous, testable without HA) and `async_create_automation(hass, pattern) -> str | None` (async, wraps the HTTP call).

### Anti-Pattern 5: Loading LitElement from CDN in the Panel JS

**What people do:** `import { LitElement } from "https://unpkg.com/lit@2/index.js?module"` in the panel JS file.

**Why it's wrong:** CDN imports break on HA instances without internet access (common). Violates HA's offline-first design. Breaks on custom DNS configurations.

**Do this instead:** Bundle LitElement into the panel JS using rollup or esbuild. The resulting `smart-habits-panel.js` is a single self-contained file. HA ships LitElement itself — check whether `haVersion >= 2023.x` exposes LitElement via HA's own module system (`/frontend_latest/...`) before adding a local copy.

---

## Scaling Considerations

This is a single-instance HA integration. Scale here means performance across different HA instance sizes.

| Scale | Consideration |
|-------|---------------|
| Small HA (< 20 entities, 7 day lookback) | All three detectors finish in < 1 second. No bottleneck. |
| Medium HA (20-100 entities, 30 day lookback) | Temporal detector has O(n²) pair complexity: 100 entities = ~5000 pairs. Still fast with pre-filter (only pairs co-active on same calendar day). 2-10 seconds on Pi 4. |
| Large HA (100+ entities, 90 day lookback) | Temporal detector may need pair count cap. Presence detector is cheap (sparse events). Add entity pair cap (e.g., top 50 by co-occurrence frequency). |

### Scaling Priorities

1. **First bottleneck:** Temporal detector pair explosion. The pre-filter (only test pairs co-active on same day) cuts 80-90% of pairs. If still slow, add a hard cap on max entity pairs evaluated.
2. **Second bottleneck:** Memory for state history. `get_significant_states` with `minimal_response=True, no_attributes=True` is already optimized. If large instances hit memory pressure, chunk entity queries (e.g., 50 entities at a time) and merge results.

---

## Sources

- [HA Developer Docs: Extending the WebSocket API](https://developers.home-assistant.io/docs/frontend/extending/websocket-api/) — HIGH confidence
- [HA Developer Docs: Creating Custom Panels](https://developers.home-assistant.io/docs/frontend/custom-ui/creating-custom-panels/) — HIGH confidence
- [HA Developer Docs: panel_custom integration](https://www.home-assistant.io/integrations/panel_custom/) — HIGH confidence
- [HA Developer Docs: Fetching data / DataUpdateCoordinator](https://developers.home-assistant.io/docs/integration_fetching_data/) — HIGH confidence
- [HA Community: Automation REST API (undocumented)](https://community.home-assistant.io/t/rest-api-docs-for-automations/119997) — MEDIUM confidence (endpoint confirmed by community but not officially documented)
- [HA Community: Adding sidebar panel to integration](https://community.home-assistant.io/t/how-to-add-a-sidebar-panel-to-a-home-assistant-integration/981585) — MEDIUM confidence
- [HA helpers/storage.py source](https://github.com/home-assistant/core/blob/dev/homeassistant/helpers/storage.py) — HIGH confidence (existing use verified in v1.0)
- v1.0 phase research (`01-RESEARCH.md`, `3-RESEARCH.md`) — HIGH confidence (patterns verified and implemented)

---

*Architecture research for: Home Assistant custom integration — v1.1 automation creation, sidebar panel, temporal + presence detectors*
*Researched: 2026-02-23*
