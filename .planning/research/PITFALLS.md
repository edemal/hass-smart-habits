# Pitfalls Research

**Domain:** Home Assistant custom integration — automation creation, LitElement sidebar panel, temporal sequence detection, presence-based pattern detection
**Researched:** 2026-02-23
**Confidence:** MEDIUM-HIGH (HA internal automation API: MEDIUM — officially undocumented; LitElement panel mechanics: HIGH from developer docs and integration blueprint patterns; detector algorithm pitfalls: HIGH from codebase analysis; HA WebSocket protocol: HIGH)

---

## Critical Pitfalls

### Pitfall 1: Automation Creation API Returns 200 But Creates Nothing

**What goes wrong:**
`POST /api/config/automation/config/<id>` returns HTTP 200 with `{"result": "ok"}` even when the automation ID is malformed, the payload violates the schema, or the automation config file is in an inconsistent state. The integration logs success, the user sees "automation created," but nothing appears in Settings > Automations. No error is raised.

**Why it happens:**
The endpoint is an internal HA API, not designed for external callers. Its success response reflects that the write to the config store was accepted, not that the automation is valid and loaded. HA validates and compiles automations lazily on the next `automation.reload` — if validation fails at that stage, the automation is silently dropped. Additionally, if `automations.yaml` was manually edited outside HA's editor, the config file may be in a state that rejects new entries without surfacing a clear error.

**How to avoid:**
After calling the creation endpoint, verify the automation actually exists by checking `hass.states.async_get(f"automation.{slug}")` is not None, or by subscribing to `EVENT_STATE_CHANGED` filtered to the new automation entity. If the state does not appear within a short timeout (2-3 seconds post-reload), surface an error to the user. Always call `hass.services.async_call("automation", "reload")` after creation and wait for it to complete before confirming success. Test the roundtrip (create → reload → verify state exists → restart HA → verify persists) as an integration test, not just a unit test.

**Warning signs:**
- Integration returns success from the HTTP call but does not verify the resulting HA state
- No `automation.reload` call after creation
- Tests mock the HTTP call and assert `status == 200` without verifying the created automation entity
- Users report "automation created" but nothing appears in the UI

**Phase to address:**
Phase 4 (Automation Creation) — the entire acceptance flow must include a verification step. Build the verify-after-create pattern on day one, not as a follow-up.

---

### Pitfall 2: Automation ID Collision With Existing Automations

**What goes wrong:**
The `POST /api/config/automation/config/<id>` endpoint uses the `<id>` path segment as the automation's unique identifier in the config store. If the integration generates an ID that collides with an existing automation (e.g. one the user created manually with the same name), the endpoint silently overwrites the existing automation. The user's hand-crafted automation is destroyed with no warning.

**Why it happens:**
Developers use deterministic ID generation from the pattern (e.g. `smart_habits_light_kitchen_0700`) without checking whether that ID already exists in the automation registry. The overwrite behavior is not documented in the endpoint's sparse documentation.

**How to avoid:**
Before calling the creation endpoint, check for ID collision:
```python
existing = hass.states.async_get(f"automation.smart_habits_{slug}")
if existing is not None:
    # Don't overwrite — return the existing automation or error
    return existing.entity_id
```
Alternatively, prefix all Smart Habits automation IDs with a unique namespace (e.g. `smart_habits_`) AND append a short random suffix to make conflicts with user automations geometrically improbable. Never silently overwrite. Emit a log warning and surface the conflict to the user.

**Warning signs:**
- ID generation uses only entity name + time with no collision check
- No guard before calling the creation endpoint
- No test case where an automation with the same derived ID already exists

**Phase to address:**
Phase 4 (Automation Creation) — enforce the collision-check pattern before any creation call is written.

---

### Pitfall 3: Panel JS Fails to Load Because of Wrong `panel_custom` Registration

**What goes wrong:**
The LitElement panel JS file is served correctly (200 OK from `www/`), but the panel shows a blank white page or "Custom element not found" error in the browser console. The `panel_custom` integration in `configuration.yaml` is configured, but the `js_url` path is wrong, the `webcomponent_name` does not match the class registered in the JS via `customElements.define()`, or the JS module fails to load because it uses ES module syntax without `module: true`.

