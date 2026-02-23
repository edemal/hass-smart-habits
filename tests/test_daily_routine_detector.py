"""Tests for DailyRoutineDetector — correctness and performance.

TDD RED phase: all tests are written before implementation exists.
Tests validate PDET-02 (daily routine detection) and PDET-05 (confidence scoring).

Algorithm under test: hour-of-day frequency binning
- Counts distinct calendar days each entity was active at each hour
- confidence = active_days / lookback_days
- Returns DetectedPattern objects sorted by confidence descending
"""

import time

import pytest

from custom_components.smart_habits.detectors import DailyRoutineDetector
from custom_components.smart_habits.detectors._utils import (
    ACTIVE_STATES,
    SKIP_STATES,
)
from custom_components.smart_habits.models import DetectedPattern
from custom_components.smart_habits.const import MIN_EVENTS_THRESHOLD


# ---------------------------------------------------------------------------
# Core detection correctness
# ---------------------------------------------------------------------------


def test_detects_perfect_daily_routine(states_90d_500e):
    """DailyRoutineDetector identifies light.bedroom morning routine (PDET-02).

    light.bedroom is on every day at ~07:00 for 90 days.
    Expected: confidence >= 0.9, peak_hour == 7.
    """
    detector = DailyRoutineDetector(min_confidence=0.6)
    patterns = detector.detect(states_90d_500e, lookback_days=90)

    bedroom_patterns = [p for p in patterns if p.entity_id == "light.bedroom"]
    assert bedroom_patterns, "Expected at least one pattern for light.bedroom"

    top = bedroom_patterns[0]
    assert top.peak_hour == 7, f"Expected peak_hour=7, got {top.peak_hour}"
    assert top.confidence >= 0.9, (
        f"Expected confidence >= 0.9 for daily bedroom routine, got {top.confidence}"
    )
    assert top.pattern_type == "daily_routine"


def test_detects_partial_routine(states_90d_500e):
    """DailyRoutineDetector detects switch.coffee_maker partial routine (PDET-02).

    switch.coffee_maker is on 63 of 90 days (7/10 day rate) at 07:30.
    Expected: 0.6 <= confidence <= 0.8, peak_hour == 7.
    """
    detector = DailyRoutineDetector(min_confidence=0.6)
    patterns = detector.detect(states_90d_500e, lookback_days=90)

    coffee_patterns = [p for p in patterns if p.entity_id == "switch.coffee_maker"]
    assert coffee_patterns, "Expected at least one pattern for switch.coffee_maker"

    top = coffee_patterns[0]
    assert top.peak_hour == 7, f"Expected peak_hour=7 for coffee maker, got {top.peak_hour}"
    assert 0.6 <= top.confidence <= 0.8, (
        f"Expected 0.6 <= confidence <= 0.8 for partial routine, got {top.confidence}"
    )


def test_no_false_positives_from_noise(states_90d_500e):
    """Random noise entities do not produce high-confidence patterns.

    498 random entities (light.entity_003 to light.entity_500) have random
    events 0-4 times per day spread across all 24 hours. With random seed 42,
    no single (entity, hour) pair should accumulate enough distinct dates
    to exceed confidence >= 0.6.

    Allows up to 9 false positives as a generous tolerance for statistical noise.
    """
    detector = DailyRoutineDetector(min_confidence=0.6)
    patterns = detector.detect(states_90d_500e, lookback_days=90)

    noise_patterns = [
        p for p in patterns
        if p.entity_id not in ("light.bedroom", "switch.coffee_maker")
        and p.confidence >= 0.6
    ]
    assert len(noise_patterns) < 10, (
        f"Expected fewer than 10 false positives from noise entities, "
        f"got {len(noise_patterns)}: {[(p.entity_id, p.confidence) for p in noise_patterns[:5]]}"
    )


# ---------------------------------------------------------------------------
# Pattern data quality
# ---------------------------------------------------------------------------


def test_confidence_score_in_range(states_90d_500e):
    """All detected patterns have confidence in [0.0, 1.0] (PDET-05)."""
    detector = DailyRoutineDetector(min_confidence=0.0)
    patterns = detector.detect(states_90d_500e, lookback_days=90)

    for p in patterns:
        assert 0.0 <= p.confidence <= 1.0, (
            f"Pattern {p.entity_id} has out-of-range confidence: {p.confidence}"
        )


def test_evidence_string_format(states_90d_500e):
    """All detected patterns have human-readable evidence strings (PDET-05).

    Evidence must contain "of last" and "days" to match the format:
    "happened N of last M days"
    """
    detector = DailyRoutineDetector(min_confidence=0.6)
    patterns = detector.detect(states_90d_500e, lookback_days=90)

    assert patterns, "Expected at least some patterns from the fixture"
    for p in patterns:
        assert "of last" in p.evidence, (
            f"Pattern {p.entity_id} evidence missing 'of last': {p.evidence!r}"
        )
        assert "days" in p.evidence, (
            f"Pattern {p.entity_id} evidence missing 'days': {p.evidence!r}"
        )


