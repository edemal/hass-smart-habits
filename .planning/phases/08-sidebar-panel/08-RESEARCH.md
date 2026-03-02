# Phase 8: Sidebar Panel - Research

**Researched:** 2026-03-02
**Domain:** Home Assistant custom panel (panel_custom + LitElement web component + WebSocket frontend)
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

None — all design and implementation decisions are delegated to Claude's discretion. The only implicit constraint is: **the panel must feel like a native HA panel, not a custom app embedded in HA**.

### Claude's Discretion

Full discretion on all visual and interaction design decisions:

- **Card Layout & Information Density**: all card layout decisions; confidence display (bar, text, or both); information density (compact, detailed, or progressive disclosure); automation preview description placement; entity icon usage
- **Category Grouping & Ordering**: grouping style (collapsible sections, flat list with headers, or tabs); sort order within groups (confidence, recency, alphabetical); category naming for the three pattern types; empty state design
- **Accept/Dismiss/Customize Interaction**: action button presentation (icon buttons, action bar, swipe); customize UX (inline expansion, modal dialog, or detail view); post-accept feedback (toast + removal, success state); whether accept requires confirmation
- **Stale Automations Section**: placement relative to suggestions; available actions (informational only, disable, or disable + delete); information displayed per stale entry; staleness threshold visibility

### Deferred Ideas (OUT OF SCOPE)

None.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PANEL-01 | Dedicated sidebar panel accessible from HA navigation displays pattern suggestions with confidence scores | Panel registration via `panel_custom.async_register_panel` + StaticPathConfig + LitElement web component receiving `hass` property |
| PANEL-02 | User can accept, dismiss, or customize suggestions directly from the panel | `hass.callWS({ type: "smart_habits/accept_pattern" })` / `dismiss_pattern` / `preview_automation` + DOM event handlers in shadow DOM |
| PANEL-03 | Patterns are grouped by category (Morning Routines, Arrival Sequences, Device Chains) | Pure JS grouping logic on `get_patterns` result, rendered as header-separated sections |
| PANEL-04 | Panel displays stale automations that haven't fired recently | `stale_automations` array already returned by `ws_get_patterns` — render as separate section |
| PANEL-05 | Panel state updates immediately after accept/dismiss actions without requiring page reload | Optimistic local removal + coordinator refresh via `ws_accept_pattern` / `ws_dismiss_pattern` — no page reload because panel holds state in JS class properties |
</phase_requirements>

---

## Summary

Phase 8 is a pure frontend phase. The WebSocket API (Phase 7) is complete; this phase adds a dedicated sidebar panel that calls those existing commands. The work splits into two pieces: (1) Python side — register the panel and serve the JS file, and (2) JavaScript side — a single-file vanilla web component that calls `hass.callWS` for all data operations.

The correct HA mechanism for custom integration panels is `panel_custom.async_register_panel` called from `async_setup_entry`, combined with `hass.http.async_register_static_paths([StaticPathConfig(...)])` to serve the JS bundle. This pattern is confirmed by the official HA developer docs, the community guide from 2025, and the HACS/KNX reference integrations. The `register_static_path` API was removed in HA 2025.7, so only `async_register_static_paths` is valid for HA 2026.2.3.

For the JS panel, the no-build approach (importing LitElement from unpkg) works but CDN reliability is a risk. The recommended approach for a production custom integration is to write vanilla HTML/JS — a plain `HTMLElement` subclass — so there are zero external dependencies and no build tooling is required. The panel receives `hass`, `narrow`, `route`, and `panel` properties automatically from HA; `hass.callWS({type: "..."})` is the standard async WebSocket call method available on that object.

