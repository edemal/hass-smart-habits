# Project Research Summary

**Project:** Smart Habits — Home Assistant Custom Integration (v1.1)
**Domain:** Home Assistant custom integration — behavioral pattern mining, automation creation, LitElement sidebar panel
**Researched:** 2026-02-23
**Confidence:** MEDIUM-HIGH

## Executive Summary

Smart Habits v1.1 extends a working v1.0 integration (daily routine detection, RecorderReader, coordinator, dismiss storage, WebSocket API) with three new pattern detector types, one-click automation creation, and a dedicated sidebar panel. The v1.0 architecture is well-validated and acts as a stable foundation — all new work builds on proven patterns without replacing them. The recommended approach is bottom-up: write the two new pure-Python detectors first (they have zero HA lifecycle coupling), wire them into the coordinator, then tackle automation creation via HA's internal file-write mechanism, and finally build the LitElement panel that ties everything together in a user-facing UI.

The highest-risk element is automation creation. The STACK.md research resolves the mechanism decision: use Option A (File Write + `automation.reload`) — the same mechanism HA's own UI uses. This requires writing a valid automation YAML dict to `automations.yaml` and calling `hass.services.async_call("automation", "reload")`. Automations created this way persist across restarts and are editable in HA's automation editor afterward. The risk is manageable with three safeguards: verify the `automations.yaml` path is writable at setup time, use `asyncio.Lock` to serialize concurrent writes, and verify the created automation actually appears in HA state after the reload. Option B (undocumented REST endpoint `POST /api/config/automation/config/<id>`) is documented as a fallback only — it is community-verified stable but officially undocumented and subject to change.

The panel is the only user-facing surface and its quality directly determines perceived product value. Using Lit 3.x bundled via Vite into a single self-contained JS file is the right approach — it matches HA's own frontend stack, produces a ~25-40KB gzip bundle with no external CDN dependencies, and the `panel_custom.async_register_panel` registration API is stable and well-documented. The two new detectors (temporal sequence and presence-based) both use pure Python stdlib — no new dependencies added — and operate on the same state history dict already returned by `RecorderReader`. Performance on Raspberry Pi 4 is the primary scaling concern: the temporal sequence detector must use a sliding deque algorithm (O(N×W)), not naive nested loops (O(n²)), which would time out on real installs with more than 20 entities.

## Key Findings

### Recommended Stack

The v1.0 stack (Python 3.14, DataUpdateCoordinator, RecorderReader, helpers.storage.Store, WebSocket API, zero external deps) is unchanged. All v1.1 additions are either HA built-ins or compile-time-only frontend tooling.

**Core technologies:**
- `panel_custom.async_register_panel` + `StaticPathConfig`: Sidebar panel registration — HA's canonical mechanism, stable since 2023, must run in `async_setup_entry` (not `configuration.yaml`); requires HA 2024.11+ for `StaticPathConfig`
- Lit 3.x (bundled via Vite): LitElement web component for the panel — matches HA's own frontend stack; bundle into single `panel.js` via Vite; do NOT load from CDN or assume HA exposes Lit at a stable module path (~25-40KB gzip, fully self-contained)
- Vite 5.x + TypeScript 5.x: Build tooling for the panel JS — build-time only, no runtime role; Node 20 LTS; output to `custom_components/smart_habits/frontend/panel.js`
- `collections.deque` + `itertools` (stdlib): Temporal sequence detector sliding-window — zero new dependencies, mandatory O(N×W) algorithm
- `hass.states.async_all("person")`: Presence detection data source — prefer `person.*` over `device_tracker.*`; `person` aggregates multiple trackers with debouncing, reducing flap noise
- File Write + `automation.reload` (Option A): Automation creation — same mechanism as HA UI; requires `asyncio.Lock` for concurrent writes and a runtime check that `automations.yaml` is writable

**Critical constraints:**
- `StaticPathConfig` requires HA 2024.11+ (older `register_static_path` still works but is deprecated — declare minimum HA version in `manifest.json`)
- Lit 3.x must be bundled — HA uses Lit internally but does not expose it at a stable public path for third-party use
- `embed_iframe=False` is mandatory for Lit panels — iframe sandboxing blocks `hass` property injection
- Zero external Python dependencies — maintained from v1.0; HAOS musl-Linux wheel incompatibility rules out scikit-learn, numpy, pandas

### Expected Features

