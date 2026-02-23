"""Smart Habits integration for Home Assistant."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_ANALYSIS_INTERVAL,
    CONF_LOOKBACK_DAYS,
    CONF_SEQUENCE_WINDOW,
    DEFAULT_ANALYSIS_INTERVAL,
    DEFAULT_LOOKBACK_DAYS,
    DEFAULT_SEQUENCE_WINDOW,
)
from .coordinator import SmartHabitsCoordinator
from .websocket_api import async_register_commands


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Smart Habits from a config entry.

    1. Creates the coordinator.
    2. Calls async_config_entry_first_refresh to validate the coordinator works.
    3. Stores coordinator in entry.runtime_data (modern HA pattern).
    4. Registers the options update listener (MC-01) so options changes propagate
       to the running coordinator without requiring a restart.
    5. Triggers background scan via entry.async_create_background_task so HA
       manages cancellation on unload automatically.
    """
    coordinator = SmartHabitsCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    entry.async_on_unload(
        entry.add_update_listener(_async_options_updated)
    )

    async_register_commands(hass)

    entry.async_create_background_task(
        hass,
        coordinator.async_trigger_scan(),
        name="smart_habits_initial_scan",
    )

    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle updated options — propagate to the running coordinator immediately.

    Called by HA whenever the user saves new options. Updates coordinator
    attributes and calls async_refresh so the next analysis cycle reflects
    the new settings without requiring a restart.
    """
    coordinator: SmartHabitsCoordinator = entry.runtime_data
    coordinator.lookback_days = int(
        entry.options.get(CONF_LOOKBACK_DAYS, DEFAULT_LOOKBACK_DAYS)
    )
    coordinator.update_interval = timedelta(
        days=int(entry.options.get(CONF_ANALYSIS_INTERVAL, DEFAULT_ANALYSIS_INTERVAL))
    )
    coordinator.sequence_window = int(
        entry.options.get(CONF_SEQUENCE_WINDOW, DEFAULT_SEQUENCE_WINDOW)
    )
    await coordinator.async_refresh()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Smart Habits config entry.

    No platforms to unload. Background tasks are automatically cancelled
    by HA via the entry lifecycle when async_create_background_task is used.
    The options update listener is deregistered via entry.async_on_unload.
    """
    return True
