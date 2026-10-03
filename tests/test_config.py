"""Unit tests for declarative Pydantic configuration models."""

import pytest
from pydantic import ValidationError

from proof.core.config import (
    ExpectConfig,
    GlobalConfig,
    RequestConfig,
    ScenarioConfig,
    StepConfig,
)


def test_global_config_default_factories() -> None:
    """Verifies headers generate fresh dictionaries for each instance."""
    config1 = GlobalConfig()
    config2 = GlobalConfig()

    assert config1.headers == {}

    config1.headers["X-Test"] = "true"

    assert "X-Test" not in config2.headers


def test_global_config_timeout_must_be_positive() -> None:
    """Verifies global timeout must be greater than zero."""
    with pytest.raises(ValidationError):
        GlobalConfig(timeout_seconds=0)

    with pytest.raises(ValidationError):
        GlobalConfig(timeout_seconds=-1)


def test_global_config_base_url_can_be_omitted() -> None:
    """Verifies global base_url may be omitted."""
    config = GlobalConfig()

    assert config.base_url is None


def test_request_config_json_alias() -> None:
    """Verifies YAML keyword 'json' maps to json_payload."""
    raw_yaml_data = {
        "method": "POST",
        "path": "/users",
        "json": {"username": "batman"},
    }

    config = RequestConfig(**raw_yaml_data)

    assert config.json_payload == {"username": "batman"}


def test_request_config_timeout_must_be_positive() -> None:
    """Verifies step-specific timeout must be greater than zero."""
    with pytest.raises(ValidationError):
        RequestConfig(
            method="GET",
            path="/",
            timeout=0,
        )

    with pytest.raises(ValidationError):
        RequestConfig(
            method="GET",
            path="/",
            timeout=-1,
        )


def test_request_config_timeout_can_be_none() -> None:
    """Verifies omitted step timeout remains valid."""
    config = RequestConfig(
        method="GET",
        path="/",
        timeout=None,
    )

    assert config.timeout is None


def test_expect_config_schema_alias() -> None:
    """Verifies YAML keyword 'schema' maps to schema_data."""
    raw_yaml_data = {
        "status": 200,
        "schema": {
            "type": "object",
            "required": ["id"],
            "properties": {
                "id": {"type": "integer"},
            },
        },
    }

    config = ExpectConfig(**raw_yaml_data)

    assert config.schema_data == raw_yaml_data["schema"]
    assert config.compiled_schema is None


def test_expect_config_max_latency_must_be_positive() -> None:
    """Verifies max_latency_ms must be greater than zero."""
    with pytest.raises(ValidationError):
        ExpectConfig(
            status=200,
            max_latency_ms=0,
        )

    with pytest.raises(ValidationError):
        ExpectConfig(
            status=200,
            max_latency_ms=-1,
        )


def test_step_config_missing_required_fields() -> None:
    """Verifies missing required blocks raise validation errors."""
    raw_step = {
        "name": "Invalid Step",
        "request": {
            "method": "GET",
            "path": "/",
        },
    }

    with pytest.raises(ValidationError) as exc_info:
        StepConfig(**raw_step)

    assert "expect" in str(exc_info.value)
    assert "Field required" in str(exc_info.value)


def test_scenario_config_interval_must_be_positive() -> None:
    """Verifies scenario interval must be greater than zero."""
    valid_step = StepConfig(
        name="Health Check",
        request=RequestConfig(
            method="GET",
            path="/health",
        ),
        expect=ExpectConfig(
            status=200,
        ),
    )

    with pytest.raises(ValidationError):
        ScenarioConfig(
            name="Invalid Scenario",
            interval_seconds=0,
            steps=[valid_step],
        )

    with pytest.raises(ValidationError):
        ScenarioConfig(
            name="Invalid Scenario",
            interval_seconds=-1,
            steps=[valid_step],
        )


def test_scenario_config_default_interval() -> None:
    """Verifies default scenario interval is 60 seconds."""
    valid_step = StepConfig(
        name="Health Check",
        request=RequestConfig(
            method="GET",
            path="/health",
        ),
        expect=ExpectConfig(
            status=200,
        ),
    )

    config = ScenarioConfig(
        name="Health Check Scenario",
        steps=[valid_step],
    )

    assert config.interval_seconds == 60
