"""DailyRoutineDetector — core pattern detection algorithm.

Implements hour-of-day frequency binning to find daily time-based routines
from Recorder state history. Pure synchronous Python; no external dependencies
(PDET-08: HAOS musl-Linux compatibility).

Usage from coordinator (Phase 2 wiring):
    patterns = await hass.async_add_executor_job(
        detector.detect, states, self.lookback_days
    )

CRITICAL: Always call detect() via hass.async_add_executor_job, never directly
from an async function. Running 500 entities × 90 days of records synchronously
will block the event loop for 1-5 seconds (Pitfall 2 from RESEARCH.md).
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from .const import DEFAULT_MIN_CONFIDENCE, MIN_EVENTS_THRESHOLD
from .models import DetectedPattern

_LOGGER = logging.getLogger(__name__)

# States indicating the entity is "active" / meaningfully on.
# Covers: lights (on), persons (home), covers (open),
# media players (playing), binary_sensors expressed as true.
ACTIVE_STATES: frozenset[str] = frozenset({"on", "home", "open", "playing", "true"})

# States that represent unavailable/unknown data — skip these records.
# Including these in active-day counts would artificially inflate confidence.
SKIP_STATES: frozenset[str] = frozenset({"unavailable", "unknown", "none"})


class DailyRoutineDetector:
    """Detect daily time-based routines from Recorder state history.

    Algorithm: hour-of-day frequency binning
    1. For each entity, iterate state records in a single pass (O(n)).
    2. Normalize each record via _extract_record — handles both full State
       objects (first/last in list) and minimal dicts (intermediate records).
    3. Skip records where state is in SKIP_STATES.
    4. For active states, extract calendar date and hour-of-day.
    5. Accumulate hour_active_dates[hour].add(date) — set of distinct dates.
    6. confidence = len(hour_active_dates[hour]) / lookback_days.
    7. Emit DetectedPattern for the highest-confidence hour per entity
       (one pattern per entity maximum).
    8. Return all patterns sorted by confidence descending.

    Pure synchronous — must be called via hass.async_add_executor_job.
    No external dependencies; stdlib only (PDET-08 compliance).
    """

    def __init__(self, min_confidence: float = DEFAULT_MIN_CONFIDENCE) -> None:
        """Initialize detector with configurable confidence threshold.

        Args:
            min_confidence: Minimum confidence to emit a pattern [0.0, 1.0].
                Default 0.6 catches weekday-only patterns (5/7 ≈ 0.71).
                See Pitfall 4 in RESEARCH.md — 0.8 is too high.
        """
        self.min_confidence = min_confidence

    def detect(
        self,
        states: dict[str, list[Any]],
        lookback_days: int,
    ) -> list[DetectedPattern]:
        """Detect daily routines from state history.

        Args:
            states: Output from RecorderReader.async_get_states().
                    Maps entity_id -> list of State objects or minimal dicts.
                    Do NOT mutate this dict — it comes from an executor thread.
            lookback_days: The configured analysis window. Used as the confidence
                denominator (known limitation: under-reports for new entities).

        Returns:
            List of DetectedPattern objects sorted by confidence descending.
            Returns [] for empty input or if no entity meets min_confidence.
        """
        patterns: list[DetectedPattern] = []

        for entity_id, state_list in states.items():
            entity_patterns = self._detect_entity(entity_id, state_list, lookback_days)
            patterns.extend(entity_patterns)

        return sorted(patterns, key=lambda p: p.confidence, reverse=True)

    def _detect_entity(
        self,
        entity_id: str,
        state_list: list[Any],
        lookback_days: int,
    ) -> list[DetectedPattern]:
        """Run hour-of-day frequency analysis for a single entity.

        Returns at most one pattern (the highest-confidence hour) to avoid
        surfacing duplicate patterns for the same entity at different hours.

        Args:
            entity_id: HA entity ID for the pattern label.
            state_list: Raw records from RecorderReader (State | dict).
            lookback_days: Analysis window for confidence denominator.

        Returns:
            List with 0 or 1 DetectedPattern for this entity.
        """
        # Early exit: too few records to form a meaningful pattern.
        # Prevents spurious patterns from entities with minimal history.
        if len(state_list) < MIN_EVENTS_THRESHOLD:
            return []

        # Map hour -> set of distinct calendar dates when entity was active.
        # Single-pass O(n) — no nested loops (see RESEARCH.md anti-patterns).
        hour_active_dates: dict[int, set] = defaultdict(set)

        for record in state_list:
            ts, state_value = self._extract_record(record)
            if ts is None:
                continue
            if state_value in SKIP_STATES:
                continue
            if state_value not in ACTIVE_STATES:
                continue

            date = ts.date()
            hour = ts.hour
            hour_active_dates[hour].add(date)

        if not hour_active_dates:
            return []

        total_days = lookback_days  # Configured window as denominator

        # Find the best hour: highest confidence above threshold.
        # Return only ONE pattern per entity (the peak hour).
        best_pattern: DetectedPattern | None = None

        for hour, active_dates in hour_active_dates.items():
            active_days = len(active_dates)
            confidence = round(active_days / total_days, 3)

            if confidence < self.min_confidence:
                continue

            if best_pattern is None or confidence > best_pattern.confidence:
                evidence = f"happened {active_days} of last {total_days} days"
                best_pattern = DetectedPattern(
                    entity_id=entity_id,
                    pattern_type="daily_routine",
                    peak_hour=hour,
                    confidence=confidence,
                    evidence=evidence,
                    active_days=active_days,
                    total_days=total_days,
                )

        return [best_pattern] if best_pattern is not None else []

    @staticmethod
    def _extract_record(record: Any) -> tuple[datetime | None, str]:
        """Normalize a State object or minimal dict to (datetime, state_str).

        Handles the three shapes returned by get_significant_states(minimal_response=True):
        - Full State object: has .last_changed (datetime) and .state (str)
          [first and last records in each entity's list]
        - Minimal dict: {"last_changed": "ISO-string", "state": "value"}
          [intermediate records — the majority]
        - Compressed dict (rare): {"lu": float, "s": str}
          [if compressed_state_format=True — handled for robustness]

        Returns:
            (datetime, state_str) on success, (None, "") on parse failure.

        Note:
            Returns (None, "") rather than raising, so callers can skip bad
            records without crashing the entire entity's analysis.
        """
        try:
            if hasattr(record, "last_changed"):
                # Full State object (first/last in list from minimal_response=True)
                ts: datetime = record.last_changed
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                return ts, str(record.state)

            if isinstance(record, dict):
                # Minimal dict: {"last_changed": "...", "state": "..."} (most common)
                # Also handle compressed format: {"lu": float, "s": str}
                raw_ts = record.get("last_changed") or record.get("lu")
                state_val = record.get("state") or record.get("s", "")

                if raw_ts is None:
                    return None, str(state_val)

                if isinstance(raw_ts, (int, float)):
                    # Compressed format: Unix timestamp float
                    ts = datetime.fromtimestamp(raw_ts, tz=timezone.utc)
                else:
                    # Standard ISO 8601 string from HA recorder
                    ts = datetime.fromisoformat(str(raw_ts))
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                return ts, str(state_val)

        except (ValueError, AttributeError, TypeError) as exc:
            _LOGGER.debug("Skipping unparseable record %r: %s", record, exc)

        return None, ""
