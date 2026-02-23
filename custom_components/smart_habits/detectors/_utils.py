"""Shared utilities for Smart Habits pattern detectors.

Contains helper function and constants used across multiple detectors.
Extracted from pattern_detector.py to avoid duplication as additional
detectors are added in Phase 4+.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

_LOGGER = logging.getLogger(__name__)

# States indicating the entity is "active" / meaningfully on.
# Covers: lights (on), persons (home), covers (open),
# media players (playing), binary_sensors expressed as true.
ACTIVE_STATES: frozenset[str] = frozenset({"on", "home", "open", "playing", "true"})

# States that represent unavailable/unknown data — skip these records.
# Including these in active-day counts would artificially inflate confidence.
SKIP_STATES: frozenset[str] = frozenset({"unavailable", "unknown", "none"})


def extract_record(record: Any) -> tuple[datetime | None, str]:
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
