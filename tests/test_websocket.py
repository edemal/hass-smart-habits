"""Static analysis tests for the Smart Habits WebSocket API.

These tests use AST parsing and source text analysis to validate:
- websocket_api.py exists and defines async_register_commands
- All three commands use the smart_habits/ namespace (prevents collision — RESEARCH pitfall 6)
- Coordinator is accessed via entries[0].runtime_data (modern HA pattern)
- Dismiss command calls dismissed_store.async_dismiss (MGMT-01/MGMT-02)
- Patterns are serialized with dataclasses.asdict
- ws_preview_automation handler exists and is registered (Plan 07-02)

No running HA instance required — all tests are static analysis.
"""

import ast
import os
import pathlib

COMPONENT_DIR = pathlib.Path(__file__).parent.parent / "custom_components" / "smart_habits"
WEBSOCKET_PATH = COMPONENT_DIR / "websocket_api.py"


def _get_source() -> str:
    return WEBSOCKET_PATH.read_text(encoding="utf-8")


def _get_tree() -> ast.Module:
    return ast.parse(_get_source())


def test_websocket_module_exists() -> None:
    """websocket_api.py must exist in the smart_habits component directory."""
    assert WEBSOCKET_PATH.exists(), (
        f"websocket_api.py not found at {WEBSOCKET_PATH}"
    )


def test_websocket_has_register_function() -> None:
    """websocket_api.py must define async_register_commands function."""
    tree = _get_tree()
    function_names = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    assert "async_register_commands" in function_names, (
        "websocket_api.py must define async_register_commands function"
    )


def test_websocket_commands_namespaced() -> None:
    """All three WebSocket commands must use the smart_habits/ namespace.

    This prevents command type collisions with other integrations (RESEARCH pitfall 6).
    """
    source = _get_source()
    assert '"smart_habits/get_patterns"' in source, (
        "websocket_api.py must register command with type 'smart_habits/get_patterns'"
    )
    assert '"smart_habits/dismiss_pattern"' in source, (
        "websocket_api.py must register command with type 'smart_habits/dismiss_pattern'"
    )
    assert '"smart_habits/trigger_scan"' in source, (
        "websocket_api.py must register command with type 'smart_habits/trigger_scan'"
    )


def test_websocket_uses_runtime_data() -> None:
    """Coordinator must be accessed via entries[0].runtime_data.

    This is the modern HA pattern for accessing per-entry data.
    The deprecated hass.data[DOMAIN] pattern must not be used.
    """
    source = _get_source()
    assert "runtime_data" in source, (
        "websocket_api.py must access coordinator via entries[0].runtime_data "
        "(modern HA pattern, not hass.data[DOMAIN])"
    )


def test_websocket_dismiss_calls_store() -> None:
    """ws_dismiss_pattern must call dismissed_store.async_dismiss to persist the dismissal (MGMT-01)."""
    source = _get_source()
    assert "dismissed_store.async_dismiss" in source, (
        "websocket_api.py ws_dismiss_pattern must call "
        "coordinator.dismissed_store.async_dismiss to persist dismissal (MGMT-01)"
    )


def test_websocket_uses_asdict() -> None:
    """WebSocket handlers must use dataclasses.asdict for serializing patterns and stale automations."""
    source = _get_source()
    assert "asdict" in source, (
        "websocket_api.py must use dataclasses.asdict to serialize "
        "DetectedPattern and StaleAutomation dataclasses for the frontend"
    )


# --- Plan 07-02: ws_preview_automation tests ---


def _find_function(tree: ast.Module, name: str) -> ast.AsyncFunctionDef | ast.FunctionDef | None:
    """Find a function definition by name in the AST."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)) and node.name == name:
            return node
    return None


def test_preview_automation_handler_exists() -> None:
    """websocket_api.py must define the ws_preview_automation handler (Plan 07-02)."""
    source = _get_source()
    assert "ws_preview_automation" in source, (
        "ws_preview_automation not found in websocket_api.py"
    )


def test_preview_automation_is_callback() -> None:
    """ws_preview_automation must be a regular @callback function (FunctionDef), not AsyncFunctionDef.

    It is synchronous because it only calls _build_automation_dict and _generate_description
    (pure computation, no I/O). Using @async_response would be incorrect here.
    See 07-RESEARCH.md Pitfall 6.
    """
    tree = _get_tree()
    func = _find_function(tree, "ws_preview_automation")
    assert func is not None, "ws_preview_automation function not found in AST"
    assert isinstance(func, ast.FunctionDef), (
        f"ws_preview_automation must be a sync @callback FunctionDef, got {type(func).__name__}. "
        "Use @callback decorator, not @async_response."
    )


def test_preview_automation_schema_required_fields() -> None:
    """ws_preview_automation schema must have required entity_id, pattern_type, peak_hour fields."""
    source = _get_source()
    # We check these appear in the source in the ws_preview_automation context
    # The easiest reliable check: all three must appear in the overall source
    # since there is only one preview command schema
    for field in ["entity_id", "pattern_type", "peak_hour"]:
        assert field in source, (
            f"ws_preview_automation schema must include required field '{field}'"
        )


def test_preview_automation_schema_optional_fields() -> None:
    """ws_preview_automation schema must have optional secondary_entity_id, trigger_hour, trigger_entities."""
    source = _get_source()
    for field in ["secondary_entity_id", "trigger_hour", "trigger_entities"]:
        assert field in source, (
            f"ws_preview_automation schema must include optional field '{field}'"
        )


def test_preview_automation_returns_description() -> None:
    """ws_preview_automation send_result must include 'description' key."""
    tree = _get_tree()
    func = _find_function(tree, "ws_preview_automation")
    assert func is not None, "ws_preview_automation function not found in AST"

    keys_found: set[str] = set()
    for node in ast.walk(func):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            keys_found.add(node.value)

    assert "description" in keys_found, (
        "ws_preview_automation must include 'description' key in its send_result response"
    )


def test_preview_automation_returns_automation_dict() -> None:
    """ws_preview_automation send_result must include 'automation_dict' key."""
    tree = _get_tree()
    func = _find_function(tree, "ws_preview_automation")
    assert func is not None, "ws_preview_automation function not found in AST"

    keys_found: set[str] = set()
    for node in ast.walk(func):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            keys_found.add(node.value)

    assert "automation_dict" in keys_found, (
        "ws_preview_automation must include 'automation_dict' key in its send_result response"
    )


def test_register_commands_has_five_commands() -> None:
    """async_register_commands must call async_register_command exactly 5 times (ws_preview_automation added)."""
    tree = _get_tree()
    register_fn = _find_function(tree, "async_register_commands")
    assert register_fn is not None, "async_register_commands not found in AST"

    count = 0
    for node in ast.walk(register_fn):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "async_register_command":
                count += 1
            elif isinstance(func, ast.Name) and func.id == "async_register_command":
                count += 1

    assert count == 5, (
        f"Expected 5 async_register_command calls in async_register_commands, found {count}. "
        "ws_preview_automation must be registered as the 5th command."
    )