**Must have (table stakes — v1.1 is incomplete without these):**
- One-click accept → create real HA automation (not YAML export, not redirect to Settings)
- Accepted patterns removed from suggestion list immediately and permanently
- Temporal sequence detection — Device A on → Device B on within configurable window
- Presence-based detection — person arrives → devices activate within window
- Sidebar panel with pattern cards, confidence scores, accept/dismiss/customize actions
- Human-readable automation preview before accepting ("Turns on kitchen lights at 07:05 every weekday")
- Customize-before-accept — panel form lets user adjust trigger time, entities, window
- Stale automation list displayed in panel (data already exists in coordinator from v1.0)

**Should have (differentiators — add to v1.1 if feasible):**
- Pattern category grouping in panel — "Morning Routines," "Arrival Sequences," "Device Chains" (panel-layer only, no backend changes)
- Configurable sequence detection window (5 min vs. 15 min per user preference — one parameter on `TemporalSequenceDetector`)
- Presence detection with multiple downstream entities per arrival event

**Defer to v2+:**
- Multi-entity routine clustering ("morning routine" as one block)
- Learn from dismissals (implicit training / fingerprint weighting)
- Lovelace card variant of the panel (duplicates sidebar lifecycle, no additive UX value)
- Opt-in notification push when new patterns found
- State correlation patterns (temperature → heater) — different data model needed

**Anti-features to avoid:**
- Auto-accept all high-confidence patterns (wrong automations fire at 3am; users lose trust immediately)
- YAML export / paste workflow (defeats the value proposition; competitors already do this poorly)
- Real-time pattern update on every state change (fires hundreds of times per minute; Pi 4 cannot sustain)
- Registering the panel from `configuration.yaml` (breaks integration lifecycle; panel persists after integration removal)

### Architecture Approach

The architecture is a layered Python integration with a frontend JS component communicating over WebSocket. All CPU-bound detection runs in a single executor job (`hass.async_add_executor_job`) using a unified detector interface — one thread context switch for all three detectors, no GIL-contention waste from separate jobs. The `detectors/` subpackage isolates each detector for independent testing. `automation_creator.py` is a standalone module wrapping the file-write + reload mechanism, isolating the highest-risk component so it can be tested and updated without touching WebSocket handlers. The panel JS is a self-contained LitElement web component registered programmatically in `async_setup_entry`.

**Major components (status):**
1. `detectors/temporal.py` (NEW) — `TemporalSequenceDetector`: sliding-window co-activation, O(N×W) algorithm, pure stdlib
2. `detectors/presence.py` (NEW) — `PresencePatternDetector`: arrival/departure correlation with mandatory dwell-time filter; prefers `person.*` domain
3. `automation_creator.py` (NEW) — translates `DetectedPattern` to HA automation dict; file write + `automation.reload`; `asyncio.Lock`; post-creation verification via `hass.states.async_get`
4. `coordinator.py` (MODIFY) — runs all three detectors in single executor job; loads `AcceptedPatternsStore`; filters both dismissed and accepted patterns
5. `websocket_api.py` (MODIFY) — adds `accept_pattern` and `get_accepted` commands with idempotency guard (`hass.data` flag prevents double-registration on config entry reload)
6. `storage.py` (MODIFY) — adds `AcceptedPatternsStore` (new key `smart_habits.accepted`); `DismissedPatternsStore` storage version bump for fingerprint extension
7. `models.py` (MODIFY) — adds `TemporalPattern`, `PresencePattern`, `AcceptedPattern` dataclasses; extends `DetectedPattern.fingerprint` with `secondary_entity_id`
8. `panel/smart-habits-panel.js` (NEW) — LitElement web component; bundled with Vite; registered via `panel_custom`
9. `__init__.py` + `manifest.json` (MODIFY) — panel registration in `async_setup_entry`; add `frontend`, `panel_custom` to `after_dependencies`

### Critical Pitfalls

1. **Automation file write succeeds but automation never appears** — always call `automation.reload` after writing to `automations.yaml`, then verify `hass.states.async_get(automation_entity_id)` is not None within a short timeout (2-3 seconds); surface a clear error to the user if verification fails; never declare success based only on the file write completing without error

2. **Automation ID collision overwrites existing user automations** — check `hass.states.async_get()` for the derived automation entity ID before writing; prefix all Smart Habits automation IDs with `smart_habits_` plus a short UUID suffix; never silently overwrite; log a warning and surface the conflict to the user

3. **Temporal sequence detector O(n²) performance explosion on large installs** — never use nested entity-pair loops; use sorted timeline + sliding deque (O(N×W)); add a mandatory performance test: 50 entities × 30 days must complete in under 10 seconds; a pre-filter (only test pairs co-active on the same calendar day) cuts 80-90% of candidate pairs

