"""Static analysis tests for RecorderReader.

These tests use AST parsing and text analysis to validate:
- No external ML dependencies (PDET-08: HAOS compatibility)
- No network calls (INTG-02: all processing local)
- Correct executor pattern (get_instance, not hass.async_add_executor_job)
- Sensible entity domain filter

No running HA instance required — all tests are static analysis.
"""

import ast
import pathlib

import pytest

# Path helpers
COMPONENT_DIR = pathlib.Path(__file__).parent.parent / "custom_components" / "smart_habits"
RECORDER_READER_PATH = COMPONENT_DIR / "recorder_reader.py"
CONST_PATH = COMPONENT_DIR / "const.py"


def _collect_imports(tree: ast.AST) -> list[str]:
    """Walk an AST tree and collect all imported module names."""
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return imports


def test_no_external_dependencies() -> None:
    """Prove recorder_reader.py imports no external ML packages (PDET-08).

    scikit-learn, numpy, and scipy are confirmed broken on HAOS (musl-Linux).
    This test guarantees they are never accidentally imported.
    """
    source = RECORDER_READER_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    all_imports = _collect_imports(tree)

    forbidden = {"numpy", "sklearn", "scikit", "scipy", "pandas"}
    for imp in all_imports:
        for banned in forbidden:
            assert banned not in imp, (
                f"External ML dependency '{banned}' found in import '{imp}'. "
                f"This will fail on HAOS (musl-Linux). Use Python stdlib instead."
            )


def test_no_network_calls() -> None:
    """Prove no custom_components files make outbound network calls (INTG-02).

    All processing must be local — no external API calls allowed.
    """
    forbidden_imports = {
        "requests",
        "httpx",
        "urllib.request",
    }
    # aiohttp is a HA built-in, but ClientSession direct usage would indicate
    # outbound calls; check for direct ClientSession import
    forbidden_patterns = ["aiohttp.ClientSession"]

    py_files = list(COMPONENT_DIR.glob("*.py"))
    assert py_files, f"No Python files found in {COMPONENT_DIR}"

    for py_file in py_files:
        source = py_file.read_text(encoding="utf-8")
        tree = ast.parse(source)
        all_imports = _collect_imports(tree)

        for imp in all_imports:
            assert imp not in forbidden_imports, (
                f"Network library '{imp}' found in {py_file.name}. "
                f"All processing must be local (INTG-02)."
            )

        for pattern in forbidden_patterns:
            assert pattern not in source, (
                f"Network pattern '{pattern}' found in {py_file.name}. "
                f"All processing must be local (INTG-02)."
            )


def test_recorder_reader_uses_correct_executor() -> None:
    """Prove RecorderReader uses get_instance executor, not the wrong pattern.

    Since HA 2022.6, DB queries MUST use get_instance(hass).async_add_executor_job,
    not hass.async_add_executor_job (which uses the generic thread pool, not the
    Recorder's dedicated DB executor).
    """
    source = RECORDER_READER_PATH.read_text(encoding="utf-8")

    # Must import get_instance from the correct location
    assert "from homeassistant.components.recorder import get_instance" in source, (
        "get_instance must be imported from homeassistant.components.recorder"
    )

    # Must use get_instance(self.hass).async_add_executor_job
    assert "get_instance(self.hass).async_add_executor_job" in source, (
        "DB queries must use get_instance(self.hass).async_add_executor_job, "
        "not hass.async_add_executor_job (wrong executor pool)"
    )

    # Must NOT use the wrong pattern (hass.async_add_executor_job without get_instance)
    # Strip legitimate mentions in comments/docstrings by checking non-comment lines
    non_comment_lines = [
        line for line in source.splitlines()
        if not line.strip().startswith("#") and not line.strip().startswith('"""')
        and not line.strip().startswith("'")
    ]
    for line in non_comment_lines:
        assert "hass.async_add_executor_job" not in line or "get_instance" in line, (
            f"Found bare 'hass.async_add_executor_job' without get_instance: {line!r}. "
            f"Always use get_instance(hass).async_add_executor_job for DB queries."
        )


def test_entity_domain_filter() -> None:
    """Verify DEFAULT_ENTITY_DOMAINS contains sensible state-changing domains.

    The domain whitelist should:
    - Include core state-changing domains: light, switch, binary_sensor
    - NOT include 'sensor' (would flood analysis with temperature/humidity noise)
    """
    # Import const via exec to avoid needing HA installed
    source = CONST_PATH.read_text(encoding="utf-8")
    namespace: dict = {}
    exec(compile(source, str(CONST_PATH), "exec"), namespace)  # noqa: S102

    domains = namespace.get("DEFAULT_ENTITY_DOMAINS")
    assert domains is not None, "DEFAULT_ENTITY_DOMAINS must be defined in const.py"
    assert isinstance(domains, list), "DEFAULT_ENTITY_DOMAINS must be a list"

    # Required state-changing domains
    required = {"light", "switch", "binary_sensor"}
    missing = required - set(domains)
    assert not missing, (
        f"DEFAULT_ENTITY_DOMAINS is missing required domains: {missing}. "
        f"These are core state-changing domains for habit detection."
    )

    # 'sensor' domain should be excluded (temperature, humidity noise)
    assert "sensor" not in domains, (
        "DEFAULT_ENTITY_DOMAINS must NOT include 'sensor'. "
        "Sensor entities produce continuous numeric readings (temperature, humidity) "
        "that flood analysis with noise. Only state-changing domains belong here."
    )
