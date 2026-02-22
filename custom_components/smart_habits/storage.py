"""Persistent storage for dismissed pattern fingerprints.

Uses homeassistant.helpers.storage.Store to write dismissed state as JSON
to .storage/smart_habits.dismissed.json, surviving HA restarts (MGMT-01).
"""
from __future__ import annotations

import logging
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

_LOGGER = logging.getLogger(__name__)

STORAGE_KEY = "smart_habits.dismissed"
STORAGE_VERSION = 1


class DismissedPatternsStore:
    """Persists the set of dismissed pattern fingerprints across HA restarts.

    Storage format:
    {
        "dismissed": [
            {"entity_id": "light.bedroom", "pattern_type": "daily_routine", "peak_hour": 7},
            ...
        ]
    }
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize with a Store backed by .storage/smart_habits.dismissed.json."""
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._dismissed: set[tuple[str, str, int]] = set()

    async def async_load(self) -> None:
        """Load dismissed patterns from persistent storage."""
        data = await self._store.async_load()
        if data and "dismissed" in data:
            self._dismissed = {
                (d["entity_id"], d["pattern_type"], d["peak_hour"])
                for d in data["dismissed"]
            }
        _LOGGER.debug("Smart Habits: loaded %d dismissed patterns", len(self._dismissed))

    async def async_dismiss(self, entity_id: str, pattern_type: str, peak_hour: int) -> None:
        """Dismiss a pattern and persist immediately."""
        key = (entity_id, pattern_type, peak_hour)
        self._dismissed.add(key)
        await self._store.async_save({
            "dismissed": [
                {"entity_id": k[0], "pattern_type": k[1], "peak_hour": k[2]}
                for k in self._dismissed
            ]
        })

    def is_dismissed(self, entity_id: str, pattern_type: str, peak_hour: int) -> bool:
        """Check if a pattern fingerprint has been dismissed."""
        return (entity_id, pattern_type, peak_hour) in self._dismissed

    @property
    def dismissed_count(self) -> int:
        """Number of dismissed pattern fingerprints."""
        return len(self._dismissed)