**Why it happens:**
HA `panel_custom` requires the `webcomponent_name` in YAML to exactly match the string passed to `customElements.define('my-panel', MyPanel)` in the JS file. A single character mismatch (e.g. `smart-habits-panel` vs `smart_habits_panel`) produces a silent failure — the element is never found, the panel is blank. Additionally, if the JS file uses `import` statements (ES modules), the `module: true` key in `panel_custom` config must be set; without it HA injects the script as a classic script and `import` throws a SyntaxError.

**How to avoid:**
Ensure `webcomponent_name` in `panel_custom` YAML exactly matches `customElements.define(...)` in the JS. Always set `module: true` when using ES module syntax. For registering from Python (avoiding manual YAML), use `hass.components.frontend.async_register_built_in_panel` or `hass.http.register_static_path` + `async_register_panel` via the integration setup, not `configuration.yaml`. Register from `async_setup_entry` so the panel lifecycle is tied to the config entry.

Minimal working pattern for integration-registered panels:
```python
# In async_setup_entry:
from homeassistant.components.frontend import async_register_built_in_panel

async_register_built_in_panel(
    hass,
    component_name="custom",
    sidebar_title="Smart Habits",
    sidebar_icon="mdi:brain",
    frontend_url_path="smart-habits",
    config={"_panel_custom": {
        "name": "smart-habits-panel",
        "js_url": "/local/smart_habits/panel.js",
        "module_url": "/local/smart_habits/panel.js",  # module: true equivalent
    }},
    require_admin=False,
)
```

**Warning signs:**
- Panel registers via `configuration.yaml` rather than `async_setup_entry` (breaks integration lifecycle)
- `webcomponent_name` and `customElements.define()` string differ in any way
- `module: true` absent when using `import` statements in the panel JS
- No `panel.js` file in `custom_components/smart_habits/www/` or `www/smart_habits/`
- Panel shows blank or console shows "Custom element smart-habits-panel is not defined"

**Phase to address:**
Phase 5 (Review Panel) — establish the panel registration skeleton before writing any UI logic. Verify the panel loads (even with a stub `<h1>Hello</h1>`) before building features on top.

---

### Pitfall 4: LitElement Panel Cannot Call WebSocket API Because of Missing `hass` Property

**What goes wrong:**
The LitElement panel component calls `this.hass.callWS({type: "smart_habits/get_patterns"})` but `this.hass` is undefined, resulting in `TypeError: Cannot read properties of undefined (reading 'callWS')`. The panel renders but no data loads.

**Why it happens:**
HA's frontend framework injects the `hass` object into custom panels by setting it as a property on the web component — it does not pass it as a constructor argument or through a slot. For HA to inject `hass`, the component must declare it as a LitElement reactive property with the correct name:
```javascript
static get properties() {
    return { hass: { type: Object }, narrow: { type: Boolean }, panel: { type: Object } };
}
```
If this declaration is missing, or if the property is named differently (e.g. `_hass`), HA cannot set the property and `this.hass` is always undefined.

**How to avoid:**
Always declare `hass`, `narrow`, and `panel` as LitElement reactive properties. Access WebSocket via `this.hass.callWS(...)` or `this.hass.connection.sendMessagePromise(...)`. Never try to import or construct a WebSocket connection manually — HA's frontend connection handles auth, reconnection, and connection sharing. Verify `this.hass` is defined before making calls (gate calls in `updated()` lifecycle hook).

```javascript
import { LitElement, html } from "https://unpkg.com/lit?module";

class SmartHabitsPanel extends LitElement {
    static get properties() {
        return {
            hass: { type: Object },
            narrow: { type: Boolean },
            panel: { type: Object },
            _patterns: { type: Array },
        };
    }

    async connectedCallback() {
        super.connectedCallback();
        if (this.hass) {
            this._patterns = await this.hass.callWS({ type: "smart_habits/get_patterns" });
        }
    }
}
customElements.define("smart-habits-panel", SmartHabitsPanel);
```