**Primary recommendation:** Single-file vanilla `HTMLElement` web component in `custom_components/smart_habits/frontend/smart-habits-panel.js`, served via `StaticPathConfig`, registered via `panel_custom.async_register_panel` in `async_setup_entry`, with `frontend.async_remove_panel` cleanup in `async_unload_entry`. No build tooling required.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `homeassistant.components.panel_custom` | built-in | Python panel registration API | The official HA mechanism for custom sidebar panels |
| `homeassistant.components.http.StaticPathConfig` | built-in (required since HA 2025.7) | Serve static JS files from integration directory | `register_static_path` (sync) was removed; only async variant is valid |
| `homeassistant.components.frontend` | built-in | `async_remove_panel` for cleanup on unload | Required for clean unload lifecycle |
| Vanilla `HTMLElement` (Web Component) | Browser built-in | Panel UI, no framework | Zero dependencies, no build step, works identically to LitElement panels |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| LitElement (via unpkg) | 3.x | Reactive templating inside panel | If reactive data binding becomes complex and build tooling is acceptable |
| HA CSS custom properties | built-in in HA | Theme-aware styling (`--primary-color`, `--card-background-color`, `--primary-text-color`, etc.) | Always — ensures native HA look |
| `ha-card` web component | built-in in HA | Native card container, inherits HA styling | Use for pattern and stale automation cards |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Vanilla HTMLElement | LitElement via unpkg | LitElement adds reactive properties but introduces CDN dependency and potential import instability |
| Vanilla HTMLElement | React (embed_iframe=true) | React requires a build step and iframe embedding — iframe panels behave differently (iOS height bugs in 2026) |
| Single JS file | TypeScript + esbuild | TypeScript gives type safety but adds build infrastructure; acceptable if project grows, overkill for this scope |

**Installation:** No npm packages required. All Python modules are HA built-ins.

```python
# manifest.json changes only:
"dependencies": ["http", "frontend", "panel_custom"]
```

---

## Architecture Patterns

### Recommended Project Structure

```
custom_components/smart_habits/
├── __init__.py              # add panel registration here
├── manifest.json            # add dependencies: ["http", "frontend", "panel_custom"]
├── frontend/
│   └── smart-habits-panel.js  # single-file web component
└── ... (existing files unchanged)
```

### Pattern 1: Panel Registration in async_setup_entry

**What:** Register static path and custom panel as part of integration setup.
**When to use:** Always — this is the only valid pattern for config-entry integrations.

```python
# __init__.py
import os
from homeassistant.components.http import StaticPathConfig
from homeassistant.components import frontend
from homeassistant.components.panel_custom import async_register_panel as _async_register_panel

PANEL_URL_BASE = "/smart_habits_frontend"
PANEL_WEBCOMPONENT = "smart-habits-panel"

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # ... existing coordinator setup ...

    # Register JS static path (idempotent guard recommended)
    frontend_path = os.path.join(os.path.dirname(__file__), "frontend")
    await hass.http.async_register_static_paths([
        StaticPathConfig(PANEL_URL_BASE, frontend_path, cache_headers=False)
    ])

    # Register sidebar panel (guard against duplicate registration)
    if "smart_habits" not in hass.data.get("frontend_panels", {}):
        await _async_register_panel(
            hass,
            webcomponent_name=PANEL_WEBCOMPONENT,
            frontend_url_path="smart_habits",
            sidebar_title="Smart Habits",
            sidebar_icon="mdi:brain",
            module_url=f"{PANEL_URL_BASE}/smart-habits-panel.js",
            embed_iframe=False,
            require_admin=False,
        )

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    frontend.async_remove_panel(hass, "smart_habits")
    return True
```

