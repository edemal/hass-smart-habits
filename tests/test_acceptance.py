"""Tests for the WebSocket accept_pattern command and extended get_patterns response.

These tests verify:
1. ws_accept_pattern handler exists in websocket_api.py
2. ws_accept_pattern is an AsyncFunctionDef (awaits async operations)
3. ws_accept_pattern schema has all required fields
4. async_register_commands includes ws_accept_pattern (4 commands total)
5. ws_get_patterns response includes accepted_patterns key
"""
import ast
import pathlib

WEBSOCKET_API_PATH = pathlib.Path(__file__).parent.parent / "custom_components" / "smart_habits" / "websocket_api.py"


def _get_source() -> str:
    return WEBSOCKET_API_PATH.read_text()


def _get_tree() -> ast.Module:
    return ast.parse(_get_source())


def _find_function(tree: ast.Module, name: str) -> ast.AsyncFunctionDef | ast.FunctionDef | None:
    """Find a function definition by name in the AST."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)) and node.name == name:
            return node
    return None


def test_websocket_has_accept_pattern_handler():
    """websocket_api.py must contain the ws_accept_pattern function."""
    source = _get_source()
    assert "ws_accept_pattern" in source, (
        "ws_accept_pattern not found in websocket_api.py"
    )


def test_accept_pattern_is_async_response():
    """ws_accept_pattern must be an async function (AsyncFunctionDef) because
    it awaits coordinator.accepted_store.async_accept and coordinator.async_refresh.
    """
    tree = _get_tree()
    func = _find_function(tree, "ws_accept_pattern")
    assert func is not None, "ws_accept_pattern function not found in AST"
    assert isinstance(func, ast.AsyncFunctionDef), (
        f"ws_accept_pattern must be async (AsyncFunctionDef), got {type(func).__name__}"
    )


def test_accept_pattern_schema_has_required_fields():
    """ws_accept_pattern schema must declare: type='smart_habits/accept_pattern',
    entity_id, pattern_type, peak_hour, and optional secondary_entity_id.
    """
    source = _get_source()
    # Find the region around ws_accept_pattern
    idx = source.find("ws_accept_pattern")
    assert idx != -1, "ws_accept_pattern not found in source"

    # All schema fields must appear in the source
    for field in [
        "smart_habits/accept_pattern",
        '"entity_id"',
        '"pattern_type"',
        '"peak_hour"',
        '"secondary_entity_id"',
    ]:
        assert field in source, f"Schema field {field!r} not found in websocket_api.py"


def test_register_commands_includes_accept():
    """async_register_commands must register ws_accept_pattern."""
    tree = _get_tree()
    register_fn = _find_function(tree, "async_register_commands")
    assert register_fn is not None, "async_register_commands not found in AST"

    # Collect all names referenced inside async_register_commands body
    referenced_names: set[str] = set()
    for node in ast.walk(register_fn):
        if isinstance(node, ast.Name):
            referenced_names.add(node.id)

    assert "ws_accept_pattern" in referenced_names, (
        "ws_accept_pattern not registered in async_register_commands"
    )


def test_register_commands_has_four_commands():
    """async_register_commands must call async_register_command exactly 4 times."""
    tree = _get_tree()
    register_fn = _find_function(tree, "async_register_commands")
    assert register_fn is not None, "async_register_commands not found in AST"

    count = 0
    for node in ast.walk(register_fn):
        if isinstance(node, ast.Call):
            func = node.func
            # Match websocket_api.async_register_command or async_register_command
            if isinstance(func, ast.Attribute) and func.attr == "async_register_command":
                count += 1
            elif isinstance(func, ast.Name) and func.id == "async_register_command":
                count += 1

    assert count == 4, (
        f"Expected 4 async_register_command calls in async_register_commands, found {count}"
    )


def test_get_patterns_returns_accepted_patterns():
    """ws_get_patterns must include 'accepted_patterns' in its send_result response."""
    tree = _get_tree()
    func = _find_function(tree, "ws_get_patterns")
    assert func is not None, "ws_get_patterns function not found in AST"

    # Walk the function body looking for 'accepted_patterns' as a string constant
    keys_found: set[str] = set()
    for node in ast.walk(func):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            keys_found.add(node.value)

    assert "accepted_patterns" in keys_found, (
        "ws_get_patterns does not include 'accepted_patterns' key in its response"
    )
