"""Tests for Smart Habits sidebar panel registration.

These tests verify:
1. async_setup_entry calls panel_custom.async_register_panel with correct kwargs
2. async_setup_entry registers static paths via hass.http.async_register_static_paths
3. async_setup_entry guards against duplicate panel registration
4. async_unload_entry calls frontend.async_remove_panel
5. manifest.json has "dependencies" including http, frontend, panel_custom
6. frontend/smart-habits-panel.js exists with customElements.define

All tests use asyncio.run() and mocking — no running HA instance required.
"""

import asyncio
import json
import pathlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

COMPONENT_DIR = pathlib.Path(__file__).parent.parent / "custom_components" / "smart_habits"
MANIFEST_PATH = COMPONENT_DIR / "manifest.json"
FRONTEND_JS_PATH = COMPONENT_DIR / "frontend" / "smart-habits-panel.js"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_hass_mock():
    """Build a minimal hass mock compatible with async_setup_entry."""
    hass = MagicMock()
    hass.data = {}

    # http mock with AsyncMock for async_register_static_paths
    hass.http = MagicMock()
    hass.http.async_register_static_paths = AsyncMock()

    # config_entries mock
    hass.config_entries = MagicMock()

    # async_add_executor_job must be awaitable
    hass.async_add_executor_job = AsyncMock(return_value=None)

    # config.path for AutomationCreator
    hass.config = MagicMock()
    hass.config.path = MagicMock(return_value="/config/automations.yaml")

    # states for automation creator
    hass.states = MagicMock()
    hass.states.get = MagicMock(return_value=None)

    # services for automation reload
    hass.services = MagicMock()
    hass.services.async_call = AsyncMock()

    return hass


def _make_entry_mock():
    """Build a minimal ConfigEntry mock."""
    entry = MagicMock()
    entry.options = {}
    entry.async_on_unload = MagicMock()
    entry.async_create_background_task = MagicMock()
    entry.add_update_listener = MagicMock(return_value=MagicMock())
    entry.runtime_data = None
    return entry


# ---------------------------------------------------------------------------
# Test 1: async_setup_entry registers the sidebar panel with correct kwargs
# ---------------------------------------------------------------------------

def test_setup_entry_registers_panel():
    """async_setup_entry must call async_register_panel with correct kwargs."""
    hass = _make_hass_mock()
    entry = _make_entry_mock()

    mock_coord = MagicMock()
    mock_coord.async_config_entry_first_refresh = AsyncMock()
    mock_coord.async_trigger_scan = AsyncMock(return_value=None)

    async def _run():
        with (
            patch(
                "custom_components.smart_habits.SmartHabitsCoordinator",
                return_value=mock_coord,
            ),
            patch(
                "custom_components.smart_habits._async_register_panel",
                new_callable=AsyncMock,
            ) as mock_register_panel,
            patch(
                "custom_components.smart_habits.frontend",
            ),
            patch(
                "custom_components.smart_habits.async_register_commands",
            ),
        ):
            from custom_components.smart_habits import async_setup_entry
            result = await async_setup_entry(hass, entry)

            assert result is True
            mock_register_panel.assert_called_once()
            kwargs = mock_register_panel.call_args.kwargs
            assert kwargs.get("frontend_url_path") == "smart_habits", (
                f"Expected frontend_url_path='smart_habits', got {kwargs.get('frontend_url_path')!r}"
            )
            assert kwargs.get("sidebar_title") == "Smart Habits", (
                f"Expected sidebar_title='Smart Habits', got {kwargs.get('sidebar_title')!r}"
            )
            assert kwargs.get("sidebar_icon") == "mdi:brain", (
                f"Expected sidebar_icon='mdi:brain', got {kwargs.get('sidebar_icon')!r}"
            )

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Test 2: async_setup_entry registers static paths with StaticPathConfig
# ---------------------------------------------------------------------------