**Source:** [community.home-assistant.io – How to Add a Sidebar Panel](https://community.home-assistant.io/t/how-to-add-a-sidebar-panel-to-a-home-assistant-integration/981585) + [HA developer blog – async_register_static_paths](https://developers.home-assistant.io/blog/2024/06/18/async_register_static_paths/)

### Pattern 2: Vanilla Web Component Panel

**What:** Single `HTMLElement` subclass that owns its shadow DOM, holds loaded patterns in `this._data`, re-renders on state change, calls `hass.callWS` for all backend operations.
**When to use:** No framework, no build step needed, fits well for a focused single-page panel.

```javascript
// frontend/smart-habits-panel.js
class SmartHabitsPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._data = null;   // { patterns: [], accepted_patterns: [], stale_automations: [] }
    this._loading = false;
    this._error = null;
  }

  // HA sets this property whenever state changes
  set hass(hass) {
    const firstLoad = this._hass === null;
    this._hass = hass;
    if (firstLoad) {
      this._loadData();
    }
  }

  connectedCallback() {
    this._render();
  }

  async _loadData() {
    this._loading = true;
    this._render();
    try {
      this._data = await this._hass.callWS({ type: "smart_habits/get_patterns" });
      this._error = null;
    } catch (e) {
      this._error = e.message || "Failed to load patterns";
    }
    this._loading = false;
    this._render();
  }

  async _acceptPattern(pattern, overrides = {}) {
    // Optimistic: remove pattern from local state immediately (PANEL-05)
    this._data.patterns = this._data.patterns.filter(p => p !== pattern);
    this._render();
    try {
      await this._hass.callWS({
        type: "smart_habits/accept_pattern",
        entity_id: pattern.entity_id,
        pattern_type: pattern.pattern_type,
        peak_hour: pattern.peak_hour,
        secondary_entity_id: pattern.secondary_entity_id,
        ...overrides,
      });
    } catch (e) {
      // Re-fetch on error to restore consistent state
      await this._loadData();
    }
  }

  async _dismissPattern(pattern) {
    // Optimistic removal (PANEL-05)
    this._data.patterns = this._data.patterns.filter(p => p !== pattern);
    this._render();
    try {
      await this._hass.callWS({
        type: "smart_habits/dismiss_pattern",
        entity_id: pattern.entity_id,
        pattern_type: pattern.pattern_type,
        peak_hour: pattern.peak_hour,
        secondary_entity_id: pattern.secondary_entity_id,
      });
    } catch (e) {
      await this._loadData();
    }
  }

  _render() {
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          height: 100%;
          background: var(--primary-background-color);
          color: var(--primary-text-color);
          font-family: var(--paper-font-body1_-_font-family, Roboto, sans-serif);
          overflow-y: auto;
        }
        /* ... component styles using HA CSS variables ... */
      </style>
      ${this._loading ? '<div class="loading">Loading...</div>' : ''}
      ${this._error ? `<div class="error">${this._error}</div>` : ''}
      ${this._data ? this._renderContent() : ''}
    `;
    this._attachEventListeners();
  }

  _renderContent() {
    // Group patterns by type, render sections, render stale automations
    return `...`;
  }
}

