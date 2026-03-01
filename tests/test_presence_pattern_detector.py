"""Tests for PresencePatternDetector.

TDD RED phase: All tests written before the implementation exists.
Tests verify:
- Known arrival-device correlation detected with correct confidence
- Flap-noise arrivals (home then not_home within 3 min) are NOT counted
- device_tracker.* entities used as presence triggers when no person.* exists
- Minimum arrivals gate (fewer than 5 arrivals: no patterns)
- Presence entity NOT in device set (no self-correlation)
- Pattern field correctness (pattern_type, peak_hour, secondary_entity_id, evidence)
- Performance: 50 entities / 30 days under 10 seconds
- Zero HA imports in presence.py module
- Empty input handling
- Results sorted by confidence descending
"""

import time

import pytest

from custom_components.smart_habits.detectors.presence import (
    PresencePatternDetector,
)


# ---------------------------------------------------------------------------
# Test 1: Known arrival-device correlation detected with correct confidence
# ---------------------------------------------------------------------------


def test_detects_known_arrival_pattern(presence_states_30d):
    """person.alice -> light.living_room fires 25/30 arrivals -> confidence ~0.83."""
    detector = PresencePatternDetector(window_seconds=300)
    patterns = detector.detect(presence_states_30d, lookback_days=30)

    matching = [
        p for p in patterns
        if p.entity_id == "person.alice" and p.secondary_entity_id == "light.living_room"
    ]
    assert len(matching) >= 1, (
        "Expected at least one pattern person.alice -> light.living_room"
    )
    best = max(matching, key=lambda p: p.confidence)
    assert best.pattern_type == "presence_arrival"
    assert best.confidence >= 0.6, f"Confidence too low: {best.confidence}"


# ---------------------------------------------------------------------------
# Test 2: Flap-noise arrivals are filtered out
# ---------------------------------------------------------------------------


def test_flap_noise_filtered(presence_states_30d):
    """person.bob with 5 flaps (3-min home/not_home): only 3 genuine arrivals.

    Bob has fewer than MIN_PAIR_OCCURRENCES=5 genuine arrivals, so no bob
    patterns should be emitted.
    """
    detector = PresencePatternDetector(window_seconds=300)
    patterns = detector.detect(presence_states_30d, lookback_days=30)

    bob_patterns = [
        p for p in patterns
        if p.entity_id == "person.bob"
    ]
    assert len(bob_patterns) == 0, (
        f"Expected no patterns for person.bob (3 genuine arrivals < MIN_PAIR_OCCURRENCES=5), "
        f"got {bob_patterns}"
    )


# ---------------------------------------------------------------------------
# Test 3: device_tracker.* used as presence triggers when no person.* exists
# ---------------------------------------------------------------------------


def test_device_tracker_fallback(presence_states_device_tracker_only):
    """When only device_tracker.* presence entities exist, arrivals detected correctly."""
    detector = PresencePatternDetector(window_seconds=300)
    patterns = detector.detect(presence_states_device_tracker_only, lookback_days=30)

    matching = [
        p for p in patterns
        if p.entity_id == "device_tracker.phone" and p.secondary_entity_id == "light.hallway"
    ]
    assert len(matching) >= 1, (
        "Expected at least one pattern device_tracker.phone -> light.hallway"
    )
    best = max(matching, key=lambda p: p.confidence)
    assert best.confidence >= 0.6, f"Confidence too low: {best.confidence}"


# ---------------------------------------------------------------------------
# Test 4: Minimum arrivals gate
# ---------------------------------------------------------------------------


def test_min_arrivals_gate():
    """Presence entity with only 3 genuine arrivals: no patterns emitted."""
    from datetime import datetime, timedelta, timezone

    base = datetime(2025, 12, 1, 18, 0, 0, tzinfo=timezone.utc)
    states = {}

    # person with only 3 genuine arrivals
    person_records = []
    for day in range(30):
        person_records.append({"last_changed": (base + timedelta(days=day)).isoformat(), "state": "not_home"})
    for day in [2, 10, 20]:
        arrival = base + timedelta(days=day)
        departure = arrival + timedelta(hours=12)
        person_records.append({"last_changed": arrival.isoformat(), "state": "home"})
        person_records.append({"last_changed": departure.isoformat(), "state": "not_home"})
    states["person.rare"] = person_records

    # device activates all 3 times
    device_records = []
    for day in [2, 10, 20]:
        on_time = base + timedelta(days=day, minutes=1)
        off_time = on_time + timedelta(hours=1)
        device_records.append({"last_changed": on_time.isoformat(), "state": "on"})
        device_records.append({"last_changed": off_time.isoformat(), "state": "off"})
    states["light.test_device"] = device_records

    detector = PresencePatternDetector(window_seconds=300)
    patterns = detector.detect(states, lookback_days=30)

    assert len(patterns) == 0, (
        f"Expected no patterns for entity with < 5 genuine arrivals, got {patterns}"
    )


