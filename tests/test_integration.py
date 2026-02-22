"""Static analysis tests for the Smart Habits integration structure.

These tests use AST parsing and text analysis to validate:
- __init__.py uses modern HA patterns (entry.runtime_data, not hass.data[DOMAIN])
- Background scan uses entry.async_create_background_task (not asyncio.create_task)
- Coordinator does not poll on a schedule (update_interval=None)
- Full module structure matches RESEARCH.md recommended layout

No running HA instance required — all tests are static analysis.
"""

import ast
import pathlib

# Path helpers
COMPONENT_DIR = pathlib.Path(__file__).parent.parent / "custom_components" / "smart_habits"
INIT_PATH = COMPONENT_DIR / "__init__.py"
COORDINATOR_PATH = COMPONENT_DIR / "coordinator.py"
REPO_ROOT = pathlib.Path(__file__).parent.parent


def test_init_imports_coordinator() -> None:
    """Verify __init__.py imports SmartHabitsCoordinator."""
    source = INIT_PATH.read_text(encoding="utf-8")
    assert "SmartHabitsCoordinator" in source, (
        "__init__.py must import SmartHabitsCoordinator from .coordinator"
    )
    assert "from .coordinator import SmartHabitsCoordinator" in source, (
        "__init__.py must use: from .coordinator import SmartHabitsCoordinator"
    )


def test_init_uses_runtime_data() -> None:
    """Verify __init__.py uses entry.runtime_data (modern HA pattern).

    The deprecated hass.data[DOMAIN] dict pattern must not be used.
    entry.runtime_data is the current HA best practice for storing per-entry data.
    """
    source = INIT_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)

    # Verify entry.runtime_data assignment exists
    assert "entry.runtime_data" in source, (
        "__init__.py must assign coordinator to entry.runtime_data "
        "(modern HA pattern, not hass.data[DOMAIN])"
    )

    # Verify deprecated hass.data[DOMAIN] pattern is NOT used
    assert "hass.data[DOMAIN]" not in source, (
        "__init__.py must NOT use hass.data[DOMAIN] — deprecated pattern. "
        "Use entry.runtime_data instead."
    )
    assert "hass.data.setdefault(DOMAIN" not in source, (
        "__init__.py must NOT use hass.data.setdefault(DOMAIN) — deprecated pattern. "
        "Use entry.runtime_data instead."
    )


def test_init_uses_background_task() -> None:
    """Verify __init__.py triggers scan via entry.async_create_background_task.

    asyncio.create_task() must NOT be used because:
    - It bypasses HA lifecycle management
    - HA cannot cancel it on entry unload
    - entry.async_create_background_task handles cancellation automatically
    """
    source = INIT_PATH.read_text(encoding="utf-8")

    assert "async_create_background_task" in source, (
        "__init__.py must trigger background scan via entry.async_create_background_task"
    )

    assert "asyncio.create_task" not in source, (
        "__init__.py must NOT use asyncio.create_task — bypasses HA lifecycle. "
        "Use entry.async_create_background_task instead."
    )


def test_coordinator_has_no_poll_interval() -> None:
    """Verify coordinator uses update_interval=None (no scheduled polling in Phase 1).

    INTG-03 requires that analysis runs as a background task, not on a schedule.
    update_interval=None ensures DataUpdateCoordinator does not create unnecessary
    background polling work during Phase 1.
    """
    source = COORDINATOR_PATH.read_text(encoding="utf-8")

    assert "update_interval=None" in source or "update_interval = None" in source, (
        "coordinator.py must set update_interval=None on DataUpdateCoordinator. "
        "Phase 1 does not poll on a schedule — background task only."
    )


def test_full_module_structure() -> None:
    """Verify all required integration files exist.

    Validates the complete module layout from RESEARCH.md:
    - Core integration files in custom_components/smart_habits/
    - hacs.json at repo root for HACS compatibility
    """
    required_component_files = [
        "__init__.py",
        "manifest.json",
        "const.py",
        "config_flow.py",
        "coordinator.py",
        "recorder_reader.py",
        "strings.json",
    ]

    for filename in required_component_files:
        filepath = COMPONENT_DIR / filename
        assert filepath.exists(), (
            f"Missing required integration file: custom_components/smart_habits/{filename}"
        )

    # hacs.json at repo root for HACS compatibility
    hacs_json = REPO_ROOT / "hacs.json"
    assert hacs_json.exists(), (
        "Missing hacs.json at repository root — required for HACS compatibility"
    )
