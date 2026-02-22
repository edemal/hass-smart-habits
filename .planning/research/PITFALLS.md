# Pitfalls Research

**Domain:** Home Assistant custom integration — ML pattern mining + automation suggestion
**Researched:** 2026-02-22
**Confidence:** MEDIUM-HIGH (core HA async/integration patterns: HIGH; ML dependency issues: HIGH from multiple confirming sources; automation creation API: MEDIUM — endpoint undocumented officially; Recorder schema internals: MEDIUM)

---

## Critical Pitfalls

### Pitfall 1: scikit-learn / numpy Cannot Install on HAOS

**What goes wrong:**
Installing `scikit-learn`, `scipy`, or heavy `numpy` builds as declared `requirements` in `manifest.json` fails on Home Assistant OS (HAOS) and Alpine-based containers. pip cannot compile from source in the restricted musl-Linux environment. Error: `ImportError: Error loading shared library ... numpy/core/_multiarray_umath.cpython-311-x86_64-linux-musl.so: Operation not permitted`. The installation silently fails or throws a permission error, and the integration never loads.

**Why it happens:**
HAOS uses a minimal musl-based Linux image. Heavy scientific packages require compiled C extensions. Prebuilt wheels for musl (Alpine) are not always available on PyPI. Additionally, HA's `package_constraints.txt` pins numpy to a specific version — even if a wheel is found, a version mismatch can cause HA to revert it on restart.

**How to avoid:**
Do not declare `scikit-learn`, `scipy`, or pandas as requirements. Use only pure-Python libraries or libraries with reliable musl wheels. For pattern detection, implement the algorithms from scratch using standard library `statistics`, `collections`, and `itertools` — or use a minimal dependency like `statistics` (stdlib). If you need clustering, implement a simple k-means or sliding-window histogram manually. This project explicitly targets lightweight ML on Raspberry Pi 4 — this constraint is your friend, not a limitation.

**Warning signs:**
- Integration setup fails with `ModuleNotFoundError` or `PermissionError` during requirement install
- Integration loads in dev Docker container (Debian-based) but fails on target HAOS
- Any `requirements` entry that pulls in a binary C extension

**Phase to address:**
Phase 1 (Foundation/DB Access) — validate the dependency strategy immediately before any ML code is written. Test on actual HAOS, not just a dev container.

---

### Pitfall 2: Blocking the Event Loop During Pattern Analysis

**What goes wrong:**
Running pandas DataFrame operations, Python loops over thousands of state rows, or `time.sleep()` calls directly inside an `async def` function blocks HA's event loop. HA (since 2024.7) actively detects and logs these as `[homeassistant.util.loop] Detected blocking call`. In severe cases, HA logs "Something is blocking Home Assistant from wrapping up the start up phase." The UI becomes unresponsive while analysis runs.

**Why it happens:**
Developers new to HA async patterns write CPU-bound analysis code in `async def _async_update_data()` without wrapping it in an executor. Pattern mining over 30-90 days of history on a busy instance can mean millions of rows — even fast pure-Python code takes seconds.

**How to avoid:**
All pattern analysis must run via `hass.async_add_executor_job()`:
```python
async def _async_update_data(self):
    return await self.hass.async_add_executor_job(self._run_pattern_analysis)

def _run_pattern_analysis(self):
    # CPU-bound work here — runs in thread pool, not event loop
    ...
```
Never call blocking file I/O (`open()`), `time.sleep()`, or synchronous DB queries directly in async methods. Use `await asyncio.sleep()` for delays.

**Warning signs:**
- HA logs containing `Detected blocking call to` from your integration's domain
- HA startup logs: "Something is blocking Home Assistant from wrapping up the start up phase"
- UI freezes or becomes sluggish when analysis is scheduled to run
- `async_add_executor_job` not used anywhere in the pattern analysis code

**Phase to address:**
Phase 1 (Foundation) — establish the executor pattern for DB access. Phase 2 (Pattern Mining) — all analysis functions must be synchronous functions called via executor, never coroutines.

---

### Pitfall 3: Querying the Recorder DB Directly Without Understanding Schema Normalization