**Warning signs:**
- No `static get properties()` declaring `hass: { type: Object }`
- Code constructs its own WebSocket connection
- `this.hass` accessed without a guard (throws when panel loads before HA injects `hass`)
- Panel shows loading spinner indefinitely with no console errors

**Phase to address:**
Phase 5 (Review Panel) — establish the LitElement property contract and a minimal `callWS` test as the first thing before building UI.

---

### Pitfall 5: Temporal Sequence Detector Produces Spurious Correlations From Automation Triggers

**What goes wrong:**
The temporal sequence detector identifies "Device A on → Device B on within 5 minutes" as a strong pattern and suggests an automation. But the reason A and B always co-occur is that an existing automation already triggers both of them. The pattern is real in the data but creating a new automation would duplicate existing behavior, or worse, create a circular trigger loop.

**Why it happens:**
The detector looks at state change timestamps without knowing *why* states changed. An existing automation that turns on lights A, B, and C in sequence will look exactly like a human behavioral sequence. The detector has no access to automation execution logs, only state history.

**How to avoid:**
Before surfacing a temporal sequence as a suggestion, check whether any existing automation targets the same entities in the same order. A heuristic: if the sequence fires with suspiciously tight timing (< 500ms between state changes), it is almost certainly an automation trigger, not a human action. Filter sequences where time-delta standard deviation is near zero (automation execution is precise; human behavior has variance). Expose `min_sequence_delta_std` as a configurable threshold.

Additionally, mark sequences that involve entities already in the same automation's action list as "likely automated — suppressed."

**Warning signs:**
- Sequence detector suggests automations that already exist (or ones very similar to them)
- Detected sequences have near-zero time variance (all within the same 100ms window)
- No check against existing automations before surfacing suggestions

**Phase to address:**
Phase 5 (Advanced Detectors) — build the correlation-suppression check into the `TemporalSequenceDetector` before it surfaces any suggestions. Include a test fixture with an existing automation that creates a spurious sequence signal.

---

### Pitfall 6: Presence-Based Detector Conflates `device_tracker` State Changes From Network Presence Flapping

**What goes wrong:**
Device tracker entities (`device_tracker.phone`) change state frequently due to WiFi, Bluetooth, or ping-based presence detection — they flap between `home` and `not_home` dozens of times per day even when the person is present. The presence detector sees rapid arrival events and generates high-confidence "arrival → device on" patterns for random entity combinations, polluting suggestions with noise.

**Why it happens:**
Network-based device trackers are inherently unreliable at short timescales. A phone that briefly disconnects from WiFi while in standby mode generates a `not_home` → `home` cycle that looks identical to a genuine arrival in the state history.

**How to avoid:**
Apply a minimum `home` dwell time before counting a `not_home` → `home` transition as a genuine arrival. A transition that reverts within 3-5 minutes is a flap, not an arrival. Implementation: only consider `home` state entries where the entity stayed `home` for at least `MIN_ARRIVAL_DWELL_SECONDS` (e.g. 300 seconds = 5 minutes) before analyzing what happened next.

```python
MIN_ARRIVAL_DWELL_SECONDS = 300  # Only real arrivals

def is_real_arrival(records: list, idx: int) -> bool:
    """Return True if the home→not_home dwell after idx exceeds threshold."""
    arrival_ts = records[idx].timestamp
    for subsequent in records[idx + 1:]:
        if subsequent.state == "not_home":
            return (subsequent.timestamp - arrival_ts).seconds >= MIN_ARRIVAL_DWELL_SECONDS
    return True  # Stayed home to end of window
```

Prefer `person` entities over raw `device_tracker` entities — the `person` domain aggregates multiple trackers with debouncing, producing far less flap noise.

**Warning signs:**
- Presence detector uses `device_tracker` directly instead of `person` domain
- No dwell-time filter on arrival detection
- High-confidence patterns suggested involving entities that change randomly throughout the day
- Detector runs in `hass.async_add_executor_job` but the arrival logic iterates through records in O(n²) — expensive on long histories

**Phase to address:**
Phase 5 (Advanced Detectors) — the presence detector should default to `person` entities (already in `DEFAULT_ENTITY_DOMAINS`) and apply dwell-time filtering before any correlation analysis.

---

