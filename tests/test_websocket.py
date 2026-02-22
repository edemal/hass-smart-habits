"""Static analysis tests for the Smart Habits WebSocket API.

These tests use AST parsing and source text analysis to validate:
- websocket_api.py exists and defines async_register_commands
- All three commands use the smart_habits/ namespace (prevents collision — RESEARCH pitfall 6)
- Coordinator is accessed via entries[0].runtime_data (modern HA pattern)
- Dismiss command calls dismissed_store.async_dismiss (MGMT-01/MGMT-02)
- Patterns are serialized with dataclasses.asdict

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