def test_patterns_sorted_by_confidence_descending(states_90d_500e):
    """detect() returns patterns sorted by confidence descending."""
    detector = DailyRoutineDetector(min_confidence=0.6)
    patterns = detector.detect(states_90d_500e, lookback_days=90)

    confidences = [p.confidence for p in patterns]
    assert confidences == sorted(confidences, reverse=True), (
        "Patterns must be sorted by confidence descending"
    )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_empty_states_returns_empty():
    """detect({}, lookback_days) returns an empty list (no crash)."""
    detector = DailyRoutineDetector()
    result = detector.detect({}, lookback_days=90)
    assert result == [], f"Expected [], got {result}"


def test_skip_unavailable_states():
    """Entity with all 'unavailable' records produces no patterns."""
    states = {
        "light.broken": [
            {"last_changed": "2025-11-01T07:00:00+00:00", "state": "unavailable"},
            {"last_changed": "2025-11-02T07:00:00+00:00", "state": "unknown"},
            {"last_changed": "2025-11-03T07:00:00+00:00", "state": "none"},
        ]
    }
    detector = DailyRoutineDetector(min_confidence=0.0)
    patterns = detector.detect(states, lookback_days=90)
    assert patterns == [], (
        f"Entity with only skip-states should produce no patterns, got {patterns}"
    )


def test_handles_mixed_record_types(states_with_mixed_types):
    """Detector handles both mock State objects and dict records without crashing.

    Exercises the hasattr(record, 'last_changed') branch in _extract_record.
    Expects light.mixed_entity to produce a pattern at hour 7 with high confidence.
    """
    detector = DailyRoutineDetector(min_confidence=0.6)
    # Should not raise; should produce a pattern for the mixed entity
    patterns = detector.detect(states_with_mixed_types, lookback_days=90)
    assert patterns, "Expected at least one pattern from mixed-type fixture"

    entity_patterns = [p for p in patterns if p.entity_id == "light.mixed_entity"]
    assert entity_patterns, "Expected pattern for light.mixed_entity"
    assert entity_patterns[0].peak_hour == 7
    assert entity_patterns[0].confidence >= 0.9


# ---------------------------------------------------------------------------
# Minimum events threshold
# ---------------------------------------------------------------------------


def test_min_events_threshold():
    """Entity with fewer than MIN_EVENTS_THRESHOLD records produces no patterns.

    This is a safety check: very sparse entities (e.g., 3 state changes in 90 days)
    cannot form meaningful patterns regardless of min_confidence.
    """
    # Build a fixture with MIN_EVENTS_THRESHOLD - 1 records, all at same hour
    # Even with perfect alignment, threshold should prevent pattern emission
    states = {
        "light.sparse": [
            {"last_changed": f"2025-11-{day:02d}T07:00:00+00:00", "state": "on"}
            for day in range(1, MIN_EVENTS_THRESHOLD)  # one less than threshold
        ]
    }
    detector = DailyRoutineDetector(min_confidence=0.0)
    patterns = detector.detect(states, lookback_days=90)
    assert patterns == [], (
        f"Entity with < {MIN_EVENTS_THRESHOLD} records should produce no patterns, "
        f"got {patterns}"
    )


# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------


def test_performance_500_entities(states_90d_500e):
    """Full 500-entity, 90-day dataset completes detection within 30 seconds.

    Performance budget for Raspberry Pi 4 class hardware (PDET success criteria).
    With pure Python hour binning (O(n) per entity, no external deps), this
    should complete in 1-5 seconds on development hardware.
    """
    detector = DailyRoutineDetector(min_confidence=0.6)
    start = time.monotonic()
    patterns = detector.detect(states_90d_500e, lookback_days=90)
    elapsed = time.monotonic() - start

    assert elapsed < 30.0, (
        f"Detection took {elapsed:.2f}s — exceeds 30s Pi 4 budget. "
        f"Check for nested loops or O(n²) patterns in _detect_entity."
    )
    # Sanity: should detect at least the two known patterns
    assert len(patterns) >= 2, f"Expected >= 2 patterns, got {len(patterns)}"


# ---------------------------------------------------------------------------
# Module-level constants validation
# ---------------------------------------------------------------------------


def test_active_states_contains_expected_values():
    """ACTIVE_STATES frozenset contains the required state values."""
    required = {"on", "home", "open", "playing", "true"}
    assert required.issubset(ACTIVE_STATES), (
        f"ACTIVE_STATES missing required values. "
        f"Expected {required}, got {ACTIVE_STATES}"
    )


def test_skip_states_contains_expected_values():
    """SKIP_STATES frozenset contains unavailable, unknown, none."""
    required = {"unavailable", "unknown", "none"}
    assert required.issubset(SKIP_STATES), (
        f"SKIP_STATES missing required values. "
        f"Expected {required}, got {SKIP_STATES}"
    )