### Pitfall 7: WebSocket Command Schema Mismatch Breaks Existing Panel When New Commands Are Added

**What goes wrong:**
The existing panel (or any frontend code calling `smart_habits/dismiss_pattern`) stops working after new WebSocket commands are registered, because the new command registration code accidentally re-registers an existing command name, or a schema change to an existing command (e.g. adding a required field to `dismiss_pattern`) breaks callers that send the old schema.

**Why it happens:**
HA's `websocket_api.async_register_command` raises no error if you register the same command name twice — the second registration silently replaces the first. This can happen if `async_register_commands` is called multiple times (e.g. on config entry reload). Schema changes to existing commands with `vol.Required(...)` fields are backward-incompatible — callers sending old message shapes receive a validation error that looks like a connection failure.

**How to avoid:**
Guard `async_register_commands` to only run once using an `hass.data` flag:
```python
def async_register_commands(hass: HomeAssistant) -> None:
    if hass.data.get(f"{DOMAIN}_ws_registered"):
        return
    hass.data[f"{DOMAIN}_ws_registered"] = True
    websocket_api.async_register_command(hass, ws_get_patterns)
    # ... new commands
```

For schema changes to existing commands, use `vol.Optional(...)` with a default value rather than `vol.Required(...)` for new fields — this maintains backward compatibility with the existing panel code.

**Warning signs:**
- `async_register_commands` called from `async_setup_entry` without a "already registered" guard
- Adding `vol.Required(...)` fields to existing command schemas
- Existing dismiss/trigger_scan commands stop working after new commands are added
- No integration test that exercises all existing commands after adding new ones

**Phase to address:**
Phase 4 (Automation Creation) — when adding `accept_pattern` and `customize_pattern` WebSocket commands, add the guard immediately. Phase 5 similarly when adding panel commands.

---

### Pitfall 8: Temporal Sequence Detector O(n²) Cross-Join Blows Up on Large Entity Sets

**What goes wrong:**
The temporal sequence detector compares every entity's state change events against every other entity's events within a sliding time window. With 100 entities each having 1000 state changes over 30 days, the naive implementation performs 100 × 100 × 1000² = 10^10 comparisons. Analysis on a Raspberry Pi 4 takes hours, exhausts RAM, and causes HA to kill the thread.

**Why it happens:**
The algorithm that seems natural — "for each event on entity A, scan all events on entity B within ±N minutes" — is O(E × E × N²) where E is entity count and N is event count per entity. This is fine for 10 entities in development. It fails catastrophically at scale.

**How to avoid:**
Use an interval-indexed approach instead of nested loops:
1. Sort all events for all entities by timestamp into a single timeline.
2. Maintain a sliding window (a deque) of events within the last N minutes.
3. For each new event, compare against entities already in the window — this is O(E × N × W) where W is the average window occupancy, typically much smaller than N.

Also constrain the candidate entity set: only detect sequences between entities in the same room/area (HA area registry), not globally across all entities. This reduces E drastically.

```python
from collections import deque

def detect_sequences(all_events: list[Event], window_seconds: int = 300):
    """O(N * W) temporal co-occurrence detection using sliding window."""
    window: deque[Event] = deque()
    sequences: dict[tuple, int] = defaultdict(int)

    for event in sorted(all_events, key=lambda e: e.timestamp):
        # Remove events outside the window
        cutoff = event.timestamp - timedelta(seconds=window_seconds)
        while window and window[0].timestamp < cutoff:
            window.popleft()

        # Count co-occurrences with events already in window
        for prior in window:
            if prior.entity_id != event.entity_id:
                sequences[(prior.entity_id, event.entity_id)] += 1

        window.append(event)

    return sequences
```

**Warning signs:**
- Sequence detection code contains nested `for entity_a in entities: for entity_b in entities:` loops
- No constraint on which entity pairs to compare
- Performance test absent or only tested against 10 entities
- Analysis runtime grows superlinearly with entity count

**Phase to address:**
Phase 5 (Advanced Detectors) — write the sliding-window algorithm from the start. Include a performance test: N=50 entities × 30 days must complete in under 10 seconds on benchmark hardware.

---

### Pitfall 9: Panel State Goes Stale Because Updates Are Not Pushed via WebSocket Subscription

