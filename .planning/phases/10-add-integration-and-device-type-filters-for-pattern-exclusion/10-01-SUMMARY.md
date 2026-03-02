---
phase: 10-add-integration-and-device-type-filters-for-pattern-exclusion
plan: "01"
subsystem: config
tags: [config-flow, options-flow, constants, filters, exclusion]
dependency_graph:
  requires: []
  provides:
    - CONF_EXCLUDED_INTEGRATIONS constant
    - CONF_EXCLUDED_DOMAINS constant
    - DEFAULT_EXCLUDED_INTEGRATIONS constant
    - DEFAULT_EXCLUDED_DOMAINS constant
    - Options flow multi-select fields for integration and domain exclusion
    - Dynamic integration list from entity registry
    - Options propagation to coordinator attributes
  affects:
    - custom_components/smart_habits/coordinator.py (Plan 02 will add these attributes)
tech_stack:
  added: []
  patterns:
    - vol.Optional with SelectSelectorConfig(multiple=True) for multi-select list fields
    - Dynamic integration discovery via er.async_get(hass) at options flow init time
    - list() wrapper on options values to prevent shared mutable state
key_files:
  created: []
  modified:
    - custom_components/smart_habits/const.py
    - custom_components/smart_habits/config_flow.py
    - custom_components/smart_habits/strings.json
    - custom_components/smart_habits/__init__.py
decisions:
  - vol.Optional used (not vol.Required) for both filter fields so existing config entries without these fields upgrade gracefully
  - Dynamic integration list built at flow init time from entity registry, not cached, so it reflects current HA state
  - list() wrapper on entry.options.get() return value ensures coordinator gets a fresh copy, not a reference to the options dict
metrics:
  duration: "2 min"
  completed_date: "2026-03-02"
  tasks_completed: 2
  files_modified: 4
---

# Phase 10 Plan 01: Integration and Domain Filter Configuration Summary

Two new multi-select exclusion filter fields wired end-to-end: constants in const.py, dynamic integration list helper + vol.Optional SelectSelector fields in options flow, UI labels in strings.json, and coordinator attribute propagation in __init__.py.

## What Was Built

### Task 1: Filter constants and options flow multi-select fields

Added four new constants to `const.py`:

```python
CONF_EXCLUDED_INTEGRATIONS = "excluded_integrations"
DEFAULT_EXCLUDED_INTEGRATIONS: list[str] = []

CONF_EXCLUDED_DOMAINS = "excluded_domains"
DEFAULT_EXCLUDED_DOMAINS: list[str] = []
```

Added `_get_available_integrations(hass)` helper to `config_flow.py` that queries the entity registry at flow init time and returns a sorted list of integration (platform) names for entities in `DEFAULT_ENTITY_DOMAINS`.

Extended `SmartHabitsOptionsFlow.async_step_init` with two `vol.Optional` multi-select fields using `SelectSelectorConfig(multiple=True, mode=SelectSelectorMode.LIST)`:
- `CONF_EXCLUDED_INTEGRATIONS`: options populated dynamically from entity registry
- `CONF_EXCLUDED_DOMAINS`: options from static `DEFAULT_ENTITY_DOMAINS` list

Added UI labels and descriptions to `strings.json` for both fields.

### Task 2: Options propagation to coordinator attributes

Extended `_async_options_updated` in `__init__.py` to set two new coordinator attributes after the existing `sequence_window` assignment:

```python
coordinator.excluded_integrations = list(
    entry.options.get(CONF_EXCLUDED_INTEGRATIONS, DEFAULT_EXCLUDED_INTEGRATIONS)
)
coordinator.excluded_domains = list(
    entry.options.get(CONF_EXCLUDED_DOMAINS, DEFAULT_EXCLUDED_DOMAINS)
)
```

The `list()` wrapper prevents shared mutable state. Both are set before `await coordinator.async_refresh()`.

## Deviations from Plan

None - plan executed exactly as written.

## Decisions Made

- `vol.Optional` (not `vol.Required`) for both filter fields: ensures existing config entries without these fields upgrade gracefully without validation errors
- Dynamic integration list at flow init time: reflects current HA entity registry state rather than stale cached values
- `list()` wrapper on options values: ensures coordinator holds a fresh copy, not a reference into the config entry options dict

## Self-Check

Checked files exist and commits present:
- `custom_components/smart_habits/const.py`: FOUND
- `custom_components/smart_habits/config_flow.py`: FOUND
- `custom_components/smart_habits/strings.json`: FOUND
- `custom_components/smart_habits/__init__.py`: FOUND
- Task 1 commit 5835b1f: FOUND
- Task 2 commit 18abb50: FOUND

## Self-Check: PASSED
