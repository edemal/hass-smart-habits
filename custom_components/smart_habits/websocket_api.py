"""WebSocket API for the Smart Habits integration.

Exposes coordinator data (patterns, stale automations) to the frontend panel
and provides commands for pattern dismissal, acceptance, and manual scan triggering.

Commands:
- smart_habits/get_patterns: Returns all active patterns, accepted patterns and stale automations
- smart_habits/dismiss_pattern: Dismisses a pattern fingerprint persistently (MGMT-01/MGMT-02)
- smart_habits/accept_pattern: Accepts a pattern persistently, creates automation via AutomationCreator
- smart_habits/trigger_scan: Triggers a manual analysis scan (PDET-07)
- smart_habits/preview_automation: Returns human-readable preview without side effects (AUTO-03)
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
    websocket_api.async_register_command(hass, ws_accept_pattern)
    websocket_api.async_register_command(hass, ws_trigger_scan)
    websocket_api.async_register_command(hass, ws_preview_automation)


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
        "accepted_patterns": [asdict(p) for p in data.get("accepted_patterns", [])],
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
    vol.Required("type"): "smart_habits/accept_pattern",
    vol.Required("entity_id"): str,
    vol.Required("pattern_type"): str,
    vol.Required("peak_hour"): int,
    vol.Optional("secondary_entity_id", default=None): vol.Any(str, None),
    vol.Optional("trigger_hour"): vol.Any(int, None),
    vol.Optional("trigger_entities"): vol.Any([str], None),
})
@async_response
async def ws_accept_pattern(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
) -> None:
    """Handle accept_pattern WebSocket command.

    Accepts a pattern fingerprint persistently via AcceptedPatternsStore, then creates
    a real HA automation via AutomationCreator. On AutomationCreationError (e.g. file not
    writable), returns accepted: True with yaml_for_manual_copy for manual paste (AUTO-05
    fallback).

    Customization overrides trigger_hour and trigger_entities are passed through to
    AutomationCreator if provided (AUTO-04).
    """
    from .automation_creator import AutomationCreator, AutomationCreationError

    entries = hass.config_entries.async_entries("smart_habits")
    if not entries:
        connection.send_error(msg["id"], "not_found", "Smart Habits integration not set up")
        return

    coordinator = entries[0].runtime_data

    # Always persist acceptance first — pattern IS accepted regardless of automation creation
    await coordinator.accepted_store.async_accept(
        msg["entity_id"],
        msg["pattern_type"],
        msg["peak_hour"],
        msg.get("secondary_entity_id"),
    )

    creator = AutomationCreator(hass)
    try:
        automation = await creator.async_create_automation(
            msg["entity_id"],
            msg["pattern_type"],
            msg["peak_hour"],
            msg.get("secondary_entity_id"),
            trigger_hour=msg.get("trigger_hour"),
            trigger_entities=msg.get("trigger_entities"),
        )
        await coordinator.async_refresh()
        connection.send_result(msg["id"], {
            "accepted": True,
            "automation_id": automation["id"],
            "automation_alias": automation["alias"],
        })
    except AutomationCreationError as err:
        import yaml
        preview_yaml = yaml.dump(
            [creator._build_automation_dict(
                msg["entity_id"],
                msg["pattern_type"],
                msg["peak_hour"],
                msg.get("secondary_entity_id"),
                trigger_hour=msg.get("trigger_hour"),
                trigger_entities=msg.get("trigger_entities"),
            )],
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )
        await coordinator.async_refresh()
        connection.send_result(msg["id"], {
            "accepted": True,
            "automation_id": None,
            "warning": str(err),
            "yaml_for_manual_copy": preview_yaml,
        })


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


@websocket_command({
    vol.Required("type"): "smart_habits/preview_automation",
    vol.Required("entity_id"): str,
    vol.Required("pattern_type"): str,
    vol.Required("peak_hour"): int,
    vol.Optional("secondary_entity_id", default=None): vol.Any(str, None),
    vol.Optional("trigger_hour"): vol.Any(int, None),
    vol.Optional("trigger_entities"): vol.Any([str], None),
})
@callback
def ws_preview_automation(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict,
) -> None:
    """Handle preview_automation WebSocket command.

    Returns a human-readable description and the full automation dict without
    any side effects — no file write, no reload (AUTO-03).

    Uses @callback (not @async_response) because _build_automation_dict and
    _generate_description are pure computation with no I/O.
    """
    from .automation_creator import AutomationCreator

    creator = AutomationCreator(hass)
    description = creator._generate_description(
        msg["entity_id"],
        msg["pattern_type"],
        msg["peak_hour"],
        msg.get("secondary_entity_id"),
    )
    automation_dict = creator._build_automation_dict(
        msg["entity_id"],
        msg["pattern_type"],
        msg["peak_hour"],
        msg.get("secondary_entity_id"),
        trigger_hour=msg.get("trigger_hour"),
        trigger_entities=msg.get("trigger_entities"),
    )
    connection.send_result(msg["id"], {
        "description": description,
        "automation_dict": automation_dict,
    })
