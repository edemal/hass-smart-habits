"""Static analysis tests for the Smart Habits integration structure.

These tests use AST parsing and text analysis to validate:
- __init__.py uses modern HA patterns (entry.runtime_data, not hass.data[DOMAIN])
- Background scan uses entry.async_create_background_task (not asyncio.create_task)
- Coordinator uses configurable timedelta update_interval (Phase 3 scheduled polling)
- Options update listener is registered (MC-01)
- Options flow casts SelectSelector values to int (MC-02)
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


def test_coordinator_has_scheduled_poll_interval() -> None:
    """Verify coordinator uses a timedelta update_interval for scheduled polling (Phase 3).

    Phase 3 replaces the Phase 1/2 update_interval=None stub with a configurable
    timedelta so HA re-runs analysis on the user's chosen schedule (PDET-07).
    The interval is read from entry.options/entry.data at coordinator construction.
    """
    source = COORDINATOR_PATH.read_text(encoding="utf-8")

    # Phase 3: coordinator must use timedelta-based interval, not None
    assert "update_interval=timedelta" in source or "update_interval = timedelta" in source, (
        "coordinator.py must set update_interval=timedelta(...) on DataUpdateCoordinator "
        "for Phase 3 scheduled scans (PDET-07). The Phase 1/2 update_interval=None stub "
        "must be replaced with a configurable timedelta from entry.options."
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


# ---------------------------------------------------------------------------
# Phase 2 Plan 02: Coordinator-detector wiring tests
# ---------------------------------------------------------------------------


def test_coordinator_imports_detector() -> None:
    """Verify coordinator.py imports DailyRoutineDetector from .pattern_detector.

    The import must use the exact relative package path so that HA's component
    loader resolves it correctly at runtime.
    """
    source = COORDINATOR_PATH.read_text(encoding="utf-8")

    assert "DailyRoutineDetector" in source, (
        "coordinator.py must reference DailyRoutineDetector"
    )
    assert "from .pattern_detector import DailyRoutineDetector" in source, (
        "coordinator.py must use: from .pattern_detector import DailyRoutineDetector"
    )


def test_coordinator_uses_generic_executor() -> None:
    """Verify _async_update_data calls self.hass.async_add_executor_job.

    The detector.detect() call is CPU-bound and must run in the generic
    executor (self.hass.async_add_executor_job), NOT the recorder's dedicated
    DB executor (get_instance(hass).async_add_executor_job). Mixing the two
    can cause deadlocks under high DB load (RESEARCH.md Anti-Pattern 2).
    """
    source = COORDINATOR_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)

    # Must use self.hass.async_add_executor_job
    assert "self.hass.async_add_executor_job" in source, (
        "coordinator.py _async_update_data must call self.hass.async_add_executor_job "
        "for CPU-bound detector work (generic executor, not recorder executor)"
    )

    # Must NOT use recorder's executor for detection
    assert "get_instance" not in source, (
        "coordinator.py must NOT use get_instance(hass).async_add_executor_job for "
        "detector work — that is the Recorder's dedicated DB thread pool. "
        "Use self.hass.async_add_executor_job for CPU-bound pattern detection."
    )


def test_async_trigger_scan_delegates_to_refresh() -> None:
    """Verify async_trigger_scan calls self.async_refresh().

    Delegating to async_refresh() avoids duplicating the DB access logic
    already in _async_update_data. This ensures a single code path for
    data retrieval and keeps async_trigger_scan as a thin orchestration layer.
    """
    source = COORDINATOR_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)

    assert "async_refresh" in source, (
        "coordinator.py async_trigger_scan must call self.async_refresh() "
        "to avoid duplicating DB access logic from _async_update_data"
    )

    # Find async_trigger_scan function body and confirm async_refresh is called
    found_trigger_scan = False
    calls_async_refresh = False
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "async_trigger_scan":
            found_trigger_scan = True
            for child in ast.walk(node):
                if isinstance(child, ast.Attribute) and child.attr == "async_refresh":
                    calls_async_refresh = True
                    break
            break

    assert found_trigger_scan, (
        "coordinator.py must define async_trigger_scan method"
    )
    assert calls_async_refresh, (
        "coordinator.py async_trigger_scan must call self.async_refresh() "
        "to delegate to _async_update_data"
    )


def test_update_data_returns_patterns_key() -> None:
    """Verify _async_update_data returns a dict containing the 'patterns' key.

    The Phase 3 WebSocket API reads coordinator.data['patterns'] to serialize
    DetectedPattern objects. This test guards the data contract so that
    Phase 3 can be built against a stable interface.
    """
    source = COORDINATOR_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)

    # Verify "patterns" string literal appears in coordinator.py source
    assert '"patterns"' in source, (
        "coordinator.py _async_update_data must return a dict with key 'patterns' "
        "(e.g. return {\"patterns\": [...]}) — required for Phase 3 WebSocket API"
    )

    # Verify _async_update_data function exists and contains a return with "patterns"
    found_update_data = False
    returns_patterns = False
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "_async_update_data":
            found_update_data = True
            for child in ast.walk(node):
                # Look for return statements containing dict with "patterns" key
                if isinstance(child, ast.Return) and child.value is not None:
                    return_src = ast.unparse(child.value)
                    if "patterns" in return_src:
                        returns_patterns = True
                        break
            break

    assert found_update_data, (
        "coordinator.py must define _async_update_data method"
    )
    assert returns_patterns, (
        "coordinator.py _async_update_data must return a dict containing 'patterns' key"
    )


# ---------------------------------------------------------------------------
# Phase 3 Plan 01: Configurable schedule + options wiring tests (MC-01/MC-02)
# ---------------------------------------------------------------------------


def test_init_registers_update_listener() -> None:
    """Verify __init__.py registers an options update listener (MC-01).

    entry.add_update_listener must be wrapped with entry.async_on_unload so that
    the listener is automatically deregistered when the config entry is unloaded.
    This ensures options changes propagate to the running coordinator live without
    requiring a restart, and avoids listener leaks on reload.
    """
    source = INIT_PATH.read_text(encoding="utf-8")

    assert "add_update_listener" in source, (
        "__init__.py must call entry.add_update_listener to register the options "
        "update listener (MC-01 fix)"
    )
    assert "async_on_unload" in source, (
        "__init__.py must wrap add_update_listener with entry.async_on_unload so the "
        "listener is automatically deregistered on config entry unload (MC-01 pattern)"
    )


def test_options_flow_casts_to_int() -> None:
    """Verify config_flow.py options flow casts SelectSelector values to int (MC-02).

    SelectSelector always returns string values. Without int() casts, storing raw
    strings causes type mismatches when coordinator code reads the options as integers.
    Both CONF_LOOKBACK_DAYS and CONF_ANALYSIS_INTERVAL must be cast.
    """
    config_flow_path = COMPONENT_DIR / "config_flow.py"
    source = config_flow_path.read_text(encoding="utf-8")

    assert "int(user_input[" in source, (
        "config_flow.py options flow must cast SelectSelector string values to int() "
        "before storing (MC-02 fix) — e.g. int(user_input[CONF_LOOKBACK_DAYS])"
    )


# ---------------------------------------------------------------------------
# Phase 3 Plan 03: WebSocket registration test
# ---------------------------------------------------------------------------


def test_init_registers_websocket_commands() -> None:
    """Verify __init__.py calls async_register_commands(hass) during setup.

    The WebSocket API must be registered in async_setup_entry so commands
    are available after integration load. This confirms the registration call
    exists in the init module source.
    """
    source = INIT_PATH.read_text(encoding="utf-8")
    assert "async_register_commands" in source, (
        "__init__.py must call async_register_commands(hass) to register "
        "WebSocket commands during async_setup_entry"
    )


def test_coordinator_reads_options_first() -> None:
    """Verify coordinator.py reads entry.options before falling back to entry.data.

    Options always override data values. The coordinator must read entry.options.get()
    first (with entry.data.get() as fallback) for both CONF_LOOKBACK_DAYS and
    CONF_ANALYSIS_INTERVAL so that live options changes take effect immediately.
    """
    source = COORDINATOR_PATH.read_text(encoding="utf-8")

    assert "entry.options.get(" in source, (
        "coordinator.py must read entry.options.get() first (with entry.data fallback) "
        "for configurable fields — ensures options always override initial config data"
    )
