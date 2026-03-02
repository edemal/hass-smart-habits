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

    # Panel registration stubs (used in __init__.py for sidebar panel)
    _ha_components_http = _make_stub("homeassistant.components.http")

    class _StaticPathConfig:
        """Minimal stub for homeassistant.components.http.StaticPathConfig."""
        def __init__(self, url_path: str, path: str, cache_headers: bool = True):
            self.url_path = url_path
            self.path = path
            self.cache_headers = cache_headers

    _ha_components_http.StaticPathConfig = _StaticPathConfig  # type: ignore[attr-defined]

    _ha_components_frontend = _make_stub("homeassistant.components.frontend")
    _ha_components_frontend.async_remove_panel = MagicMock()  # type: ignore[attr-defined]

    _ha_components_panel = _make_stub("homeassistant.components.panel_custom")
    _ha_components_panel.async_register_panel = MagicMock()  # type: ignore[attr-defined]

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


# ---------------------------------------------------------------------------
# Presence pattern fixtures: 30-day state history for PresencePatternDetector
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def presence_states_30d():
    """Generate a 30-day state history with known presence arrival patterns.

    Entities:
    - person.alice: arrives home (state="home") daily at 18:00, stays home until 06:00
      next day. 30 genuine arrivals total.
    - person.bob: flaps home/not_home within 3 min on days 5,10,15,20,25, plus 3
      genuine arrivals on days 1, 8, 16. Flaps are filtered out; only 3 genuine
      arrivals remain — below MIN_PAIR_OCCURRENCES=5, so no bob patterns emitted.
    - light.living_room: turns on within 2 min of alice's arrival on 25 of 30 days
      (skip every 6th day starting from day 5). Confidence ~25/30 ~0.833.
    - light.porch: turns on within 1 min of alice's arrival on 18 of 30 days
      (skip days where day % 5 == 4, i.e. days 4,9,14,19,24,29 = 6 days skipped).
      Confidence ~24/30 = 0.8 — adjusted below for exact count.
    - device_tracker.phone: arrives home on 10 days (days 0,3,6,...,27). Used for
      device_tracker fallback test.
    - light.noise_001 through light.noise_010: random activations (seeded RNG=77).

    All records as minimal dicts {"last_changed": ISO-string, "state": value}.
    """
    base_time = datetime(2025, 12, 1, 0, 0, 0, tzinfo=timezone.utc)
    states: dict[str, list[dict]] = {}

    # person.alice: daily arrival at 18:00, departure at 06:00 next day
    alice_records = []
    for day in range(30):
        arrival = base_time + timedelta(days=day, hours=18)
        departure = base_time + timedelta(days=day + 1, hours=6)
        # Initial "not_home" state at midnight so we can detect transitions
        alice_records.append({"last_changed": (base_time + timedelta(days=day)).isoformat(), "state": "not_home"})
        alice_records.append({"last_changed": arrival.isoformat(), "state": "home"})
        alice_records.append({"last_changed": departure.isoformat(), "state": "not_home"})
    states["person.alice"] = alice_records

    # person.bob: 3 genuine arrivals + 5 flap events (home/not_home within 3 min)
    bob_records = []
    genuine_days = [1, 8, 16]
    flap_days = [5, 10, 15, 20, 25]
    for day in range(30):
        bob_records.append({"last_changed": (base_time + timedelta(days=day)).isoformat(), "state": "not_home"})
        if day in genuine_days:
            arrival = base_time + timedelta(days=day, hours=17)
            departure = base_time + timedelta(days=day + 1, hours=5)
            bob_records.append({"last_changed": arrival.isoformat(), "state": "home"})
            bob_records.append({"last_changed": departure.isoformat(), "state": "not_home"})
        elif day in flap_days:
            # Flap: arrives home, then leaves within 3 minutes
            arrival = base_time + timedelta(days=day, hours=17)
            flap_out = arrival + timedelta(minutes=3)
            bob_records.append({"last_changed": arrival.isoformat(), "state": "home"})
            bob_records.append({"last_changed": flap_out.isoformat(), "state": "not_home"})
    states["person.bob"] = bob_records

    # light.living_room: on within 2 min of alice's arrival on 25 of 30 days
    # Skip days where day % 6 == 5: days 5,11,17,23,29 = 5 days skipped -> 25 activations
    living_room_records = []
    for day in range(30):
        if day % 6 != 5:  # 25 out of 30 days
            alice_arrival = base_time + timedelta(days=day, hours=18)
            on_time = alice_arrival + timedelta(minutes=2)
            off_time = on_time + timedelta(hours=2)
            living_room_records.append({"last_changed": on_time.isoformat(), "state": "on"})
            living_room_records.append({"last_changed": off_time.isoformat(), "state": "off"})
    states["light.living_room"] = living_room_records

    # light.porch: on within 1 min of alice's arrival on 18 of 30 days
    # Skip days where day % 5 == 4: days 4,9,14,19,24,29 = 6 days skipped -> 24 activations
    # But also skip days 0,6,12,18 (every 6th from 0) = 5 more -> roughly 18-19 range
    # Use simpler rule: keep days where day % 5 != 4 AND day % 6 != 3
    # days skipped by % 5==4: 4,9,14,19,24,29 (6 days)
    # days skipped by % 6==3: 3,9,15,21,27 (5 days, 9 already counted)
    # union: 3,4,9,14,15,19,21,24,27,29 = 10 days skipped, 20 kept
    # Adjust: skip every 5th day starting from 1: days 1,6,11,16,21,26 (6 days) -> 24 kept
    # Simple: skip days where (day+1) % 5 == 0, i.e. days 4,9,14,19,24,29 -> 6 skipped -> 24 kept
    # Let's use skip every 6th from start: day % 6 in {4,5} -> 10 skipped -> 20 kept
    # Plan says ~18/30. Use: skip days 2,5,8,11,14,17,20,23,26,29,3,7 = complicated
    # Simplest: skip every 5th day (day % 5 == 4) gives 24, skip extra days to get 18
    # Use: skip day if day % 5 == 4 or day % 7 == 0 -> combined unique skips
    # days%5==4: 4,9,14,19,24,29 (6) + days%7==0: 0,7,14,21,28 (5, 14 already) = 10 unique skipped -> 20 kept
    # That gives ~20. For exactly 18: also skip day%11==0 (days 0,11,22 = 3 more, 0 and 14 overlap slightly)
    # Actually plan says ~18/30, let's just use: skip if day % 5 == 4 or day % 4 == 0
    # day%4==0: 0,4,8,12,16,20,24,28 (8) + day%5==4: 4,9,14,19,24,29 (6, 4&24 overlap) = 12 unique -> 18 kept
    porch_records = []
    for day in range(30):
        skip = (day % 4 == 0) or (day % 5 == 4)
        if not skip:
            alice_arrival = base_time + timedelta(days=day, hours=18)
            on_time = alice_arrival + timedelta(seconds=45)
            off_time = on_time + timedelta(hours=1)
            porch_records.append({"last_changed": on_time.isoformat(), "state": "on"})
            porch_records.append({"last_changed": off_time.isoformat(), "state": "off"})
    states["light.porch"] = porch_records

    # device_tracker.phone: arrives home on days 0,3,6,9,...,27 (every 3rd day = 10 days)
    phone_records = []
    for day in range(30):
        phone_records.append({"last_changed": (base_time + timedelta(days=day)).isoformat(), "state": "not_home"})
        if day % 3 == 0:
            arrival = base_time + timedelta(days=day, hours=19)
            departure = base_time + timedelta(days=day + 1, hours=7)
            phone_records.append({"last_changed": arrival.isoformat(), "state": "home"})
            phone_records.append({"last_changed": departure.isoformat(), "state": "not_home"})
    states["device_tracker.phone"] = phone_records

    # 10 noise entities with random activations (seeded RNG=77)
    rng = random.Random(77)
    for i in range(1, 11):
        entity_id = f"light.noise_{i:03d}"
        entity_records = []
        for day in range(30):
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
def presence_states_device_tracker_only():
    """Fixture with only device_tracker.* presence entities (no person.* at all).

    Entities:
    - device_tracker.phone: arrives home daily at 17:00, 30 genuine arrivals.
    - light.hallway: turns on within 2 min of phone arrival on 22 of 30 days.
    """
    base_time = datetime(2025, 12, 1, 0, 0, 0, tzinfo=timezone.utc)
    states: dict[str, list[dict]] = {}

    # device_tracker.phone: arrives daily at 17:00
    phone_records = []
    for day in range(30):
        phone_records.append({"last_changed": (base_time + timedelta(days=day)).isoformat(), "state": "not_home"})
        arrival = base_time + timedelta(days=day, hours=17)
        departure = base_time + timedelta(days=day + 1, hours=8)
        phone_records.append({"last_changed": arrival.isoformat(), "state": "home"})
        phone_records.append({"last_changed": departure.isoformat(), "state": "not_home"})
    states["device_tracker.phone"] = phone_records

    # light.hallway: on within 2 min on 22 of 30 days
    # Skip every 6th day (5 skips) and every 9th day (3 skips, with overlap check)
    # days%6==5: 5,11,17,23,29 (5 days) + days%9==4: 4,13,22 (3 days) -> 8 unique -> 22 kept
    hallway_records = []
    for day in range(30):
        skip = (day % 6 == 5) or (day % 9 == 4)
        if not skip:
            phone_arrival = base_time + timedelta(days=day, hours=17)
            on_time = phone_arrival + timedelta(minutes=1, seconds=30)
            off_time = on_time + timedelta(hours=1)
            hallway_records.append({"last_changed": on_time.isoformat(), "state": "on"})
            hallway_records.append({"last_changed": off_time.isoformat(), "state": "off"})
    states["light.hallway"] = hallway_records

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
