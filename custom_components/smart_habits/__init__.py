"""Smart Habits integration for Home Assistant."""
from __future__ import annotations

import logging
import os
from datetime import timedelta

from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.panel_custom import async_register_panel as _async_register_panel
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_ANALYSIS_INTERVAL,
    CONF_EXCLUDED_DOMAINS,
    CONF_EXCLUDED_INTEGRATIONS,
    CONF_LOOKBACK_DAYS,
    CONF_SEQUENCE_WINDOW,
    DEFAULT_ANALYSIS_INTERVAL,
    DEFAULT_EXCLUDED_DOMAINS,
    DEFAULT_EXCLUDED_INTEGRATIONS,
    DEFAULT_LOOKBACK_DAYS,
    DEFAULT_SEQUENCE_WINDOW,
)
from .coordinator import SmartHabitsCoordinator
from .websocket_api import async_register_commands

_LOGGER = logging.getLogger(__name__)

PANEL_URL_BASE = "/smart_habits_frontend"
PANEL_WEBCOMPONENT = "smart-habits-panel"


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

    # Register frontend panel
    frontend_path = os.path.join(os.path.dirname(__file__), "frontend")
    await hass.http.async_register_static_paths([
        StaticPathConfig(PANEL_URL_BASE, frontend_path, cache_headers=False)
    ])
    if "smart_habits" not in hass.data.get("frontend_panels", {}):
        try:
            await _async_register_panel(
                hass,
                webcomponent_name=PANEL_WEBCOMPONENT,
                frontend_url_path="smart_habits",
                sidebar_title="Smart Habits",
                sidebar_icon="mdi:brain",
                module_url=f"{PANEL_URL_BASE}/smart-habits-panel.js",
                embed_iframe=False,
                require_admin=False,
            )
        except Exception:
            _LOGGER.warning("Smart Habits: panel registration failed (panel may already be registered)")

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
    coordinator.excluded_integrations = list(
        entry.options.get(CONF_EXCLUDED_INTEGRATIONS, DEFAULT_EXCLUDED_INTEGRATIONS)
    )
    coordinator.excluded_domains = list(
        entry.options.get(CONF_EXCLUDED_DOMAINS, DEFAULT_EXCLUDED_DOMAINS)
    )
    await coordinator.async_refresh()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Smart Habits config entry.

    No platforms to unload. Background tasks are automatically cancelled
    by HA via the entry lifecycle when async_create_background_task is used.
    The options update listener is deregistered via entry.async_on_unload.
    Removes the sidebar panel so re-setup is clean (prevents duplicate registration).
    """
    frontend.async_remove_panel(hass, "smart_habits")
    return True
