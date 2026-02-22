# Architecture Research

**Domain:** Home Assistant custom integration — ML pattern mining with frontend panel
**Researched:** 2026-02-22
**Confidence:** MEDIUM-HIGH (official HA docs + community guides + verified patterns)

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                     Home Assistant Runtime                            │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │                     Frontend Layer (Browser)                     │ │
│  │                                                                  │ │
│  │  ┌──────────────────────────────────────────────────────────┐   │ │
│  │  │          auto-pattern Sidebar Panel (JS Web Component)    │   │ │
│  │  │  - Pattern list (pending/accepted/dismissed)              │   │ │
│  │  │  - Confidence scores + detail view                        │   │ │
│  │  │  - Accept / Customize / Dismiss actions                   │   │ │
│  │  │  - Settings (lookback period, threshold)                  │   │ │
│  │  └────────────────────┬─────────────────────────────────────┘   │ │
│  └───────────────────────┼──────────────────────────────────────────┘ │
│                           │ WebSocket (hass.connection.sendMessagePromise)
│  ┌────────────────────────┼──────────────────────────────────────────┐ │
│  │                 Python Integration Layer                           │ │
│  │                                                                    │ │
│  │  ┌─────────────┐  ┌──────────────┐  ┌──────────────────────────┐ │ │
│  │  │ __init__.py │  │  ws_api.py   │  │   config_flow.py         │ │ │
│  │  │ (setup,     │  │ (WebSocket   │  │   (UI setup: lookback,   │ │ │
│  │  │  teardown,  │  │  command     │  │    threshold, entities   │ │ │
│  │  │  panel reg) │  │  handlers)   │  │    to include/exclude)   │ │ │
│  │  └──────┬──────┘  └──────┬───────┘  └──────────────────────────┘ │ │
│  │         │                │                                         │ │
│  │  ┌──────▼────────────────▼────────────────────────────────────┐  │ │
│  │  │                PatternCoordinator                           │  │ │
│  │  │  (DataUpdateCoordinator subclass)                           │  │ │
│  │  │  - Schedules periodic analysis runs                        │  │ │
│  │  │  - Holds in-memory pattern store (pending/accepted/etc.)   │  │ │
│  │  │  - Notifies panel via WebSocket subscription               │  │ │
│  │  └──────────────────────┬─────────────────────────────────────┘  │ │
│  │                          │ async_add_executor_job                  │ │
│  │  ┌───────────────────────▼────────────────────────────────────┐  │ │
│  │  │                 PatternAnalyzer (sync, CPU-bound)           │  │ │
│  │  │  - TemporalSequenceDetector                                 │  │ │
│  │  │  - DailyRoutineDetector                                     │  │ │
│  │  │  - PresencePatternDetector                                  │  │ │
│  │  │  - ExistingAutomationFilter                                 │  │ │
│  │  └──────────────────────┬─────────────────────────────────────┘  │ │
│  │                          │                                          │ │
│  │  ┌───────────────────────▼────────────────────────────────────┐  │ │
│  │  │                   RecorderReader                            │  │ │
│  │  │  - Direct SQLAlchemy query to recorder DB                  │  │ │
│  │  │  - Reads states + states_meta tables                       │  │ │
│  │  │  - Respects configurable lookback window                   │  │ │
│  │  └──────────────────────┬─────────────────────────────────────┘  │ │
│  │                          │                                          │ │
│  │  ┌───────────────────────▼────────────────────────────────────┐  │ │
│  │  │                 AutomationBuilder                           │  │ │
│  │  │  - Generates HA automation YAML dict from pattern          │  │ │
│  │  │  - Posts to /api/config/automation/config/<id> (REST)      │  │ │
│  │  │  - Reads automation registry to filter duplicates          │  │ │
│  │  └────────────────────────────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │                      Storage Layer                                   │ │
│  │  ┌────────────────────┐  ┌──────────────────┐  ┌─────────────────┐ │ │
│  │  │ Recorder DB        │  │ HA Automation     │  │ .storage/       │ │ │
│  │  │ (SQLite/MariaDB)   │  │ Registry          │  │ auto_pattern    │ │ │
│  │  │ states, states_meta│  │ (existing         │  │ (dismissed,     │ │ │
│  │  │ statistics tables  │  │ automations)      │  │ accepted IDs,   │ │ │
│  │  └────────────────────┘  └──────────────────┘  │ pattern cache)  │ │ │
│  │                                                  └─────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| `__init__.py` | Integration entry point, setup/teardown, panel registration, coordinator init | `async_setup_entry()`, `async_unload_entry()`, `panel_custom.async_register_panel()` |
| `config_flow.py` | User config UI: lookback period, confidence threshold, entity filters | `ConfigFlow` class with `async_step_user()` |
| `PatternCoordinator` | Periodic background orchestration, in-memory pattern store, listener notification | `DataUpdateCoordinator` subclass, `_async_update_data()` calling executor |
| `PatternAnalyzer` | CPU-bound ML analysis: sequence, routine, presence detection | Synchronous Python class, runs in thread pool via `async_add_executor_job` |
| `RecorderReader` | Historical state retrieval from Recorder DB | Direct SQLAlchemy queries to `states` + `states_meta` tables |
| `AutomationBuilder` | Convert patterns to HA automation dicts, create via REST API | Generates YAML dict, POST to `/api/config/automation/config/<id>` |
| `ws_api.py` | WebSocket command handlers: list patterns, accept, dismiss, trigger analysis | `@websocket_api.websocket_command` decorated handlers |
| `panel/` (JS) | Sidebar web component: pattern review UI, action dispatch | LitElement web component receiving `hass` object, calls `hass.connection.sendMessagePromise` |
| `.storage/auto_pattern` | Persistent state across restarts: dismissed IDs, accepted IDs, cached patterns | HA `Store` helper (`homeassistant.helpers.storage`) |
| `ExistingAutomationFilter` | Check patterns against automation registry to suppress duplicates | Read `hass.states` filtered to `automation.*` domain + state attributes |

