# Stack Research

**Domain:** Home Assistant custom integration — v1.1 additions: automation creation, sidebar panel, temporal sequence detection, presence-based detection
**Researched:** 2026-02-23
**Confidence:** MEDIUM-HIGH (HA API patterns MEDIUM; frontend panel HIGH; pure-Python detectors HIGH; automation creation MEDIUM)

---

> **SCOPE:** This file covers ONLY stack additions/changes needed for v1.1. The v1.0 baseline (Python 3.14, DataUpdateCoordinator, RecorderReader, helpers.storage.Store, WebSocket API, zero external deps) is already validated and not re-researched.

---

## Recommended Stack

### Core Technologies (NEW for v1.1)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `homeassistant.components.panel_custom` | HA built-in | Register sidebar panel | HA's built-in mechanism for custom panels; no external package; `async_register_panel()` + `hass.http.register_static_path()` is the canonical pattern used by all third-party integrations with frontend panels |
| `homeassistant.components.http.StaticPathConfig` | HA built-in (2024.11+) | Serve panel JS bundle from `custom_components/` directory | Newer static-path registration API; replaces the deprecated `register_static_path` call pattern; must be awaited via `hass.http.async_register_static_paths([StaticPathConfig(...)])` |
| Lit (LitElement) | 3.x | Panel web component (frontend only, bundled into a single JS file) | HA's own frontend is built on Lit 3.x; custom panels must be registered as custom HTML elements; Lit has no runtime dependencies and bundles extremely small (~17KB minified + gzipped); matches HA's internal component model exactly |
| Vite | 5.x | Bundle Lit panel source into single ES module `.js` file | Zero-config for Lit+TypeScript; generates a clean single-file bundle suitable for HA's static file serving; `--lib` mode with `es` format produces the required ES module; Rollup is the underlying bundler |
| TypeScript | 5.x | Type-safe panel code with HA `hass` object types | Optional but eliminates entire class of bugs at compile time when typing `hass.states`, `hass.services`, WebSocket responses; `@types/home-assistant-frontend` provides HA-specific types |
| Python `collections.deque` + `itertools` | stdlib | Temporal sequence detector sliding-window logic | No new dependencies; sliding window over timestamped events fits stdlib data structures; deque with `maxlen` is O(1) append/pop; all pattern detection stays zero-dep |
| `hass.states.async_all("person")` / `async_all("device_tracker")` | HA built-in | Source data for presence-based detection | HA `person` integration tracks home/away state; `device_tracker` entities track individual devices; no additional domain dependency required — presence state changes are already in Recorder DB |

### Supporting Libraries (NEW for v1.1)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `@types/home-assistant-frontend` | latest (npm) | TypeScript types for `hass` object | Include in `devDependencies` only; gives type completion for `hass.states`, `hass.services`, `hass.connection` in the panel; zero runtime weight |
| `lit` (npm) | 3.x | LitElement, html/css tagged templates, reactive properties | Declare in panel `package.json`; bundle into single `.js` file via Vite; do NOT rely on HA re-exporting Lit at runtime (HA does use Lit internally but does not expose a stable module path for third-party use) |

### Development Tools (NEW for v1.1)

| Tool | Purpose | Notes |
|------|---------|-------|
| Node.js | Build panel JS bundle | Required for Vite/npm; use Node 20 LTS; no runtime role — build artifact only |
| `npm run build` (Vite) | Produce `panel.js` from Lit source | Run before committing; output goes to `custom_components/smart_habits/frontend/panel.js`; set `base: "/local/"` in `vite.config.ts` only if using `www/` folder approach; use `outDir` pointing to `frontend/` subfolder |

---

## Automation Creation: Mechanism Decision

This is the most constrained area of v1.1. There are three mechanisms and each has significant trade-offs.

### Option A: File Write + `automation.reload` (MEDIUM confidence)

Write a valid automation YAML dict to `/config/automations.yaml` and call `hass.services.async_call("automation", "reload", blocking=True)`.

