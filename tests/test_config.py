"""Unit tests for the declarative Pydantic configuration models."""

import pytest
from pydantic import ValidationError

from proof.core.config import GlobalConfig, RequestConfig, StepConfig


def test_global_config_default_factories() -> None:
    """Verifies that headers generate fresh dictionaries, avoiding memory leaks."""
    config1 = GlobalConfig()
    config2 = GlobalConfig()
    
    assert config1.headers == {}
    config1.headers["X-Test"] = "true"
    assert "X-Test" not in config2.headers


def test_request_config_json_alias() -> None:
    """Verifies that the YAML keyword 'json' properly maps to 'json_payload'."""
    raw_yaml_data = {
        "method": "POST",
        "path": "/users",
        "json": {"username": "batman"}
    }
    
    config = RequestConfig(**raw_yaml_data)
    
    assert config.json_payload == {"username": "batman"}


def test_step_config_missing_required_fields() -> None:
    """Verifies that omitting a required block (like 'expect') raises an error."""
    raw_step = {
        "name": "Invalid Step",
        "request": {
            "method": "GET",
            "path": "/"
        }
        # 'expect' block is missing!
    }
    
    with pytest.raises(ValidationError) as exc_info:
        StepConfig(**raw_step)
        
    assert "expect" in str(exc_info.value)
    assert "Field required" in str(exc_info.value)