**What goes wrong:**
The panel loads patterns on `connectedCallback` via a one-shot `callWS`. After the user accepts a pattern (creating an automation), dismisses a pattern, or triggers a scan from the panel, the displayed list does not update. The user must reload the page to see current state. This feels broken even though the underlying data is correct.

**Why it happens:**
`callWS` is a request-response call. Once the panel loads, it holds a snapshot of the pattern list. Actions taken in the panel (or externally, e.g. another tab) do not push updates back. The panel has no way to know the coordinator's data changed.

**How to avoid:**
After any mutating action (accept, dismiss, trigger_scan), explicitly re-fetch patterns from the coordinator:
```javascript
async _handleAccept(pattern) {
    await this.hass.callWS({ type: "smart_habits/accept_pattern", ...pattern });
    // Re-fetch immediately after mutation
    const result = await this.hass.callWS({ type: "smart_habits/get_patterns" });
    this._patterns = result.patterns;
    this.requestUpdate();
}
```

For real-time push (e.g. scan completes in background), consider adding a `smart_habits/subscribe_patterns` WebSocket command that uses `connection.subscriptions` to push coordinator updates. This is HA's standard pattern for reactive panels (used by the automation editor, entity registry panel, etc.).

**Warning signs:**
- No data refresh after accept/dismiss actions in the panel
- Pattern list updates only visible after full page reload
- No `requestUpdate()` or `this._patterns = ...` after mutating calls

**Phase to address:**
Phase 5 (Review Panel) — build the "fetch after mutate" pattern into the panel skeleton. Deferred real-time subscriptions are acceptable for MVP but must be tracked.

---

### Pitfall 10: `accept_pattern` WebSocket Command Creates Automation on Event Loop Thread

**What goes wrong:**
The `accept_pattern` WebSocket handler calls `hass.async_add_job(create_automation_via_rest)` where `create_automation_via_rest` makes an HTTP request to the local HA REST API. The HTTP call blocks the executor thread for up to several seconds. On Raspberry Pi 4, concurrent accept operations queue up and HA's thread pool saturates.

**Why it happens:**
The REST endpoint `/api/config/automation/config/<id>` must be called via `aiohttp` (async HTTP), not `requests` (blocking HTTP). Developers accustomed to synchronous Python naturally use `requests` or `urllib`. Even `requests` inside `async_add_executor_job` is better than on the event loop, but still wastes a thread slot on a simple local HTTP call.

**How to avoid:**
Use `hass.async_add_executor_job` for the REST call only if using a synchronous HTTP library. Better: use HA's built-in `aiohttp` session for async HTTP — `hass.helpers.aiohttp_client.async_get_clientsession(hass)` returns an `aiohttp.ClientSession` that can be used directly from async context without blocking:

```python
async def _async_create_automation(hass: HomeAssistant, automation_config: dict) -> str:
    """Create automation via HA REST API using async HTTP."""
    session = async_get_clientsession(hass)
    url = f"http://localhost:{hass.config.api.port}/api/config/automation/config/{automation_id}"
    headers = {"Authorization": f"Bearer {hass.auth.async_generate_token(...)}"}
    async with session.post(url, json=automation_config, headers=headers) as resp:
        return await resp.json()
```

Note: calling HA's own REST API from within the integration requires a valid long-lived access token or an internal token. The cleanest alternative is to call the HA config storage directly via internal Python APIs rather than going through HTTP (see Pitfall 11).

**Warning signs:**
- `import requests` in any integration file
- `hass.async_add_executor_job` wrapping an HTTP call to localhost
- Automation creation hangs or is slow under concurrent operations
- No use of `async_get_clientsession`

**Phase to address:**
Phase 4 (Automation Creation) — decide up front whether to use HTTP vs. internal Python API for automation creation. The HTTP approach requires auth token management. The internal API approach is cleaner but more fragile (undocumented).

---

### Pitfall 11: `DetectedPattern` Fingerprint Is Insufficient for Temporal and Presence Pattern Types

