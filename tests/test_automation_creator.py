"""TDD tests for AutomationCreator.

Tests cover:
- Deterministic ID generation from pattern fingerprint (AUTO-05)
- automation dict building for all 3 pattern types (daily_routine, temporal_sequence, presence_arrival)
- Human-readable description generation (AUTO-03)
- File I/O: write, dedup, missing file creation, writability check
- YAML output preserves insertion key order (sort_keys=False)

All file I/O tests use tmp_path fixture to avoid touching real files.
"""

import hashlib
import os
import stat
import sys

import pytest
import yaml

# ---------------------------------------------------------------------------
# Ensure automation_creator module is importable without a running HA instance.
# conftest.py already stubs homeassistant.core, but we need to verify imports
# work before the module exists.
# ---------------------------------------------------------------------------

from custom_components.smart_habits.automation_creator import (
    AutomationCreationError,
    AutomationCreator,
)
from custom_components.smart_habits.const import AUTOMATION_ID_PREFIX


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_hass(tmp_path):
    """Create a minimal mock hass where hass.config.path() returns tmp_path files."""
    from unittest.mock import MagicMock

    hass = MagicMock()
    hass.config.path.side_effect = lambda filename: str(tmp_path / filename)
    return hass


# ---------------------------------------------------------------------------
# _get_automation_id tests
# ---------------------------------------------------------------------------


class TestGetAutomationId:
    def test_returns_string_starting_with_prefix(self, tmp_path):
        hass = make_hass(tmp_path)
        creator = AutomationCreator(hass)
        automation_id = creator._get_automation_id(
            "light.bedroom", "daily_routine", 7, None
        )
        assert automation_id.startswith(AUTOMATION_ID_PREFIX)
        assert automation_id.startswith("smart_habits_")

    def test_deterministic_same_inputs_same_id(self, tmp_path):
        hass = make_hass(tmp_path)
        creator = AutomationCreator(hass)
        id1 = creator._get_automation_id("light.bedroom", "daily_routine", 7, None)
        id2 = creator._get_automation_id("light.bedroom", "daily_routine", 7, None)
        assert id1 == id2

    def test_different_fingerprints_produce_different_ids(self, tmp_path):
        hass = make_hass(tmp_path)
        creator = AutomationCreator(hass)
        id_a = creator._get_automation_id("light.bedroom", "daily_routine", 7, None)
        id_b = creator._get_automation_id("light.kitchen", "daily_routine", 8, None)
        assert id_a != id_b

    def test_secondary_entity_changes_id(self, tmp_path):
        hass = make_hass(tmp_path)
        creator = AutomationCreator(hass)
        id_no_secondary = creator._get_automation_id(
            "light.hallway", "temporal_sequence", 0, None
        )
        id_with_secondary = creator._get_automation_id(
            "light.hallway", "temporal_sequence", 0, "light.kitchen"
        )
        assert id_no_secondary != id_with_secondary

    def test_id_uses_md5_hash(self, tmp_path):
        hass = make_hass(tmp_path)
        creator = AutomationCreator(hass)
        fingerprint = "light.bedroom|daily_routine|7|None"
        expected_hash = hashlib.md5(fingerprint.encode()).hexdigest()[:8]
        expected_id = f"smart_habits_{expected_hash}"
        actual_id = creator._get_automation_id("light.bedroom", "daily_routine", 7, None)
        assert actual_id == expected_id


# ---------------------------------------------------------------------------
# _build_automation_dict tests
# ---------------------------------------------------------------------------