customElements.define("smart-habits-panel", SmartHabitsPanel);
```

### Pattern 3: Pattern Grouping (PANEL-03)

**What:** Client-side grouping of the `patterns` array by `pattern_type`.
**Mapping from pattern_type to display category:**

| `pattern_type` value | Display category |
|---------------------|-----------------|
| `daily_routine` | "Morning Routines" (or time-appropriate "Daily Routines") |
| `temporal_sequence` | "Device Chains" |
| `presence_arrival` | "Arrival Sequences" |

```javascript
_groupPatterns(patterns) {
  const CATEGORY_LABELS = {
    daily_routine: "Daily Routines",
    temporal_sequence: "Device Chains",
    presence_arrival: "Arrival Sequences",
  };
  const groups = {};
  for (const p of patterns) {
    const label = CATEGORY_LABELS[p.pattern_type] || p.pattern_type;
    if (!groups[label]) groups[label] = [];
    groups[label].push(p);
  }
  // Sort within groups by confidence descending
  for (const label of Object.keys(groups)) {
    groups[label].sort((a, b) => b.confidence - a.confidence);
  }
  return groups;
}
```

### Pattern 4: Customize Flow (PANEL-02, AUTO-04)

**What:** When user clicks "Customize", call `smart_habits/preview_automation` to get description + automation dict, show an inline form allowing `trigger_hour` and `trigger_entities` overrides, then call `smart_habits/accept_pattern` with overrides.

```javascript
async _previewPattern(pattern, overrides = {}) {
  return await this._hass.callWS({
    type: "smart_habits/preview_automation",
    entity_id: pattern.entity_id,
    pattern_type: pattern.pattern_type,
    peak_hour: pattern.peak_hour,
    secondary_entity_id: pattern.secondary_entity_id,
    ...overrides,
  });
}
```

### Anti-Patterns to Avoid

- **Setting `hass` as a reactive Lit property directly:** Causes massive re-render on every state change. Instead, use `set hass(hass)` setter and load data once on first call.
- **Calling `register_static_path` (sync):** Removed in HA 2025.7. Use `async_register_static_paths` only.
- **Calling `frontend.async_register_built_in_panel`:** This is for built-in (core) panels. Custom integrations must use `panel_custom.async_register_panel`.
- **Using `embed_iframe: True` without reason:** iframe panels have known iOS height bugs (reported Jan 2026) and behave differently from inline panels. Only use for React-based panels.
- **Registering the panel in `async_setup` instead of `async_setup_entry`:** For config-entry integrations, registration should be in `async_setup_entry` and cleanup in `async_unload_entry`.
- **Bare import specifiers in panel JS** (`import { LitElement } from 'lit'`): Does not work without a bundler/import map. Use unpkg `?module` URLs or write vanilla HTMLElement.
- **No duplicate-registration guard:** Calling `async_register_panel` a second time will error. Guard with `if DOMAIN not in hass.data.get("frontend_panels", {})`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Serving JS files | Custom HTTP handler | `StaticPathConfig` + `async_register_static_paths` | HA's built-in static path system handles caching, headers, security |
| Panel navigation entry | Manually inject HTML into HA sidebar | `panel_custom.async_register_panel` | HA manages sidebar ordering, icon rendering, user permissions |
| WebSocket connection | Raw WebSocket in JS | `this._hass.callWS({type: "..."})` | `hass` object already has authenticated, auto-reconnecting connection |
| Theme-aware styling | Custom CSS color variables | HA CSS custom properties (`--primary-color`, `--card-background-color`, etc.) | Auto-adapts to user's selected HA theme |
| Pattern sorting/filtering | Full-featured state management library | Simple JS arrays + `_render()` method | Panel state is shallow (one endpoint, one data structure); no complex state machine needed |

**Key insight:** The `hass` object passed to the panel element is the single source of truth for the HA connection. Building anything around it (auth, reconnect, theme) is unnecessary and will break on HA updates.

---

## Common Pitfalls

### Pitfall 1: Duplicate Panel Registration on Reload

**What goes wrong:** `async_register_panel` throws an error or silently no-ops if the panel URL path is already registered. If the config entry is reloaded (e.g., after options change), `async_setup_entry` is called again.
**Why it happens:** HA does not auto-deregister panels on entry unload unless `async_remove_panel` is explicitly called.
**How to avoid:** (a) Call `frontend.async_remove_panel(hass, "smart_habits")` in `async_unload_entry`. (b) Add a guard check `if "smart_habits" not in hass.data.get("frontend_panels", {})` before registering.
**Warning signs:** `RuntimeError: Route already registered` or panel silently disappearing from sidebar after reload.

### Pitfall 2: JS File Not Found After Registration

**What goes wrong:** Panel loads but JS fails with 404. The sidebar entry appears but the panel shows blank or error.
**Why it happens:** `StaticPathConfig` path must be the directory (not the file), and `module_url` must be `f"{url_base}/{filename}.js"`. Mismatch between the two causes 404.
**How to avoid:** Verify `os.path.join(os.path.dirname(__file__), "frontend")` resolves to a real directory that exists at integration install time. Create the `frontend/` directory as part of the integration.
**Warning signs:** Browser dev tools show 404 for the JS file; panel shows "Unable to load panel".

### Pitfall 3: hass Property Not Set on First Render

**What goes wrong:** `connectedCallback()` fires before `set hass(hass)` — `this._hass` is null when initial render happens. Any `_hass.callWS()` call will throw.
**Why it happens:** HA sets element properties after the element is connected to the DOM.
**How to avoid:** Always null-check `this._hass` before using it. Trigger data load only from the `set hass(hass)` setter on the first call, not from `connectedCallback`.
**Warning signs:** `TypeError: Cannot read property 'callWS' of null`.

### Pitfall 4: Shadow DOM Style Isolation Breaking HA Component Rendering

**What goes wrong:** `ha-card` or other `ha-*` components used inside the shadow DOM do not render correctly — they appear unstyled or missing.
**Why it happens:** `ha-*` components are lazy-loaded. If the panel is the first page visited after HA loads, those components may not be registered yet.
**How to avoid:** For a simple panel, use standard HTML elements (`div`, `button`) styled with HA CSS variables rather than relying on `ha-card` or `mwc-button`. This eliminates the lazy-loading dependency.
**Warning signs:** Component renders fine after visiting the Lovelace dashboard but fails on direct URL load.

### Pitfall 5: cache_headers=True Causing Stale Panel During Development

**What goes wrong:** JS changes are not reflected in the panel even after HA restart, because the browser serves the cached file.
**Why it happens:** `StaticPathConfig(url, path, cache_headers=True)` tells HA to send aggressive cache headers.
**How to avoid:** Use `cache_headers=False` during development. For production, `True` is fine since users don't iterate on the JS file.
**Warning signs:** Old panel behavior persists after updating the JS file.

### Pitfall 6: manifest.json Missing Dependencies

**What goes wrong:** `panel_custom.async_register_panel` fails at import or runtime because `panel_custom` is not loaded when the integration starts.
**Why it happens:** HA resolves integration dependencies declared in `manifest.json`. If `panel_custom` is not in `dependencies`, it may not be loaded yet.
**How to avoid:** Add `"dependencies": ["http", "frontend", "panel_custom"]` to `manifest.json`.
**Warning signs:** `ImportError` or `AttributeError` when calling `async_register_panel`.

---

## Code Examples

Verified patterns from official sources and community guides:

### Minimal Python Registration (verified pattern)

```python
# Source: community.home-assistant.io/t/981585 + developers.home-assistant.io/blog/2024/06/18/
import os
from homeassistant.components.http import StaticPathConfig
from homeassistant.components import frontend
from homeassistant.components.panel_custom import async_register_panel as _panel_register

