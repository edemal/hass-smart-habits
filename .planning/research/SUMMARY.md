# Project Research Summary

**Project:** auto-pattern — Home Assistant ML Pattern Mining & Automation Suggestion Integration
**Domain:** Home Assistant custom integration — behavioral pattern mining with local ML
**Researched:** 2026-02-22
**Confidence:** MEDIUM-HIGH

## Executive Summary

auto-pattern is a Home Assistant custom integration that mines behavioral patterns from historical device state data and surfaces actionable automation suggestions through a sidebar panel UI. The research is clear on how to build this correctly: the integration must follow the standard HA custom component structure (`custom_components/auto_pattern/`), use `DataUpdateCoordinator` for background analysis orchestration, query the Recorder DB exclusively via executor jobs (never from async context), and use lightweight scikit-learn or pure-Python statistical algorithms sized for Raspberry Pi 4 class hardware. The frontend panel is a LitElement web component registered programmatically on integration setup, communicating with the backend via custom WebSocket commands.

The recommended approach is to build bottom-up: establish the DB query layer and async execution patterns first, then layer pattern detection, automation creation, and the UI on top. Each layer is independently testable before the next is added. The biggest competitive gaps this integration fills are genuine one-click automation creation (competitors produce YAML to paste), deduplication against existing automations, and presence/sequence-based pattern detection which no current community tool does.

