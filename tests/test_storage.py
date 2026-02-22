"""Static analysis tests for DismissedPatternsStore (storage.py).

These tests parse the AST and source of storage.py to verify structural
correctness without requiring a running HA instance — consistent with
Phase 1/2 test style.
"""
import ast
import os


STORAGE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "custom_components", "smart_habits", "storage.py"
)


def _get_source() -> str:
    with open(STORAGE_PATH) as f:
        return f.read()


def _get_tree() -> ast.Module:
    return ast.parse(_get_source())


def _get_class_node(tree: ast.Module, class_name: str) -> ast.ClassDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return node
    return None


def test_storage_module_exists():
    """storage.py must exist at the expected path."""
    assert os.path.isfile(STORAGE_PATH), "custom_components/smart_habits/storage.py not found"


def test_storage_uses_ha_store():
    """storage.py must import Store from homeassistant.helpers.storage."""
    source = _get_source()
    assert "from homeassistant.helpers.storage import Store" in source, (
        "storage.py must import Store from homeassistant.helpers.storage"
    )


def test_storage_key_is_namespaced():
    """STORAGE_KEY must be 'smart_habits.dismissed' (namespaced to prevent collision)."""
    source = _get_source()
    assert '"smart_habits.dismissed"' in source or "'smart_habits.dismissed'" in source, (
        "STORAGE_KEY must be 'smart_habits.dismissed' (prevents key collision per RESEARCH pitfall 5)"
    )


def test_storage_has_required_methods():
    """DismissedPatternsStore must define async_load, async_dismiss, and is_dismissed."""
    tree = _get_tree()
    cls = _get_class_node(tree, "DismissedPatternsStore")
    assert cls is not None, "DismissedPatternsStore class not found in storage.py"

    method_names = {
        node.name
        for node in ast.walk(cls)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    required = {"async_load", "async_dismiss", "is_dismissed"}
    missing = required - method_names
    assert not missing, f"DismissedPatternsStore missing methods: {missing}"


def test_storage_dismiss_is_async():
    """async_dismiss must be an AsyncFunctionDef — it must await Store.async_save."""
    tree = _get_tree()
    cls = _get_class_node(tree, "DismissedPatternsStore")
    assert cls is not None, "DismissedPatternsStore class not found in storage.py"

    async_dismiss_node = None
    for node in ast.walk(cls):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "async_dismiss":
            async_dismiss_node = node
            break

    assert async_dismiss_node is not None, (
        "async_dismiss must be an AsyncFunctionDef (needs to await Store.async_save)"
    )