# ---------------------------------------------------------------------------
# Test 5: Presence entity NOT in device set (no self-correlation)
# ---------------------------------------------------------------------------


def test_presence_entity_not_in_device_set(presence_states_30d):
    """No pattern has secondary_entity_id that is a person.* or device_tracker.* entity."""
    detector = PresencePatternDetector(window_seconds=300)
    patterns = detector.detect(presence_states_30d, lookback_days=30)

    presence_domains = {"person", "device_tracker"}
    for p in patterns:
        if p.secondary_entity_id is not None:
            domain = p.secondary_entity_id.split(".")[0]
            assert domain not in presence_domains, (
                f"Pattern secondary_entity_id={p.secondary_entity_id!r} is a presence entity "
                f"(domain={domain!r}). Presence entities must be excluded from device set."
            )


# ---------------------------------------------------------------------------
# Test 6: Pattern fields are correct
# ---------------------------------------------------------------------------


def test_pattern_fields(presence_states_30d):
    """pattern_type='presence_arrival', peak_hour=0, secondary_entity_id set, evidence has 'arriving'."""
    detector = PresencePatternDetector(window_seconds=300)
    patterns = detector.detect(presence_states_30d, lookback_days=30)

    assert len(patterns) > 0, "Expected at least one pattern"

    for p in patterns:
        assert p.pattern_type == "presence_arrival", (
            f"Wrong pattern_type: {p.pattern_type}"
        )
        assert p.peak_hour == 0, f"peak_hour should be 0 sentinel, got {p.peak_hour}"
        assert p.secondary_entity_id is not None, "secondary_entity_id must be set"
        assert "arriving" in p.evidence, (
            f"evidence should contain 'arriving', got: {p.evidence!r}"
        )
        assert "activates within" in p.evidence, (
            f"evidence should contain 'activates within', got: {p.evidence!r}"
        )


# ---------------------------------------------------------------------------
# Test 7: Performance — 50 entities / 30 days under 10 seconds
# ---------------------------------------------------------------------------


def test_performance_50_entities(presence_states_30d):
    """50 entities / 30 days processed in under 10 seconds."""
    # presence_states_30d has ~15 entities; supplement with noise to reach 50
    from datetime import datetime, timedelta, timezone
    import random

    states = dict(presence_states_30d)  # copy
    base_time = datetime(2025, 12, 1, 0, 0, 0, tzinfo=timezone.utc)
    rng = random.Random(42)

    # Add extra noise entities to reach 50 total
    extra = 50 - len(states)
    for i in range(extra):
        entity_id = f"light.perf_noise_{i:03d}"
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

    detector = PresencePatternDetector(window_seconds=300)
    start = time.monotonic()
    patterns = detector.detect(states, lookback_days=30)
    elapsed = time.monotonic() - start

    assert elapsed < 10.0, f"Performance threshold exceeded: {elapsed:.2f}s (limit 10s)"


# ---------------------------------------------------------------------------
# Test 8: No homeassistant imports in presence.py module
# ---------------------------------------------------------------------------


def test_no_ha_imports():
    """presence.py must not import from homeassistant.*."""
    import inspect
    import re
    import custom_components.smart_habits.detectors.presence as mod

    src = inspect.getsource(mod)
    # Check for actual import statements only (not occurrences in comments/docstrings)
    ha_imports = re.findall(r"^\s*(import|from)\s+homeassistant", src, re.MULTILINE)
    assert len(ha_imports) == 0, (
        f"Found homeassistant import statements in presence.py: {ha_imports}"
    )


# ---------------------------------------------------------------------------
# Test 9: Empty input returns empty list
# ---------------------------------------------------------------------------


def test_empty_input():
    """detect({}, 30) returns [] without error."""
    detector = PresencePatternDetector()
    result = detector.detect({}, 30)
    assert result == [], f"Expected [], got {result}"


# ---------------------------------------------------------------------------
# Test 10: Results sorted by confidence descending
# ---------------------------------------------------------------------------


def test_sorted_by_confidence_desc(presence_states_30d):
    """Returned patterns sorted by confidence descending."""
    detector = PresencePatternDetector(window_seconds=300)
    patterns = detector.detect(presence_states_30d, lookback_days=30)

    if len(patterns) < 2:
        pytest.skip("Need at least 2 patterns to verify sorting")

    confidences = [p.confidence for p in patterns]
    assert confidences == sorted(confidences, reverse=True), (
        f"Patterns not sorted by confidence desc: {confidences[:5]}"
    )