DOMAIN = "smart_habits"
PANEL_URL_BASE = "/smart_habits_frontend"
PANEL_COMPONENT = "smart-habits-panel"

# In async_setup_entry:
frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
await hass.http.async_register_static_paths([
    StaticPathConfig(PANEL_URL_BASE, frontend_dir, cache_headers=False)
])
if DOMAIN not in hass.data.get("frontend_panels", {}):
    await _panel_register(
        hass,
        webcomponent_name=PANEL_COMPONENT,
        frontend_url_path=DOMAIN,
        sidebar_title="Smart Habits",
        sidebar_icon="mdi:brain",
        module_url=f"{PANEL_URL_BASE}/smart-habits-panel.js",
        embed_iframe=False,
        require_admin=False,
    )

# In async_unload_entry:
frontend.async_remove_panel(hass, DOMAIN)
```

### manifest.json Changes

```json
{
  "domain": "smart_habits",
  "dependencies": ["http", "frontend", "panel_custom"],
  ...existing fields...
}
```

### hass.callWS Usage (all 5 commands)

```javascript
// Source: community.home-assistant.io/t/981585

// Load patterns
const data = await this._hass.callWS({ type: "smart_habits/get_patterns" });
// data = { patterns: [...], accepted_patterns: [...], stale_automations: [...] }

