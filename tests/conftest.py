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

    _ha_helpers_selector = _make_stub("homeassistant.helpers.selector")
    _ha_helpers_selector.SelectSelector = MagicMock  # type: ignore[attr-defined]
    _ha_helpers_selector.SelectSelectorConfig = MagicMock  # type: ignore[attr-defined]
    _ha_helpers_selector.SelectSelectorMode = MagicMock  # type: ignore[attr-defined]

    _ha_components_ws = _make_stub("homeassistant.components.websocket_api")
    _ha_components_ws.async_register_command = MagicMock()  # type: ignore[attr-defined]
    _ha_components_ws.ActiveConnection = MagicMock  # type: ignore[attr-defined]
    _ha_components_ws.async_response = lambda f: f  # type: ignore[attr-defined]
    _ha_components_ws.websocket_command = lambda schema: (lambda f: f)  # type: ignore[attr-defined]

    # voluptuous is used in websocket_api.py for schema validation
    if "voluptuous" not in sys.modules:
        _vol = _make_stub("voluptuous")
        _vol.Required = MagicMock(return_value=MagicMock())  # type: ignore[attr-defined]
        _vol.Optional = MagicMock(return_value=MagicMock())  # type: ignore[attr-defined]
        _vol.Any = MagicMock(return_value=MagicMock())  # type: ignore[attr-defined]


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


# ---------------------------------------------------------------------------
# Temporal sequence fixture: 50-entity, 30-day state history
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def temporal_states_30d():
    """Generate a 50-entity, 30-day state history with known A->B sequences.

    Known sequences embedded for assertion:
    - light.hallway -> light.kitchen: hallway activates every day; kitchen
      activates 2-3 min later on 20 of 30 days (skip every 3rd day).
      Confidence ~20/30 ≈ 0.67 at 5-min window.
    - switch.door_sensor -> light.porch: door_sensor activates daily; porch
      activates within 1 min on 25 of 30 days (skip every 6th day).
      Confidence ~25/30 ≈ 0.83 at 5-min window.
    - 46 noise entities: random activations with a seeded RNG.

    All records as minimal dicts {"last_changed": ISO-string, "state": "on"/"off"}.
    """
    base_time = datetime(2025, 12, 1, 8, 0, 0, tzinfo=timezone.utc)
    states: dict[str, list[dict]] = {}

    # Known pair 1: light.hallway -> light.kitchen (20/30 days, within 3 min)
    hallway_records = []
    kitchen_records = []
    for day in range(30):
        # hallway activates every day at 08:00 + slight jitter
        h_on = base_time + timedelta(days=day, minutes=day % 5)
        hallway_records.append({"last_changed": h_on.isoformat(), "state": "on"})
        hallway_records.append({"last_changed": (h_on + timedelta(minutes=30)).isoformat(), "state": "off"})

        # kitchen activates 2-3 min after hallway on 20 of 30 days (skip every 3rd day)
        if day % 3 != 2:  # 20 out of 30 days (days 0,1,3,4,6,7,... — skip day 2,5,8,...)
            k_on = h_on + timedelta(minutes=2 + (day % 2))  # 2 or 3 minutes later
            kitchen_records.append({"last_changed": k_on.isoformat(), "state": "on"})
            kitchen_records.append({"last_changed": (k_on + timedelta(minutes=20)).isoformat(), "state": "off"})

    states["light.hallway"] = hallway_records
    states["light.kitchen"] = kitchen_records

    # Known pair 2: switch.door_sensor -> light.porch (25/30 days, within 1 min)
    door_records = []
    porch_records = []
    for day in range(30):
        # door_sensor activates every day at 18:00
        d_on = base_time + timedelta(days=day, hours=10)
        door_records.append({"last_changed": d_on.isoformat(), "state": "on"})
        door_records.append({"last_changed": (d_on + timedelta(minutes=1)).isoformat(), "state": "off"})

        # porch activates within 1 min on 25 of 30 days (skip every 6th day)
        if day % 6 != 5:  # 25 out of 30 days
            p_on = d_on + timedelta(seconds=30)
            porch_records.append({"last_changed": p_on.isoformat(), "state": "on"})
            porch_records.append({"last_changed": (p_on + timedelta(minutes=30)).isoformat(), "state": "off"})

    states["switch.door_sensor"] = door_records
    states["light.porch"] = porch_records

    # 46 noise entities: random activations (seeded for reproducibility)
    rng = random.Random(99)
    for i in range(1, 47):
        entity_id = f"light.noise_{i:03d}"
        entity_records = []
        for day in range(30):
            # 0-3 random events per day
            for _ in range(rng.randint(0, 3)):
                hour = rng.randint(0, 23)
                minute = rng.randint(0, 59)
                on_time = base_time + timedelta(days=day, hours=hour, minutes=minute)
                off_time = on_time + timedelta(minutes=rng.randint(5, 60))
                entity_records.append({"last_changed": on_time.isoformat(), "state": "on"})
                entity_records.append({"last_changed": off_time.isoformat(), "state": "off"})
        states[entity_id] = entity_records

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
