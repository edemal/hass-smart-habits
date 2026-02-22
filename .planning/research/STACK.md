# Stack Research

**Domain:** Home Assistant custom integration — ML-based pattern mining on device state history
**Researched:** 2026-02-22
**Confidence:** MEDIUM-HIGH (HA integration patterns HIGH; ML lib choices MEDIUM; automation creation mechanism LOW)

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python (async) | 3.13+ | Integration runtime | HA 2025.2+ requires Python 3.13; all integration code must be async-compatible to avoid blocking the event loop |
| Home Assistant Integration Framework | HA 2025.x | Custom integration scaffold | Standard `custom_components/` directory, `manifest.json`, `config_flow.py`, `coordinator.py` pattern — this is the only supported mechanism for deep HA integration |
| DataUpdateCoordinator | HA built-in | Background data coordination | Provides scheduled polling, subscriber fan-out, and error propagation without reinventing async scheduling; use `async_create_background_task` for the heavyweight ML analysis pass |
| SQLAlchemy (via HA Recorder) | HA-bundled | Recorder DB access | HA already has SQLAlchemy installed; use `get_instance(hass).async_add_executor_job(sync_query_fn)` to run DB queries safely on the recorder's executor thread, never blocking the event loop |
| Lit (LitElement) | 3.x | Frontend panel web component | HA's own frontend is built on Lit; panels must be custom elements; Lit is the lowest-friction choice and matches what HA internals use |

### ML & Data Libraries

| Library | Version | Purpose | Why Recommended |
|---------|---------|---------|-----------------|
| scikit-learn | 1.6+ (pinned, e.g. 1.6.1) | Clustering, pattern detection | Python 3.13-compatible (1.6+); provides OPTICS, IsolationForest, and MiniBatchKMeans — all usable on Raspberry Pi 4 if applied to pre-aggregated data; declare in `manifest.json` `requirements` array |
| NumPy | 1.26+ | Numeric array ops, windowing | Dependency of scikit-learn; use NumPy stride tricks for sliding-window time-series aggregation before clustering; avoids Pandas overhead for pure numeric data |
| pandas | 2.x (optional) | DataFrame-style aggregation from Recorder rows | Useful for pivot/resample of raw Recorder state rows into hourly/daily feature vectors; only pull in if feature engineering complexity warrants it; adds ~50MB install |

**Do NOT use:** TensorFlow, PyTorch, Prophet, Dask, or any deep-learning framework. They are far too large for Raspberry Pi class hardware and HA's install constraints.

### Frontend Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| home-assistant-js-websocket | HA-bundled (available via `this._hass`) | WS communication panel → backend | Always — the `hass` object passed to your panel already exposes `hass.connection.sendMessagePromise()` for custom WS commands; no separate install needed |
| Vite + Rollup | Vite 5.x | JS bundle for production panel | Bundle Lit + any helpers; use `vite build --lib` targeting a single ES module file; serves via HA's static file path; avoids CDN import instability issues |
| TypeScript | 5.x | Type safety for panel code | Optional but strongly recommended; catches `hass` object shape errors at compile time |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| pytest-homeassistant-custom-component | Test fixtures matching HA core | Install via pip; provides `hass`, `recorder_mock`, `enable_custom_integrations` fixtures; updated daily to match latest HA release |
| Ruff | Python linting and formatting | HA's own linter; enforces async patterns and import hygiene; configure via `pyproject.toml` |
| mypy | Python type checking | Use `homeassistant-stubs` for HA type hints |
| devcontainer (VS Code) | Reproducible dev environment | HA's recommended dev setup; eliminates "works on my machine" Recorder DB version skew |

---

## Integration Architecture (Key Patterns)

### Pattern: Recorder DB Access