// Accept
const result = await this._hass.callWS({
  type: "smart_habits/accept_pattern",
  entity_id: "light.bedroom",
  pattern_type: "daily_routine",
  peak_hour: 7,
  secondary_entity_id: null,
  trigger_hour: 7,          // optional override
  trigger_entities: null,   // optional override
});
// result = { accepted: true, automation_id: "...", automation_alias: "..." }
// OR { accepted: true, automation_id: null, warning: "...", yaml_for_manual_copy: "..." }

// Dismiss
await this._hass.callWS({
  type: "smart_habits/dismiss_pattern",
  entity_id: "light.bedroom",
  pattern_type: "daily_routine",
  peak_hour: 7,
  secondary_entity_id: null,
});

// Preview (for customize flow)
const preview = await this._hass.callWS({
  type: "smart_habits/preview_automation",
  entity_id: "light.bedroom",
  pattern_type: "daily_routine",
  peak_hour: 7,
  secondary_entity_id: null,
  trigger_hour: 8,  // optional
});
// preview = { description: "Turns on bedroom at 08:00", automation_dict: {...} }

// Trigger scan
await this._hass.callWS({ type: "smart_habits/trigger_scan" });
```

### HA CSS Variables for Native Look

```css
/* Source: home-assistant.io/integrations/frontend + community theming docs */
:host {
  background: var(--primary-background-color);
  color: var(--primary-text-color);
}
.card {
  background: var(--card-background-color);
  border-radius: var(--ha-card-border-radius, 12px);
  box-shadow: var(--ha-card-box-shadow, none);
  padding: 16px;
  margin-bottom: 12px;
}
.category-header {
  color: var(--secondary-text-color);
  font-size: 12px;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  padding: 12px 0 4px;
}
.confidence-bar-fill {
  background: var(--primary-color);
  height: 4px;
  border-radius: 2px;
}
button.action-accept {
  background: var(--primary-color);
  color: var(--text-primary-color);
  border: none;
  border-radius: 4px;
  padding: 6px 12px;
  cursor: pointer;
}
button.action-dismiss {
  background: transparent;
  color: var(--secondary-text-color);
  border: 1px solid var(--divider-color);
  border-radius: 4px;
  padding: 6px 12px;
  cursor: pointer;
}
```

### Test Pattern for Python Registration (mock-based)

```python
# Source: derived from existing project conftest.py pattern
from unittest.mock import AsyncMock, MagicMock, patch

async def test_panel_is_registered(hass_mock):
    with patch(
        "homeassistant.components.panel_custom.async_register_panel",
        new_callable=AsyncMock,
    ) as mock_register:
        await async_setup_entry(hass_mock, mock_entry)
        mock_register.assert_called_once()
        call_kwargs = mock_register.call_args.kwargs
        assert call_kwargs["frontend_url_path"] == "smart_habits"
        assert call_kwargs["sidebar_icon"] == "mdi:brain"
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `hass.http.register_static_path(url, path, cache)` | `await hass.http.async_register_static_paths([StaticPathConfig(url, path, cache)])` | HA 2024.8 deprecated, **removed HA 2025.7** | Old code will crash on HA 2026.2.3 — must use new API |
| `frontend.async_register_built_in_panel` | `panel_custom.async_register_panel` | HA 0.115+ | Built-in variant is for HA core integrations only |
| Import LitElement from unpkg CDN | Vendor locally or use vanilla HTMLElement | Ongoing (2024-2025 instability reports) | CDN approach works but has reliability risk; vanilla is safer for production |
| `embed_iframe: True` for all custom panels | `embed_iframe: False` (default) unless using React | HA 2021+ best practice | iframe panels have known iOS height rendering bugs as of Jan 2026 |

**Deprecated/outdated:**
- `hass.http.register_static_path`: **removed** in HA 2025.7, will crash on target HA 2026.2.3
- `hass.components.frontend.async_register_built_in_panel`: for core panels only, not for custom integrations

---

## Open Questions