## Recommended Project Structure

```
custom_components/
└── auto_pattern/
    ├── __init__.py          # Integration setup, coordinator init, panel registration
    ├── manifest.json        # name, domain, version, dependencies (recorder, frontend, panel_custom)
    ├── const.py             # DOMAIN, CONF_* constants, default values
    ├── config_flow.py       # ConfigFlow + OptionsFlow for lookback/threshold/filters
    ├── coordinator.py       # PatternCoordinator (DataUpdateCoordinator subclass)
    ├── analyzer/
    │   ├── __init__.py
    │   ├── base.py          # PatternAnalyzer abstract base class
    │   ├── temporal.py      # TemporalSequenceDetector (Device A → B within N mins)
    │   ├── routine.py       # DailyRoutineDetector (same state at same time daily)
    │   ├── presence.py      # PresencePatternDetector (person arrives → devices)
    │   └── filter.py        # ExistingAutomationFilter (dedup against HA registry)
    ├── recorder/
    │   ├── __init__.py
    │   └── reader.py        # RecorderReader — SQLAlchemy queries against recorder DB
    ├── automation/
    │   ├── __init__.py
    │   └── builder.py       # AutomationBuilder — pattern → HA automation dict + create
    ├── storage.py           # Persistent store wrapper (accepted, dismissed, cache)
    ├── ws_api.py            # WebSocket command registration and handlers
    ├── strings.json         # UI strings for config flow
    ├── translations/
    │   └── en.json
    └── panel/
        ├── auto-pattern-panel.js    # LitElement web component (bundled)
        └── auto-pattern-panel.css  # Optional: embedded in JS or separate
```

### Structure Rationale

- **`analyzer/`:** Separates ML algorithm logic from HA plumbing. Each detector is independently testable without HA running. `filter.py` consults live HA state.
- **`recorder/`:** Isolates all DB access. If HA changes its Recorder schema, only this module needs updating. Reader is sync (SQLAlchemy is not async-native here); wraps in executor.
- **`automation/`:** Isolates the unstable REST API call for automation creation. Single place to update when HA changes the endpoint.
- **`panel/`:** Frontend assets served statically. Co-located with the integration for HACS compatibility — no separate installation step.
- **`ws_api.py`:** All WebSocket command definitions in one file keeps protocol surface area visible and reviewable.
- **`storage.py`:** HA's `.storage` directory is the correct place for persistent non-config data. Avoids writing to arbitrary files.

