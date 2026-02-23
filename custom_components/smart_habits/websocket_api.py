"""WebSocket API for the Smart Habits integration.

Exposes coordinator data (patterns, stale automations) to the frontend panel
and provides commands for pattern dismissal and manual scan triggering.

Commands:
- smart_habits/get_patterns: Returns all active patterns and stale automations
- smart_habits/dismiss_pattern: Dismisses a pattern fingerprint persistently (MGMT-01/MGMT-02)
- smart_habits/trigger_scan: Triggers a manual analysis scan (PDET-07)
"""
from __future__ import annotations

import logging
from dataclasses import asdict

import voluptuous as vol

from homeassistant.core import HomeAssistant, callback
from homeassistant.components import websocket_api
from homeassistant.components.websocket_api import (
    ActiveConnection,
    async_response,
    websocket_command,
)

_LOGGER = logging.getLogger(__name__)


def async_register_commands(hass: HomeAssistant) -> None:
    """Register all Smart Habits WebSocket commands with HA."""
    websocket_api.async_register_command(hass, ws_get_patterns)
    websocket_api.async_register_command(hass, ws_dismiss_pattern)
    websocket_api.async_register_command(hass, ws_trigger_scan)


@websocket_command({
    vol.Required("type"): "smart_habits/get_patterns",
})
@callback
def ws_get_patterns(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
) -> None:
    """Handle get_patterns WebSocket command.

    Returns all active detected patterns and stale automations from the coordinator.
    Uses entry.runtime_data to access the coordinator (modern HA pattern).
    """
    entries = hass.config_entries.async_entries("smart_habits")
    if not entries:
        connection.send_error(msg["id"], "not_found", "Smart Habits integration not set up")
        return

    coordinator = entries[0].runtime_data
    data = coordinator.data or {}

    connection.send_result(msg["id"], {
        "patterns": [asdict(p) for p in data.get("patterns", [])],
        "stale_automations": [asdict(s) for s in data.get("stale_automations", [])],
    })


@websocket_command({
    vol.Required("type"): "smart_habits/dismiss_pattern",
    vol.Required("entity_id"): str,
    vol.Required("pattern_type"): str,
    vol.Required("peak_hour"): int,
    vol.Optional("secondary_entity_id", default=None): vol.Any(str, None),
})
@async_response
async def ws_dismiss_pattern(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
) -> None:
    """Handle dismiss_pattern WebSocket command.

    Dismisses a pattern fingerprint persistently via DismissedPatternsStore (MGMT-01)
    and refreshes the coordinator so the change is reflected immediately (MGMT-02).
    The optional secondary_entity_id supports temporal sequence pattern dismissal.
    """
    entries = hass.config_entries.async_entries("smart_habits")
    if not entries:
        connection.send_error(msg["id"], "not_found", "Smart Habits integration not set up")
        return

    coordinator = entries[0].runtime_data

    await coordinator.dismissed_store.async_dismiss(
        msg["entity_id"],
        msg["pattern_type"],
        msg["peak_hour"],
        msg.get("secondary_entity_id"),
    )
    await coordinator.async_refresh()

    connection.send_result(msg["id"], {"dismissed": True})


@websocket_command({
    vol.Required("type"): "smart_habits/trigger_scan",
})
@async_response
async def ws_trigger_scan(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
) -> None:
    """Handle trigger_scan WebSocket command.

    Triggers a manual analysis scan and returns the updated pattern count (PDET-07).
    """
    entries = hass.config_entries.async_entries("smart_habits")
    if not entries:
        connection.send_error(msg["id"], "not_found", "Smart Habits integration not set up")
        return

    coordinator = entries[0].runtime_data

    await coordinator.async_trigger_scan()
    data = coordinator.data or {}

    connection.send_result(msg["id"], {
        "pattern_count": len(data.get("patterns", [])),
    })
