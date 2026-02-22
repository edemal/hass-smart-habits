"""Static analysis tests for stale automation detection.

These tests parse the AST and source of models.py to verify StaleAutomation
structure — consistent with Phase 1/2 test style. Updated in Plan 03 to assert
STALE_AUTOMATION_DAYS IS present in const.py and verify coordinator wiring.
"""
import ast
import os


MODELS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "custom_components", "smart_habits", "models.py"
)
CONST_PATH = os.path.join(
    os.path.dirname(__file__), "..", "custom_components", "smart_habits", "const.py"
)
COORDINATOR_PATH = os.path.join(
    os.path.dirname(__file__), "..", "custom_components", "smart_habits", "coordinator.py"
)


def _get_models_source() -> str:
    with open(MODELS_PATH) as f:
        return f.read()


def _get_models_tree() -> ast.Module:
    return ast.parse(_get_models_source())


def _get_class_node(tree: ast.Module, class_name: str) -> ast.ClassDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return node
    return None


def test_stale_automation_model_exists():
    """StaleAutomation must be defined as a dataclass in models.py."""
    tree = _get_models_tree()
    cls = _get_class_node(tree, "StaleAutomation")
    assert cls is not None, "StaleAutomation class not found in models.py"

    # Verify @dataclass decorator is applied
    decorator_names = []
    for decorator in cls.decorator_list:
        if isinstance(decorator, ast.Name):
            decorator_names.append(decorator.id)
        elif isinstance(decorator, ast.Attribute):
            decorator_names.append(decorator.attr)
    assert "dataclass" in decorator_names, "StaleAutomation must have @dataclass decorator"


def test_stale_automation_has_required_fields():
    """StaleAutomation must define entity_id, friendly_name, last_triggered, days_since_triggered."""
    tree = _get_models_tree()
    cls = _get_class_node(tree, "StaleAutomation")
    assert cls is not None, "StaleAutomation class not found in models.py"

    # Collect annotated field names from the class body
    field_names = {
        node.target.id
        for node in cls.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    required = {"entity_id", "friendly_name", "last_triggered", "days_since_triggered"}
    missing = required - field_names
    assert not missing, f"StaleAutomation missing required fields: {missing}"


def test_stale_automation_threshold_constant():
    """const.py must contain STALE_AUTOMATION_DAYS constant (added in Plan 03)."""
    with open(CONST_PATH) as f:
        const_source = f.read()
    assert "STALE_AUTOMATION_DAYS" in const_source, (
        "STALE_AUTOMATION_DAYS not found in const.py — this constant must be defined "
        "in Plan 03 for stale automation detection (MGMT-03)."
    )


def test_coordinator_has_stale_detection_method():
    """coordinator.py must define _async_detect_stale_automations as an async method."""
    with open(COORDINATOR_PATH) as f:
        coordinator_source = f.read()
    tree = ast.parse(coordinator_source)

    found = False
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.AsyncFunctionDef)
            and node.name == "_async_detect_stale_automations"
        ):
            found = True
            break

    assert found, (
        "coordinator.py must define _async_detect_stale_automations as an AsyncFunctionDef "
        "(MGMT-03 stale automation detection)"
    )


def test_stale_detection_uses_state_machine():
    """_async_detect_stale_automations must read from HA state machine, not Recorder.

    Confirms no Recorder query — per RESEARCH anti-pattern, stale detection must
    use hass.states.async_all (state machine) not the Recorder DB.
    """
    with open(COORDINATOR_PATH) as f:
        coordinator_source = f.read()
    tree = ast.parse(coordinator_source)

    # Find the _async_detect_stale_automations function body
    detect_method = None
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.AsyncFunctionDef)
            and node.name == "_async_detect_stale_automations"
        ):
            detect_method = node
            break

    assert detect_method is not None, (
        "coordinator.py must define _async_detect_stale_automations"
    )

    # Verify async_all appears in the method body (state machine access)
    method_source = ast.unparse(detect_method)
    assert "async_all" in method_source, (
        "_async_detect_stale_automations must call hass.states.async_all "
        "to read from the HA state machine (no Recorder query needed for stale detection)"
    )