## Architectural Patterns

### Pattern 1: DataUpdateCoordinator for Background Analysis

**What:** A `DataUpdateCoordinator` subclass owns the analysis lifecycle. Entities and the WebSocket panel both subscribe to it via listeners. The coordinator schedules periodic re-analysis and triggers immediate re-analysis on demand (e.g., user changes lookback window).

**When to use:** Whenever multiple consumers need the same expensive data. Here, the sidebar panel and any sensor entities all consume the same pattern list — the coordinator ensures analysis runs once.

**Trade-offs:** Coordinator runs on a schedule even when no one is watching. Good for this use case since patterns should stay fresh. Schedule interval needs tuning — too frequent wastes CPU on Pi 4; too infrequent feels stale.

**Example:**
```python
class PatternCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, config_entry):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(hours=6),  # configurable
        )
        self._analyzer = PatternAnalyzer(config_entry.options)
        self._reader = RecorderReader(hass)

    async def _async_update_data(self):
        """Fetch data — runs in coordinator's async context."""
        raw_states = await self.hass.async_add_executor_job(
            self._reader.fetch_states,
            self.config_entry.options[CONF_LOOKBACK_DAYS],
        )
        patterns = await self.hass.async_add_executor_job(
            self._analyzer.analyze, raw_states
        )
        return patterns
```

### Pattern 2: WebSocket API for Panel-Backend Communication

**What:** Custom WebSocket commands expose integration data and actions to the JavaScript panel. All panel→backend calls go through typed WebSocket messages, not REST.

**When to use:** Anytime the HA frontend panel needs to read or mutate integration state. This is the HA-idiomatic approach — avoids CORS issues, respects HA auth, reuses existing connection.

**Trade-offs:** More setup than REST calls but much more robust. WebSocket reconnects are handled by the HA frontend automatically.

**Example:**
```python
# ws_api.py
@websocket_api.websocket_command({
    vol.Required("type"): "auto_pattern/list_patterns",
})
@websocket_api.async_response
async def ws_list_patterns(hass, connection, msg):
    coordinator = hass.data[DOMAIN][connection.user.id_or_none]
    connection.send_result(msg["id"], {
        "patterns": [p.to_dict() for p in coordinator.data],
    })

# Registration in __init__.py async_setup_entry:
websocket_api.async_register_command(hass, ws_list_patterns)
```

### Pattern 3: Executor Job for CPU-Bound Analysis

**What:** All synchronous, CPU-bound ML analysis runs via `hass.async_add_executor_job()`, which dispatches work to a thread pool without blocking the HA event loop.

**When to use:** Any synchronous code that takes more than ~100ms (SQLAlchemy queries, pattern scoring loops, data transformations).

**Trade-offs:** Thread pool has limits on Pi 4. Analysis must be genuinely stateless or use proper locking if it writes shared state. Keep individual jobs under 30s to avoid HA watchdog warnings.

**Example:**
```python
async def _async_update_data(self):
    # RecorderReader.fetch_states is sync SQLAlchemy — run in executor
    raw = await self.hass.async_add_executor_job(
        self._reader.fetch_states, lookback_days
    )
    # PatternAnalyzer.analyze is CPU-bound — run in executor
    return await self.hass.async_add_executor_job(
        self._analyzer.analyze, raw
    )
```

### Pattern 4: Panel Registration via panel_custom in Code

**What:** Integrations register sidebar panels programmatically in `async_setup_entry()` using `panel_custom.async_register_panel()`. The JS web component is served from the integration's `panel/` directory.

**When to use:** When the panel must stay in sync with the integration version (shipped together, no separate install).

**Trade-offs:** Requires `frontend` and `panel_custom` in manifest dependencies. Panel JS must be a proper custom element — any framework works as long as it exports one.

**Example:**
```python
# __init__.py
from homeassistant.components import panel_custom

async def async_setup_entry(hass, entry):
    await panel_custom.async_register_panel(
        hass,
        webcomponent_name="auto-pattern-panel",
        frontend_url_path="auto-pattern",
        sidebar_title="Auto Pattern",
        sidebar_icon="mdi:robot",
        module_url="/auto_pattern_static/auto-pattern-panel.js",
        require_admin=False,
    )
```