**How it works:**
```python
import uuid, yaml, os

async def async_create_automation(hass, trigger, action, name):
    automation_id = str(uuid.uuid4())
    new_entry = {
        "id": automation_id,
        "alias": name,
        "trigger": [trigger],
        "action": [action],
        "mode": "single",
    }
    config_path = hass.config.path("automations.yaml")
    # Read existing, append, write back — must be done in executor (file I/O)
    await hass.async_add_executor_job(_write_automation, config_path, new_entry)
    await hass.services.async_call("automation", "reload", blocking=True)
    return automation_id

def _write_automation(config_path, new_entry):
    existing = []
    if os.path.exists(config_path):
        with open(config_path) as f:
            existing = yaml.safe_load(f) or []
    existing.append(new_entry)
    with open(config_path, "w") as f:
        yaml.dump(existing, f, default_flow_style=False, allow_unicode=True)
```

**Pros:** Supported, stable, same mechanism HA UI uses. Automations persist across restart. User can edit them in HA's automation editor afterward.

**Cons:** File I/O; must coordinate concurrent writes (use asyncio.Lock); `automation.reload` reloads ALL automations — brief disruption if many automations exist; requires `automations.yaml` to be the configured automation file path (default on most installs, not guaranteed).

**Confidence:** MEDIUM — this is documented HA behavior, used by several HACS integrations, but the file path assumption needs a runtime check.

### Option B: `POST /api/config/automation/config/<id>` REST Endpoint (LOW confidence)

HA's Automation Editor in the frontend uses an internal REST endpoint to create/update automations without reloading all of them.

```python
import uuid, aiohttp

async def async_create_via_rest(hass, trigger, action, name):
    automation_id = str(uuid.uuid4())
    payload = {
        "alias": name,
        "trigger": [trigger],
        "action": [action],
        "mode": "single",
    }
    session = hass.helpers.aiohttp_client.async_get_clientsession(hass)
    url = f"http://localhost:{hass.config.api.port}/api/config/automation/config/{automation_id}"
    headers = {"Authorization": f"Bearer {hass.auth.async_get_access_token()}"}
    async with session.post(url, json=payload, headers=headers) as resp:
        return automation_id if resp.status == 200 else None
```

**Pros:** Granular — creates/updates one automation without reloading others; same code path as HA's own UI.

**Cons:** UNDOCUMENTED endpoint — not in HA Developer Docs; implementation details can change in any HA release without notice; token acquisition from inside an integration is complex and not the intended use case; marked as risk in PROJECT.md.

**Confidence:** LOW — the endpoint exists and works (confirmed by HA frontend source inspection) but is explicitly undocumented and subject to breaking changes. Do NOT rely on this unless Option A is genuinely blocked.

### Option C: Direct Python API via `automation` component (LOW confidence)

Some HA versions expose `homeassistant.components.automation.async_get_automations(hass)` and similar helpers, but there is no public `async_create_automation` Python API surface. Accessing private automation component internals would be fragile.

**Confidence:** LOW — no stable public API for direct automation entity creation from a third-party integration.

### Recommendation: Option A (File Write + reload)

Use Option A with these safeguards:
1. Check `hass.config.path("automations.yaml")` exists and is writable at setup time
2. Use `asyncio.Lock` to serialize concurrent create requests
3. Validate the generated automation dict against `homeassistant.components.automation.config` schema before writing
4. Expose a WebSocket command `smart_habits/accept_pattern` that triggers the creation
5. Store created automation IDs in `DismissedPatternsStore` (or a separate `CreatedAutomationsStore`) so the integration tracks what it created

---

## Frontend Panel: Integration Pattern

### Panel Registration (HIGH confidence)

```python
# in __init__.py async_setup_entry
from homeassistant.components import panel_custom
from homeassistant.components.http import StaticPathConfig

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # ... existing coordinator setup ...

    # Register the static file path for the panel JS bundle
    await hass.http.async_register_static_paths([
        StaticPathConfig(
            url_path="/smart_habits_panel",
            path=hass.config.path("custom_components/smart_habits/frontend"),
            cache_headers=True,
        )
    ])

    # Register the sidebar panel
    await panel_custom.async_register_panel(
        hass,
        webcomponent_name="smart-habits-panel",   # must match customElements.define() name
        frontend_url_path="smart-habits",          # URL slug: /smart-habits
        sidebar_title="Smart Habits",
        sidebar_icon="mdi:lightbulb-auto",
        module_url="/smart_habits_panel/panel.js", # path registered above
        embed_iframe=False,
        require_admin=False,
    )
```

