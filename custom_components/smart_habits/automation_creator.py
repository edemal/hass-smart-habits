"""AutomationCreator: converts DetectedPattern data into HA automation YAML.

Implements AUTO-01 through AUTO-05:
- AUTO-01: Writes to automations.yaml so automation appears in Settings > Automations
- AUTO-02: YAML persists on disk and is re-read on HA restart
- AUTO-03: Human-readable description for preview (via _generate_description)
- AUTO-04: Supports trigger_hour and trigger_entities customization overrides
- AUTO-05: Deterministic ID from MD5 fingerprint prevents duplicate automations

Implementation notes:
- File I/O always runs in executor via hass.async_add_executor_job (never blocks event loop)
- automation.reload called on event loop AFTER file write completes (not from executor)
- Uses HA 2024.9+ plural syntax (triggers/actions)
- Checks os.access(path, os.W_OK) before writing; raises AutomationCreationError if not writable
- If automations.yaml doesn't exist but parent dir is writable, creates the file
"""

from __future__ import annotations

import hashlib
import logging
import os
import yaml
from pathlib import Path

from homeassistant.core import HomeAssistant

from .const import AUTOMATION_ID_PREFIX

_LOGGER = logging.getLogger(__name__)


class AutomationCreationError(Exception):
    """Raised when automation creation fails (file not writable, unknown pattern type, etc.)."""