4. **Presence detector flap noise from `device_tracker` entities** — prefer `person.*` domain exclusively (it aggregates and debounces trackers); apply `MIN_ARRIVAL_DWELL_SECONDS = 300` filter — a `not_home` → `home` transition that reverts within 5 minutes is a flap, not an arrival; only `person` entities that stay `home` for at least 5 minutes are counted as genuine arrivals

5. **`DetectedPattern` fingerprint insufficient for new pattern types** — extend `DetectedPattern` with `secondary_entity_id: str | None = None`; update `DismissedPatternsStore` fingerprint, WebSocket schema, and bump `STORAGE_VERSION` in the same change; write migration for existing dismissed records (add `None` for `secondary_entity_id`); do this before writing the detectors

6. **LitElement panel blank due to `webcomponent_name` mismatch or missing `hass` property declaration** — `webcomponent_name` in `async_register_panel` must match `customElements.define()` string exactly (byte-for-byte); declare `hass: { type: Object }` in `static get properties()`; set `embed_iframe=False`; establish a non-blank stub panel before building any UI features

7. **WebSocket command double-registration on config entry reload** — guard `async_register_commands` with an `hass.data` flag so it runs once per HA instance lifetime; use `vol.Optional()` with defaults for new fields on existing commands (not `vol.Required()`) to maintain backward compatibility

## Implications for Roadmap

Research confirms the ARCHITECTURE.md build order: bottom-up, each layer independently tested before wiring the next. The phase structure maps directly to the architectural dependency chain — each phase's output is a required input for the next.

### Phase 1: Temporal Sequence Detector

**Rationale:** Pure Python, zero HA lifecycle coupling; fastest to build and unit-test in isolation; validates the sliding-deque algorithm and establishes the `detectors/` subpackage structure before any HA wiring; also the right phase to extend the `DetectedPattern` fingerprint since that model change must precede all three new phases
**Delivers:** `TemporalSequenceDetector` class with full unit test coverage; `TemporalPattern` dataclass; `detectors/` subpackage (`__init__.py`, `daily_routine.py` moved, `temporal.py` new); `DetectedPattern.secondary_entity_id` fingerprint extension with `STORAGE_VERSION` bump and migration
**Addresses:** Temporal sequence detection (P1 table stakes); fingerprint extension (cross-cutting prerequisite)
**Avoids:** Pitfall 3 (O(n²) explosion) — sliding-deque algorithm is the only acceptable implementation; Pitfall 5 (fingerprint collision) — model extended before detectors are wired

### Phase 2: Presence Pattern Detector

**Rationale:** Same interface contract as Phase 1 (`detect(states, lookback_days) -> list[Pattern]`); depends on `detectors/` subpackage and fingerprint extension from Phase 1; validates arrival dwell-time filter in pure Python before wiring to coordinator
**Delivers:** `PresencePatternDetector` class with unit tests including flap-noise fixture; `PresencePattern` dataclass; dwell-time filter (`MIN_ARRIVAL_DWELL_SECONDS = 300`) proven in isolation; fallback to `device_tracker.*` when no `person.*` entities exist
**Addresses:** Presence-based detection (P1 table stakes)
**Avoids:** Pitfall 4 (flap noise) — dwell-time filter is a first-class requirement of this phase, not an afterthought; using `person.*` as primary domain is enforced from the start

### Phase 3: Coordinator Multi-Detector Wiring + Acceptance Store

**Rationale:** Requires both new detectors to exist; establishes the merged data model and acceptance persistence that automation creation and the panel both depend on; the `AcceptedPatternsStore` and coordinator filter must exist before `ws_accept_pattern` can be implemented
**Delivers:** Coordinator runs all three detectors in single executor job (`_run_all_detectors`); `AcceptedPatternsStore` added to storage; coordinator filters dismissed + accepted patterns; `coordinator.data["accepted_patterns"]` key added; storage version migration tested end-to-end
**Addresses:** Accepted patterns filtered from list (P1 fast-follow on acceptance); storage version bump and migration for fingerprint extension
**Avoids:** Anti-pattern of running each detector in a separate executor job (GIL means no parallelism; one thread switch is optimal); Pitfall 5 migration tested here before acceptance flow is built on top

### Phase 4: AutomationCreator + Accept WebSocket Command

