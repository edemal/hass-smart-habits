"""Tests for TemporalSequenceDetector.

TDD RED phase: All tests written before the implementation exists.
Tests verify:
- Known sequence detection with correct confidence
- Window-boundary behavior
- Minimum occurrence gate (MIN_PAIR_OCCURRENCES=5)
- Self-pair exclusion
- Pattern field correctness
- Performance: 50 entities / 30 days under 10 seconds
- Zero HA imports in detector module
- Empty input handling
- Sorting by confidence descending
"""

import time

import pytest

from custom_components.smart_habits.detectors.temporal_sequence import (
    TemporalSequenceDetector,
)


# ---------------------------------------------------------------------------
# Test 1: Known sequence detected with correct confidence
# ---------------------------------------------------------------------------


def test_detects_known_sequence(temporal_states_30d):
    """light.hallway -> light.kitchen fires 20/30 days within 5 min -> confidence ~0.67."""
    detector = TemporalSequenceDetector(window_seconds=300)
    patterns = detector.detect(temporal_states_30d, lookback_days=30)

    matching = [
        p for p in patterns
        if p.entity_id == "light.hallway" and p.secondary_entity_id == "light.kitchen"
    ]
    assert len(matching) >= 1, (
        "Expected at least one pattern light.hallway -> light.kitchen"
    )
    best = max(matching, key=lambda p: p.confidence)
    assert best.pattern_type == "temporal_sequence"
    assert best.confidence >= 0.5, f"Confidence too low: {best.confidence}"


# ---------------------------------------------------------------------------
# Test 2: High-confidence sequence detected
# ---------------------------------------------------------------------------


def test_detects_high_confidence_sequence(temporal_states_30d):
    """switch.door_sensor -> light.porch fires 25/30 days -> confidence ~0.83."""
    detector = TemporalSequenceDetector(window_seconds=300)
    patterns = detector.detect(temporal_states_30d, lookback_days=30)

    matching = [
        p for p in patterns
        if p.entity_id == "switch.door_sensor" and p.secondary_entity_id == "light.porch"
    ]
    assert len(matching) >= 1, (
        "Expected at least one pattern switch.door_sensor -> light.porch"
    )
    best = max(matching, key=lambda p: p.confidence)
    assert best.confidence >= 0.7, f"Expected confidence >= 0.7, got {best.confidence}"


# ---------------------------------------------------------------------------
# Test 3: Window boundary — outside window not detected, inside window detected
# ---------------------------------------------------------------------------


def test_no_pattern_outside_window():
    """A activates, then B activates 10 minutes later. 5-min window: no pattern.
    15-min window: pattern detected."""
    from datetime import datetime, timedelta, timezone

    base = datetime(2025, 11, 1, 8, 0, 0, tzinfo=timezone.utc)
    states = {}

    # A activates at 08:00 each day
    # B activates at 08:10 each day (10 minutes later)
    a_records = []
    b_records = []
    for day in range(30):
        a_time = base + timedelta(days=day)
        b_time = a_time + timedelta(minutes=10)
        a_records.append({"last_changed": a_time.isoformat(), "state": "on"})
        a_records.append({"last_changed": (a_time + timedelta(hours=1)).isoformat(), "state": "off"})
        b_records.append({"last_changed": b_time.isoformat(), "state": "on"})
        b_records.append({"last_changed": (b_time + timedelta(hours=1)).isoformat(), "state": "off"})

    states["light.entity_a"] = a_records
    states["light.entity_b"] = b_records

    # 5-minute window: B is outside window -> no pattern for A->B
    detector_narrow = TemporalSequenceDetector(window_seconds=300, min_confidence=0.6)
    patterns_narrow = detector_narrow.detect(states, lookback_days=30)
    ab_narrow = [
        p for p in patterns_narrow
        if p.entity_id == "light.entity_a" and p.secondary_entity_id == "light.entity_b"
    ]
    assert len(ab_narrow) == 0, f"Expected no pattern with 5-min window, got {ab_narrow}"

    # 15-minute window: B is inside window -> pattern detected
    detector_wide = TemporalSequenceDetector(window_seconds=900, min_confidence=0.6)
    patterns_wide = detector_wide.detect(states, lookback_days=30)
    ab_wide = [
        p for p in patterns_wide
        if p.entity_id == "light.entity_a" and p.secondary_entity_id == "light.entity_b"
    ]
    assert len(ab_wide) >= 1, f"Expected pattern with 15-min window, got nothing"


# ---------------------------------------------------------------------------
# Test 4: Minimum occurrences gate
# ---------------------------------------------------------------------------


