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
    """Verify coordinator.py imports DailyRoutineDetector from the detectors subpackage.

    Phase 4 moved DailyRoutineDetector into the detectors/ subpackage.
    The import must use the new canonical path.
    """
    source = COORDINATOR_PATH.read_text(encoding="utf-8")

    assert "DailyRoutineDetector" in source, (
        "coordinator.py must reference DailyRoutineDetector"
    )
    assert "from .detectors import DailyRoutineDetector" in source, (
        "coordinator.py must use: from .detectors import DailyRoutineDetector "
        "(Phase 4: moved from .pattern_detector to .detectors subpackage)"
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


# ---------------------------------------------------------------------------
# Phase 6 Plan 01: Single executor job, AcceptedPatternsStore, accepted filtering
# ---------------------------------------------------------------------------


def test_coordinator_uses_single_executor_job() -> None:
    """Verify _async_update_data contains exactly one async_add_executor_job call.

    Phase 6 consolidates three separate executor jobs (one per detector) into
    a single _run_all_detectors call. Exactly 1 call must appear in the body
    of _async_update_data.
    """
    source = COORDINATOR_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)

    # Find _async_update_data and count async_add_executor_job calls in its body
    update_data_node = None
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "_async_update_data":
            update_data_node = node
            break

    assert update_data_node is not None, (
        "coordinator.py must define _async_update_data"
    )

    # Count async_add_executor_job attribute accesses in the function body
    executor_call_count = sum(
        1
        for child in ast.walk(update_data_node)
        if isinstance(child, ast.Attribute) and child.attr == "async_add_executor_job"
    )

    assert executor_call_count == 1, (
        f"_async_update_data must contain exactly 1 async_add_executor_job call, "
        f"found {executor_call_count}. Phase 6 consolidates three calls into one "
        "_run_all_detectors call."
    )


def test_coordinator_has_run_all_detectors() -> None:
    """Verify coordinator.py defines a _run_all_detectors method."""
    source = COORDINATOR_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)

    method_names = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert "_run_all_detectors" in method_names, (
        "coordinator.py must define _run_all_detectors method "
        "(Phase 6: consolidates three detectors into one executor call)"
    )


def test_coordinator_imports_accepted_store() -> None:
    """Verify coordinator.py imports AcceptedPatternsStore from .storage."""
    source = COORDINATOR_PATH.read_text(encoding="utf-8")

    assert "AcceptedPatternsStore" in source, (
        "coordinator.py must reference AcceptedPatternsStore"
    )

    # Find the storage import line and verify AcceptedPatternsStore is on it
    storage_import_lines = [
        line for line in source.splitlines()
        if "from .storage import" in line
    ]
    assert any("AcceptedPatternsStore" in line for line in storage_import_lines), (
        "coordinator.py must import AcceptedPatternsStore via 'from .storage import ...'"
    )


def test_coordinator_returns_accepted_patterns_key() -> None:
    """Verify _async_update_data return statements include 'accepted_patterns' key.

    Both the early-return path (no entity_ids) and the main return path must
    include accepted_patterns in the returned dict.
    """
    source = COORDINATOR_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)

    update_data_node = None
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "_async_update_data":
            update_data_node = node
            break

    assert update_data_node is not None, "coordinator.py must define _async_update_data"

    # Collect all return statement sources within the function
    return_srcs = []
    for child in ast.walk(update_data_node):
        if isinstance(child, ast.Return) and child.value is not None:
            return_srcs.append(ast.unparse(child.value))

    assert len(return_srcs) >= 2, (
        "_async_update_data should have at least 2 return paths "
        "(early return + main return)"
    )

    assert all("accepted_patterns" in s for s in return_srcs), (
        "All return paths in _async_update_data must include 'accepted_patterns' key. "
        f"Returns found: {return_srcs}"
    )


def test_coordinator_merges_all_detectors() -> None:
    """Behavioral merge test (SC-1): _run_all_detectors returns patterns from all three detectors.

    Instantiates SmartHabitsCoordinator with mocked dependencies. Patches all
    three detector classes so each .detect() returns a pattern with a distinct
    pattern_type. Calls _run_all_detectors directly and asserts the merged result
    covers all three types.

    This test catches any implementation that silently drops a detector's output.
    """
    from unittest.mock import MagicMock, patch
    from custom_components.smart_habits.coordinator import SmartHabitsCoordinator
    from custom_components.smart_habits.models import DetectedPattern

    # Build minimal mock entry
    mock_entry = MagicMock()
    mock_entry.options = {}
    mock_entry.data = {}

    # Build minimal mock hass
    mock_hass = MagicMock()

    # Create coordinator without calling __init__ fully by patching Store and DataUpdateCoordinator
    with (
        patch("custom_components.smart_habits.coordinator.DismissedPatternsStore"),
        patch("custom_components.smart_habits.coordinator.AcceptedPatternsStore"),
    ):
        coordinator = SmartHabitsCoordinator.__new__(SmartHabitsCoordinator)
        coordinator.hass = mock_hass
        coordinator.min_confidence = 0.6
        coordinator.sequence_window = 300

    # Create one fake pattern per detector type
    pattern_daily = DetectedPattern(
        entity_id="light.bedroom",
        pattern_type="daily_routine",
        peak_hour=7,
        confidence=0.9,
        evidence="test",
        active_days=27,
        total_days=30,
    )
    pattern_sequence = DetectedPattern(
        entity_id="light.hallway",
        pattern_type="temporal_sequence",
        peak_hour=0,
        confidence=0.8,
        evidence="test",
        active_days=20,
        total_days=30,
        secondary_entity_id="light.kitchen",
    )
    pattern_presence = DetectedPattern(
        entity_id="person.alice",
        pattern_type="presence_arrival",
        peak_hour=0,
        confidence=0.85,
        evidence="test",
        active_days=25,
        total_days=30,
        secondary_entity_id="light.living_room",
    )

    daily_mock = MagicMock()
    daily_mock.detect.return_value = [pattern_daily]

    seq_mock = MagicMock()
    seq_mock.detect.return_value = [pattern_sequence]

    presence_mock = MagicMock()
    presence_mock.detect.return_value = [pattern_presence]

    states: dict = {"light.bedroom": [], "light.hallway": [], "person.alice": []}
    lookback_days = 30

    with (
        patch("custom_components.smart_habits.coordinator.DailyRoutineDetector", return_value=daily_mock),
        patch("custom_components.smart_habits.coordinator.TemporalSequenceDetector", return_value=seq_mock),
        patch("custom_components.smart_habits.coordinator.PresencePatternDetector", return_value=presence_mock),
    ):
        result = coordinator._run_all_detectors(states, lookback_days)

    assert len(result) >= 3, (
        f"_run_all_detectors must return at least 3 patterns (one per detector type), got {len(result)}"
    )
    types_found = {p.pattern_type for p in result}
    expected_types = {"daily_routine", "temporal_sequence", "presence_arrival"}
    assert expected_types.issubset(types_found), (
        f"_run_all_detectors must return patterns covering all three types. "
        f"Expected {expected_types}, got {types_found}"
    )
