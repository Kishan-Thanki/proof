"""Unit and integration tests for Proof configuration compiler and AOT schema compilation."""

from pathlib import Path

import fastjsonschema
import pytest

from proof.core.compiler import ConfigCompilerError, load_and_compile_config


def test_load_and_compile_config_integration() -> None:
    """Verifies end-to-end config compilation using the example scenario file."""
    project_root = Path(__file__).parent.parent
    scenario_path = project_root / "scenarios" / "example.yaml"

    config = load_and_compile_config(scenario_path)

    # Global config verification
    assert config.global_config is not None
    assert (
        str(config.global_config.base_url).rstrip("/")
        == "https://jsonplaceholder.typicode.com"
    )
    assert config.global_config.timeout_seconds == 5.0

    # Scenario & Step level verification
    scenario = config.scenarios[0]
    step = scenario.steps[0]

    assert scenario.name == "User Profile Check"
    assert scenario.interval_seconds == 60
    assert step.name == "Fetch User #1"
    assert step.expect.max_latency_ms == 1000.0

    # Verify AOT compiled schema is attached and executable
    schema_func = step.expect.compiled_schema
    assert schema_func is not None
    assert callable(schema_func)

    # Test executing the compiled schema function against valid data
    valid_payload = {
        "id": 1,
        "name": "Leanne Graham",
        "username": "Bret",
        "email": "Sincere@april.biz",
    }
    assert schema_func(valid_payload) == valid_payload

    # Test executing the compiled schema function against invalid data
    invalid_payload = {"id": "not-an-int"}  # 'id' must be integer
    with pytest.raises(fastjsonschema.JsonSchemaValueException):
        schema_func(invalid_payload)


def test_load_and_compile_file_not_found() -> None:
    """Verifies that non-existent config paths raise ConfigCompilerError."""
    missing_path = Path("scenarios/non_existent_file.yaml")

    with pytest.raises(ConfigCompilerError) as exc_info:
        load_and_compile_config(missing_path)

    assert "Configuration file not found" in str(exc_info.value)


def test_load_and_compile_missing_base_url(tmp_path: Path) -> None:
    """Verifies that compilation fails if base_url is missing at all levels."""
    bad_yaml = tmp_path / "bad_config.yaml"
    bad_yaml.write_text(
        """
version: "1.0"
scenarios:
  - name: "No URL Scenario"
    steps:
      - name: "Step 1"
        request:
          method: "GET"
          path: "/ping"
        expect:
          status: 200
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigCompilerError) as exc_info:
        load_and_compile_config(bad_yaml)

    assert "missing 'base_url'" in str(exc_info.value)
