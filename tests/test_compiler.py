"""Unit and integration tests for Proof configuration compiler."""

from pathlib import Path

import fastjsonschema
import pytest

from proof.core.compiler import ConfigCompilerError, load_and_compile_config


def test_load_and_compile_config_integration() -> None:
    """Verifies end-to-end config compilation using the example scenario."""
    project_root = Path(__file__).parent.parent
    scenario_path = project_root / "scenarios" / "example.yaml"

    config = load_and_compile_config(scenario_path)

    assert config.global_config is not None
    assert (
        str(config.global_config.base_url).rstrip("/")
        == "https://jsonplaceholder.typicode.com"
    )
    assert config.global_config.timeout_seconds == 5.0

    scenario = config.scenarios[0]
    step = scenario.steps[0]

    assert scenario.name == "User Profile Check"
    assert scenario.interval_seconds == 60
    assert step.name == "Fetch User #1"
    assert step.expect.max_latency_ms == 1000.0

    schema_func = step.expect.compiled_schema

    assert schema_func is not None
    assert callable(schema_func)

    valid_payload = {
        "id": 1,
        "name": "Leanne Graham",
        "username": "Bret",
        "email": "Sincere@april.biz",
    }

    assert schema_func(valid_payload) == valid_payload

    invalid_payload = {"id": "not-an-int"}

    with pytest.raises(fastjsonschema.JsonSchemaValueException):
        schema_func(invalid_payload)


def test_load_and_compile_file_not_found() -> None:
    """Verifies missing config paths raise ConfigCompilerError."""
    missing_path = Path("scenarios/non_existent_file.yaml")

    with pytest.raises(ConfigCompilerError) as exc_info:
        load_and_compile_config(missing_path)

    assert "Configuration file not found" in str(exc_info.value)


def test_load_and_compile_invalid_yaml(tmp_path: Path) -> None:
    """Verifies malformed YAML raises ConfigCompilerError."""
    config_path = tmp_path / "invalid.yaml"

    config_path.write_text(
        """
version: "1.0"
global:
  base_url: "https://example.com"
  timeout_seconds: [
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigCompilerError) as exc_info:
        load_and_compile_config(config_path)

    assert "Invalid YAML syntax" in str(exc_info.value)


def test_load_and_compile_non_mapping_yaml(tmp_path: Path) -> None:
    """Verifies a non-mapping YAML document is rejected."""
    config_path = tmp_path / "invalid.yaml"

    config_path.write_text(
        """
- one
- two
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigCompilerError) as exc_info:
        load_and_compile_config(config_path)

    assert "Expected a top-level YAML mapping" in str(exc_info.value)


