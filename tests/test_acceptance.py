"""Tests for the WebSocket accept_pattern command and extended get_patterns response.

These tests verify:
1. ws_accept_pattern handler exists in websocket_api.py
2. ws_accept_pattern is an AsyncFunctionDef (awaits async operations)
3. ws_accept_pattern schema has all required fields
4. async_register_commands includes ws_accept_pattern (4 commands total)
5. ws_get_patterns response includes accepted_patterns key
6. ws_accept_pattern imports and uses AutomationCreator (Plan 07-02)
7. ws_accept_pattern schema includes optional trigger_hour and trigger_entities fields
8. ws_accept_pattern calls async_create_automation and returns automation_id
9. ws_accept_pattern handles AutomationCreationError with yaml_for_manual_copy fallback
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


# --- Plan 07-02: AutomationCreator integration tests ---


def test_accept_pattern_imports_automation_creator():
    """websocket_api.py must import AutomationCreator (required for Plan 07-02 automation creation)."""
    source = _get_source()
    assert "AutomationCreator" in source, (
        "websocket_api.py must import or reference AutomationCreator from automation_creator"
    )


def test_accept_pattern_imports_automation_creation_error():
    """websocket_api.py must import AutomationCreationError for graceful error handling."""
    source = _get_source()
    assert "AutomationCreationError" in source, (
        "websocket_api.py must import or reference AutomationCreationError from automation_creator"
    )


def test_accept_pattern_has_trigger_hour_optional():
    """ws_accept_pattern schema must have optional trigger_hour field for customization (AUTO-04)."""
    source = _get_source()
    assert "trigger_hour" in source, (
        "ws_accept_pattern schema must include optional 'trigger_hour' field"
    )


def test_accept_pattern_has_trigger_entities_optional():
    """ws_accept_pattern schema must have optional trigger_entities field for customization (AUTO-04)."""
    source = _get_source()
    assert "trigger_entities" in source, (
        "ws_accept_pattern schema must include optional 'trigger_entities' field"
    )


def test_accept_pattern_calls_create_automation():
    """ws_accept_pattern body must call async_create_automation to create the HA automation (AUTO-01)."""
    source = _get_source()
    assert "async_create_automation" in source, (
        "ws_accept_pattern must call AutomationCreator.async_create_automation"
    )


def test_accept_pattern_returns_automation_id():
    """ws_accept_pattern must include automation_id in its send_result response."""
    tree = _get_tree()
    func = _find_function(tree, "ws_accept_pattern")
    assert func is not None, "ws_accept_pattern function not found in AST"

    # Walk function body looking for 'automation_id' as a string constant in send_result
    keys_found: set[str] = set()
    for node in ast.walk(func):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            keys_found.add(node.value)

    assert "automation_id" in keys_found, (
        "ws_accept_pattern must include 'automation_id' key in its send_result response"
    )


def test_accept_pattern_handles_creation_error():
    """ws_accept_pattern body must handle AutomationCreationError for graceful fallback (AUTO-05)."""
    tree = _get_tree()
    func = _find_function(tree, "ws_accept_pattern")
    assert func is not None, "ws_accept_pattern function not found in AST"

    # Walk function body looking for AutomationCreationError as a Name node in an exception handler
    error_names: set[str] = set()
    for node in ast.walk(func):
        if isinstance(node, ast.Name):
            error_names.add(node.id)

    assert "AutomationCreationError" in error_names, (
        "ws_accept_pattern must catch AutomationCreationError (for yaml_for_manual_copy fallback)"
    )


def test_accept_pattern_has_yaml_fallback():
    """ws_accept_pattern must include yaml_for_manual_copy in error response (AUTO-05 fallback)."""
    tree = _get_tree()
    func = _find_function(tree, "ws_accept_pattern")
    assert func is not None, "ws_accept_pattern function not found in AST"

    keys_found: set[str] = set()
    for node in ast.walk(func):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            keys_found.add(node.value)

    assert "yaml_for_manual_copy" in keys_found, (
        "ws_accept_pattern must include 'yaml_for_manual_copy' key in error fallback response"
    )
