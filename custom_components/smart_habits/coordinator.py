"""Coordinator for the Smart Habits integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_LOOKBACK_DAYS, DEFAULT_LOOKBACK_DAYS, DOMAIN
from .recorder_reader import RecorderReader

_LOGGER = logging.getLogger(__name__)


class SmartHabitsCoordinator(DataUpdateCoordinator):
    """Manages data access and background analysis for the Smart Habits integration.

    Uses DataUpdateCoordinator with update_interval=None so HA does not poll
    on a schedule during Phase 1. Polling will be added in Phase 3.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=None,
        )
        self.entry = entry
        self.reader = RecorderReader(hass)
        self.lookback_days: int = entry.data.get(CONF_LOOKBACK_DAYS, DEFAULT_LOOKBACK_DAYS)

    async def _async_setup(self) -> None:
        """Set up the coordinator.

        Phase 1: log initialization only. No-op setup.
        This method runs during async_config_entry_first_refresh.
        """
        _LOGGER.debug("Smart Habits coordinator initialized")

    async def _async_update_data(self) -> dict:
        """Fetch data from the Recorder DB.

        Phase 1 stub — returns empty dict.
        Phase 2 will expand this to run actual pattern detection.
        """
        _LOGGER.debug(
            "Smart Habits update cycle — no patterns computed yet (Phase 1 stub)"
        )
        return {}

    async def async_trigger_scan(self) -> None:
        """Run the initial analysis scan in the background.

        Called via entry.async_create_background_task so HA manages cancellation
        automatically when the config entry is unloaded.
        """
        _LOGGER.info("Smart Habits: starting initial analysis scan")

        entity_ids = self.reader.get_analyzable_entity_ids()
        if not entity_ids:
            _LOGGER.warning(
                "Smart Habits: no analyzable entities found — skipping initial scan"
            )
            return

        states = await self.reader.async_get_states(entity_ids, self.lookback_days)
        _LOGGER.info(
            "Smart Habits: initial scan complete — retrieved states for %d entities",
            len(states),
        )
        # Phase 1: states are retrieved but not processed further.
        # Phase 2 will add pattern detection here.