**What goes wrong:**
The `states` table does not store `entity_id` as a string column. Queries like `SELECT * FROM states WHERE entity_id = 'light.kitchen'` return nothing. The schema is normalized: `states.metadata_id` joins to `states_meta.entity_id`, and `states.attributes_id` joins to `state_attributes.shared_attrs`. Missing these JOINs produces silently empty result sets, wasted query time, or incorrect data.

**Why it happens:**
The schema changed significantly in HA 2022-2023 from a flat design to a normalized one. Old tutorials and forum posts use the old flat schema. Developers inspect the DB file and see the `states` table but don't notice it lacks readable entity IDs.

**How to avoid:**
Always JOIN `states_meta` when filtering by entity_id:
```sql
SELECT s.state, s.last_updated_ts
FROM states s
JOIN states_meta sm ON s.metadata_id = sm.metadata_id
WHERE sm.entity_id = 'light.kitchen'
  AND s.last_updated_ts >= :start_ts
ORDER BY s.last_updated_ts
```
Use `last_updated_ts` (Unix timestamp) not `last_updated` (deprecated string column). Test queries interactively via SQLite Web add-on before embedding in code.

**Warning signs:**
- Queries return 0 rows despite entities clearly having history
- Code references `states.entity_id` directly
- No JOIN to `states_meta` in any query

**Phase to address:**
Phase 1 (DB Access layer) — write a dedicated query module with tested JOINs before any pattern logic is built on top.

---

### Pitfall 4: Triggering a Full DB Scan on Every Analysis Run

**What goes wrong:**
Each analysis run issues `SELECT * FROM states JOIN states_meta ...` without filtering by `last_updated_ts`, loading all history for every entity into memory. On an instance with 1+ year of history and hundreds of entities, this is millions of rows. Raspberry Pi 4 with 4GB RAM hits memory limits. SQLite takes 30-120 seconds. HA may log the thread as hung.

**Why it happens:**
During development the DB is small. The query works fine in dev. In production with a real user's multi-year history, the same query becomes catastrophic. The absence of a `WHERE last_updated_ts >= :cutoff` clause is the most common form of this mistake.

**How to avoid:**
Always scope queries to the configurable lookback window (7/14/30/90 days):
```python
cutoff_ts = (datetime.now() - timedelta(days=lookback_days)).timestamp()
```
Add an index hint or verify the Recorder's existing indices cover `last_updated_ts`. For entities with high state-change frequency (binary sensors, weather, power meters), further filter at the entity selection stage — skip entities with >10k state changes in the window unless they are specifically in scope.

**Warning signs:**
- Analysis works fine in dev/test but times out on a real installation
- No `WHERE last_updated_ts >=` clause in history queries
- Query fetches states for ALL entities rather than a targeted subset
- Memory usage spikes during analysis runs

**Phase to address:**
Phase 2 (Pattern Mining) — build with lookback filtering from day one, not as an optimization later.

---

### Pitfall 5: Creating Automations by Writing to automations.yaml Directly

**What goes wrong:**
The integration writes YAML directly to `/config/automations.yaml` to create suggested automations. This corrupts the file if the user has customized the automation file structure, uses `!include_dir_merge_list`, or has the file opened by the editor. Automations don't appear in the UI. HA's automation editor assumes it owns `automations.yaml` — concurrent writes cause YAML parse errors and can brick the user's automation config.

**Why it happens:**
Writing files seems like the obvious approach since automations ARE stored as YAML. But HA's internal automation management goes through a config entry registry, not direct file manipulation.

**How to avoid:**
Use HA's internal automation creation API — `POST /api/config/automation/config/<automation_id>` with a JSON payload, or call the `automation.reload` service after writing. Better: use the `EntityRegistry` and `ConfigEntries` patterns to create automations programmatically through HA's config flow system. Look at how the official automation editor creates automations (inspect network requests in DevTools) and replicate the same internal calls. Never write to `automations.yaml` directly from integration code.

**Warning signs:**
- Code contains `open('/config/automations.yaml', 'a')` or similar
- Race conditions between automation writes and HA reloads
- Users report automations disappearing after HA restart

