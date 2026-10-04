"""Exhaustive unit tests for declarative Pydantic configuration models."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from proof.core.config import (
    ExpectConfig,
    GlobalConfig,
    ProofConfig,
    RequestConfig,
    ScenarioConfig,
    StepConfig,
)

# ============================================================================
# GlobalConfig Tests
# ============================================================================


def test_global_config_defaults() -> None:
    """Verifies default values for GlobalConfig."""
    config = GlobalConfig()

    assert config.base_url is None
    assert config.timeout_seconds == 10.0
    assert config.headers == {}


def test_global_config_custom_valid() -> None:
    """Verifies instantiation with valid custom arguments."""
    config = GlobalConfig(
        base_url="https://api.example.com",
        timeout_seconds=5.5,
        headers={"Authorization": "Bearer token123"},
    )

    assert str(config.base_url) == "https://api.example.com"
    assert config.timeout_seconds == 5.5
    assert config.headers == {"Authorization": "Bearer token123"}


def test_global_config_headers_default_factory_isolation() -> None:
    """Verifies default header dicts are isolated across model instances."""
    config1 = GlobalConfig()
    config2 = GlobalConfig()

    config1.headers["X-Test"] = "true"

    assert "X-Test" not in config2.headers


@pytest.mark.parametrize("invalid_timeout", [0, -1, -0.001])
def test_global_config_timeout_gt_zero(invalid_timeout: float) -> None:
    """Verifies global timeout must be strictly greater than zero."""
    with pytest.raises(ValidationError) as exc_info:
        GlobalConfig(timeout_seconds=invalid_timeout)

    assert "timeout_seconds" in str(exc_info.value)


# ============================================================================
# RequestConfig Tests
# ============================================================================


def test_request_config_required_fields() -> None:
    """Verifies missing required fields
    ('method' and 'path') trigger validation errors."""
    with pytest.raises(ValidationError) as exc_info:
        RequestConfig.model_validate({})

    errors = str(exc_info.value)
    assert "method" in errors
    assert "path" in errors


def test_request_config_defaults() -> None:
    """Verifies default optional fields for RequestConfig."""
    config = RequestConfig(method="GET", path="/health")

    assert config.headers == {}
    assert config.params == {}
    assert config.json_payload is None
    assert config.timeout is None


def test_request_config_json_alias() -> None:
    """Verifies YAML key 'json' correctly maps to 'json_payload'."""
    raw_data = {
        "method": "POST",
        "path": "/users",
        "json": {"name": "Alice", "role": "admin"},
    }

    config = RequestConfig(**raw_data)

    assert config.json_payload == {"name": "Alice", "role": "admin"}


def test_request_config_dict_isolation() -> None:
    """Verifies default factories for headers and params are isolated."""
    req1 = RequestConfig(method="GET", path="/a")
    req2 = RequestConfig(method="GET", path="/b")

    req1.headers["X-Step"] = "1"
    req1.params["debug"] = True

    assert "X-Step" not in req2.headers
    assert "debug" not in req2.params


@pytest.mark.parametrize("invalid_timeout", [0, -1.0, -0.0001])
def test_request_config_timeout_gt_zero(invalid_timeout: float) -> None:
    """Verifies step request timeout must be greater than zero when provided."""
    with pytest.raises(ValidationError) as exc_info:
        RequestConfig(
            method="GET",
            path="/",
            timeout=invalid_timeout,
        )

    assert "timeout" in str(exc_info.value)


# ============================================================================
# ExpectConfig Tests
# ============================================================================


def test_expect_config_required_fields() -> None:
    """Verifies 'status' is required."""
    with pytest.raises(ValidationError) as exc_info:
        ExpectConfig.model_validate({})

    assert "status" in str(exc_info.value)


def test_expect_config_defaults() -> None:
    """Verifies default optional fields for ExpectConfig."""
    config = ExpectConfig(status=200)

    assert config.status == 200
    assert config.headers == {}
    assert config.max_latency_ms is None
    assert config.schema_data is None
    assert config.compiled_schema is None


def test_expect_config_schema_alias_and_types() -> None:
    """Verifies 'schema' alias supports inline dicts and file paths."""
    dict_schema = ExpectConfig(
        status=200,
        schema={"type": "object", "properties": {"id": {"type": "integer"}}},
    )
    assert isinstance(dict_schema.schema_data, dict)

    path_schema = ExpectConfig(status=200, schema="schemas/user.json")
    assert path_schema.schema_data == "schemas/user.json"


def test_expect_config_arbitrary_types_compiled_schema() -> None:
    """Verifies callable functions can be assigned to compiled_schema
    (ConfigDict arbitrary_types_allowed)."""
    dummy_validator = lambda x: True  # noqa: E731

    config = ExpectConfig(status=200, compiled_schema=dummy_validator)

    assert callable(config.compiled_schema)
    assert config.compiled_schema({"any": "data"}) is True


@pytest.mark.parametrize("invalid_latency", [0, -1, -500.0])
def test_expect_config_max_latency_gt_zero(invalid_latency: float) -> None:
    """Verifies max_latency_ms must be strictly positive."""
    with pytest.raises(ValidationError) as exc_info:
        ExpectConfig(status=200, max_latency_ms=invalid_latency)

    assert "max_latency_ms" in str(exc_info.value)


# ============================================================================
# StepConfig Tests
# ============================================================================


def test_step_config_required_fields() -> None:
    """Verifies 'name', 'request', and 'expect' are mandatory."""
    with pytest.raises(ValidationError) as exc_info:
        StepConfig.model_validate({})

    errors = str(exc_info.value)
    assert "name" in errors
    assert "request" in errors
    assert "expect" in errors


def test_step_config_valid_and_extract_isolation() -> None:
    """Verifies StepConfig initialization and variable extraction dict isolation."""
    step1 = StepConfig(
        name="Step 1",
        request=RequestConfig(method="GET", path="/items"),
        expect=ExpectConfig(status=200),
    )
    step2 = StepConfig(
        name="Step 2",
        request=RequestConfig(method="POST", path="/items"),
        expect=ExpectConfig(status=201),
    )

    step1.extract["item_id"] = "$.id"

    assert step1.extract == {"item_id": "$.id"}
    assert step2.extract == {}


def test_step_config_nested_validation_error() -> None:
    """Verifies nested validation failures inside request
    or expect bubble up correctly."""
    invalid_raw_step = {
        "name": "Invalid Request Method Step",
        "request": {
            # Missing mandatory 'method' and 'path'
        },
        "expect": {"status": 200},
    }

    with pytest.raises(ValidationError) as exc_info:
        StepConfig(**invalid_raw_step)

    assert "request" in str(exc_info.value)


# ============================================================================
# ScenarioConfig Tests
# ============================================================================


def test_scenario_config_required_fields() -> None:
    """Verifies 'name' and 'steps' are mandatory."""
    with pytest.raises(ValidationError) as exc_info:
        ScenarioConfig.model_validate({})

    errors = str(exc_info.value)
    assert "name" in errors
    assert "steps" in errors


def test_scenario_config_defaults() -> None:
    """Verifies default values for scenario settings."""
    step = StepConfig(
        name="Ping",
        request=RequestConfig(method="GET", path="/ping"),
        expect=ExpectConfig(status=200),
    )

    scenario = ScenarioConfig(name="Ping Scenario", steps=[step])

    assert scenario.base_url is None
    assert scenario.interval_seconds == 60
    assert len(scenario.steps) == 1


@pytest.mark.parametrize("invalid_interval", [0, -1, -60])
def test_scenario_config_interval_gt_zero(invalid_interval: int) -> None:
    """Verifies scenario daemon interval must be strictly positive."""
    step = StepConfig(
        name="Ping",
        request=RequestConfig(method="GET", path="/ping"),
        expect=ExpectConfig(status=200),
    )

    with pytest.raises(ValidationError) as exc_info:
        ScenarioConfig(
            name="Bad Interval",
            interval_seconds=invalid_interval,
            steps=[step],
        )

    assert "interval_seconds" in str(exc_info.value)


# ============================================================================
# ProofConfig Tests
# ============================================================================


def test_proof_config_required_fields() -> None:
    """Verifies 'version' and 'scenarios' are mandatory at the root config level."""
    with pytest.raises(ValidationError) as exc_info:
        ProofConfig.model_validate({})

    errors = str(exc_info.value)
    assert "version" in errors
    assert "scenarios" in errors


@pytest.mark.parametrize("invalid_version", ["2.0", "1.1", "1", "v1.0", 1.0])
def test_proof_config_version_literal_strictly_enforced(
    invalid_version: Any,
) -> None:
    """Verifies schema version strictly rejects anything
    other than literal string '1.0'."""
    raw_config = {
        "version": invalid_version,
        "scenarios": [
            {
                "name": "Dummy",
                "steps": [
                    {
                        "name": "S",
                        "request": {"method": "GET", "path": "/"},
                        "expect": {"status": 200},
                    }
                ],
            }
        ],
    }

    with pytest.raises(ValidationError) as exc_info:
        ProofConfig(**raw_config)

    assert "version" in str(exc_info.value)


def test_proof_config_global_alias_unpacking() -> None:
    """Verifies root YAML alias 'global' correctly populates 'global_config'."""
    raw_config = {
        "version": "1.0",
        "global": {
            "base_url": "https://jsonplaceholder.typicode.com",
            "timeout_seconds": 15.0,
            "headers": {"X-App": "Proof"},
        },
        "scenarios": [
            {
                "name": "Suite",
                "steps": [
                    {
                        "name": "Step 1",
                        "request": {"method": "GET", "path": "/"},
                        "expect": {"status": 200},
                    }
                ],
            }
        ],
    }

    config = ProofConfig(**raw_config)

    assert config.global_config is not None
    assert str(config.global_config.base_url) == "https://jsonplaceholder.typicode.com"
    assert config.global_config.timeout_seconds == 15.0
    assert config.global_config.headers == {"X-App": "Proof"}


def test_proof_config_full_exhaustive_yaml_parsing() -> None:
    """Verifies complete end-to-end parsing of a
    complex multi-scenario YAML structure."""
    raw_yaml_dict = {
        "version": "1.0",
        "global": {
            "base_url": "https://api.service.io",
            "timeout_seconds": 8.0,
            "headers": {"User-Agent": "Proof-Daemon/1.0"},
        },
        "scenarios": [
            {
                "name": "E2E User Flow",
                "base_url": "https://override.service.io",
                "interval_seconds": 30,
                "steps": [
                    {
                        "name": "Create User",
                        "request": {
                            "method": "POST",
                            "path": "/users",
                            "headers": {"Content-Type": "application/json"},
                            "params": {"notify": True},
                            "json": {"username": "john_doe"},
                            "timeout": 3.0,
                        },
                        "expect": {
                            "status": 201,
                            "max_latency_ms": 1500,
                            "headers": {"Content-Type": "application/json"},
                            "schema": {"type": "object", "required": ["id"]},
                        },
                        "extract": {"user_id": "$.id"},
                    }
                ],
            }
        ],
    }

    config = ProofConfig(**raw_yaml_dict)

    # Root
    assert config.version == "1.0"
    assert config.global_config is not None
    assert config.global_config.timeout_seconds == 8.0

    # Scenario
    scenario = config.scenarios[0]
    assert scenario.name == "E2E User Flow"
    assert str(scenario.base_url) == "https://override.service.io"
    assert scenario.interval_seconds == 30

    # Step & Request & Expect
    step = scenario.steps[0]
    assert step.name == "Create User"
    assert step.request.method == "POST"
    assert step.request.params == {"notify": True}
    assert step.request.json_payload == {"username": "john_doe"}
    assert step.request.timeout == 3.0
    assert step.expect.status == 201
    assert step.expect.max_latency_ms == 1500
    assert step.extract == {"user_id": "$.id"}