**What goes wrong:**
The existing `DismissedPatternsStore` uses `(entity_id, pattern_type, peak_hour)` as a fingerprint. This works for `daily_routine` patterns. But temporal sequence patterns involve *two* entity IDs and no single `peak_hour`. Presence patterns involve a `person` entity and multiple triggered entities. If the new detectors emit `DetectedPattern` objects, the fingerprint uniqueness constraint breaks — two different sequence patterns on the same entity at the same hour collide.

**Why it happens:**
The fingerprint was designed specifically for `daily_routine` patterns and encoded into both `DismissedPatternsStore` and the WebSocket `dismiss_pattern` command schema. The new pattern types have a richer identity that doesn't fit this structure.

**How to avoid:**
Extend `DetectedPattern` with an optional `secondary_entity_id` field (for sequences) and update the fingerprint computation:
```python
@dataclass
class DetectedPattern:
    # Existing fields
    entity_id: str
    pattern_type: str
    peak_hour: int
    # New for sequence/presence patterns
    secondary_entity_id: str | None = None
    sequence_window_seconds: int | None = None

    @property
    def fingerprint(self) -> tuple:
        return (self.entity_id, self.pattern_type, self.peak_hour, self.secondary_entity_id)
```

Update `DismissedPatternsStore`, `ws_dismiss_pattern` schema, and all serialization points simultaneously. Do not let the v1.0 fingerprint format silently persist — bump `STORAGE_VERSION` in `DismissedPatternsStore` and write a migration that adds `None` for `secondary_entity_id` to existing dismissed records.

**Warning signs:**
- `TemporalSequenceDetector` or `PresenceDetector` emits `DetectedPattern` objects with `secondary_entity_id=None` for patterns that have a second entity
- Two distinct sequence patterns have the same `(entity_id, pattern_type, peak_hour)` fingerprint
- `DismissedPatternsStore.STORAGE_VERSION` not bumped when fingerprint format changes
- `ws_dismiss_pattern` schema not updated to accept optional `secondary_entity_id`

**Phase to address:**
Phase 5 (Advanced Detectors) — extend the data model before writing the detectors. Migration for existing dismissed patterns must be in the same PR as the model change.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| One-shot `callWS` in panel (no subscription) | Simpler frontend code | Stale state after mutations; poor UX | Acceptable in MVP; must add re-fetch after every mutation |
| Use HTTP REST API for automation creation vs. internal Python API | Well-understood interface | Requires auth token generation inside the integration; more moving parts | Acceptable if auth token pattern is tested end-to-end |
| Use `device_tracker` entities in presence detector instead of `person` | Broader coverage of presence signals | High flap noise; spurious suggestions | Never — always prefer `person` domain as primary |
| Emit raw sequence co-occurrence counts without min-count threshold | Easy to implement | Extremely noisy suggestions from rare co-occurrences | Never — require minimum co-occurrence count (e.g. 5×) before surfacing |
| Skip fingerprint extension for new pattern types | No model changes needed | Dismiss/accept fingerprint collisions; broken dismissed-pattern filtering | Never — fix the model before adding detectors |
| Register panel from `configuration.yaml` instead of `async_setup_entry` | Slightly simpler setup doc | Panel does not unload with the integration; persists after integration removal | Never for programmatic panels |

---

## Integration Gotchas