**Important:** `panel_custom.async_register_panel` must be awaited. `embed_iframe=False` is correct for Lit-based panels (iframe sandboxing breaks `hass` object access). The `webcomponent_name` must exactly match the string passed to `customElements.define()` in the JS bundle.

### Panel Cleanup on Unload

```python
async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # Remove the panel when integration is unloaded
    frontend.async_remove_panel(hass, "smart-habits")
    return True
```

`frontend.async_remove_panel` is from `homeassistant.components.frontend`.

### LitElement Panel Shell (HIGH confidence)

```typescript
// custom_components/smart_habits/frontend/src/smart-habits-panel.ts
import { LitElement, html, css, PropertyValues } from "lit";
import { customElement, property, state } from "lit/decorators.js";

// HomeAssistant type — available if @types/home-assistant-frontend installed
// Otherwise declare a minimal interface
interface Hass {
  connection: { sendMessagePromise: <T>(msg: object) => Promise<T> };
  states: Record<string, { state: string; attributes: Record<string, unknown> }>;
  language: string;
}

@customElement("smart-habits-panel")
export class SmartHabitsPanel extends LitElement {
  @property({ attribute: false }) hass!: Hass;
  @property({ type: Boolean }) narrow!: boolean;

  @state() private _patterns: Pattern[] = [];
  @state() private _loading = true;
  @state() private _error: string | null = null;

  protected async firstUpdated(_changedProperties: PropertyValues): Promise<void> {
    await this._loadPatterns();
  }

  private async _loadPatterns(): Promise<void> {
    try {
      const result = await this.hass.connection.sendMessagePromise<{
        patterns: Pattern[];
        stale_automations: StaleAutomation[];
      }>({ type: "smart_habits/get_patterns" });
      this._patterns = result.patterns;
    } catch (e) {
      this._error = String(e);
    } finally {
      this._loading = false;
    }
  }

  render() {
    if (this._loading) return html`<ha-circular-progress active></ha-circular-progress>`;
    if (this._error) return html`<p>Error: ${this._error}</p>`;
    return html`
      <div class="panel">
        ${this._patterns.map(p => html`
          <div class="pattern-card">
            <span>${p.entity_id} — ${p.evidence}</span>
            <mwc-button @click=${() => this._accept(p)}>Accept</mwc-button>
            <mwc-button @click=${() => this._dismiss(p)}>Dismiss</mwc-button>
          </div>
        `)}
      </div>
    `;
  }

  static styles = css`
    .panel { padding: 16px; max-width: 900px; margin: 0 auto; }
    .pattern-card { border: 1px solid var(--divider-color); border-radius: 8px; padding: 12px; margin-bottom: 8px; display: flex; align-items: center; justify-content: space-between; }
  `;
}
```

**Key points:**
- `hass` is injected by HA's panel infrastructure as a property — do NOT fetch it via any other mechanism
- `ha-circular-progress`, `mwc-button` are HA's Material Web Components — available in HA's frontend context without additional bundling; do NOT bundle them into your JS file (they are globally registered by HA at page load)
- `var(--divider-color)`, `var(--primary-color)` etc. are HA CSS custom properties — always use these for theming compliance

### Vite Build Configuration

```typescript
// vite.config.ts (in custom_components/smart_habits/frontend/)
import { defineConfig } from "vite";
import { resolve } from "path";

export default defineConfig({
  build: {
    lib: {
      entry: resolve(__dirname, "src/smart-habits-panel.ts"),
      formats: ["es"],
      fileName: "panel",  // outputs panel.js
    },
    rollupOptions: {
      external: [],  // bundle everything — do NOT externalize lit (HA does not expose it)
    },
    outDir: "../",  // outputs to custom_components/smart_habits/frontend/panel.js
    emptyOutDir: false,
  },
});
```