class TestBuildAutomationDict:
    def test_daily_routine_structure(self, tmp_path):
        hass = make_hass(tmp_path)
        creator = AutomationCreator(hass)
        result = creator._build_automation_dict(
            entity_id="light.bedroom",
            pattern_type="daily_routine",
            peak_hour=7,
            secondary_entity_id=None,
        )
        assert "id" in result
        assert result["id"].startswith("smart_habits_")
        assert "alias" in result
        assert "description" in result
        assert "triggers" in result
        assert "conditions" in result
        assert "actions" in result

    def test_daily_routine_time_trigger(self, tmp_path):
        hass = make_hass(tmp_path)
        creator = AutomationCreator(hass)
        result = creator._build_automation_dict(
            entity_id="light.bedroom",
            pattern_type="daily_routine",
            peak_hour=7,
            secondary_entity_id=None,
        )
        triggers = result["triggers"]
        assert len(triggers) == 1
        assert triggers[0]["trigger"] == "time"
        assert triggers[0]["at"] == "07:00:00"

    def test_daily_routine_turn_on_action(self, tmp_path):
        hass = make_hass(tmp_path)
        creator = AutomationCreator(hass)
        result = creator._build_automation_dict(
            entity_id="light.bedroom",
            pattern_type="daily_routine",
            peak_hour=7,
            secondary_entity_id=None,
        )
        actions = result["actions"]
        assert len(actions) == 1
        assert actions[0]["action"] == "homeassistant.turn_on"
        assert "light.bedroom" in str(actions[0]["target"]["entity_id"])

    def test_daily_routine_uses_plural_keys(self, tmp_path):
        hass = make_hass(tmp_path)
        creator = AutomationCreator(hass)
        result = creator._build_automation_dict(
            entity_id="light.bedroom",
            pattern_type="daily_routine",
            peak_hour=7,
            secondary_entity_id=None,
        )
        # HA 2024.9+ plural syntax
        assert "triggers" in result
        assert "actions" in result
        # Must NOT use old singular keys
        assert "trigger" not in result
        assert "action" not in result

    def test_temporal_sequence_state_trigger(self, tmp_path):
        hass = make_hass(tmp_path)
        creator = AutomationCreator(hass)
        result = creator._build_automation_dict(
            entity_id="light.hallway",
            pattern_type="temporal_sequence",
            peak_hour=0,
            secondary_entity_id="light.kitchen",
        )
        triggers = result["triggers"]
        assert len(triggers) == 1
        assert triggers[0]["trigger"] == "state"
        assert triggers[0]["entity_id"] == "light.hallway"
        assert triggers[0]["to"] == "on"

    def test_temporal_sequence_turn_on_secondary(self, tmp_path):
        hass = make_hass(tmp_path)
        creator = AutomationCreator(hass)
        result = creator._build_automation_dict(
            entity_id="light.hallway",
            pattern_type="temporal_sequence",
            peak_hour=0,
            secondary_entity_id="light.kitchen",
        )
        actions = result["actions"]
        assert len(actions) == 1
        assert actions[0]["action"] == "homeassistant.turn_on"
        assert actions[0]["target"]["entity_id"] == "light.kitchen"

    def test_presence_arrival_state_trigger_to_home(self, tmp_path):
        hass = make_hass(tmp_path)
        creator = AutomationCreator(hass)
        result = creator._build_automation_dict(
            entity_id="person.alice",
            pattern_type="presence_arrival",
            peak_hour=0,
            secondary_entity_id="light.living_room",
        )
        triggers = result["triggers"]
        assert len(triggers) == 1
        assert triggers[0]["trigger"] == "state"
        assert triggers[0]["entity_id"] == "person.alice"
        assert triggers[0]["to"] == "home"

    def test_presence_arrival_turn_on_secondary(self, tmp_path):
        hass = make_hass(tmp_path)
        creator = AutomationCreator(hass)
        result = creator._build_automation_dict(
            entity_id="person.alice",
            pattern_type="presence_arrival",
            peak_hour=0,
            secondary_entity_id="light.living_room",
        )
        actions = result["actions"]
        assert len(actions) == 1
        assert actions[0]["action"] == "homeassistant.turn_on"
        assert actions[0]["target"]["entity_id"] == "light.living_room"

    def test_unknown_pattern_type_raises_error(self, tmp_path):
        hass = make_hass(tmp_path)
        creator = AutomationCreator(hass)
        with pytest.raises(AutomationCreationError, match="Unknown pattern_type"):
            creator._build_automation_dict(
                entity_id="light.bedroom",
                pattern_type="unknown_type",
                peak_hour=7,
                secondary_entity_id=None,
            )

    def test_trigger_hour_override_applied(self, tmp_path):
        hass = make_hass(tmp_path)
        creator = AutomationCreator(hass)
        result = creator._build_automation_dict(
            entity_id="light.bedroom",
            pattern_type="daily_routine",
            peak_hour=7,
            secondary_entity_id=None,
            trigger_hour=9,  # override: use 9, not 7
        )
        assert result["triggers"][0]["at"] == "09:00:00"

    def test_trigger_entities_override_applied(self, tmp_path):
        hass = make_hass(tmp_path)
        creator = AutomationCreator(hass)
        override_entities = ["light.bedroom", "light.bathroom"]
        result = creator._build_automation_dict(
            entity_id="light.bedroom",
            pattern_type="daily_routine",
            peak_hour=7,
            secondary_entity_id=None,
            trigger_entities=override_entities,
        )
        assert result["actions"][0]["target"]["entity_id"] == override_entities

    def test_dict_key_order(self, tmp_path):
        hass = make_hass(tmp_path)
        creator = AutomationCreator(hass)
        result = creator._build_automation_dict(
            entity_id="light.bedroom",
            pattern_type="daily_routine",
            peak_hour=7,
            secondary_entity_id=None,
        )
        keys = list(result.keys())
        # Expected logical order: id, alias, description, triggers, conditions, actions
        assert keys == ["id", "alias", "description", "triggers", "conditions", "actions"]


