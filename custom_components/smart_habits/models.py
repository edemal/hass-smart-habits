"""Data models for Smart Habits integration.

Defines value objects returned by the pattern detection engine.
All models are pure Python dataclasses with no HA dependencies
(PDET-08: HAOS compatibility, no external ML libraries).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DetectedPattern:
    """A single detected behavioral pattern with confidence scoring.

    Produced by DailyRoutineDetector and consumed by:
    - SmartHabitsCoordinator (stores in coordinator.data)
    - WebSocket API (Phase 3, serialized via dataclasses.asdict)
    - UI panel (Phase 5, displayed as pattern cards)

    Attributes:
        entity_id: The HA entity this pattern was observed on.
        pattern_type: Category string, e.g. "daily_routine".
        peak_hour: Hour-of-day (0-23) where activity is highest.
        confidence: Fraction of days pattern was observed [0.0, 1.0].
            Computed as active_days / total_days (lookback window).
        evidence: Human-readable evidence string, e.g.
            "happened 8 of last 10 days" (PDET-05).
        active_days: Count of distinct calendar days the pattern fired.
        total_days: Total days in the analysis window (lookback_days).
    """

    entity_id: str
    pattern_type: str
    peak_hour: int
    confidence: float
    evidence: str
    active_days: int
    total_days: int


@dataclass
class StaleAutomation:
    """An automation entity not triggered within the staleness threshold.

    Produced by SmartHabitsCoordinator._async_detect_stale_automations (MGMT-03).
    Consumed by WebSocket API (Phase 3) and UI panel (Phase 5).

    Attributes:
        entity_id: The automation entity (e.g. "automation.morning_lights").
        friendly_name: Human-readable name from state attributes.
        last_triggered: ISO 8601 timestamp of last trigger, or None if never triggered.
        days_since_triggered: Days since last trigger, or None if never triggered.
    """

    entity_id: str
    friendly_name: str
    last_triggered: str | None
    days_since_triggered: int | None