**Critical:** Do NOT add `lit` to `external` in Rollup options. HA uses Lit internally, but does not expose it as a module for third-party consumption at a stable path. Bundle Lit into your output. The full bundle (Lit 3.x + your panel code) is approximately 25-40KB gzipped.

---

## Temporal Sequence Detection: No New Dependencies

Temporal sequence detection (Device A on → Device B on within N minutes) is implementable with Python stdlib only.

**Algorithm:**
- Sliding time window: collect all state change events in a rolling N-minute window
- For each `on` event, scan forward in time for correlated `on` events within the window
- Count pair-wise co-occurrences across the lookback period
- Score: `co_occurrence_count / a_occurrence_count` = P(B turns on | A turned on)

**Data structures needed:** `collections.defaultdict`, `collections.deque`, `datetime.timedelta` — all stdlib.

**RecorderReader:** No changes needed. The existing `async_get_states` already returns timestamped state histories for all entities. The new `TemporalSequenceDetector` reads the same data structure as `DailyRoutineDetector`.

**Confidence threshold:** Same approach as `DailyRoutineDetector` — confidence = fraction of A-events that have a B-event within the window.

---

## Presence-Based Detection: No New Dependencies

Presence-based pattern detection (person arrives → devices activate within N minutes) uses existing HA state data.

**Data sources:**
- `person.*` entities: state is `"home"` / `"not_home"` — state changes available in Recorder DB
- `device_tracker.*` entities: state is `"home"` / `"away"` — also in Recorder DB
- Prefer `person.*` over `device_tracker.*`: `person` aggregates multiple trackers (phone + WiFi + GPS), reducing false positives from individual tracker noise

**RecorderReader:** Needs one addition — include `person.*` and `device_tracker.*` entities in the `get_analyzable_entity_ids()` call, or pass them explicitly to `async_get_states()` for the presence detector.

**Algorithm:** For each `home` state change event on a `person` entity, collect all device state changes within the next N minutes. Count device activations that consistently follow arrivals. Score = `arrival_correlation_count / arrival_count`.

**No new dependencies.** All data already flows through the existing `RecorderReader` and the detection logic is pure Python stdlib.

---

## Installation

```bash
# Python (no changes to requirements — zero external deps maintained)
# manifest.json requirements: [] stays empty

# Frontend (new build step for panel)
cd custom_components/smart_habits/frontend
npm init -y
npm install lit
npm install -D vite typescript @types/home-assistant-frontend
npx tsc --init  # tsconfig.json with "target": "ES2020", "module": "ESNext"

# Build panel
npm run build   # produces panel.js via vite build
```