1. **`hass.data.get("frontend_panels", {})` guard reliability**
   - What we know: Multiple sources reference checking this dict to prevent duplicate registration; `async_remove_panel` in unload should make the guard unnecessary if unload is always called
   - What's unclear: The exact internal key structure of `hass.data["frontend_panels"]` is not officially documented — it could be a different internal key
   - Recommendation: Implement both the `async_remove_panel` in unload AND a try/except around `async_register_panel` in case it's called twice; log a warning rather than raising

2. **Panel rendering with null `yaml_for_manual_copy` fallback**
   - What we know: `ws_accept_pattern` returns `{ accepted: true, automation_id: null, yaml_for_manual_copy: "..." }` when the automation file write fails
   - What's unclear: Best UX for surfacing YAML in a sidebar panel (copy-to-clipboard button vs. pre element)
   - Recommendation: Show a collapsible `<pre>` block with a copy button; this is a rare edge case and does not need to be the primary design focus

3. **`async_register_static_paths` idempotency on config entry reload**
   - What we know: `async_register_panel` can be called at most once per URL path; static path registration behavior on duplicate URLs is less documented
   - What's unclear: Whether `async_register_static_paths` throws or silently ignores a second registration of the same URL path
   - Recommendation: Since `async_remove_panel` is called in unload, and static paths are typically permanent for the HA session, register the static path unconditionally but guard only the panel registration

---

## Sources

### Primary (HIGH confidence)

- [HA Developer Blog: Making http path registration async safe with `async_register_static_paths`](https://developers.home-assistant.io/blog/2024/06/18/async_register_static_paths/) — StaticPathConfig API, migration from `register_static_path`, confirmed removal in 2025.7
- [HA Developer Docs: Creating custom panels](https://developers.home-assistant.io/docs/frontend/custom-ui/creating-custom-panels/) — panel properties (hass, narrow, route, panel), LitElement example, `customElements.define`
- [HA Integration: panel_custom](https://www.home-assistant.io/integrations/panel_custom/) — `async_register_panel` parameters, `module_url`, `embed_iframe`, `sidebar_title`, `sidebar_icon`

### Secondary (MEDIUM confidence)

- [Community Guide: How to Add a Sidebar Panel to a HA Integration (2025)](https://community.home-assistant.io/t/how-to-add-a-sidebar-panel-to-a-home-assistant-integration/981585) — complete working `__init__.py` + JS code example, `hass.callWS` usage, `frontend_url_path` parameter, directory structure; verified against official docs
- [GitHub: home-assistant/home-assistant-js-websocket](https://github.com/home-assistant/home-assistant-js-websocket) — underlying WS library; confirms `hass.callWS` wraps this library
- [HA Community: Use of HA Web components in custom UI](https://community.home-assistant.io/t/use-of-ha-web-components-in-custom-ui/379296) — `ha-card`, `ha-icon-button` usage, lazy-loading caveat
- [HA Community: Lit-html import unreliability (2024)](https://community.home-assistant.io/t/lit-html-import-not-reachable-lately-in-custom-card/863814) — CDN import risk; motivates vanilla HTMLElement recommendation

### Tertiary (LOW confidence)

- [GitHub Issue: `hass-subpage` incorrect height on iOS in `ha-panel-custom` (Jan 2026)](https://github.com/home-assistant/frontend/issues/28868) — `embed_iframe: False` recommendation based on this bug; flagged for validation since iOS behavior may be irrelevant for this use case

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — `panel_custom.async_register_panel` and `StaticPathConfig` are official HA APIs; removal of `register_static_path` in 2025.7 is documented and confirmed
- Architecture: HIGH — the registration pattern is confirmed by multiple sources (official docs, community guide, HACS/KNX reference implementations); vanilla HTMLElement approach is straightforward
- Pitfalls: MEDIUM — most pitfalls derived from community reports and known HA issues; `hass.data["frontend_panels"]` key structure is LOW confidence (not officially documented)

**Research date:** 2026-03-02
**Valid until:** 2026-09-02 (6 months — HA frontend APIs are stable; `panel_custom` API unlikely to change)