## Data Flow

### Analysis Trigger Flow

```
HA Startup / Schedule Timer / User Action (UI)
    ↓
PatternCoordinator._async_update_data() [async, event loop]
    ↓
hass.async_add_executor_job(RecorderReader.fetch_states) [thread pool]
    ↓ returns raw state history
hass.async_add_executor_job(PatternAnalyzer.analyze) [thread pool]
    ↓ returns List[Pattern] with confidence scores
ExistingAutomationFilter.filter(patterns) [checks hass.states for existing automations]
    ↓ returns de-duplicated List[Pattern]
Coordinator stores result → notifies all listeners
    ↓
Panel re-renders via WebSocket subscription update
```

### User Accepts Pattern Flow

```
User clicks "Accept" in Panel JS (auto-pattern-panel.js)
    ↓
hass.connection.sendMessagePromise({type: "auto_pattern/accept_pattern", pattern_id: "..."})
    ↓ WebSocket message to HA backend
ws_api.ws_accept_pattern() handler [async]
    ↓
AutomationBuilder.build(pattern) → generates HA automation dict
    ↓
POST /api/config/automation/config/<generated_uuid> with Bearer token
    ↓ HA creates automation in automations.yaml
storage.mark_accepted(pattern_id) → persists to .storage/auto_pattern
    ↓
coordinator.async_request_refresh() → triggers re-analysis to filter now-accepted pattern
    ↓
Panel receives updated list (accepted pattern moves to "accepted" view)
```

### User Dismisses Pattern Flow

```
User clicks "Dismiss" in Panel JS
    ↓
hass.connection.sendMessagePromise({type: "auto_pattern/dismiss_pattern", pattern_id: "..."})
    ↓
ws_api.ws_dismiss_pattern() handler
    ↓
storage.mark_dismissed(pattern_id)
    ↓
coordinator.async_request_refresh() — OR — remove from in-memory list immediately
    ↓
Panel updates (dismissed pattern disappears from pending view)
```

### State Management

```
PatternCoordinator.data (in-memory List[Pattern])
    ↑ written by _async_update_data on each analysis run
    ↓ read by:
        - ws_api handlers (on panel request)
        - Any HA sensor entities subscribed via CoordinatorEntity

.storage/auto_pattern (persistent across restarts)
    - accepted_ids: Set[str]
    - dismissed_ids: Set[str]
    - last_analysis_ts: datetime
    Read at: coordinator init
    Written at: accept/dismiss actions
```

### Key Data Flows Summary

1. **Read flow (states):** Recorder DB → RecorderReader (sync/executor) → PatternAnalyzer (sync/executor) → Coordinator.data → WebSocket → Panel
2. **Write flow (automations):** Panel → WebSocket → AutomationBuilder → HA REST API → automations.yaml
3. **Persistence flow:** Accept/dismiss actions → `storage.py` → HA `.storage/auto_pattern` JSON
4. **Filter flow:** Coordinator analysis → ExistingAutomationFilter → check `hass.states` automation entities → remove already-covered patterns

## Build Order (Phase Dependencies)

Building bottom-up eliminates blockers. Each phase is independently testable:

```
Phase 1: RecorderReader
  └── Depends on: Nothing (just SQLAlchemy + HA recorder DB schema)
  └── Test: Query states from a test HA instance

Phase 2: PatternAnalyzer (pure Python, no HA)
  └── Depends on: RecorderReader output format
  └── Test: Unit test with static state history fixtures

Phase 3: Core Integration Skeleton
  └── Depends on: PatternAnalyzer, RecorderReader
  └── Files: __init__.py, manifest.json, const.py, config_flow.py, coordinator.py
  └── Test: Integration loads, config flow works, coordinator runs

Phase 4: WebSocket API + Storage
  └── Depends on: Phase 3 (coordinator with data)
  └── Files: ws_api.py, storage.py
  └── Test: Commands respond correctly, persistence survives restart

Phase 5: AutomationBuilder + Accept flow
  └── Depends on: Phase 4 (accept command wiring)
  └── Files: automation/builder.py
  └── Test: Automation created in HA, filtered from future suggestions

Phase 6: Frontend Panel
  └── Depends on: Phase 4 (WebSocket API is stable)
  └── Files: panel/auto-pattern-panel.js
  └── Test: Panel loads in sidebar, data displays, actions work end-to-end
```