| Integration Point | Common Mistake | Correct Approach |
|-------------------|----------------|------------------|
| Automation creation REST API | Call without verifying resulting HA state | Always verify `hass.states.async_get(automation_entity_id)` after creation + reload |
| Automation creation REST API | Use `requests` (blocking) from async context | Use `hass.helpers.aiohttp_client.async_get_clientsession` for async HTTP |
| LitElement panel | `webcomponent_name` mismatch with `customElements.define()` | Must be byte-for-byte identical; use a constant shared between YAML and JS |
| LitElement panel | Missing `static get properties()` for `hass` | HA injects `hass` as a property; must declare with `{ type: Object }` |
| WebSocket command registration | Calling `async_register_commands` on every config entry reload | Guard with `hass.data` flag; register once per HA instance lifetime |
| Presence detector | Using `device_tracker` entities directly | Use `person` domain; it aggregates tracker data with debouncing |
| Temporal sequence detector | Nested entity-pair loops | Use sorted-timeline + sliding deque; O(N×W) not O(N²×E²) |
| Dismissed pattern store | Adding new pattern types without extending fingerprint | Extend fingerprint before adding detectors; bump `STORAGE_VERSION` |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Temporal sequence detector nested loops | Analysis takes >60s on Pi 4; HA kills thread | Sliding deque algorithm (O(N×W)); constrain entity pairs by HA area | Any real install with >20 entities and 30 days of history |
| Loading full state history for presence detection | OOM on Pi 4 with large `person` history | Scope queries to `person` and `light/switch` domains only; apply lookback filter | Large install with person entities tracked for >1 year |
| Presence flap creating O(N²) spurious correlations | Hundreds of low-quality suggestions generated per analysis run | Dwell-time filter (300s minimum for genuine arrival) before correlation | From first real install |
| Panel re-renders entire list on every WebSocket response | UI janky on large pattern sets (>50 patterns) | Use LitElement's `repeat()` directive with key functions; only update changed items | If user has >50 suggestions, which is plausible on large installs |
| Automation creation HTTP call from executor thread | Thread pool starvation under concurrent operations | Use async HTTP client (`aiohttp`) on event loop, not executor | Concurrent accept operations (unlikely but possible) |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Generating auth token from within integration for REST API calls | Long-lived token stored in memory; leaked in logs | Use HA's internal Python API for automation creation rather than HTTP; or use `hass.auth.async_create_access_token` with minimal lifetime |
| Panel makes WebSocket calls without checking `hass.user.is_admin` | Non-admin users can create automations | Gate `accept_pattern` WebSocket command with admin check in the handler: `if not connection.user.is_admin: raise Unauthorized` |
| Automation payload includes user-controlled strings injected into template | Template injection: user string in automation action creates runnable HA template | Never interpolate user-facing strings into automation YAML templates; construct action payloads from validated entity IDs only |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Panel shows "creating..." but gives no feedback if creation fails | User clicks accept, spinner spins forever, no resolution | Always show success (green check + automation link) or failure (error message) within 5 seconds |
| Panel does not show what the created automation actually does | User cannot verify before accepting | Show plain-language preview: "When you arrive home → Turn on kitchen lights" before showing the Accept button |
| Temporal sequences displayed with entity IDs instead of friendly names | `automation.0a1b2c` / `light.xxxx_kitchen` in suggestion text | Always use `hass.states.get(entity_id).attributes.get("friendly_name", entity_id)` for display |
| Panel lists all pattern types (daily, sequence, presence) in a flat undifferentiated list | Overwhelming; user cannot tell what type of pattern they're looking at | Group by category: "Daily Routines", "Arrival Sequences", "Device Chains"; show a type badge on each card |
| Customization UI exposes raw YAML to the user | Non-technical users abandon the feature | Provide structured form fields (time picker, entity picker, condition toggle) — never raw YAML in the panel |

---

## "Looks Done But Isn't" Checklist