def test_setup_entry_registers_static_paths():
    """async_setup_entry must register /smart_habits_frontend static path."""
    hass = _make_hass_mock()
    entry = _make_entry_mock()

    mock_coord = MagicMock()
    mock_coord.async_config_entry_first_refresh = AsyncMock()
    mock_coord.async_trigger_scan = AsyncMock(return_value=None)

    async def _run():
        with (
            patch(
                "custom_components.smart_habits.SmartHabitsCoordinator",
                return_value=mock_coord,
            ),
            patch(
                "custom_components.smart_habits._async_register_panel",
                new_callable=AsyncMock,
            ),
            patch(
                "custom_components.smart_habits.frontend",
            ),
            patch(
                "custom_components.smart_habits.async_register_commands",
            ),
        ):
            from custom_components.smart_habits import async_setup_entry
            result = await async_setup_entry(hass, entry)

        assert result is True
        hass.http.async_register_static_paths.assert_called_once()
        # Verify the static path config contains /smart_habits_frontend
        call_args = hass.http.async_register_static_paths.call_args
        static_paths = call_args[0][0]  # positional arg: list of StaticPathConfig
        assert len(static_paths) == 1, "Expected exactly one StaticPathConfig"
        config = static_paths[0]
        assert config.url_path == "/smart_habits_frontend", (
            f"Expected url_path='/smart_habits_frontend', got {config.url_path!r}"
        )
        assert config.cache_headers is False, (
            f"Expected cache_headers=False, got {config.cache_headers!r}"
        )

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Test 3: Duplicate registration guard — skips if already registered
# ---------------------------------------------------------------------------

def test_setup_entry_guards_duplicate_registration():
    """async_setup_entry must skip panel registration if already in hass.data."""
    hass = _make_hass_mock()
    # Pre-populate frontend_panels as if panel is already registered
    hass.data["frontend_panels"] = {"smart_habits": MagicMock()}
    entry = _make_entry_mock()

    mock_coord = MagicMock()
    mock_coord.async_config_entry_first_refresh = AsyncMock()
    mock_coord.async_trigger_scan = AsyncMock(return_value=None)

    async def _run():
        with (
            patch(
                "custom_components.smart_habits.SmartHabitsCoordinator",
                return_value=mock_coord,
            ),
            patch(
                "custom_components.smart_habits._async_register_panel",
                new_callable=AsyncMock,
            ) as mock_register_panel,
            patch(
                "custom_components.smart_habits.frontend",
            ),
            patch(
                "custom_components.smart_habits.async_register_commands",
            ),
        ):
            from custom_components.smart_habits import async_setup_entry
            result = await async_setup_entry(hass, entry)

            assert result is True
            # Panel was already registered, so _async_register_panel should NOT be called
            mock_register_panel.assert_not_called()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Test 4: async_unload_entry calls frontend.async_remove_panel
# ---------------------------------------------------------------------------

def test_unload_entry_removes_panel():
    """async_unload_entry must call frontend.async_remove_panel(hass, 'smart_habits')."""
    hass = _make_hass_mock()
    entry = _make_entry_mock()

    async def _run():
        with patch(
            "custom_components.smart_habits.frontend",
        ) as mock_frontend:
            mock_frontend.async_remove_panel = MagicMock()

            from custom_components.smart_habits import async_unload_entry
            result = await async_unload_entry(hass, entry)

        assert result is True
        mock_frontend.async_remove_panel.assert_called_once_with(hass, "smart_habits")

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Test 5: manifest.json has "dependencies" with http, frontend, panel_custom
# ---------------------------------------------------------------------------

def test_manifest_has_required_dependencies():
    """manifest.json must declare dependencies on http, frontend, and panel_custom."""
    assert MANIFEST_PATH.exists(), f"manifest.json not found at {MANIFEST_PATH}"

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert "dependencies" in manifest, (
        "manifest.json must have a 'dependencies' key"
    )
    deps = manifest["dependencies"]
    for required_dep in ("http", "frontend", "panel_custom"):
        assert required_dep in deps, (
            f"manifest.json 'dependencies' must include '{required_dep}', got {deps!r}"
        )


# ---------------------------------------------------------------------------
# Test 6: frontend/smart-habits-panel.js exists with customElements.define
# ---------------------------------------------------------------------------

def test_frontend_js_exists_and_defines_custom_element():
    """frontend/smart-habits-panel.js must exist and call customElements.define."""
    assert FRONTEND_JS_PATH.exists(), (
        f"frontend/smart-habits-panel.js not found at {FRONTEND_JS_PATH}"
    )

    source = FRONTEND_JS_PATH.read_text(encoding="utf-8")
    assert "customElements.define" in source, (
        "smart-habits-panel.js must call customElements.define to register the element"
    )
    assert "smart-habits-panel" in source, (
        "smart-habits-panel.js must register a custom element named 'smart-habits-panel'"
    )