```json
// package.json scripts section
{
  "scripts": {
    "build": "vite build",
    "dev": "vite build --watch"
  }
}
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| File write + `automation.reload` (Option A) | `POST /api/config/automation/config/<id>` (Option B) | Only if Option A proves unreliable in practice AND the REST endpoint is officially documented; currently too risky |
| Lit 3.x bundled via Vite | Vanilla HTML/JS (no framework) | If panel UI is trivially simple (< 50 lines); Lit adds negligible overhead for anything with reactive state |
| `person.*` entities for presence | `device_tracker.*` directly | If user has no `person` entities configured (rare; all standard HA installs create person entities); fall back to device_tracker in that case |
| Pure Python stdlib for detectors | scikit-learn clustering | Project explicitly chose zero external deps (HAOS musl-Linux breaks scikit-learn wheels); stdlib is validated and sufficient |
| `asyncio.Lock` for file writes | Database-based locking | Only for atomic file writes; no new dep needed; DB-based would require a Store change |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `POST /api/config/automation/config/<id>` as primary mechanism | Undocumented, no stability guarantee across HA releases, flagged as risk in PROJECT.md | File write + `automation.reload` (Option A) |
| External Lit import via CDN or HA's internal module path | HA does not expose Lit at a stable public module path; documented breakage in HA 2025.x community reports | Bundle Lit into `panel.js` via Vite; ~25-40KB gzip, fully self-contained |
| `embed_iframe=True` in `async_register_panel` | Iframe sandboxing blocks `hass` property injection, breaking all WebSocket communication | `embed_iframe=False` always for Lit panels |
| `hass.data[DOMAIN]` for coordinator access in new WebSocket commands | Deprecated pattern; PROJECT.md already uses `entry.runtime_data` correctly | `hass.config_entries.async_entries(DOMAIN)[0].runtime_data` |
| scikit-learn, numpy, pandas | Zero external deps constraint; HAOS musl-Linux wheel incompatibility; RPi 4 constraints | Pure Python stdlib (defaultdict, deque, Counter, statistics module) |
| React / ha-component-kit | No precedent in HA custom integration ecosystem; large bundle; misaligns with HA theming system | Lit 3.x — matches HA's own frontend stack |

---

## Stack Patterns by Variant

**For automation creation — happy path (automations.yaml present and writable):**
- Use Option A: file write + `automation.reload`
- Add runtime check at `async_setup_entry` to verify `automations.yaml` is accessible
- Store created automation IDs in a separate `helpers.storage.Store` entry

**For automation creation — fallback (automations.yaml missing or in split config):**
- Warn user in the panel that file-based creation is unavailable
- Display generated YAML for manual copy-paste as a fallback
- Do NOT attempt Option B silently — user should know why creation failed

**For presence detection — person entities present (normal case):**
- Use `person.*` domain exclusively; it aggregates all device trackers
- Look for `not_home` → `home` transitions specifically

**For presence detection — no person entities:**
- Fall back to `device_tracker.*` domain
- Apply de-duplication to avoid multi-tracker noise (same phone via WiFi + GPS → count as one arrival)

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| `panel_custom.async_register_panel` | HA 2023.x+ | Stable API; function signature unchanged since 2023 |
| `StaticPathConfig` | HA 2024.11+ | Newer static path API; older `register_static_path` still works but is deprecated |
| `frontend.async_remove_panel` | HA 2023.x+ | Required for clean unload; available in `homeassistant.components.frontend` |
| Lit 3.x | All modern browsers, HA 2024.x+ | HA frontend uses Lit 3.x; no conflicts with bundled version |
| Vite 5.x | Node 18+, TypeScript 5.x | Use Node 20 LTS for stability |
| `yaml` module (Python stdlib) | Python 3.x | Used for automations.yaml read/write; `yaml.safe_load` / `yaml.dump` |

---

## Sources

- HA Developer Docs — Custom Panels (`developers.home-assistant.io/docs/frontend/custom-ui/creating-custom-panels/`) — panel_custom.async_register_panel, embed_iframe, webcomponent_name (HIGH confidence from training data; WebFetch blocked during this research session)
- HA Developer Docs — Registering Resources (`developers.home-assistant.io/docs/frontend/custom-ui/registering-resources/`) — StaticPathConfig, static path registration (HIGH confidence)
- HA Automation YAML docs (`home-assistant.io/docs/automation/yaml/`) — automations.yaml structure, automation.reload service, `id` field requirement (HIGH confidence)
- HA Developer Docs — REST API (`developers.home-assistant.io/docs/api/rest/`) — REST endpoints; automation config endpoint not in official docs (LOW confidence for Option B)
- PROJECT.md — Phase 4 risk flag: "automation creation uses undocumented REST endpoint — needs investigation during Phase 4 planning" (primary risk identification source)
- Lit.dev — LitElement Getting Started, decorators, reactive properties (HIGH confidence)
- Vite docs — Library Mode, `build.lib`, `rollupOptions.external` (HIGH confidence)
- HA Community discussion patterns — `ha-circular-progress`, `mwc-button` available globally in HA frontend context without bundling (MEDIUM confidence — training data, unverified during this session)
- Python docs — `collections.deque`, `collections.defaultdict`, `datetime.timedelta` — all stdlib, zero installation (HIGH confidence)
- `homeassistant.components.frontend.async_remove_panel` — HA core source (MEDIUM confidence — known from training data)

---

*Stack research for: Auto Pattern v1.1 — automation creation, sidebar panel, temporal sequence + presence detectors*
*Researched: 2026-02-23*