class AutomationCreator:
    """Creates HA automations by writing to automations.yaml and reloading.

    Single-responsibility class that handles all automation file operations.
    Designed to be instantiated by the WebSocket handler or coordinator
    after an acceptance event.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize with reference to the HA instance."""
        self._hass = hass

    def _get_automation_id(
        self,
        entity_id: str,
        pattern_type: str,
        peak_hour: int,
        secondary_entity_id: str | None,
    ) -> str:
        """Generate deterministic automation ID from pattern fingerprint.

        Uses MD5 hash of the 4-tuple so the same pattern always produces
        the same ID — enabling AUTO-05 duplicate prevention.

        Returns a string of the form: "smart_habits_<8-char-hex-hash>"
        """
        fingerprint = f"{entity_id}|{pattern_type}|{peak_hour}|{secondary_entity_id}"
        short_hash = hashlib.md5(fingerprint.encode()).hexdigest()[:8]
        return f"{AUTOMATION_ID_PREFIX}{short_hash}"

    def _build_automation_dict(
        self,
        entity_id: str,
        pattern_type: str,
        peak_hour: int,
        secondary_entity_id: str | None,
        alias: str | None = None,
        trigger_hour: int | None = None,
        trigger_entities: list[str] | None = None,
    ) -> dict:
        """Build a valid HA automation dict from pattern fields.

        Uses new plural syntax (triggers/actions) introduced in HA 2024.9+.
        Falls back to peak_hour if trigger_hour override not provided.
        Falls back to [entity_id] if trigger_entities override not provided.

        Dict keys are in logical order: id, alias, description, triggers, conditions, actions.

        Raises AutomationCreationError for unknown pattern_type.
        """
        automation_id = self._get_automation_id(
            entity_id, pattern_type, peak_hour, secondary_entity_id
        )
        effective_hour = trigger_hour if trigger_hour is not None else peak_hour
        description = alias or self._generate_description(
            entity_id, pattern_type, peak_hour, secondary_entity_id
        )

        if pattern_type == "daily_routine":
            return {
                "id": automation_id,
                "alias": description,
                "description": f"Auto-created by Smart Habits from {pattern_type} pattern",
                "triggers": [
                    {
                        "trigger": "time",
                        "at": f"{effective_hour:02d}:00:00",
                    }
                ],
                "conditions": [],
                "actions": [
                    {
                        "action": "homeassistant.turn_on",
                        "target": {"entity_id": trigger_entities or [entity_id]},
                    }
                ],
            }

        elif pattern_type == "temporal_sequence":
            # Trigger: primary entity turns on; action: turn on secondary entity
            return {
                "id": automation_id,
                "alias": description,
                "description": f"Auto-created by Smart Habits from {pattern_type} pattern",
                "triggers": [
                    {
                        "trigger": "state",
                        "entity_id": entity_id,
                        "to": "on",
                    }
                ],
                "conditions": [],
                "actions": [
                    {
                        "action": "homeassistant.turn_on",
                        "target": {"entity_id": secondary_entity_id},
                    }
                ],
            }

        elif pattern_type == "presence_arrival":
            # Trigger: presence entity transitions to "home" state
            return {
                "id": automation_id,
                "alias": description,
                "description": f"Auto-created by Smart Habits from {pattern_type} pattern",
                "triggers": [
                    {
                        "trigger": "state",
                        "entity_id": entity_id,
                        "to": "home",
                    }
                ],
                "conditions": [],
                "actions": [
                    {
                        "action": "homeassistant.turn_on",
                        "target": {"entity_id": secondary_entity_id},
                    }
                ],
            }

        else:
            raise AutomationCreationError(
                f"Unknown pattern_type: {pattern_type!r}. "
                "Supported types: daily_routine, temporal_sequence, presence_arrival"
            )

    def _generate_description(
        self,
        entity_id: str,
        pattern_type: str,
        peak_hour: int,
        secondary_entity_id: str | None,
    ) -> str:
        """Generate a human-readable description for AUTO-03.

        Converts entity IDs to friendly names by replacing dots and underscores
        with spaces and applying title case.

        Examples:
            "Turns on Light Bedroom every day at 07:00"
            "Turns on Light Kitchen when Light Hallway turns on"
            "Turns on Light Living Room when Person Alice arrives home"
        """
        def friendly(eid: str) -> str:
            return eid.replace(".", " ").replace("_", " ").title()

        friendly_entity = friendly(entity_id)
        friendly_secondary = friendly(secondary_entity_id) if secondary_entity_id else ""

        if pattern_type == "daily_routine":
            return f"Turns on {friendly_entity} every day at {peak_hour:02d}:00"
        elif pattern_type == "temporal_sequence":
            return f"Turns on {friendly_secondary} when {friendly_entity} turns on"
        elif pattern_type == "presence_arrival":
            return f"Turns on {friendly_secondary} when {friendly_entity} arrives home"

        return f"Smart Habits automation for {entity_id}"

    def create_automation_sync(
        self,
        entity_id: str,
        pattern_type: str,
        peak_hour: int,
        secondary_entity_id: str | None = None,
        alias: str | None = None,
        trigger_hour: int | None = None,
        trigger_entities: list[str] | None = None,
    ) -> dict:
        """Synchronous file I/O — MUST be called via hass.async_add_executor_job.

        Checks writability, loads existing automations, deduplicates by ID,
        appends new automation, and writes back.

        Returns the created automation dict on success (same dict even if dedup skipped write).
        Raises AutomationCreationError if file is not writable.
        """
        automations_path = Path(self._hass.config.path("automations.yaml"))

        # Check writability before attempting write (AUTO-05 fallback trigger)
        # If file doesn't exist, check parent directory writability instead
        if automations_path.exists():
            if not os.access(automations_path, os.W_OK):
                raise AutomationCreationError(
                    f"automations.yaml is not writable at {automations_path}. "
                    "Check that 'automation: !include automations.yaml' is in configuration.yaml "
                    "and the file has write permissions."
                )
        else:
            parent = automations_path.parent
            if not os.access(parent, os.W_OK):
                raise AutomationCreationError(
                    f"Cannot create automations.yaml — parent directory is not writable: {parent}"
                )

        # Load existing automations (file may be empty, contain [], or list of dicts)
        existing: list[dict] = []
        if automations_path.exists():
            with open(automations_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if isinstance(data, list):
                    existing = data
                # If data is None (empty file) or not a list, start fresh with []

        # Build new automation dict
        new_automation = self._build_automation_dict(
            entity_id,
            pattern_type,
            peak_hour,
            secondary_entity_id,
            alias,
            trigger_hour,
            trigger_entities,
        )

        # AUTO-05: Dedup check by deterministic automation ID
        automation_id = new_automation["id"]
        if any(a.get("id") == automation_id for a in existing):
            _LOGGER.debug(
                "Smart Habits: automation %s already exists in automations.yaml, skipping write",
                automation_id,
            )
            return new_automation

        # Append and write back with sort_keys=False to preserve logical key order
        existing.append(new_automation)
        with open(automations_path, "w", encoding="utf-8") as f:
            yaml.dump(
                existing,
                f,
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,
            )

        _LOGGER.info(
            "Smart Habits: created automation '%s' (%s) in %s",
            new_automation.get("alias", automation_id),
            automation_id,
            automations_path,
        )
        return new_automation

    async def async_create_automation(
        self,
        entity_id: str,
        pattern_type: str,
        peak_hour: int,
        secondary_entity_id: str | None = None,
        alias: str | None = None,
        trigger_hour: int | None = None,
        trigger_entities: list[str] | None = None,
    ) -> dict:
        """Async wrapper: file I/O in executor thread, then reload automation service.

        This is the primary entry point for WebSocket handlers.

        Returns the created automation dict on success.
        Raises AutomationCreationError if file write fails.

        IMPORTANT: automation.reload is called on the event loop (NOT from executor).
        This ensures HA's async requirements are satisfied. See RESEARCH.md Pitfall 2.
        """
        # Run blocking file I/O in executor to avoid blocking the event loop
        result = await self._hass.async_add_executor_job(
            self.create_automation_sync,
            entity_id,
            pattern_type,
            peak_hour,
            secondary_entity_id,
            alias,
            trigger_hour,
            trigger_entities,
        )

        # Call automation.reload back on the event loop with blocking=True
        # so the new entity is registered before the WebSocket response fires
        await self._hass.services.async_call(
            "automation", "reload", blocking=True
        )

        return result