def test_load_and_compile_missing_base_url(tmp_path: Path) -> None:
    """Verifies compilation fails when base_url is missing."""
    config_path = tmp_path / "bad_config.yaml"

    config_path.write_text(
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
        load_and_compile_config(config_path)

    assert "missing 'base_url'" in str(exc_info.value)


def test_scenario_inherits_global_base_url(tmp_path: Path) -> None:
    """Verifies scenario inherits base_url from global configuration."""
    config_path = tmp_path / "config.yaml"

    config_path.write_text(
        """
version: "1.0"

global:
  base_url: "https://api.example.com"

scenarios:
  - name: "Inherited URL Scenario"
    steps:
      - name: "Health Check"
        request:
          method: "GET"
          path: "/health"
        expect:
          status: 200
""",
        encoding="utf-8",
    )

    config = load_and_compile_config(config_path)

    assert config.scenarios[0].base_url is not None
    assert str(config.scenarios[0].base_url).rstrip("/") == "https://api.example.com"


def test_step_inherits_global_timeout(tmp_path: Path) -> None:
    """Verifies step inherits timeout from global configuration."""
    config_path = tmp_path / "config.yaml"

    config_path.write_text(
        """
version: "1.0"

global:
  base_url: "https://api.example.com"
  timeout_seconds: 7.5

scenarios:
  - name: "Inherited Timeout Scenario"
    steps:
      - name: "Health Check"
        request:
          method: "GET"
          path: "/health"
        expect:
          status: 200
""",
        encoding="utf-8",
    )

    config = load_and_compile_config(config_path)

    assert config.scenarios[0].steps[0].request.timeout == 7.5


def test_step_timeout_overrides_global_timeout(tmp_path: Path) -> None:
    """Verifies step timeout overrides global timeout."""
    config_path = tmp_path / "config.yaml"

    config_path.write_text(
        """
version: "1.0"

global:
  base_url: "https://api.example.com"
  timeout_seconds: 7.5

scenarios:
  - name: "Step Timeout Scenario"
    steps:
      - name: "Health Check"
        request:
          method: "GET"
          path: "/health"
          timeout: 3.0
        expect:
          status: 200
""",
        encoding="utf-8",
    )

    config = load_and_compile_config(config_path)

    assert config.scenarios[0].steps[0].request.timeout == 3.0


def test_global_headers_are_merged_with_step_headers(
    tmp_path: Path,
) -> None:
    """Verifies global headers are inherited and step headers override them."""
    config_path = tmp_path / "config.yaml"

    config_path.write_text(
        """
version: "1.0"

global:
  base_url: "https://api.example.com"
  headers:
    Authorization: "Bearer global-token"
    X-Environment: "production"
    X-Shared: "global"

scenarios:
  - name: "Header Merge Scenario"
    steps:
      - name: "Health Check"
        request:
          method: "GET"
          path: "/health"
          headers:
            X-Shared: "step"
            X-Step: "true"
        expect:
          status: 200
""",
        encoding="utf-8",
    )

    config = load_and_compile_config(config_path)

    headers = config.scenarios[0].steps[0].request.headers

    assert headers == {
        "Authorization": "Bearer global-token",
        "X-Environment": "production",
        "X-Shared": "step",
        "X-Step": "true",
    }


def test_inline_schema_is_compiled(tmp_path: Path) -> None:
    """Verifies inline JSON schema compilation."""
    config_path = tmp_path / "config.yaml"

    config_path.write_text(
        """
version: "1.0"

global:
  base_url: "https://api.example.com"

scenarios:
  - name: "Inline Schema Scenario"
    steps:
      - name: "Health Check"
        request:
          method: "GET"
          path: "/health"
        expect:
          status: 200
          schema:
            type: object
            required:
              - id
            properties:
              id:
                type: integer
""",
        encoding="utf-8",
    )

    config = load_and_compile_config(config_path)

    schema_func = config.scenarios[0].steps[0].expect.compiled_schema

    assert schema_func is not None
    assert schema_func({"id": 123}) == {"id": 123}

    with pytest.raises(fastjsonschema.JsonSchemaValueException):
        schema_func({"id": "invalid"})


def test_external_schema_is_compiled(tmp_path: Path) -> None:
    """Verifies JSON schema files are resolved relative to YAML."""
    schema_path = tmp_path / "user_schema.json"
    config_path = tmp_path / "config.yaml"

    schema_path.write_text(
        """
{
  "type": "object",
  "required": ["id"],
  "properties": {
    "id": {
      "type": "integer"
    }
  }
}
""",
        encoding="utf-8",
    )

    config_path.write_text(
        """
version: "1.0"

global:
  base_url: "https://api.example.com"

scenarios:
  - name: "External Schema Scenario"
    steps:
      - name: "Health Check"
        request:
          method: "GET"
          path: "/health"
        expect:
          status: 200
          schema: "user_schema.json"
""",
        encoding="utf-8",
    )

    config = load_and_compile_config(config_path)

    schema_func = config.scenarios[0].steps[0].expect.compiled_schema

    assert schema_func is not None
    assert schema_func({"id": 1}) == {"id": 1}


def test_missing_external_schema_raises_error(tmp_path: Path) -> None:
    """Verifies missing external schema raises ConfigCompilerError."""
    config_path = tmp_path / "config.yaml"

    config_path.write_text(
        """
version: "1.0"

global:
  base_url: "https://api.example.com"

scenarios:
  - name: "Missing Schema Scenario"
    steps:
      - name: "Health Check"
        request:
          method: "GET"
          path: "/health"
        expect:
          status: 200
          schema: "missing.json"
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigCompilerError) as exc_info:
        load_and_compile_config(config_path)

    assert "JSON Schema file not found" in str(exc_info.value)