- [ ] **Automation creation:** Verify the created automation appears in Settings > Automations, triggers correctly, and persists after HA restart — not just that the API returned 200
- [ ] **Automation ID collision:** Verify that accepting a pattern does NOT overwrite an existing automation with a similar name
- [ ] **Panel loads:** Verify the sidebar panel is visible, loads the JS file (no 404 in browser network tab), and the web component renders (not a blank page)
- [ ] **`hass` injection:** Verify `this.hass` is defined when panel's `connectedCallback` fires — log it in dev, add a guard in prod
- [ ] **Dismiss still works for new pattern types:** Verify dismissing a temporal sequence or presence pattern does not incorrectly match the fingerprint of a different pattern
- [ ] **Presence flap filter:** Verify that a device tracker flapping `home` → `not_home` → `home` within 2 minutes does NOT generate a presence-based suggestion
- [ ] **Sequence detector performance:** Run detector against a fixture of 50 entities × 30 days and verify completion in < 10 seconds on Pi 4-equivalent hardware
- [ ] **Panel state after accept:** Verify pattern moves from "suggestions" to "accepted" in the panel immediately after accepting, without a page reload
- [ ] **WebSocket re-registration guard:** Reload the integration config entry and verify WebSocket commands are not double-registered (check HA logs for warning)
- [ ] **Storage version migration:** After upgrading from v1.0 storage format, verify existing dismissed patterns are still dismissed (not lost due to fingerprint format change)

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Automation creation returns 200 but creates nothing | MEDIUM — add verify-after-create + surface error to user | Add `hass.states.async_get` check post-creation; emit error event to panel; add `automation.reload` wait |
| ID collision overwrites user automation | HIGH — requires restore from HA backup | Add collision check before creation; implement soft-delete (mark Smart Habits automations with metadata); add warning in release notes |
| Panel blank due to `webcomponent_name` mismatch | LOW — fix the string, redeploy | Align `webcomponent_name` with `customElements.define()`; add browser console check to test suite |
| Sequence detector OOM/timeout | MEDIUM — rewrite inner loop | Replace nested loops with sliding-deque algorithm; add performance test as regression guard |
| Fingerprint collision for new pattern types | MEDIUM — model change + migration | Extend fingerprint; bump `STORAGE_VERSION`; write migration for existing dismissed patterns |
| Presence detector swamped by flap noise | LOW-MEDIUM — add dwell filter | Add `MIN_ARRIVAL_DWELL_SECONDS` constant; apply filter before correlation; re-run analysis on existing history |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Automation creation API returns 200 but creates nothing | Phase 4: Automation Creation | Integration test: create → reload → `hass.states.async_get` → restart HA → re-verify |
| Automation ID collision overwrites existing automation | Phase 4: Automation Creation | Test fixture: pre-create automation with same derived ID; verify accept does NOT overwrite |
| Panel `webcomponent_name` mismatch | Phase 5: Review Panel (skeleton) | Browser console shows no "custom element not defined" errors; panel renders non-blank |
| `hass` property not injected into LitElement | Phase 5: Review Panel (skeleton) | `console.log(this.hass)` in `connectedCallback` returns the HA object, not undefined |
| Temporal sequence spurious correlations from existing automations | Phase 5: Advanced Detectors | Test fixture: create automation A→B; verify detector does NOT suggest creating A→B automation |
| Presence detector flap noise | Phase 5: Advanced Detectors | Test fixture: simulate flapping device tracker; verify 0 suggestions generated |
| Temporal sequence O(n²) performance | Phase 5: Advanced Detectors | Benchmark test: 50 entities × 30 days completes in < 10s |
| WebSocket double-registration | Phase 4: Automation Creation | Reload config entry twice; verify `hass.data` guard prevents duplicate registration |
| `DetectedPattern` fingerprint insufficient for new types | Phase 5: Advanced Detectors | Model extension PR includes fingerprint update, storage version bump, and migration test |
| Panel state not updated after mutations | Phase 5: Review Panel (skeleton) | Dismiss a pattern; verify it disappears from the panel immediately without page reload |
| Automation creation using blocking HTTP | Phase 4: Automation Creation | No `import requests` in codebase; all HTTP via `async_get_clientsession` |

---

## Sources

- Home Assistant Developer Docs: WebSocket API — HIGH confidence (training knowledge, verified against existing codebase patterns)
- Home Assistant Developer Docs: Custom Panels / `panel_custom` — HIGH confidence (well-documented in developer portal)
- Home Assistant Developer Docs: Frontend LitElement panel architecture — HIGH confidence (official docs)
- HA REST API `/api/config/automation/config/` — MEDIUM confidence (undocumented officially; behavior inferred from HA source code analysis and community reports)
- Existing codebase analysis (`websocket_api.py`, `storage.py`, `models.py`) — HIGH confidence (ground truth for integration pitfalls)
- Algorithm complexity analysis for temporal sliding window — HIGH confidence (fundamental CS; no external source required)
- HA `person` vs `device_tracker` reliability — HIGH confidence (HA docs state `person` aggregates and debounces tracker data)
- `aiohttp` vs `requests` in HA integrations — HIGH confidence (HA contribution guidelines mandate no blocking I/O in async context)

---
*Pitfalls research for: Home Assistant — automation creation, LitElement sidebar panel, temporal sequence detection, presence-based pattern detection*
*Researched: 2026-02-23*