## Integration Points

### External Services (HA Internal)

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Recorder DB (SQLite/MariaDB) | Direct SQLAlchemy query via `get_instance(hass).engine` | Sync — must use executor job. Schema changes in HA releases are a risk; pin query to stable columns (`states`, `states_meta`, `state_id`, `metadata_id`, `state`, `last_updated_ts`) |
| HA Automation registry | Read: `hass.states.async_all("automation")` for existing automations; Write: POST `/api/config/automation/config/<id>` | The write endpoint is undocumented/internal. Stable in practice but could change across HA major versions |
| HA WebSocket API | `websocket_api.async_register_command()` for custom commands | Well-documented, stable, preferred over REST for panel↔backend |
| HA panel_custom | `panel_custom.async_register_panel()` in setup | Requires `frontend` + `panel_custom` in manifest.json dependencies |
| HA Storage | `homeassistant.helpers.storage.Store` class | Official API, stable, correct place for non-config persistent data |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| PatternCoordinator ↔ PatternAnalyzer | Direct Python call via executor job | Analyzer is stateless — receives state snapshot, returns pattern list. No shared mutable state. |
| PatternCoordinator ↔ RecorderReader | Direct Python call via executor job | Reader is instantiated with hass reference; coordinator calls it in executor |
| ws_api.py ↔ PatternCoordinator | `hass.data[DOMAIN][entry_id].coordinator` lookup | Standard HA pattern for accessing coordinator from handlers |
| Panel JS ↔ ws_api.py | WebSocket messages (typed by `type` field) | All messages require HA auth automatically — no separate auth needed |
| AutomationBuilder ↔ HA REST | HTTP POST with `hass.auth` Bearer token | Runs async in event loop (aiohttp), not in executor |
| storage.py ↔ Coordinator | Called from ws_api handlers; state read at coordinator init | `Store.async_load()` / `Store.async_save()` — both async |

## Anti-Patterns

### Anti-Pattern 1: Blocking the Event Loop with SQLAlchemy

**What people do:** Call `session.query(...)` directly inside `async def` functions without using an executor.

**Why it's wrong:** SQLAlchemy's sync queries block the entire HA event loop. On a Pi 4, a 30-day state history query can take 2-10 seconds, during which HA cannot process any other events (automations, state changes, API calls).

**Do this instead:**
```python
# WRONG
async def _async_update_data(self):
    states = self.reader.session.query(States).all()  # blocks event loop!

# CORRECT
async def _async_update_data(self):
    states = await self.hass.async_add_executor_job(self.reader.fetch_states)
```

### Anti-Pattern 2: Storing Patterns in Config Entry Data

**What people do:** Write pattern results back into `config_entry.data` or `config_entry.options` for persistence.

**Why it's wrong:** Config entry data is for user configuration (lookback period, threshold, entity filters), not for runtime results. Storing thousands of pattern records there pollutes HA's config storage and confuses the options flow.

**Do this instead:** Use `homeassistant.helpers.storage.Store` (writes to `.storage/auto_pattern`). Keep coordinator.data as the in-memory working set; persist only accepted/dismissed IDs.

### Anti-Pattern 3: Querying States via `hass.states` for History

**What people do:** Use `hass.states.get("sensor.foo")` to get historical data, or iterate `hass.states.async_all()` to build a history.

**Why it's wrong:** `hass.states` only holds the *current* state of each entity, not history. Using it for pattern mining returns one data point per entity — useless for temporal analysis.

**Do this instead:** Query the Recorder DB directly (`states` table has the full history) or use `homeassistant.components.recorder.history.get_significant_states()` for the official history API.

### Anti-Pattern 4: Using Panel Config YAML Instead of Programmatic Registration

**What people do:** Document that users must add `panel_custom:` entries to their `configuration.yaml` to see the integration's panel.