**Rationale:** Automation creation is the highest-risk feature; isolating it to a dedicated phase limits blast radius if the file-write mechanism needs revision; the REST endpoint risk must be resolved before building any UI that depends on it; verifying the full accept roundtrip (write → reload → verify state exists → restart HA → verify persists) is mandatory before Phase 5
**Delivers:** `automation_creator.py` with `build_automation_dict()` (synchronous, testable without HA) and `async_create_automation()` (async, wraps file write + reload + verification); `smart_habits/accept_pattern` and `smart_habits/get_accepted` WS commands with idempotency guard; `AutomationBuilder.to_description()` for human-readable preview; post-creation verification against HA state; graceful fallback (display generated YAML for manual copy) if `automations.yaml` is not writable
**Addresses:** One-click accept → create real automation (P1); human-readable preview (P1); customized accept (P1)
**Avoids:** Pitfall 1 (silent creation failure — verify-after-create is mandatory); Pitfall 2 (ID collision check before every write); Pitfall 7 (WS double-registration guard added here); Pitfall 10 (concurrent writes — `asyncio.Lock` in `automation_creator.py`)

### Phase 5: Sidebar Panel (LitElement)

**Rationale:** Panel depends on all backend WebSocket commands being stable; frontend iteration is slowest to test (requires browser + HA restart cycles); building last means the API contract does not change mid-panel-development; the pre-built `panel.js` must be committed to the repo for HACS distribution
**Delivers:** LitElement web component bundled via Vite; panel registration in `async_setup_entry` with cleanup on unload; pattern cards with confidence + evidence; accept/dismiss/customize actions; stale automation list; fetch-after-mutate pattern for immediate state updates after every action; HA CSS custom properties for theming; friendly names via `hass.states.get(entity_id).attributes.get("friendly_name", entity_id)`
**Addresses:** Sidebar panel (P1 table stakes); stale automation display in panel (P1 — UI only, data already in coordinator); pattern category grouping (P2 — low cost, panel-layer only)
**Avoids:** Pitfall 6 (panel blank — establish non-blank stub before building features); Pitfall 4 (missing `hass` property declaration — verify `this.hass` defined in `connectedCallback` before any WS call); Pitfall 9 (stale panel state — fetch-after-mutate built into every action handler); Anti-pattern 5 (CDN LitElement import — Vite bundles Lit into output)

### Phase Ordering Rationale

- Phases 1-2 (detectors) before Phase 3 (coordinator) because `_run_all_detectors` must import all three detector classes
- The fingerprint extension (`secondary_entity_id`) is in Phase 1 because it is a prerequisite for correct dismiss/accept behavior in Phases 3-5; doing it later requires retroactive migration testing
- Phase 3 (coordinator + acceptance store) before Phase 4 (automation creation) because `ws_accept_pattern` calls `coordinator.accepted_store.async_accept()` which requires the accepted store to exist
- Phase 4 (automation creation) before Phase 5 (panel) because the panel is built against a stable, tested WebSocket API; any change to `accept_pattern` schema after the panel is written requires double-rework
- The Vite build step (`npm run build` → `panel.js` committed to repo) must be established in Phase 5 setup before any panel UI code is written; the built artifact is what HACS installs

### Research Flags

Phases needing deeper investigation or live HA testing during planning:

- **Phase 4 (Automation Creation):** The Option A file-write + reload mechanism needs live HA testing to confirm: (a) `hass.config.path("automations.yaml")` resolves to the correct path and the file is writable, (b) the YAML dict structure is accepted without schema validation error, (c) the created automation appears in `hass.states` within the expected timeout, (d) the automation persists through HA restart. If Option A fails in practice (e.g., user uses `!include_dir_merge_list`), Option B (REST endpoint) becomes the fallback — which requires investigating auth token acquisition from inside a running integration. This risk is flagged in `PROJECT.md` and must be resolved in Phase 4 planning before code is written.

- **Phase 5 (Panel Registration):** Panel registration via `panel_custom.async_register_panel` has shifted between HA versions. The `StaticPathConfig` API requires HA 2024.11+. Verify the exact registration call sequence against the target minimum HA version before writing panel UI. The `embed_iframe=False` requirement and exact `webcomponent_name` match are easy to get wrong silently — establish a passing stub test before any UI work.

Phases with well-documented patterns (skip dedicated research):

- **Phase 1-2 (Detectors):** Pure Python stdlib. No HA API surface. Algorithm is well-understood. Unit tests with static fixtures.