**Phase to address:**
Phase 3 (Automation Creation) — research the correct internal API before writing any automation creation code. Test automation creation/deletion roundtrip in isolation.

---

### Pitfall 6: Blocking Analysis at HA Startup

**What goes wrong:**
The integration's `async_setup_entry` triggers pattern analysis immediately during HA startup. HA logs "Something is blocking Home Assistant from wrapping up the start up phase." Other integrations load slowly. The analysis fails because the Recorder DB may not be fully initialized when the integration loads.

**Why it happens:**
It feels natural to run analysis during setup so patterns are ready immediately. But HA's integration loading happens before the Recorder is fully warm, and long-running setup tasks hold up the entire startup chain.

**How to avoid:**
Defer analysis until after HA is fully started:
```python
async def async_setup_entry(hass, entry):
    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STARTED,
        _start_background_analysis
    )
    return True
```
Schedule subsequent analysis runs using `async_track_time_interval` on a conservative interval (hours, not minutes). Never run analysis in `async_setup` or `async_setup_entry` directly.

**Warning signs:**
- `async_setup_entry` runs analysis inline without deferral
- No `EVENT_HOMEASSISTANT_STARTED` listener
- Users report slow HA startup after installing the integration

**Phase to address:**
Phase 1 (Foundation) — establish the deferred startup pattern as a non-negotiable architectural constraint.

---

### Pitfall 7: Deprecated HA APIs Break Integration on Updates

**What goes wrong:**
The integration uses deprecated APIs that are removed in a subsequent HA release. Users update HA and the integration stops loading entirely. Common examples: `async_forward_entry_setup` (singular, removed in HA 2025.6 — must be `async_forward_entry_setups` plural), `hass.http.register_static_path` (deprecated for blocking I/O), `HomeAssistantType` alias (removed in 2025.5).

**Why it happens:**
HA releases monthly with deprecation notices in the developer blog. Custom integration developers don't monitor this blog. Tutorials and Stack Overflow answers reference deprecated patterns. The integration works fine until a specific HA version removes the deprecated API.

**How to avoid:**
Subscribe to the HA developer blog at `developers.home-assistant.io/blog`. Use the integration blueprint from `hacs/integration_blueprint` as a starting template — it tracks current patterns. Add HA version range constraints to `manifest.json` via `homeassistant` key. Test against the latest HA dev/beta before each release.

**Warning signs:**
- Using `async_forward_entry_setup` (singular) instead of the plural form
- Any `hass.components.frontend` access
- `HomeAssistantType` imported from `homeassistant.helpers.typing`
- Not checking the developer blog for the monthly release cycle

**Phase to address:**
Phase 1 (Foundation) — use the latest integration blueprint. Ongoing — monitor developer blog.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Query all entities, filter in Python | Simpler query code | Memory exhaustion on real installs with large DBs | Never — always filter at SQL level |
| Hardcode pattern thresholds | Faster initial build | Users with non-standard schedules see garbage suggestions | Only in MVP if thresholds are easily configurable later |
| Skip existing automation filtering on first build | Ship sooner | Users get suggested automations they already have; erodes trust | Only if clearly marked as known gap |
| Store patterns in `hass.data` dict without persistence | Simple in-memory state | Patterns lost on restart, re-analysis every boot | Acceptable in MVP if analysis is cheap; unacceptable if analysis takes >30s |
| Use the `statistics` table instead of `states` for patterns | Much smaller dataset | Statistics are hourly aggregates — loses precise timing needed for sequence detection | Never for sequence/temporal patterns; OK for long-term frequency baselines |

---

## Integration Gotchas

