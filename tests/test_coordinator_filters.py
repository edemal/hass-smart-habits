"""Unit tests for the coordinator exclusion filter logic (Phase 10).

Tests exercise `_is_pattern_excluded` directly by constructing DetectedPattern
objects and mocking the entity registry. The full coordinator refresh cycle is
NOT tested here — only the filter method in isolation.
"""

from unittest.mock import MagicMock

import pytest

from custom_components.smart_habits.models import DetectedPattern
from custom_components.smart_habits.coordinator import SmartHabitsCoordinator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_coord() -> SmartHabitsCoordinator:
    """Return a bare SmartHabitsCoordinator instance without __init__ side effects."""
    return SmartHabitsCoordinator.__new__(SmartHabitsCoordinator)


def _make_registry(**platform_by_entity_id: str) -> MagicMock:
    """Return a mock EntityRegistry where each entity_id maps to a given platform.

    Unknown entity_ids (not in platform_by_entity_id) return None from async_get.
    """
    registry = MagicMock()

    def _async_get(entity_id: str):
        if entity_id in platform_by_entity_id:
            entry = MagicMock()
            entry.platform = platform_by_entity_id[entity_id]
            return entry
        return None

    registry.async_get = MagicMock(side_effect=_async_get)
    return registry


def _make_pattern(
    entity_id: str,
    secondary_entity_id: str | None = None,
) -> DetectedPattern:
    """Return a minimal DetectedPattern for filter testing."""
    return DetectedPattern(
        entity_id=entity_id,
        pattern_type="daily_routine",
        peak_hour=7,
        confidence=0.9,
        evidence="test",
        active_days=20,
        total_days=30,
        secondary_entity_id=secondary_entity_id,
    )


# ---------------------------------------------------------------------------
# Test 1: Primary entity excluded by integration
# ---------------------------------------------------------------------------

def test_primary_entity_excluded_by_integration() -> None:
    """Pattern with primary entity from excluded integration is excluded."""
    coord = _make_coord()
    registry = _make_registry(**{"sensor.vacuum_battery": "roborock"})
    pattern = _make_pattern("sensor.vacuum_battery")

    result = coord._is_pattern_excluded(
        registry, pattern,
        excluded_integrations=["roborock"],
        excluded_domains=[],
    )

    assert result is True


# ---------------------------------------------------------------------------
# Test 2: Secondary entity excluded by integration
# ---------------------------------------------------------------------------

def test_secondary_entity_excluded_by_integration() -> None:
    """Pattern with secondary_entity from excluded integration is excluded."""
    coord = _make_coord()
    registry = _make_registry(**{"sensor.vacuum_status": "roborock"})
    pattern = _make_pattern("light.bedroom", secondary_entity_id="sensor.vacuum_status")

    result = coord._is_pattern_excluded(
        registry, pattern,
        excluded_integrations=["roborock"],
        excluded_domains=[],
    )

    assert result is True


# ---------------------------------------------------------------------------
# Test 3: Primary entity excluded by domain (entity_id prefix)
# ---------------------------------------------------------------------------

def test_primary_entity_excluded_by_domain() -> None:
    """Pattern with primary entity whose domain is excluded is filtered out."""
    coord = _make_coord()
    registry = _make_registry()  # empty — no registry lookups needed for domain check
    pattern = _make_pattern("binary_sensor.motion_hall")

    result = coord._is_pattern_excluded(
        registry, pattern,
        excluded_integrations=[],
        excluded_domains=["binary_sensor"],
    )

    assert result is True


# ---------------------------------------------------------------------------
# Test 4: Secondary entity excluded by domain
# ---------------------------------------------------------------------------

def test_secondary_entity_excluded_by_domain() -> None:
    """Pattern with secondary entity whose domain is excluded is filtered out."""
    coord = _make_coord()
    registry = _make_registry()
    pattern = _make_pattern("light.bedroom", secondary_entity_id="binary_sensor.motion_hall")

    result = coord._is_pattern_excluded(
        registry, pattern,
        excluded_integrations=[],
        excluded_domains=["binary_sensor"],
    )

    assert result is True


# ---------------------------------------------------------------------------
# Test 5: Unregistered entity is NOT excluded even with integration filter set
# ---------------------------------------------------------------------------

def test_unregistered_entity_not_excluded() -> None:
    """Entity not in registry (async_get returns None) is NOT excluded."""
    coord = _make_coord()
    # registry returns None for any entity_id
    registry = _make_registry()
    pattern = _make_pattern("light.unknown_device")

    result = coord._is_pattern_excluded(
        registry, pattern,
        excluded_integrations=["roborock"],
        excluded_domains=[],
    )

    assert result is False


# ---------------------------------------------------------------------------
# Test 6: Empty exclusion lists — fast path, no filtering
# ---------------------------------------------------------------------------

def test_empty_exclusion_lists_pass_all() -> None:
    """Empty excluded_integrations and excluded_domains let all patterns through."""
    coord = _make_coord()
    registry = _make_registry(**{"light.bedroom": "hue"})
    pattern = _make_pattern("light.bedroom")

    result = coord._is_pattern_excluded(
        registry, pattern,
        excluded_integrations=[],
        excluded_domains=[],
    )

    assert result is False


# ---------------------------------------------------------------------------
# Test 7: Combined integration + domain filters — either match excludes
# ---------------------------------------------------------------------------

def test_combined_filter_integration_match_excludes() -> None:
    """Pattern matching integration filter is excluded even if domain is not excluded."""
    coord = _make_coord()
    registry = _make_registry(**{"light.hue_bulb": "hue"})
    pattern = _make_pattern("light.hue_bulb")

    result = coord._is_pattern_excluded(
        registry, pattern,
        excluded_integrations=["hue"],
        excluded_domains=["binary_sensor"],  # doesn't match light domain
    )

    assert result is True


def test_combined_filter_domain_match_excludes() -> None:
    """Pattern matching domain filter is excluded even if integration is not excluded."""
    coord = _make_coord()
    # Entity has platform "hue" but domain "binary_sensor" is in excluded list
    registry = _make_registry(**{"binary_sensor.hue_motion": "hue"})
    pattern = _make_pattern("binary_sensor.hue_motion")

    result = coord._is_pattern_excluded(
        registry, pattern,
        excluded_integrations=["roborock"],  # doesn't match hue
        excluded_domains=["binary_sensor"],
    )

    assert result is True


# ---------------------------------------------------------------------------
# Test 8: Pattern not matching any filter passes through unchanged
# ---------------------------------------------------------------------------

def test_non_matching_pattern_passes_through() -> None:
    """Pattern that matches no integration or domain filter is NOT excluded."""
    coord = _make_coord()
    registry = _make_registry(**{"light.bedroom": "hue"})
    pattern = _make_pattern("light.bedroom", secondary_entity_id="switch.coffee_maker")

    result = coord._is_pattern_excluded(
        registry, pattern,
        excluded_integrations=["roborock"],
        excluded_domains=["binary_sensor"],
    )

    assert result is False
