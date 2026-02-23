"""Static analysis and functional tests for DismissedPatternsStore (storage.py).

These tests parse the AST and source of storage.py to verify structural
correctness without requiring a running HA instance — consistent with
Phase 1/2 test style.

v2 migration tests verify:
- V1 data (without secondary_entity_id) loads correctly with None as 4th element
- 4-element fingerprints are distinct (entity+type+hour+secondary_entity_id)
"""
import ast
import asyncio
import os
from unittest.mock import AsyncMock, MagicMock


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


def test_storage_version_is_2():
    """STORAGE_VERSION must be 2 for the v2 schema with secondary_entity_id."""
    source = _get_source()
    assert "STORAGE_VERSION = 2" in source, (
        "STORAGE_VERSION must be 2 (bumped from 1 to support 4-element fingerprints)"
    )


def test_storage_contains_secondary_entity_id():
    """storage.py must contain secondary_entity_id for 4-element fingerprints."""
    source = _get_source()
    assert "secondary_entity_id" in source, (
        "storage.py must use secondary_entity_id for temporal sequence dismiss support"
    )


# ---------------------------------------------------------------------------
# Functional tests: v1 to v2 migration (using mocked Store)
# ---------------------------------------------------------------------------


def _make_store_instance(v1_data=None):
    """Create a DismissedPatternsStore with a mocked _store.async_load."""
    from unittest.mock import patch
    from custom_components.smart_habits.storage import DismissedPatternsStore

    # Patch the Store class in storage module so __init__ doesn't call the real Store
    mock_inner_store = MagicMock()
    mock_inner_store.async_load = AsyncMock(return_value=v1_data)
    mock_inner_store.async_save = AsyncMock(return_value=None)

    mock_store_class = MagicMock(return_value=mock_inner_store)

    with patch("custom_components.smart_habits.storage.Store", mock_store_class):
        mock_hass = MagicMock(spec=[])  # empty spec to prevent speccing issues
        store = DismissedPatternsStore(mock_hass)

    return store


def test_v1_data_migrates_secondary_entity_id_to_none():
    """V1 dismissed records (without secondary_entity_id) load with None as 4th element.

    This is the core migration test: old storage data must still be recognized
    as dismissed after the v2 schema change.
    """
    v1_data = {
        "dismissed": [
            {"entity_id": "light.bedroom", "pattern_type": "daily_routine", "peak_hour": 7},
        ]
    }
    store = _make_store_instance(v1_data)

    # Run async_load synchronously using asyncio.run
    asyncio.run(store.async_load())

    # V1 record with no secondary_entity_id → treated as secondary_entity_id=None
    assert store.is_dismissed("light.bedroom", "daily_routine", 7), (
        "V1 record should be dismissed (backward compat: secondary_entity_id defaults to None)"
    )
    assert store.is_dismissed("light.bedroom", "daily_routine", 7, None), (
        "is_dismissed with explicit None should match V1 record"
    )


def test_secondary_entity_id_creates_distinct_fingerprint():
    """Dismissing with different secondary_entity_id values creates distinct fingerprints.

    A sequence pattern (light.bedroom -> light.kitchen) must be dismissed
    independently from the daily routine pattern (light.bedroom, secondary=None).
    """
    store = _make_store_instance(None)  # empty store

    asyncio.run(store.async_load())

    # Dismiss with secondary_entity_id="light.kitchen"
    asyncio.run(store.async_dismiss("light.bedroom", "daily_routine", 7, "light.kitchen"))

    # The kitchen-sequence fingerprint IS dismissed
    assert store.is_dismissed("light.bedroom", "daily_routine", 7, "light.kitchen"), (
        "Pattern dismissed with secondary_entity_id='light.kitchen' should be dismissed"
    )

    # The None fingerprint is NOT dismissed (distinct key)
    assert not store.is_dismissed("light.bedroom", "daily_routine", 7, None), (
        "Pattern with secondary_entity_id=None should NOT be dismissed (distinct fingerprint)"
    )
    assert not store.is_dismissed("light.bedroom", "daily_routine", 7), (
        "Pattern without secondary_entity_id should NOT be dismissed (defaults to None, distinct)"
    )
