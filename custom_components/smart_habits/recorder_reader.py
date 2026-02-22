"""Recorder DB access layer for Smart Habits integration."""

from datetime import timedelta

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import DEFAULT_ENTITY_DOMAINS


class RecorderReader:
    """Wraps Home Assistant Recorder DB queries in a non-blocking async interface.

    All DB access uses get_instance(hass).async_add_executor_job to run
    synchronous SQLAlchemy queries on the Recorder's dedicated DB thread pool,
    never blocking the HA event loop.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Store the HomeAssistant instance for later use."""
        self.hass = hass

    async def async_get_states(
        self,
        entity_ids: list[str],
        lookback_days: int,
    ) -> dict[str, list]:
        """Query Recorder DB for state history without blocking the event loop.

        Uses get_instance(hass).async_add_executor_job so the synchronous
        SQLAlchemy call runs on the Recorder's dedicated DB executor thread,
        not the async event loop.

        Args:
            entity_ids: List of entity IDs to query history for.
            lookback_days: Number of days of history to retrieve.

        Returns:
            Dict mapping entity_id to list of State/dict records.
        """
        end_time = dt_util.utcnow()
        start_time = end_time - timedelta(days=lookback_days)

        return await get_instance(self.hass).async_add_executor_job(
            get_significant_states,
            self.hass,
            start_time,
            end_time,
            entity_ids,
            None,   # filters
            False,  # include_start_time_state
            True,   # significant_changes_only
            True,   # minimal_response (only last_changed + state, faster)
            True,   # no_attributes (skip attributes, much faster)
        )

    def get_analyzable_entity_ids(self) -> list[str]:
        """Return sorted list of entity IDs whose domain is in DEFAULT_ENTITY_DOMAINS.

        Filters all current HA states to only include state-changing domains
        (lights, switches, binary sensors, etc.), excluding noisy sensor
        domains (temperature, humidity readings).

        Returns:
            Sorted list of entity_id strings ready for analysis.
        """
        all_entity_ids = self.hass.states.async_entity_ids()
        return sorted(
            entity_id
            for entity_id in all_entity_ids
            if entity_id.split(".")[0] in DEFAULT_ENTITY_DOMAINS
        )