def test_min_occurrences_gate():
    """Entity A with only 3 activations (below MIN_PAIR_OCCURRENCES=5): no patterns."""
    from datetime import datetime, timedelta, timezone

    base = datetime(2025, 11, 1, 8, 0, 0, tzinfo=timezone.utc)
    states = {}

    # A activates only 3 times
    a_records = []
    for day in range(3):
        a_time = base + timedelta(days=day)
        a_records.append({"last_changed": a_time.isoformat(), "state": "on"})
        a_records.append({"last_changed": (a_time + timedelta(hours=1)).isoformat(), "state": "off"})
    states["light.rare_entity"] = a_records

    # B activates 20 times (sufficient)
    b_records = []
    for day in range(20):
        b_time = base + timedelta(days=day, minutes=2)
        b_records.append({"last_changed": b_time.isoformat(), "state": "on"})
        b_records.append({"last_changed": (b_time + timedelta(hours=1)).isoformat(), "state": "off"})
    states["light.frequent_entity"] = b_records

    detector = TemporalSequenceDetector(window_seconds=300)
    patterns = detector.detect(states, lookback_days=30)

    patterns_involving_a = [
        p for p in patterns
        if p.entity_id == "light.rare_entity" or p.secondary_entity_id == "light.rare_entity"
    ]
    assert len(patterns_involving_a) == 0, (
        f"Expected no patterns for entity with < 5 activations, got {patterns_involving_a}"
    )


# ---------------------------------------------------------------------------
# Test 5: Self-pair excluded
# ---------------------------------------------------------------------------


def test_self_pair_excluded(temporal_states_30d):
    """No pattern should have entity_id == secondary_entity_id."""
    detector = TemporalSequenceDetector(window_seconds=300)
    patterns = detector.detect(temporal_states_30d, lookback_days=30)

    self_pairs = [p for p in patterns if p.entity_id == p.secondary_entity_id]
    assert len(self_pairs) == 0, f"Found self-pairs: {self_pairs}"


# ---------------------------------------------------------------------------
# Test 6: Pattern fields are correct
# ---------------------------------------------------------------------------


def test_pattern_fields(temporal_states_30d):
    """Emitted patterns have correct field values."""
    detector = TemporalSequenceDetector(window_seconds=300)
    patterns = detector.detect(temporal_states_30d, lookback_days=30)

    assert len(patterns) > 0, "Expected at least one pattern"

    for p in patterns:
        assert p.pattern_type == "temporal_sequence", (
            f"Wrong pattern_type: {p.pattern_type}"
        )
        assert p.peak_hour == 0, f"peak_hour should be 0 sentinel, got {p.peak_hour}"
        assert p.secondary_entity_id is not None, "secondary_entity_id must be set"
        assert "activates within" in p.evidence, (
            f"evidence should contain 'activates within', got: {p.evidence}"
        )


# ---------------------------------------------------------------------------
# Test 7: Performance — 50 entities / 30 days under 10 seconds
# ---------------------------------------------------------------------------


def test_performance_50_entities_30_days(temporal_states_30d):
    """Detector processes 50 entities / 30 days in under 10 seconds."""
    detector = TemporalSequenceDetector(window_seconds=300)
    start = time.monotonic()
    patterns = detector.detect(temporal_states_30d, lookback_days=30)
    elapsed = time.monotonic() - start

    assert elapsed < 10.0, f"Performance threshold exceeded: {elapsed:.2f}s (limit 10s)"


# ---------------------------------------------------------------------------
# Test 8: No homeassistant imports in detector module
# ---------------------------------------------------------------------------


def test_no_ha_imports():
    """Detector module must not import from homeassistant.*."""
    import inspect
    import re
    import custom_components.smart_habits.detectors.temporal_sequence as mod

    src = inspect.getsource(mod)
    # Check for actual import statements only (not occurrences in comments/docstrings)
    ha_imports = re.findall(r"^\s*(import|from)\s+homeassistant", src, re.MULTILINE)
    assert len(ha_imports) == 0, (
        f"Found homeassistant import statements in temporal_sequence.py: {ha_imports}"
    )


# ---------------------------------------------------------------------------
# Test 9: Empty input returns empty list
# ---------------------------------------------------------------------------


def test_empty_input():
    """detect({}, 30) returns empty list without crashing."""
    detector = TemporalSequenceDetector()
    result = detector.detect({}, 30)
    assert result == [], f"Expected [], got {result}"


# ---------------------------------------------------------------------------
# Test 10: Results sorted by confidence descending
# ---------------------------------------------------------------------------


def test_sorted_by_confidence_desc(temporal_states_30d):
    """Returned patterns are sorted by confidence descending."""
    detector = TemporalSequenceDetector(window_seconds=300)
    patterns = detector.detect(temporal_states_30d, lookback_days=30)

    if len(patterns) < 2:
        pytest.skip("Need at least 2 patterns to verify sorting")

    confidences = [p.confidence for p in patterns]
    assert confidences == sorted(confidences, reverse=True), (
        f"Patterns not sorted by confidence desc: {confidences[:5]}"
    )