- **Phase 3 (Coordinator wiring):** Follows identical `DataUpdateCoordinator` and `helpers.storage.Store` patterns proven in v1.0. No new HA API surface.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM-HIGH | HA built-in panel registration (HIGH — official docs confirmed); Lit 3.x + Vite bundling (HIGH — official docs); automation creation Option A file-write (MEDIUM — documented HA behavior, used by several HACS integrations, but `automations.yaml` path assumption needs runtime check); Option B REST endpoint fallback (LOW — community-verified, officially undocumented) |
| Features | HIGH | Table stakes, differentiators, and anti-features are well-defined from existing v1.0 research, competitor analysis, and `PROJECT.md` requirements. No ambiguity about what v1.1 must deliver. Prioritization matrix is clear. |
| Architecture | HIGH | Layer structure, component boundaries, and data flow are clearly specified with code examples. Unified detector interface is clean and independently validated. v1.0 coordinator and storage patterns are proven in production. |
| Pitfalls | HIGH | All pitfalls are concrete, specific, and derived from codebase analysis + HA API patterns. Performance pitfall (O(n²)) is mathematically certain. Flap noise is empirically documented in HA community. Fingerprint collision is a data model fact, not a speculation. WebSocket double-registration is a known HA integration lifecycle edge case. |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- **Automation creation path assumption:** The default `automations.yaml` path holds for most HA installs but fails for users with `!include_dir_merge_list` or custom split configs. Implement a runtime check at `async_setup_entry` that verifies the path exists and is writable; if not, warn the user in the panel and display generated YAML for manual copy as a fallback. Do not attempt Option B silently.

- **HA minimum version declaration:** `StaticPathConfig` requires HA 2024.11+. Declare `"homeassistant": "2024.11.0"` (or later) in `manifest.json` before Phase 5. Choose the minimum version that covers `StaticPathConfig` and any other new HA API surface used in v1.1.

- **`person` entity availability at runtime:** Research recommends `person.*` as primary presence source, but notes this assumes standard HA installs. Add a runtime check in `PresencePatternDetector.detect()`: if `hass.states.async_all("person")` is empty, fall back to `device_tracker.*` with explicit de-duplication logic to handle multi-tracker noise.

- **Vite build artifact in HACS distribution:** HACS installs the raw repository contents. The pre-built `panel.js` must be committed to version control. Establish a clear convention in Phase 5: run `npm run build` before tagging any release; add `frontend/panel.js` to git-tracked files explicitly; document the build step in `CONTRIBUTING.md`.

## Sources

### Primary (HIGH confidence)
- HA Developer Docs: Custom Panels (`developers.home-assistant.io/docs/frontend/custom-ui/creating-custom-panels/`) — `panel_custom.async_register_panel`, `embed_iframe`, `webcomponent_name`
- HA Developer Docs: Registering Resources — `StaticPathConfig`, static path registration
- HA Developer Docs: WebSocket API (`developers.home-assistant.io/docs/frontend/extending/websocket-api/`) — custom command registration, `@websocket_command`
- HA Developer Docs: DataUpdateCoordinator — coordinator lifecycle, subscriber model
- HA Automation YAML docs (`home-assistant.io/docs/automation/yaml/`) — `automations.yaml` structure, `automation.reload` service, `id` field requirement
- HA Developer Docs: `helpers.storage.Store` (`github.com/home-assistant/core/blob/dev/homeassistant/helpers/storage.py`) — existing use verified in v1.0
- Lit.dev — LitElement reactive properties, decorators, `static get properties()`
- Vite docs — Library mode, `build.lib`, `rollupOptions.external`
- Python docs — `collections.deque`, `defaultdict`, `datetime.timedelta`

### Secondary (MEDIUM confidence)
- HA Community: Adding sidebar panel to integration — panel_custom.async_register_panel patterns, idempotency
- HA Community: REST API for automations (`community.home-assistant.io/t/rest-api-docs-for-automations/119997`) — Option B endpoint behavior
- `@types/home-assistant-frontend` — TypeScript types for `hass` object
- v1.0 phase research (`01-RESEARCH.md`, `3-RESEARCH.md`) — coordinator, storage, WebSocket patterns confirmed and carried forward
- Competitor analysis (Danm72, ai_automation_suggester, TaraHome/Sherrin) — feature gap confirmation

### Tertiary (LOW confidence, needs validation)
- `POST /api/config/automation/config/<id>` REST endpoint — community-verified, HA source-inspected; officially undocumented; needs live HA testing to confirm payload format and auth mechanism before using as Option B fallback
- Automation file-write + `automation.reload` on non-default config layouts (`!include_dir_merge_list`) — behavior not confirmed; runtime path check is the mitigation

---
*Research completed: 2026-02-23*
*Ready for roadmap: yes*