Never query the Recorder DB directly from an async context. The correct pattern (as used in HA core's `history_stats` integration):

```python
from homeassistant.components.recorder import get_instance

async def _fetch_states_for_analysis(hass, entity_ids, start, end):
    instance = get_instance(hass)
    return await instance.async_add_executor_job(
        _sync_query_states, hass, entity_ids, start, end
    )

def _sync_query_states(hass, entity_ids, start, end):
    # Runs on recorder's executor thread — blocking SQLAlchemy calls are fine here
    from homeassistant.components.recorder.history import state_changes_during_period
    # ... query logic
```

### Pattern: Background ML Analysis Job

Use `hass.async_create_background_task` (not `async_create_task`) so the analysis loop does not block HA startup:

```python
async def async_setup_entry(hass, entry):
    coordinator = PatternCoordinator(hass, entry)
    entry.async_create_background_task(
        hass,
        coordinator.async_start_analysis_loop(),
        "auto_pattern_analysis"
    )
```

### Pattern: Custom WebSocket Command

```python
from homeassistant.components import websocket_api
import voluptuous as vol

@websocket_api.websocket_command({
    vol.Required("type"): "auto_pattern/get_patterns",
})
@websocket_api.async_response
async def ws_get_patterns(hass, connection, msg):
    patterns = await hass.data[DOMAIN].get_patterns()
    connection.send_result(msg["id"], {"patterns": patterns})
```

### Pattern: Panel Registration

```python
# in __init__.py async_setup_entry
from homeassistant.components import panel_custom
from homeassistant.components.http import StaticPathConfig

hass.http.register_static_path(
    "/auto_pattern/panel",
    hass.config.path("custom_components/auto_pattern/frontend"),
    cache_headers=False,
)
await panel_custom.async_register_panel(
    hass,
    webcomponent_name="auto-pattern-panel",
    frontend_url_path="auto-pattern",
    sidebar_title="Auto Pattern",
    sidebar_icon="mdi:robot",
    module_url="/auto_pattern/panel/auto-pattern-panel.js",
    embed_iframe=False,
    require_admin=False,
)
```

### Pattern: Automation Creation

There is no native `automation.create` service. The correct approach is to write a dict matching the automation config schema and call the automation component's internal service:

```python
await hass.services.async_call(
    "automation",
    "reload",   # after writing to automations.yaml
    blocking=True,
)
```

**Recommended approach for this project:** Generate the automation YAML dict and append it to `automations.yaml` via file I/O, then call `automation.reload`. This is the same mechanism used by the HA UI editor. Alternatively, register a Config Entry–backed `automation` entity via `hass.config_entries.async_forward_entry_setups` — but this is significantly more complex and underdocumented for third-party integrations.

---

## Installation

```bash
# Python dev environment (inside devcontainer or venv)
pip install homeassistant
pip install pytest-homeassistant-custom-component
pip install ruff mypy

# Runtime dependencies (declared in manifest.json, auto-installed by HA)
# "requirements": ["scikit-learn==1.6.1", "numpy>=1.26,<2.0"]
# Pandas is optional — only add if feature engineering warrants it

# Frontend build (from custom_components/auto_pattern/frontend/)
npm create vite@latest . -- --template lit-ts
npm install
npm run build   # outputs to dist/, copy to frontend/
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| scikit-learn OPTICS/MiniBatchKMeans | DBSCAN | Never for this use case — DBSCAN has O(n²) worst-case memory, documented to OOM on modest hardware even at <200K rows |
| NumPy windowed aggregation | Pandas resample | Use Pandas if you need DatetimeIndex-aware resampling and the install weight is acceptable |
| Vite + Rollup bundle | CDN import of Lit | Never — CDN imports are flaky in HA's sandboxed environment, documented as broken in 2025 |
| Lit (LitElement) | React (ha-component-kit) | If the team already knows React deeply and is building a complex, large UI — but adds significant bundle weight and has no HA-native precedent |
| `async_add_executor_job` (recorder executor) | Direct `hass.async_add_executor_job` | Never for Recorder queries — HA will log "Detected integration that accesses database without database executor" warning and behavior is undefined |
| File-write + `automation.reload` | Internal automation component API | Use the internal API only if writing to disk is unacceptable — the internal API is undocumented and subject to breaking changes |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| TensorFlow / PyTorch | 500MB+ install, requires AVX2 CPU, 2–8GB RAM at runtime — not viable on Raspberry Pi 4 | scikit-learn with classical algorithms |
| DBSCAN (sklearn) at scale | O(n²) memory complexity; documented OOM even on powerful machines with 180K rows | OPTICS (same result, lower memory) or MiniBatchKMeans |
| `hass.async_add_job` / `async_run_job` | Removed in HA 2025.4 | `hass.async_create_background_task` or `async_add_executor_job` |
| Synchronous Recorder queries in async context | Blocks the HA event loop; triggers HA internal warning | `get_instance(hass).async_add_executor_job(...)` |
| CDN imports for Lit in panel JS | Unreliable in HA's environment; documented breakage in 2025 | Bundle locally with Vite/Rollup |
| pandas as a hard dependency | ~50MB install weight on constrained HA installs; adds startup time | NumPy arrays for pure numeric windowing; add Pandas optionally |
| AppDaemon | External process, separate install, not a custom integration | Native HA custom integration in `custom_components/` |

---

## Stack Patterns by Variant

**If SQLite (default HA install):**
- Standard Recorder query patterns work as-is
- Database file is `/config/home-assistant_v2.db`
- Keep queries short and bounded by time range to avoid lock contention

**If MariaDB/MySQL:**
- Same query patterns apply via SQLAlchemy abstraction
- Avoid schema-altering queries — use SELECT only
- Watch for InnoDB schema migration bugs (documented HA 2025.3→2025.4 issue)

**If running on Raspberry Pi 4 (4GB RAM):**
- Limit lookback window query to 30 days max per analysis pass
- Pre-aggregate states into hourly bins before feeding to sklearn
- Use OPTICS over DBSCAN; use MiniBatchKMeans over KMeans
- Run analysis at off-peak hours (e.g., 3am) via `async_track_time_interval`

**If running on NUC or x86 with 8GB+ RAM:**
- Same patterns apply but memory budget is less constrained
- Can expand lookback to 90 days without pre-aggregation
- Still use async_add_executor_job — async correctness is non-negotiable

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| scikit-learn 1.6.x | Python 3.13, HA 2025.2+ | First version with official Python 3.13 support |
| scikit-learn 1.7.x+ | Python 3.10+, HA 2025.2+ | Drops Python 3.9; safe to use on any current HA install |
| numpy 1.26.x | scikit-learn 1.6, Python 3.12–3.13 | Lower-bound version; numpy 2.x works with sklearn 1.6+ |
| pandas 2.x | numpy 1.26+, Python 3.13 | Optional; only if needed for resample/pivot |
| Lit 3.x | All modern browsers, HA frontend | HA itself moved from Polymer to Lit; Lit 3.x is current stable |

---

## Sources

- [HA Developer Docs — Creating Your First Integration](https://developers.home-assistant.io/docs/creating_component_index/) — integration structure, manifest fields (HIGH confidence)
- [HA Developer Docs — Integration Manifest](https://developers.home-assistant.io/docs/creating_integration_manifest/) — `iot_class`, `requirements`, `version` fields (HIGH confidence)
- [HA Developer Docs — Fetching Data / DataUpdateCoordinator](https://developers.home-assistant.io/docs/integration_fetching_data/) — coordinator pattern, async_timeout, subscriber model (HIGH confidence)
- [HA Developer Docs — Extending the WebSocket API](https://developers.home-assistant.io/docs/frontend/extending/websocket-api/) — `@websocket_command` decorator, `send_result`, `async_register_command` (HIGH confidence)
- [HA Developer Docs — Creating Custom Panels](https://developers.home-assistant.io/docs/frontend/custom-ui/creating-custom-panels/) — panel registration, Lit web component, `hass` object properties (HIGH confidence)
- [HA Community — Adding a Sidebar Panel to a HA Integration](https://community.home-assistant.io/t/how-to-add-a-sidebar-panel-to-a-home-assistant-integration/981585) — `panel_custom.async_register_panel`, `StaticPathConfig`, manifest dependencies (MEDIUM confidence)
- [HA Developer Docs — Deprecating async_run_job / async_add_job](https://developers.home-assistant.io/blog/2024/03/13/deprecate_add_run_job/) — removed in HA 2025.4 (HIGH confidence)
- [HA Core — history_stats data.py](https://github.com/home-assistant/core/blob/dev/homeassistant/components/history_stats/data.py) — canonical `get_instance().async_add_executor_job` pattern (HIGH confidence, source code)
- [scikit-learn PyPI](https://pypi.org/project/scikit-learn/) — v1.8.0 latest as of Dec 2025, Python 3.11–3.13 wheels (HIGH confidence)
- [scikit-learn — DBSCAN docs](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.DBSCAN.html) — O(n²) worst-case memory warning (HIGH confidence, official docs)
- [scikit-learn GitHub — DBSCAN memory issues #17650](https://github.com/scikit-learn/scikit-learn/issues/17650) — real-world OOM reports (MEDIUM confidence)
- [HA Community — Python 3.13 required for HA 2025.2](https://community.home-assistant.io/t/python-3-13-deprecated-ha/902801) — version requirement (MEDIUM confidence)
- [HA Community — Using scikit-learn with custom integration](https://community.home-assistant.io/t/how-to-use-scikit-learn-with-a-custom-intigration/536939) — manifest requirements pattern (MEDIUM confidence)
- [HACS — Publishing an Integration](https://www.hacs.xyz/docs/publish/integration/) — hacs.json, GitHub requirements, `home-assistant/brands` (MEDIUM confidence)
- [Lit.dev — Build for Production](https://lit.dev/docs/v1/tools/build/) — Rollup/Vite recommended bundler (HIGH confidence)
- [Automation creation mechanism](https://www.home-assistant.io/docs/automation/yaml/) — no native `automation.create` service; file-write + reload is the standard approach (MEDIUM confidence — based on multiple sources, no single authoritative statement)

---

*Stack research for: Home Assistant ML Pattern Mining Custom Integration*
*Researched: 2026-02-22*