| Integration Point | Common Mistake | Correct Approach |
|-------------------|----------------|------------------|
| Recorder DB access | Bypass HA's session management, open SQLite file directly with `sqlite3` | Use HA's internal `get_instance(hass).async_add_executor_job()` to run DB operations on Recorder's thread |
| Automation creation | Write directly to `automations.yaml` | Use `/api/config/automation/config/` endpoint or HA's internal config storage |
| Panel registration | Use deprecated `hass.http.register_static_path` | Use `hass.http.register_view` or serve panel JS from `www/` via `panel_custom` |
| DB queries | Use `entity_id` directly on `states` table | JOIN with `states_meta` for entity_id filtering |
| Automation filtering | Manually parse `automations.yaml` to detect existing automations | Use `hass.states.async_all()` + automation entity attributes or the automation registry |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Full-table states scan without time filter | Analysis takes minutes, OOM on Pi | Always add `last_updated_ts >= cutoff` WHERE clause | First real user with >6 months of history |
| Loading all state attributes into memory | Memory spikes; slow JSON parse | Only SELECT `state` and `last_updated_ts`; skip `shared_attrs` unless needed | Instances with chatty sensors logging large attribute blobs |
| Running analysis every few minutes | DB locked errors, high CPU on Pi | Schedule analysis every 6-24 hours, not frequently | From day one on low-RAM hardware |
| Loading full entity history for pattern detection when only frequency counts matter | Unnecessarily large result set | Use `COUNT()` + `GROUP BY` for frequency; only pull raw timestamps for sequence detection | Large instances with high-frequency binary sensors |
| Synchronous DB access from async context | Event loop blocks, HA becomes unresponsive | Wrap ALL DB calls in `async_add_executor_job` | Immediately on any real workload |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Accepting raw user input for DB queries without parameterization | SQL injection into the local Recorder DB | Use parameterized queries always, never string-interpolated SQL |
| Exposing internal DB structure through the panel | Users can see all entity history they don't own (multi-user HA) | Filter suggestions by the authenticated user's entity access; respect HA's user/entity permissions |
| Creating automations without validating entity IDs exist | Broken automations that reference non-existent entities | Validate all entity IDs against `hass.states` before writing automation |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Showing patterns with low confidence scores without explanation | Users accept junk automations, trust erodes quickly | Display confidence score with a plain-language explanation: "This pattern happened 4 out of 7 days in the last 14 days" |
| Suggesting automations that duplicate existing ones | Confusion, clutter, distrust | Always filter suggestions against existing automation entity states before presenting |
| Surfacing too many suggestions at once | Overwhelm; users dismiss everything | Limit to top 5-10 suggestions by confidence; let users request more |
| Making pattern analysis blocking/visible to the user | Users think something is wrong when it runs | Run analysis entirely in background; surface only the results, never the process |
| Offering no way to permanently dismiss a suggestion | Same bad suggestion reappears every analysis run | Persist dismissed suggestion IDs in `Store`; exclude from future analysis results |

---

## "Looks Done But Isn't" Checklist

