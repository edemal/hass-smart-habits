"""PresencePatternDetector — arrival-correlated device activation detection.

Finds patterns where a person (or device_tracker) arrives home and a device
activates within a configurable time window. Includes GPS flap filtering to
avoid counting brief home/not_home transitions as genuine arrivals.

Algorithm:
1. Partition state history into presence entities (person.*, device_tracker.*)
   and device entities (everything else).
2. For each presence entity: collect genuine arrival timestamps using
   _collect_arrivals(), which filters out flap noise (home->not_home within
   FLAP_WINDOW_SECONDS). Skip presence entities with fewer than
   MIN_PAIR_OCCURRENCES genuine arrivals.
3. For each (presence, device) pair: count device activations that follow
   within window_seconds of an arrival using _count_followed_by() two-pointer
   scan. confidence = followed_count / total_arrivals.
4. Emit DetectedPattern with pattern_type="presence_arrival", peak_hour=0
   sentinel, entity_id=presence_id, secondary_entity_id=device_id.

Pure synchronous — must be called via hass.async_add_executor_job.
ZERO homeassistant imports — only stdlib + relative imports.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from ..const import DEFAULT_MIN_CONFIDENCE, DEFAULT_SEQUENCE_WINDOW
from ..models import DetectedPattern
from ._utils import ACTIVE_STATES, SKIP_STATES, extract_record

_LOGGER = logging.getLogger(__name__)

# Entity domains classified as "presence" (trigger) vs. "device" (follower).
PRESENCE_DOMAINS: frozenset[str] = frozenset({"person", "device_tracker"})

# Flap filter: if a person transitions home then away within this many seconds,
# the arrival is considered a GPS glitch, not a genuine home arrival.
FLAP_WINDOW_SECONDS: int = 300  # 5 minutes (per PDET-10 success criterion 2)

# Minimum number of genuine arrivals required to form a pattern.
# Prevents low-sample spurious correlations.
MIN_PAIR_OCCURRENCES: int = 5


class PresencePatternDetector:
    """Detect presence-arrival patterns from Recorder state history.

    Finds (presence_entity, device_entity) pairs where device reliably activates
    within `window_seconds` after a genuine home arrival. Flap noise
    (home->not_home within FLAP_WINDOW_SECONDS) is filtered before counting.

    Pure synchronous — must be called via hass.async_add_executor_job.
    No homeassistant imports — compatible with HAOS musl-Linux (PDET-10).
    """

    def __init__(
        self,
        window_seconds: int = DEFAULT_SEQUENCE_WINDOW,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    ) -> None:
        """Initialize with configurable detection window and confidence threshold.

        Args:
            window_seconds: Maximum seconds from arrival to count device as
                following. Default 300 (5 minutes).
            min_confidence: Minimum followed_count/total_arrivals ratio to emit
                pattern. Default 0.6.
        """
        self.window = timedelta(seconds=window_seconds)
        self.min_confidence = min_confidence

    def detect(
        self,
        states: dict[str, list[Any]],
        lookback_days: int,
    ) -> list[DetectedPattern]:
        """Find presence-arrival patterns from state history.

        Args:
            states: Maps entity_id -> list of State objects or minimal dicts
                (output from RecorderReader.async_get_states).
            lookback_days: Analysis window (not used as denominator —
                confidence uses actual arrival and activation counts).

        Returns:
            List of DetectedPattern objects sorted by confidence descending.
        """
        if not states:
            return []

        # Partition entities into presence (trigger) and device (follower) sets.
        presence_ids: list[str] = []
        device_ids: list[str] = []
        for entity_id in states:
            domain = entity_id.split(".")[0]
            if domain in PRESENCE_DOMAINS:
                presence_ids.append(entity_id)
            else:
                device_ids.append(entity_id)

        if not presence_ids or not device_ids:
            return []

        # Collect genuine arrival timestamps for each presence entity.
        arrivals_map: dict[str, list[datetime]] = {}
        for pid in presence_ids:
            genuine = self._collect_arrivals(states[pid])
            if len(genuine) >= MIN_PAIR_OCCURRENCES:
                arrivals_map[pid] = genuine

        if not arrivals_map:
            return []

        # Collect device activation timestamps.
        device_activations: dict[str, list[datetime]] = {}
        for did in device_ids:
            acts = self._collect_activations(states[did])
            if acts:
                device_activations[did] = acts

        if not device_activations:
            return []

        # Evaluate all (presence, device) pairs.
        patterns: list[DetectedPattern] = []
        for pid, arrivals in arrivals_map.items():
            total_arrivals = len(arrivals)
            for did, device_acts in device_activations.items():
                followed = self._count_followed_by(arrivals, device_acts, self.window)
                confidence = round(followed / total_arrivals, 3)

                if confidence < self.min_confidence:
                    continue

                window_min = int(self.window.total_seconds()) // 60
                evidence = (
                    f"{did} activates within {window_min}min of {pid} arriving "
                    f"on {followed} of {total_arrivals} arrivals"
                )

                patterns.append(DetectedPattern(
                    entity_id=pid,
                    pattern_type="presence_arrival",
                    peak_hour=0,  # Sentinel — presence patterns are not hour-based
                    confidence=confidence,
                    evidence=evidence,
                    active_days=followed,
                    total_days=total_arrivals,
                    secondary_entity_id=did,
                ))

        return sorted(patterns, key=lambda p: p.confidence, reverse=True)

    def _collect_arrivals(self, state_list: list[Any]) -> list[datetime]:
        """Extract genuine arrival timestamps, filtering GPS flap noise.

        A "genuine arrival" is a transition to "home" state that is NOT
        immediately followed by a "not_home" (or non-home) transition within
        FLAP_WINDOW_SECONDS. Flap detection uses the next state in the sorted
        sequence to identify short-duration home visits.

        Args:
            state_list: Raw records from RecorderReader.

        Returns:
            List of genuine arrival datetimes sorted ascending.
        """
        # Normalize all records to (timestamp, state_val) pairs and sort by time.
        records: list[tuple[datetime, str]] = []
        for record in state_list:
            ts, state_val = extract_record(record)
            if ts is None:
                continue
            if state_val in SKIP_STATES:
                continue
            records.append((ts, state_val))

        records.sort(key=lambda r: r[0])

        arrivals: list[datetime] = []
        for i, (ts, state_val) in enumerate(records):
            if state_val != "home":
                continue

            # Check for flap: if next record is non-home within FLAP_WINDOW_SECONDS.
            if i + 1 < len(records):
                next_ts, next_state = records[i + 1]
                elapsed = (next_ts - ts).total_seconds()
                if next_state != "home" and elapsed < FLAP_WINDOW_SECONDS:
                    # This is a flap — skip it
                    continue

            arrivals.append(ts)

        return arrivals

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
        1. Advance b_idx to skip B-activations that are before a_ts.
        2. Use a local j starting at b_idx to find if any B falls in
           [a_ts, a_ts + window]. Count A at most once even if multiple
           B-activations fall within the window.

        Time complexity: O(|a| + |b|) amortized over all A-activations.

        Args:
            a_activations: Sorted activation/arrival times for entity A.
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
            while b_idx < b_len and b_activations[b_idx] < a_ts:
                b_idx += 1

            # Scan from b_idx (local copy) to find a B in [a_ts, deadline].
            j = b_idx
            while j < b_len and b_activations[j] <= deadline:
                count += 1
                break  # Each A-activation counts at most once

        return count
