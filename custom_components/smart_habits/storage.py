"""Persistent storage for dismissed pattern fingerprints.

Uses homeassistant.helpers.storage.Store to write dismissed state as JSON
to .storage/smart_habits.dismissed.json, surviving HA restarts (MGMT-01).

Storage v2 adds secondary_entity_id to the 4-element fingerprint tuple to
support temporal sequence patterns. V1 data (missing secondary_entity_id)
is migrated inline by defaulting to None on load.
"""
from __future__ import annotations

import logging
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

_LOGGER = logging.getLogger(__name__)

STORAGE_KEY = "smart_habits.dismissed"
STORAGE_VERSION = 2


class DismissedPatternsStore:
    """Persists the set of dismissed pattern fingerprints across HA restarts.

    Storage format v2:
    {
        "dismissed": [
            {
                "entity_id": "light.bedroom",
                "pattern_type": "daily_routine",
                "peak_hour": 7,
                "secondary_entity_id": null
            },
            ...
        ]
    }

    V1 records (missing secondary_entity_id) are migrated on load by
    defaulting to None, preserving backward compatibility.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize with a Store backed by .storage/smart_habits.dismissed.json."""
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._dismissed: set[tuple[str, str, int, str | None]] = set()

    async def async_load(self) -> None:
        """Load dismissed patterns from persistent storage.

        Handles both v1 (3-element, no secondary_entity_id) and v2 (4-element)
        records by using d.get("secondary_entity_id", None) as the 4th element.
        """
        data = await self._store.async_load()
        if data and "dismissed" in data:
            self._dismissed = {
                (
                    d["entity_id"],
                    d["pattern_type"],
                    d["peak_hour"],
                    d.get("secondary_entity_id", None),
                )
                for d in data["dismissed"]
            }
        _LOGGER.debug("Smart Habits: loaded %d dismissed patterns", len(self._dismissed))

    async def async_dismiss(
        self,
        entity_id: str,
        pattern_type: str,
        peak_hour: int,
        secondary_entity_id: str | None = None,
    ) -> None:
        """Dismiss a pattern and persist immediately."""
        key = (entity_id, pattern_type, peak_hour, secondary_entity_id)
        self._dismissed.add(key)
        await self._store.async_save({
            "dismissed": [
                {
                    "entity_id": k[0],
                    "pattern_type": k[1],
                    "peak_hour": k[2],
                    "secondary_entity_id": k[3],
                }
                for k in self._dismissed
            ]
        })

    def is_dismissed(
        self,
        entity_id: str,
        pattern_type: str,
        peak_hour: int,
        secondary_entity_id: str | None = None,
    ) -> bool:
        """Check if a pattern fingerprint has been dismissed."""
        return (entity_id, pattern_type, peak_hour, secondary_entity_id) in self._dismissed

    @property
    def dismissed_count(self) -> int:
        """Number of dismissed pattern fingerprints."""
        return len(self._dismissed)
