"""Shared pytest fixtures for Smart Habits tests.

This conftest.py:
1. Stubs out the homeassistant module so pure-Python tests can import
   custom_components without a running HA instance.
2. Provides a 90-day, 500-entity state history fixture used across all
   DailyRoutineDetector tests. Uses scope="module" to avoid rebuilding the
   large dataset for each test function (critical for test suite speed).
"""

import random
import sys
import types
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Homeassistant module stubs
#
# The integration's __init__.py imports from homeassistant at package load
# time. Since HA is not installed in the test environment, we inject minimal
# stub modules into sys.modules so Python's import machinery resolves them
# without errors. All HA-dependent files still work via static analysis tests
# (test_integration.py, test_recorder_reader.py). These stubs only allow
# pure-Python submodules (models.py, pattern_detector.py, const.py) to be
# imported without triggering HA's transitive dependency chain.
# ---------------------------------------------------------------------------

def _make_stub(name: str) -> types.ModuleType:
    """Create a minimal stub module for a given dotted name."""
    mod = types.ModuleType(name)
    sys.modules[name] = mod
    return mod


# Only stub if homeassistant is not already installed
if "homeassistant" not in sys.modules:
    _ha = _make_stub("homeassistant")
    _ha_core = _make_stub("homeassistant.core")
    _ha_core.HomeAssistant = MagicMock  # type: ignore[attr-defined]
    _ha_core.callback = lambda f: f  # type: ignore[attr-defined]

    _ha_config = _make_stub("homeassistant.config_entries")
    _ha_config.ConfigEntry = MagicMock  # type: ignore[attr-defined]

    _ha_components = _make_stub("homeassistant.components")
    _ha_recorder = _make_stub("homeassistant.components.recorder")
    _ha_recorder.get_instance = MagicMock()  # type: ignore[attr-defined]

    _ha_recorder_history = _make_stub("homeassistant.components.recorder.history")
    _ha_recorder_history.get_significant_states = MagicMock()  # type: ignore[attr-defined]

    _ha_util = _make_stub("homeassistant.util")
    _ha_dt = _make_stub("homeassistant.util.dt")
    _ha_dt.utcnow = MagicMock()  # type: ignore[attr-defined]
    _ha_dt.as_local = MagicMock()  # type: ignore[attr-defined]

    _ha_helpers = _make_stub("homeassistant.helpers")
    _ha_update_coord = _make_stub("homeassistant.helpers.update_coordinator")
    _ha_update_coord.DataUpdateCoordinator = MagicMock  # type: ignore[attr-defined]
    _ha_update_coord.UpdateFailed = Exception  # type: ignore[attr-defined]

    _ha_helpers_entity = _make_stub("homeassistant.helpers.entity_registry")
    _ha_helpers_entity.async_get = MagicMock()  # type: ignore[attr-defined]

    _ha_helpers_storage = _make_stub("homeassistant.helpers.storage")
    _ha_helpers_storage.Store = MagicMock  # type: ignore[attr-defined]

    _ha_components_ws = _make_stub("homeassistant.components.websocket_api")
    _ha_components_ws.async_register_command = MagicMock()  # type: ignore[attr-defined]
    _ha_components_ws.ActiveConnection = MagicMock  # type: ignore[attr-defined]
    _ha_components_ws.async_response = lambda f: f  # type: ignore[attr-defined]
    _ha_components_ws.websocket_command = lambda schema: (lambda f: f)  # type: ignore[attr-defined]

    # voluptuous is used in websocket_api.py for schema validation
    if "voluptuous" not in sys.modules:
        _vol = _make_stub("voluptuous")
        _vol.Required = MagicMock(return_value=MagicMock())  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Large shared fixture: 90-day, 500-entity state history
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def states_90d_500e():
    """Generate a 90-day, 500-entity state history fixture.

    Embeds known patterns for assertion:
    - light.bedroom: turns on every day at ~07:00 (90/90 days, confidence=1.0)
    - switch.coffee_maker: turns on 7/10 days at 07:30 (63/90, confidence=0.7)
    - light.entity_003 through light.entity_500: random noise — no reliable pattern
      expected at any single hour across 90 days.

    All records are minimal dicts {"last_changed": ISO-string, "state": value}
    to match the format returned by get_significant_states(minimal_response=True).
    """
    base_time = datetime(2025, 11, 1, 0, 0, 0, tzinfo=timezone.utc)
    states: dict[str, list[dict]] = {}

    # Entity 1: perfect daily morning routine at 07:00 (varying minutes 0-14)
    bedroom_states = []
    for day in range(90):
        on_time = base_time + timedelta(days=day, hours=7, minutes=day % 15)
        off_time = on_time + timedelta(hours=1)
        bedroom_states.append({"last_changed": on_time.isoformat(), "state": "on"})
        bedroom_states.append({"last_changed": off_time.isoformat(), "state": "off"})
    states["light.bedroom"] = bedroom_states

    # Entity 2: partial routine — on 63 of 90 days at 07:30
    # 7 out of every 10 days: day % 10 in {0,1,2,3,4,5,6} = 7 days
    coffee_states = []
    for day in range(90):
        if day % 10 < 7:
            on_time = base_time + timedelta(days=day, hours=7, minutes=30)
            off_time = on_time + timedelta(minutes=30)
            coffee_states.append({"last_changed": on_time.isoformat(), "state": "on"})
            coffee_states.append({"last_changed": off_time.isoformat(), "state": "off"})
    states["switch.coffee_maker"] = coffee_states

    # Entities 3-500: random noise (no detectable routine at any single hour)
    # Uses seeded RNG for reproducibility
    rng = random.Random(42)
    for i in range(3, 501):
        entity_id = f"light.entity_{i:03d}"
        entity_states = []
        for day in range(90):
            # 0-4 random events per day scattered across all 24 hours
            for _ in range(rng.randint(0, 4)):
                hour = rng.randint(0, 23)
                minute = rng.randint(0, 59)
                on_time = base_time + timedelta(days=day, hours=hour, minutes=minute)
                off_time = on_time + timedelta(minutes=rng.randint(5, 120))
                entity_states.append({"last_changed": on_time.isoformat(), "state": "on"})
                entity_states.append({"last_changed": off_time.isoformat(), "state": "off"})
        states[entity_id] = entity_states

    return states


@pytest.fixture(scope="module")
def states_with_mixed_types():
    """Fixture with both mock State objects and minimal dicts in the same list.

    Exercises the _extract_record path that handles full State objects
    (returned as first/last records by get_significant_states(minimal_response=True)).
    Confirms the detector handles both without crashing.
    """
    base_time = datetime(2025, 11, 1, 7, 0, 0, tzinfo=timezone.utc)

    # Create a mock State object (simulates HA's State class)
    mock_state_on = MagicMock()
    mock_state_on.last_changed = base_time
    mock_state_on.state = "on"

    mock_state_off = MagicMock()
    mock_state_off.last_changed = base_time + timedelta(hours=1)
    mock_state_off.state = "off"

    # Mix State objects (first/last) with dict records (intermediate)
    mixed_records = [mock_state_on]  # State object first
    for day in range(1, 90):
        on_time = base_time + timedelta(days=day)
        off_time = on_time + timedelta(hours=1)
        mixed_records.append({"last_changed": on_time.isoformat(), "state": "on"})
        mixed_records.append({"last_changed": off_time.isoformat(), "state": "off"})
    mixed_records.append(mock_state_off)  # State object last

    return {"light.mixed_entity": mixed_records}
