"""TemporalSequenceDetector — co-activation sequence detection.

Finds entity pairs (A, B) where B reliably activates within a configurable
time window after A activates. Confidence = followed_count / total_a_activations.

Algorithm (two-pass sliding window):
1. For each entity, collect sorted activation timestamps using extract_record
   from _utils.py with ACTIVE_STATES/SKIP_STATES filtering. Skip entities
   with fewer than MIN_PAIR_OCCURRENCES activations.
2. For each ordered pair (A, B) where A != B, count how many A-activations
   are followed by at least one B-activation within [a_ts, a_ts + window].
   Uses a two-pointer scan for O(n + m) time per pair.
3. confidence = followed_count / total_a_activations. Emit a DetectedPattern
   for pairs meeting min_confidence threshold.

Pure synchronous — must be called via hass.async_add_executor_job.
ZERO homeassistant imports — only stdlib + relative imports.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from ..const import DEFAULT_MIN_CONFIDENCE, DEFAULT_SEQUENCE_WINDOW
from ..models import DetectedPattern
from ._utils import ACTIVE_STATES, SKIP_STATES, extract_record

_LOGGER = logging.getLogger(__name__)

# Minimum number of A-activations required to form a pair pattern.
# Prevents low-sample spurious correlations.
MIN_PAIR_OCCURRENCES = 5


class TemporalSequenceDetector:
    """Detect temporal co-activation sequences from Recorder state history.

    Finds pairs (A, B) where B activates within `window_seconds` after A,
    with frequency meeting `min_confidence`. Both A->B and B->A are evaluated
    independently — if both meet threshold, both patterns are emitted.

    Pure synchronous — must be called via hass.async_add_executor_job.
    No homeassistant imports — compatible with HAOS musl-Linux (PDET-08).
    """

    def __init__(
        self,
        window_seconds: int = DEFAULT_SEQUENCE_WINDOW,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    ) -> None:
        """Initialize with configurable detection window and confidence threshold.

        Args:
            window_seconds: Maximum seconds from A-activation to count B as
                following. Default 300 (5 minutes).
            min_confidence: Minimum followed_count/total_a ratio to emit pattern.
                Default 0.6.
        """
        self.window = timedelta(seconds=window_seconds)
        self.min_confidence = min_confidence

    def detect(
        self,
        states: dict[str, list[Any]],
        lookback_days: int,
    ) -> list[DetectedPattern]:
        """Find temporal sequence patterns from state history.

        Args:
            states: Maps entity_id -> list of State objects or minimal dicts
                (output from RecorderReader.async_get_states).
            lookback_days: Analysis window (not used as denominator here —
                confidence uses actual activation counts).

        Returns:
            List of DetectedPattern objects sorted by confidence descending.
        """
        if not states:
            return []

        # Phase 1: Collect sorted activation timestamps per entity.
        # Only retain entities meeting the minimum occurrence threshold.
        activations: dict[str, list[datetime]] = {}
        for entity_id, state_list in states.items():
            acts = self._collect_activations(state_list)
            if len(acts) >= MIN_PAIR_OCCURRENCES:
                activations[entity_id] = acts

        if len(activations) < 2:
            return []

        entity_ids = sorted(activations.keys())
        patterns: list[DetectedPattern] = []

        # Phase 2: Evaluate all ordered pairs (A, B) where A != B.
        for i, a_id in enumerate(entity_ids):
            for j, b_id in enumerate(entity_ids):
                if i == j:
                    continue
                pattern = self._detect_pair(
                    a_id, activations[a_id],
                    b_id, activations[b_id],
                    lookback_days,
                )
                if pattern is not None:
                    patterns.append(pattern)

        return sorted(patterns, key=lambda p: p.confidence, reverse=True)

    def _collect_activations(self, state_list: list[Any]) -> list[datetime]:
        """Extract sorted activation timestamps from a raw state record list.

        Uses extract_record to normalize both full State objects and minimal
        dicts. Skips SKIP_STATES (unavailable/unknown). Collects ACTIVE_STATES.

        Args:
            state_list: Raw records from RecorderReader.

        Returns:
            List of datetime objects sorted ascending.
        """
        activations: list[datetime] = []
        for record in state_list:
            ts, state_val = extract_record(record)
            if ts is None:
                continue
            if state_val in SKIP_STATES:
                continue
            if state_val in ACTIVE_STATES:
                activations.append(ts)
        activations.sort()
        return activations

    def _count_followed_by(
        self,
        a_activations: list[datetime],
        b_activations: list[datetime],
        window: timedelta,
    ) -> int:
        """Count A-activations where at least one B-activation follows within window.

        Two-pointer scan: both lists are sorted ascending. For each a_ts:
        1. Advance b_idx to skip B-activations that are before a_ts (they
           cannot follow A). Since a_activations is sorted, b_idx never
           needs to go backwards.
        2. Use a local j starting at b_idx to find if any B falls in
           [a_ts, a_ts + window]. Count A at most once even if multiple
           B-activations fall within the window.

        Time complexity: O(|a| + |b|) amortized over all A-activations.

        Args:
            a_activations: Sorted activation times for entity A.
            b_activations: Sorted activation times for entity B.
            window: Maximum time delta from A to B.

        Returns:
            Count of A-activations with at least one following B in window.
        """
        if not b_activations:
            return 0

        count = 0
        b_idx = 0
        b_len = len(b_activations)

        for a_ts in a_activations:
            deadline = a_ts + window

            # Advance b_idx past B-activations strictly before a_ts.
            # Safe because a_activations is sorted: any B < a_ts is also
            # < all future a_ts values.
            while b_idx < b_len and b_activations[b_idx] < a_ts:
                b_idx += 1

            # Scan from b_idx (local copy) to find a B in [a_ts, deadline].
            j = b_idx
            while j < b_len and b_activations[j] <= deadline:
                count += 1
                break  # Each A-activation counts at most once
                # j += 1  # unreachable — left for algorithmic clarity

        return count

    def _detect_pair(
        self,
        a_id: str,
        a_acts: list[datetime],
        b_id: str,
        b_acts: list[datetime],
        lookback_days: int,
    ) -> DetectedPattern | None:
        """Evaluate one ordered pair (A, B) and emit pattern if above threshold.

        Args:
            a_id: Entity ID of A (trigger).
            a_acts: Sorted activation times for A.
            b_id: Entity ID of B (follower).
            b_acts: Sorted activation times for B.
            lookback_days: Unused as denominator; included for interface parity.

        Returns:
            DetectedPattern if confidence >= min_confidence, else None.
        """
        total_a = len(a_acts)
        if total_a == 0:
            return None

        followed = self._count_followed_by(a_acts, b_acts, self.window)
        confidence = round(followed / total_a, 3)

        if confidence < self.min_confidence:
            return None

        window_min = int(self.window.total_seconds()) // 60
        evidence = (
            f"{b_id} activates within {window_min}min after {a_id} "
            f"on {followed} of {total_a} occurrences"
        )

        return DetectedPattern(
            entity_id=a_id,
            pattern_type="temporal_sequence",
            peak_hour=0,  # Sentinel — sequences are not hour-based
            confidence=confidence,
            evidence=evidence,
            active_days=followed,
            total_days=total_a,
            secondary_entity_id=b_id,
        )
