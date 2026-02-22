"""Smart Habits integration for Home Assistant."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .coordinator import SmartHabitsCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Smart Habits from a config entry.

    1. Creates the coordinator.
    2. Calls async_config_entry_first_refresh to validate the coordinator works.
    3. Stores coordinator in entry.runtime_data (modern HA pattern).
    4. Triggers background scan via entry.async_create_background_task so HA
       manages cancellation on unload automatically.
    """
    coordinator = SmartHabitsCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    entry.async_create_background_task(
        hass,
        coordinator.async_trigger_scan(),
        name="smart_habits_initial_scan",
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Smart Habits config entry.

    Phase 1: no platforms to unload. Background task is automatically cancelled
    by HA via the entry lifecycle when async_create_background_task is used.
    """
    return True