The key risks are clustered around two areas: environment constraints (scikit-learn may not install on HAOS's musl-Linux environment — must validate in Phase 1 or fall back to pure-Python algorithms) and the undocumented automation creation API (POST `/api/config/automation/config/<id>` is the correct endpoint but is not officially documented and is subject to change). Both risks are manageable with early validation and isolation of the unstable surface area behind a single `AutomationBuilder` component.

---

## Key Findings

### Recommended Stack

The integration runtime is Python 3.13+ (required by HA 2025.2+), structured as a standard HA custom component with `DataUpdateCoordinator` for background scheduling. ML analysis uses scikit-learn 1.6+ (OPTICS, MiniBatchKMeans) and NumPy for windowed aggregation — **with the critical caveat that these packages must be validated against HAOS's musl-Linux environment before committing to them**. If they fail to install on HAOS, the fallback is pure-Python frequency counting with `statistics` and `collections`. The frontend is a LitElement 3.x web component bundled with Vite + Rollup, served statically and registered programmatically via `panel_custom.async_register_panel()`. Recorder DB access always uses `get_instance(hass).async_add_executor_job()` wrapping synchronous SQLAlchemy calls — the `history_stats` integration in HA core is the canonical model.

**Core technologies:**
- Python 3.13+ async custom component: HA 2025.2+ runtime requirement, all code must be async-compatible
- DataUpdateCoordinator: background scheduling, subscriber fan-out, avoids reinventing async task management
- scikit-learn 1.6+ / pure-Python fallback: OPTICS and MiniBatchKMeans for clustering; fallback if HAOS install fails
- NumPy 1.26+: windowed time-series aggregation; lighter than pandas for pure numeric data
- LitElement 3.x (Vite-bundled): matches HA's own frontend framework; no CDN imports (documented breakage)
- WebSocket API (`@websocket_api.websocket_command`): panel-to-backend communication; HA-idiomatic, auth-aware
- HA Storage (`homeassistant.helpers.storage.Store`): persistence for dismissed/accepted IDs

**Do not use:** TensorFlow, PyTorch, DBSCAN at scale, CDN-imported Lit, direct `automations.yaml` file writes, `hass.async_add_job` (removed HA 2025.4).

### Expected Features

The feature research identifies a clear MVP: a working pattern detection and review cycle that proves the core value proposition. All P1 features form an interdependent chain — Recorder query layer → pattern detection → confidence scoring → suggestion storage → review panel → accept to create automation. Breaking any link in this chain means the product cannot demonstrate its core value.

**Must have (table stakes):**
- Recorder DB query layer — handles SQLite + MariaDB; respects configurable lookback window
- Time-based routine detection — frequency + time-window bucketing; the most universal pattern class
- Confidence score per suggestion — frequency × consistency; configurable minimum threshold
- Existing automation deduplication — suppresses suggestions already automated
- User and domain filtering — exclude accounts and entity domains from analysis
- Persistent dismiss — dismissed suggestions survive HA restart
- Sidebar review panel — browse suggestions, trigger scan, manage accepted/dismissed state
- Accept → real automation creation — one click creates a live HA automation (not YAML to paste)

**Should have (competitive differentiators, v1.x):**
- Presence-based pattern detection — person arrives → devices activate; no competitor does this
- Temporal sequence detection (A→B) — TV on → lights dim; the most sophisticated and trusted pattern class
- Stale automation detection — surface unused automations; independent of pattern engine, can ship early
- Pattern preview in human language — "Turns on kitchen lights every weekday at 07:05" before accepting
- Customize before accepting — edit time, threshold, entities before creation

**Defer (v2+):**
- Multi-entity routine clustering — "morning routine" as a single block; very high complexity
- Learn from dismissals (implicit training) — defer until dismiss volume is measurable
- Pattern category grouping — cosmetic; only valuable at high suggestion volume
- State correlation patterns (temperature → heater) — different data model needed; out of v1 scope

### Architecture Approach

The integration uses a layered, bottom-up architecture with clear separation between HA plumbing and ML logic. The `PatternCoordinator` (DataUpdateCoordinator subclass) owns the analysis lifecycle and in-memory pattern store. All CPU-bound work (`RecorderReader` SQL queries, `PatternAnalyzer` scoring loops) runs in executor jobs off the event loop. The `AutomationBuilder` isolates the unstable REST API call for automation creation. The frontend JS web component communicates exclusively via typed WebSocket messages, never REST, to respect HA auth and avoid CORS issues. Persistence uses HA's `.storage/auto_pattern` Store for dismissed/accepted IDs — not config entry data.

**Major components:**
1. `RecorderReader` — synchronous SQLAlchemy queries against `states` + `states_meta` tables; runs in executor
2. `PatternAnalyzer` (with sub-detectors: `DailyRoutineDetector`, `TemporalSequenceDetector`, `PresencePatternDetector`, `ExistingAutomationFilter`) — pure Python, stateless, CPU-bound, runs in executor
3. `PatternCoordinator` — DataUpdateCoordinator subclass; schedules analysis, holds pattern store, notifies panel
4. `AutomationBuilder` — converts pattern dicts to HA automation YAML; POSTs via internal REST API
5. `ws_api.py` — all WebSocket command handlers; single file for visibility of protocol surface area
6. `panel/auto-pattern-panel.js` — LitElement web component; Vite-bundled; registered programmatically in setup
7. `storage.py` — HA Store wrapper for persistent accepted/dismissed IDs
8. `config_flow.py` — ConfigFlow + OptionsFlow for lookback period, threshold, entity filters

### Critical Pitfalls

1. **scikit-learn/numpy install failure on HAOS** — these packages require compiled C extensions and may fail on HAOS's musl-Linux environment with `PermissionError` or `ImportError`. Validate installation on real HAOS in Phase 1 before writing any ML code. Have a pure-Python fallback ready using `statistics`, `collections`, and simple frequency counting.

2. **Blocking the event loop during analysis** — running synchronous DB queries or CPU-bound loops inside `async def` functions freezes HA. HA 2024.7+ actively detects and logs this. Every DB call and every analysis function must be wrapped in `async_add_executor_job`. Never call SQLAlchemy sync APIs from async context.

3. **Incorrect Recorder DB schema — missing `states_meta` JOIN** — `states.entity_id` does not exist as a direct column; it is stored in `states_meta.entity_id` joined via `states.metadata_id`. Queries that try to filter by entity_id directly return silently empty results. Always use the normalized join pattern and `last_updated_ts` (not the deprecated `last_updated` string column).

4. **Full DB scan without time filter** — querying all history without a `WHERE last_updated_ts >= cutoff` clause causes OOM and multi-minute query times on real installs with years of history. Always scope queries to the configurable lookback window from day one, never as an optimization later.

5. **Blocking HA startup with inline analysis** — calling analysis in `async_setup_entry()` delays HA startup and may fail because the Recorder is not fully initialized. Always defer the first analysis run to `EVENT_HOMEASSISTANT_STARTED` and use `async_track_time_interval` for subsequent runs.

6. **Direct `automations.yaml` file writes** — concurrent writes corrupt the file and break HA's automation editor. Use the internal REST API (`POST /api/config/automation/config/<id>`) exclusively. Isolate this behind `AutomationBuilder` so it can be updated in one place if the endpoint changes.

7. **Deprecated HA APIs breaking integration on updates** — `async_forward_entry_setup` (singular), `hass.async_add_job`, `HomeAssistantType` have all been removed. Use the `hacs/integration_blueprint` as a starting template, monitor the HA developer blog, and pin a minimum HA version in `manifest.json`.

---

## Implications for Roadmap

Research strongly supports a 5-phase build sequence aligned with the architectural dependency chain. Each phase is independently testable before the next begins.

### Phase 1: Foundation — Async Patterns, DB Access, Integration Scaffold

**Rationale:** Every subsequent feature depends on correct async patterns and a working Recorder query layer. Discovering HAOS dependency failures or event loop blocking late is extremely expensive to fix (full ML rewrite). Phase 1 validates the riskiest assumptions before committing to them.

**Delivers:** A loadable HA custom integration with config flow, coordinator skeleton, tested RecorderReader, confirmed HAOS dependency compatibility, and established async execution patterns.

**Addresses (from FEATURES.md):** Recorder DB query layer (P1 foundation), configurable lookback period, user/domain filtering (applied at query time).

**Avoids (from PITFALLS.md):** Pitfalls 1 (HAOS install), 2 (event loop blocking), 3 (Recorder schema), 5 (blocking startup), 7 (deprecated APIs). These are all "foundation" pitfalls — discovering them here costs days; discovering them in Phase 4 costs weeks.

**Research flag:** Needs validation testing on real HAOS, not just dev container. Validate scikit-learn or confirm pure-Python fallback path before proceeding.

### Phase 2: Pattern Detection Engine

**Rationale:** The analysis logic is pure Python with no HA dependencies — it can be built and unit-tested against static state fixtures without a running HA instance. Building detection before the UI and before automation creation means the core algorithm is validated before the harder integration work begins.

**Delivers:** `DailyRoutineDetector` (time-based patterns), confidence scoring, `ExistingAutomationFilter` (dedup), all unit-tested with fixtures representing real Recorder output shapes.

**Addresses (from FEATURES.md):** Time-based routine detection (P1), confidence scoring (P1), existing automation deduplication (P1).

**Avoids (from PITFALLS.md):** Pitfall 4 (full DB scan) — implement lookback-scoped queries and row-count limits from the start. Pitfall 4's load test requirement: validate against a large fixture (500 entities, 90-day snapshot) in this phase.

**Research flag:** Standard ML/statistics patterns; no additional research needed. Algorithm choices (OPTICS vs MiniBatchKMeans vs pure-Python frequency counting) depend on Phase 1 HAOS validation outcome.

### Phase 3: Core Integration Wiring — Coordinator, WebSocket API, Storage, Panel Skeleton

**Rationale:** Wire the tested detector into the HA integration lifecycle. Establish all communication channels (coordinator → WebSocket → panel) before building the full UI. A thin panel (JSON display) is sufficient to validate the data flow end to end.

**Delivers:** PatternCoordinator with scheduled and on-demand analysis, full WebSocket API surface (`list_patterns`, `accept`, `dismiss`, `trigger_scan`), persistent storage for dismissed/accepted IDs, panel skeleton that displays pattern JSON from real coordinator data.

**Addresses (from FEATURES.md):** Configurable analysis schedule/manual trigger (P1), persistent dismiss (P1), on-demand scan trigger (P1).

**Avoids (from PITFALLS.md):** Pitfall 2 (event loop blocking — coordinator wires executor correctly here), Pitfall 5 (startup blocking — EVENT_HOMEASSISTANT_STARTED pattern established here).

**Research flag:** WebSocket API registration is well-documented (HIGH confidence). DataUpdateCoordinator pattern is well-established. Standard patterns, no additional research needed.

### Phase 4: Automation Creation

**Rationale:** Automation creation is the highest-risk feature — the REST endpoint is undocumented, and the YAML structure varies by trigger type. Isolating it to a dedicated phase limits blast radius if the API approach needs revision. This phase also completes the core user journey: see suggestion → click accept → automation exists.

**Delivers:** `AutomationBuilder` converting patterns to HA automation dicts, POST to `/api/config/automation/config/<id>`, full accept flow with persistence and coordinator refresh, automation deduplication verified end-to-end.

**Addresses (from FEATURES.md):** Accept → real automation creation (P1, highest implementation cost).

**Avoids (from PITFALLS.md):** Pitfall 6 (direct YAML file writes — `AutomationBuilder` uses REST API only). Isolating this component means a single file update if the internal endpoint changes.

**Research flag:** Needs deeper research during planning. The REST endpoint is undocumented officially; inspect HA network traffic in DevTools to confirm current endpoint structure. Verify automation persistence across HA restart.

### Phase 5: Review Panel UI

**Rationale:** The WebSocket API is stable by Phase 4, so the panel has a well-defined contract to build against. Building UI last avoids rework when data shapes change during earlier phases.

**Delivers:** Full LitElement sidebar panel — tabbed view (pending/accepted/dismissed), confidence scores with plain-language explanations, evidence examples ("happened 8/10 mornings"), accept/customize/dismiss actions, settings for lookback and threshold, manual scan trigger.

**Addresses (from FEATURES.md):** Dedicated review UI (P1), show pattern evidence (P1), configurable lookback/threshold (P1).

**Avoids (from PITFALLS.md):** UX pitfalls — confidence score must include plain-language explanation (not just a number), suggestion count must be capped to avoid overwhelm, dismissed suggestions must visually confirm persistence.

**Research flag:** LitElement + Vite bundling is well-documented. Panel registration pattern is HIGH confidence. Standard patterns; no additional research needed beyond Phase 1 panel skeleton validation.

### Phase 6: Differentiators (v1.x Post-Launch)

**Rationale:** After the core loop is proven working and users are engaging, add the features that create real competitive advantage. These are deliberately deferred to avoid scope creep before the MVP is validated.

**Delivers:** Presence-based pattern detection (`PresencePatternDetector`), stale automation detection tab, pattern preview in human language, customize-before-accepting flow, temporal sequence detection (A→B).

**Addresses (from FEATURES.md):** All P2 features — presence detection, sequence detection, stale automation detection, human-language preview, customize before accept.

**Research flag:** Presence-based and sequence detection need research during planning. Correlating `person`/`device_tracker` state changes with downstream entity events is a different algorithm path than daily routine detection. Temporal sequence detection conflicts with simple frequency counting — plan as a separate detector, not an extension of existing ones.

### Phase Ordering Rationale

- **Foundation first:** HAOS dependency validation and async patterns are load-bearing assumptions. Discovering them broken in Phase 4 requires rewriting everything above them.
- **Detection before UI:** Pure Python detectors are testable without HA running. Building them first produces validated, fixture-tested logic before wiring HA plumbing around it.
- **WebSocket API before full UI:** Thin panel in Phase 3 validates the data contract. Full UI in Phase 5 builds against a stable API with real data shapes.
- **Automation creation isolated:** The highest-risk, lowest-documented feature gets its own phase with no UI pressure. If the internal API approach fails, the fallback (file write + automation.reload) is swapped in one component without touching Phase 5.
- **Differentiators deferred:** Presence and sequence detection are different algorithm paths that conflict with the simpler frequency analysis. Bolting them on during MVP development adds complexity that could delay delivery of table-stakes features.

### Research Flags

Phases needing deeper research during planning:
- **Phase 1:** HAOS dependency validation — test `requirements` installation on real HAOS instance; have pure-Python fallback strategy documented before phase begins.
- **Phase 4:** Automation creation API — inspect current HA network traffic to confirm endpoint structure and payload format; test automation CRUD roundtrip in isolation before integrating with coordinator.
- **Phase 6:** Presence and sequence detection algorithms — needs specific research into HA `person`/`device_tracker` entity state history format and co-occurrence scoring approaches.

Phases with standard patterns (skip additional research):
- **Phase 2:** Pure Python statistics and frequency counting are well-understood; algorithm choice confirmed by Phase 1 dependency outcome.
- **Phase 3:** DataUpdateCoordinator + WebSocket API are HIGH confidence, extensively documented.
- **Phase 5:** LitElement + Vite bundling + panel registration are HIGH confidence.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM-HIGH | HA integration patterns (HIGH); scikit-learn on HAOS (LOW — documented failures, needs validation); Lit/Vite panel bundle (HIGH); automation creation REST endpoint (MEDIUM — undocumented officially) |
| Features | MEDIUM | Competitor analysis from direct code/README inspection (MEDIUM); UX principles from peer-reviewed sources (MEDIUM); smart home ML research (MEDIUM); one-click automation creation as differentiator (HIGH — no competitor does it) |
| Architecture | MEDIUM-HIGH | Official HA developer docs for coordinator, WebSocket, panel registration (HIGH); Recorder DB schema internals (MEDIUM — schema documented by community, not official spec); automation REST API (LOW — confirmed by community, not official docs) |
| Pitfalls | HIGH | HAOS install failure: multiple confirmed reports (HIGH); event loop blocking: official HA docs (HIGH); Recorder schema normalization: HA source code confirmation (HIGH); automation API: community consensus (MEDIUM) |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- **HAOS dependency validation:** Whether scikit-learn 1.6+ installs on HAOS is the single highest-risk unknown. Must be resolved in Phase 1 — do not write any ML code that depends on it until validated on a real HAOS instance. Pure-Python fallback algorithms (frequency counting with `statistics` + sliding window with `collections.Counter`) should be prototyped in parallel.

- **Automation creation API endpoint stability:** `POST /api/config/automation/config/<id>` is the community-confirmed approach but is not in official documentation. Inspect HA DevTools network traffic to confirm current payload structure. Design `AutomationBuilder` so the API call is a single swappable function — if the endpoint changes, one function changes.

- **Recorder schema stability across HA versions:** The `states`/`states_meta` normalized schema has been stable since 2022-2023. However, minor column changes occur. Use only the documented stable columns (`state_id`, `metadata_id`, `state`, `last_updated_ts`). Test against both current HA stable and current HA dev/beta.

- **Large-instance performance:** All load testing has been reasoning-based, not empirical. A 500-entity, 90-day fixture test in Phase 2 is the only way to validate that lookback windowing and entity filtering keep analysis under 30 seconds on Pi 4 class hardware.

---

## Sources

### Primary (HIGH confidence)

- [HA Developer Docs — DataUpdateCoordinator](https://developers.home-assistant.io/docs/integration_fetching_data/) — coordinator pattern, subscriber model
- [HA Developer Docs — WebSocket API](https://developers.home-assistant.io/docs/frontend/extending/websocket-api/) — custom command registration
- [HA Developer Docs — Custom Panels](https://developers.home-assistant.io/docs/frontend/custom-ui/creating-custom-panels/) — panel registration, LitElement
- [HA Developer Docs — Blocking Operations](https://developers.home-assistant.io/docs/asyncio_blocking_operations/) — executor job patterns
- [HA Developer Docs — Deprecations (async_run_job/add_job)](https://developers.home-assistant.io/blog/2024/03/13/deprecate_add_run_job/) — removed in 2025.4
- [HA Core — history_stats/data.py](https://github.com/home-assistant/core/blob/dev/homeassistant/components/history_stats/data.py) — canonical Recorder executor pattern
- [scikit-learn PyPI](https://pypi.org/project/scikit-learn/) — version compatibility (1.6+, Python 3.13)
- [GitHub — Unable to import scikit-learn on HAOS](https://github.com/home-assistant/operating-system/issues/3040) — HAOS install failure reports
- [HA Docs — Recorder](https://www.home-assistant.io/integrations/recorder) — backend DB schema
- [Lit.dev — Build for Production](https://lit.dev/docs/v1/tools/build/) — Vite/Rollup bundling

### Secondary (MEDIUM confidence)

- [GitHub — Danm72/home-assistant-automation-suggestions](https://github.com/Danm72/home-assistant-automation-suggestions) — competitor analysis, frequency+time-window bucketing approach
- [GitHub — ITSpecialist111/ai_automation_suggester](https://github.com/ITSpecialist111/ai_automation_suggester) — competitor analysis, LLM approach (cloud)
- [Hackaday — Habit Detection for Home Assistant (TaraHome)](https://hackaday.com/2026/02/08/habit-detection-for-home-assistant/) — competitor, automatic YAML generation
- [HA Community — Adding Sidebar Panel to Integration](https://community.home-assistant.io/t/how-to-add-a-sidebar-panel-to-a-home-assistant-integration/981585) — panel_custom.async_register_panel
- [HA Community — scikit-learn with custom integration](https://community.home-assistant.io/t/how-to-use-scikit-learn-with-a-custom-intigration/536939) — HAOS requirements pattern
- [SmartHomeScene — HA Database Model](https://smarthomescene.com/blog/understanding-home-assistants-database-and-statistics-model/) — states_meta schema
- [HA Community — REST API for automations](https://community.home-assistant.io/t/rest-api-docs-for-automations/119997) — undocumented automation endpoint

### Tertiary (LOW confidence, needs validation)

- Automation REST API payload structure — confirmed by community inspection, no official spec; verify with DevTools before Phase 4 implementation
- HAOS musl wheel availability for scikit-learn — reported failures from 2023-2024; may have improved; must test against current HAOS version

---

*Research completed: 2026-02-22*
*Ready for roadmap: yes*