**Why it's wrong:** Creates a two-step install process that HACS users don't expect. The panel can and should be registered programmatically in `async_setup_entry()` so it appears automatically on integration install.

**Do this instead:** Call `panel_custom.async_register_panel()` in setup; call `homeassistant.components.frontend.async_remove_panel()` in unload.

### Anti-Pattern 5: Running Analysis on Every State Change

**What people do:** Subscribe to `EVENT_STATE_CHANGED` and re-run full pattern analysis on every device state change event.

**Why it's wrong:** A busy HA instance fires hundreds of state changes per minute. Running ML analysis on each one will saturate the Pi 4 CPU and cause HA to become unresponsive.

**Do this instead:** Use `DataUpdateCoordinator` with a fixed interval (e.g., every 6 hours) plus an on-demand trigger from the panel UI. Analysis is inherently a batch operation.

## Scaling Considerations

This is a single-instance Home Assistant integration. "Scaling" here means performing well across a range of HA instance sizes.

| Scale | Architecture Adjustments |
|-------|--------------------------|
| Small HA (< 20 entities, 7 day lookback) | Default settings work. Analysis completes in seconds. Update interval can be shorter (hourly). |
| Medium HA (20-100 entities, 30 day lookback) | May need 30-60s for analysis on Pi 4. Update interval should be 6-12 hours. Cap entities analyzed or allow entity filter config. |
| Large HA (100+ entities, 90 day lookback) | Risk of OOM or timeout on Pi 4. Must paginate or chunk DB queries. Consider analyzing entity subsets. Hard cap on state rows loaded (e.g., max 500K rows). |

### Scaling Priorities

1. **First bottleneck:** DB query time and memory for large state history. Mitigate with: configurable lookback window (shorter = faster), entity inclusion filter (analyze only selected entity types), SQL LIMIT on rows fetched.

2. **Second bottleneck:** Pattern scoring algorithm complexity. Mitigate with: vectorized operations (numpy arrays instead of nested loops), early termination when confidence threshold met.

## Sources

- [HA Integration Architecture Overview](https://developers.home-assistant.io/docs/architecture_components/) — Official docs (MEDIUM confidence — accessed via search result)
- [DataUpdateCoordinator Pattern](https://aarongodfrey.dev/home%20automation/use-coordinatorentity-with-the-dataupdatecoordinator/) — Verified against HA developer docs (MEDIUM confidence)
- [Writing a HA Integration — Jon Seager](https://jnsgr.uk/2024/10/writing-a-home-assistant-integration/) — Published Oct 2024, comprehensive walkthrough (MEDIUM confidence)
- [Extending the WebSocket API](https://developers.home-assistant.io/docs/frontend/extending/websocket-api/) — Official developer docs (HIGH confidence)
- [Creating Custom Panels](https://developers.home-assistant.io/docs/frontend/custom-ui/creating-custom-panels/) — Official developer docs (HIGH confidence)
- [Adding a Sidebar Panel to an Integration](https://community.home-assistant.io/t/how-to-add-a-sidebar-panel-to-a-home-assistant-integration/981585) — Community guide (MEDIUM confidence)
- [Recorder and Statistics — DeepWiki](https://deepwiki.com/home-assistant/core/3.1-recorder-and-statistics) — Derived from HA source (MEDIUM confidence)
- [HA Recorder Database Schema](https://smarthomescene.com/blog/understanding-home-assistants-database-and-statistics-model/) — Third-party analysis (LOW confidence — verify schema columns against current HA source)
- [async_add_executor_job Pattern](https://developers.home-assistant.io/docs/asyncio_working_with_async/) — Official docs (HIGH confidence)
- [Automation REST API — undocumented](https://community.home-assistant.io/t/rest-api-docs-for-automations/119997) — Community-confirmed, intentionally unstable (LOW confidence — needs monitoring across HA versions)
- [integration_blueprint (GitHub)](https://github.com/jpawlowski/hacs.integration_blueprint) — Modern blueprint for 2025.7+ (MEDIUM confidence)

---
*Architecture research for: Home Assistant custom integration — ML pattern mining with sidebar panel*
*Researched: 2026-02-22*