- [ ] **Pattern detection works on dev DB:** Verify same code handles a real 90-day, 500-entity production DB without timeout or OOM
- [ ] **Automation creation:** Verify the created automation actually appears in HA's automation list, runs correctly, and persists after HA restart
- [ ] **Existing automation filter:** Verify that suggestions are actually suppressed when a near-identical automation already exists — don't rely on string matching alone
- [ ] **Dismissed suggestions:** Verify dismissed suggestions do NOT reappear after HA restart (must be persisted, not just in-memory)
- [ ] **Panel loads correctly:** Verify panel registers correctly, appears in sidebar, and loads on both ES5 and modern JS builds
- [ ] **HAOS installation:** Verify all declared `requirements` actually install on HAOS (not just dev Docker) before any Phase 2 work
- [ ] **Startup deferral:** Verify analysis does NOT run during HA startup — check logs for "Something is blocking" warnings

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| scikit-learn/numpy dependency discovered late | HIGH — requires rewriting all ML code in pure Python | Profile what sklearn features are actually used; reimplement as simple frequency counting + standard deviation with stdlib |
| Full-table scan causing OOM in production | MEDIUM — requires query rewrite + testing | Add `LIMIT` + `WHERE last_updated_ts >= cutoff` immediately; batch large queries |
| Blocking event loop discovered | MEDIUM — requires refactor of analysis pipeline | Wrap analysis function in `async_add_executor_job`; verify with asyncio debug mode |
| Direct `automations.yaml` write corrupting user config | HIGH — requires file I/O removal + API migration | Stop all file writes; migrate to internal HA API; add config backup step before any write |
| Deprecated API breaking integration on HA update | LOW-MEDIUM — usually a 1-line fix, but requires release | Track deprecation notices; use integration blueprint patterns; pin `homeassistant` version minimum in manifest |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| scikit-learn / numpy install failure on HAOS | Phase 1: Foundation | Test `requirements` installation on real HAOS instance before writing any ML code |
| Blocking event loop during analysis | Phase 1: Foundation | Enable HA asyncio debug mode; verify no "Detected blocking call" logs during analysis |
| Incorrect Recorder schema / missing JOINs | Phase 1: DB Access | Query unit tests against a real Recorder DB; verify correct entity_id filtering |
| Full DB scan without time filter | Phase 2: Pattern Mining | Load test with a 500-entity, 90-day Recorder snapshot |
| Analysis running at HA startup | Phase 1: Foundation | Check HA startup logs for "blocking" warnings; verify `EVENT_HOMEASSISTANT_STARTED` pattern |
| Direct automations.yaml file writes | Phase 3: Automation Creation | Test automation creation/deletion using only HA API; verify persistence across restart |
| Deprecated HA API usage | Phase 1: Foundation | Use integration blueprint as template; run against HA dev/beta |
| No persistence for dismissed suggestions | Phase 3: Automation Creation | Restart HA after dismissing a suggestion; verify it does not reappear |
| Low-confidence suggestions without explanation | Phase 4: Panel UI | User test with non-technical user; require confidence explanation in the UI spec |
| Duplicate suggestions despite existing automations | Phase 3: Automation Creation | Create matching automation manually; verify suggestion is suppressed in next analysis run |

---

## Sources

- [Home Assistant Developer Docs: Blocking Operations in Asyncio](https://developers.home-assistant.io/docs/asyncio_blocking_operations/) — HIGH confidence
- [Home Assistant Developer Blog](https://developers.home-assistant.io/blog/) — HIGH confidence (deprecation tracking)
- [Home Assistant Community: How to use Scikit-learn with a custom integration](https://community.home-assistant.io/t/how-to-use-scikit-learn-with-a-custom-intigration/536939) — HIGH confidence (multiple confirming reports, no resolution found)
- [GitHub: Unable to import scikit-learn on HAOS](https://github.com/home-assistant/operating-system/issues/3040) — HIGH confidence
- [Home Assistant Docs: Recorder](https://www.home-assistant.io/integrations/recorder) — HIGH confidence
- [Home Assistant Docs: Backend Database](https://www.home-assistant.io/docs/backend/database) — HIGH confidence
- [SmartHomeScene: Understanding Home Assistant's Database Model](https://smarthomescene.com/blog/understanding-home-assistants-database-and-statistics-model/) — MEDIUM confidence
- [Home Assistant Developer Docs: Fetching Data (DataUpdateCoordinator)](https://developers.home-assistant.io/docs/integration_fetching_data/) — HIGH confidence
- [GitHub: home-assistant-automation-suggestions (Danm72)](https://github.com/Danm72/home-assistant-automation-suggestions) — MEDIUM confidence (reference implementation for comparison)
- [Home Assistant Community: REST API docs for automations](https://community.home-assistant.io/t/rest-api-docs-for-automations/119997) — MEDIUM confidence (automation API is undocumented officially)
- [GitHub Issues: Something is blocking Home Assistant startup](https://github.com/home-assistant/core/issues/149244) — HIGH confidence (recurring pattern across multiple reports)
- [Home Assistant Custom Panel Docs](https://www.home-assistant.io/integrations/panel_custom/) — HIGH confidence
- [Home Assistant Developer Docs: Creating Custom Panels](https://developers.home-assistant.io/docs/frontend/custom-ui/creating-custom-panels/) — HIGH confidence
- [Home Assistant Docs: Automation YAML](https://www.home-assistant.io/docs/automation/yaml/) — HIGH confidence

---
*Pitfalls research for: Home Assistant custom integration — ML pattern mining + automation suggestion*
*Researched: 2026-02-22*