# ---------------------------------------------------------------------------
# _generate_description tests
# ---------------------------------------------------------------------------


class TestGenerateDescription:
    def test_daily_routine_description(self, tmp_path):
        hass = make_hass(tmp_path)
        creator = AutomationCreator(hass)
        desc = creator._generate_description(
            "light.bedroom", "daily_routine", 7, None
        )
        assert "07:00" in desc
        # entity name should be rendered in friendly form
        assert "Light Bedroom" in desc or "light bedroom" in desc.lower()
        assert "every day" in desc.lower() or "Turns on" in desc

    def test_daily_routine_exact_format(self, tmp_path):
        hass = make_hass(tmp_path)
        creator = AutomationCreator(hass)
        desc = creator._generate_description("light.bedroom", "daily_routine", 7, None)
        assert desc == "Turns on Light Bedroom every day at 07:00"

    def test_temporal_sequence_description(self, tmp_path):
        hass = make_hass(tmp_path)
        creator = AutomationCreator(hass)
        desc = creator._generate_description(
            "light.hallway", "temporal_sequence", 0, "light.kitchen"
        )
        assert desc == "Turns on Light Kitchen when Light Hallway turns on"

    def test_presence_arrival_description(self, tmp_path):
        hass = make_hass(tmp_path)
        creator = AutomationCreator(hass)
        desc = creator._generate_description(
            "person.alice", "presence_arrival", 0, "light.living_room"
        )
        assert desc == "Turns on Light Living Room when Person Alice arrives home"

    def test_peak_hour_zero_padding(self, tmp_path):
        hass = make_hass(tmp_path)
        creator = AutomationCreator(hass)
        desc = creator._generate_description("light.bedroom", "daily_routine", 8, None)
        assert "08:00" in desc


# ---------------------------------------------------------------------------
# create_automation_sync file I/O tests
# ---------------------------------------------------------------------------


class TestCreateAutomationSync:
    def test_writes_new_automation_to_file(self, tmp_path):
        hass = make_hass(tmp_path)
        creator = AutomationCreator(hass)
        automations_path = tmp_path / "automations.yaml"
        # Create empty file (writable)
        automations_path.write_text("", encoding="utf-8")

        result = creator.create_automation_sync(
            entity_id="light.bedroom",
            pattern_type="daily_routine",
            peak_hour=7,
        )

        assert result["id"].startswith("smart_habits_")
        # Read back and confirm it was written
        data = yaml.safe_load(automations_path.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == result["id"]

    def test_returns_automation_dict(self, tmp_path):
        hass = make_hass(tmp_path)
        creator = AutomationCreator(hass)
        automations_path = tmp_path / "automations.yaml"
        automations_path.write_text("", encoding="utf-8")

        result = creator.create_automation_sync(
            entity_id="light.bedroom",
            pattern_type="daily_routine",
            peak_hour=7,
        )
        assert isinstance(result, dict)
        assert "id" in result
        assert "triggers" in result
        assert "actions" in result

    def test_skips_write_when_id_already_exists(self, tmp_path):
        hass = make_hass(tmp_path)
        creator = AutomationCreator(hass)
        automations_path = tmp_path / "automations.yaml"

        # Pre-write an automation with the same fingerprint
        existing_id = creator._get_automation_id("light.bedroom", "daily_routine", 7, None)
        existing_data = [{"id": existing_id, "alias": "existing", "description": "", "triggers": [], "conditions": [], "actions": []}]
        automations_path.write_text(
            yaml.dump(existing_data, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

        result = creator.create_automation_sync(
            entity_id="light.bedroom",
            pattern_type="daily_routine",
            peak_hour=7,
        )

        # File should still have only 1 entry (no duplicate appended)
        data = yaml.safe_load(automations_path.read_text(encoding="utf-8"))
        assert len(data) == 1

    def test_raises_error_when_not_writable(self, tmp_path):
        hass = make_hass(tmp_path)
        creator = AutomationCreator(hass)
        automations_path = tmp_path / "automations.yaml"
        automations_path.write_text("[]", encoding="utf-8")
        # Make file read-only
        automations_path.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)

        try:
            with pytest.raises(AutomationCreationError):
                creator.create_automation_sync(
                    entity_id="light.bedroom",
                    pattern_type="daily_routine",
                    peak_hour=7,
                )
        finally:
            # Restore permissions so tmp_path cleanup works
            automations_path.chmod(stat.S_IRUSR | stat.S_IWUSR)

    def test_creates_file_when_missing(self, tmp_path):
        hass = make_hass(tmp_path)
        creator = AutomationCreator(hass)
        automations_path = tmp_path / "automations.yaml"
        # Ensure file does NOT exist
        assert not automations_path.exists()

        result = creator.create_automation_sync(
            entity_id="light.bedroom",
            pattern_type="daily_routine",
            peak_hour=7,
        )

        assert automations_path.exists()
        data = yaml.safe_load(automations_path.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == result["id"]

    def test_preserves_existing_automations(self, tmp_path):
        hass = make_hass(tmp_path)
        creator = AutomationCreator(hass)
        automations_path = tmp_path / "automations.yaml"

        # Pre-write a different existing automation
        other_data = [{"id": "other_automation_1", "alias": "Other Automation"}]
        automations_path.write_text(
            yaml.dump(other_data, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

        creator.create_automation_sync(
            entity_id="light.bedroom",
            pattern_type="daily_routine",
            peak_hour=7,
        )

        data = yaml.safe_load(automations_path.read_text(encoding="utf-8"))
        assert len(data) == 2
        ids = [a["id"] for a in data]
        assert "other_automation_1" in ids

    def test_yaml_output_sort_keys_false(self, tmp_path):
        hass = make_hass(tmp_path)
        creator = AutomationCreator(hass)
        automations_path = tmp_path / "automations.yaml"
        automations_path.write_text("", encoding="utf-8")

        creator.create_automation_sync(
            entity_id="light.bedroom",
            pattern_type="daily_routine",
            peak_hour=7,
        )

        raw_yaml = automations_path.read_text(encoding="utf-8")
        # id should appear before alias in the output (logical order)
        id_pos = raw_yaml.index("id:")
        alias_pos = raw_yaml.index("alias:")
        assert id_pos < alias_pos, "YAML must preserve insertion order (id before alias)"
