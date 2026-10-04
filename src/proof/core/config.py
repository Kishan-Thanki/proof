"""Declarative configuration models for Proof synthetic monitoring scenarios.

This module defines the Pydantic schemas used to parse, validate, and structure
YAML monitoring scenarios, including global settings, request parameters,
expectations, schema validations, and extraction rules.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class GlobalConfig(BaseModel):
    """Global default settings applied across all scenarios and steps."""

    base_url: HttpUrl | str | None = Field(
        default=None,
        description="Default root URL target for scenarios.",
    )
    timeout_seconds: float = Field(
        default=10.0,
        gt=0,
        description="Default HTTP request timeout ceiling in seconds.",
    )
    headers: dict[str, str] = Field(
        default_factory=dict,
        description="Default HTTP headers sent with all requests.",
    )


class RequestConfig(BaseModel):
    """Defines the parameters for an outgoing HTTP request."""

    method: str = Field(
        ...,
        description="HTTP method (e.g., GET, POST, PUT, DELETE).",
    )
    path: str = Field(
        ...,
        description="Endpoint path relative to base_url.",
    )
    headers: dict[str, str] = Field(
        default_factory=dict,
        description="Key-value pairs for HTTP request headers.",
    )
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="URL query parameters.",
    )
    json_payload: Any = Field(
        default=None,
        alias="json",
        description="JSON serializable body payload.",
    )
    timeout: float | None = Field(
        default=None,
        gt=0,
        description="Step-specific HTTP request timeout ceiling in seconds.",
    )


class ExpectConfig(BaseModel):
    """Defines assertion criteria evaluated against the HTTP response."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    status: int = Field(
        ...,
        description="Expected HTTP status code.",
    )
    headers: dict[str, str] = Field(
        default_factory=dict,
        description="Expected HTTP headers and their exact values.",
    )
    max_latency_ms: float | None = Field(
        default=None,
        gt=0,
        description="Maximum allowed response latency in milliseconds.",
    )
    schema_data: str | dict[str, Any] | None = Field(
        default=None,
        alias="schema",
        description="Path to a JSON schema file or inline schema dictionary.",
    )
    compiled_schema: Callable[[Any], Any] | None = Field(
        default=None,
        description="AOT-compiled fastjsonschema validation function.",
    )


class StepConfig(BaseModel):
    """Represents an atomic execution step in a multi-step API scenario."""

    name: str = Field(
        ...,
        description="Human-readable identifier for the scenario step.",
    )
    request: RequestConfig = Field(
        ...,
        description="HTTP request specifications.",
    )
    expect: ExpectConfig = Field(
        ...,
        description="Response assertion rules.",
    )
    extract: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of variable names to JSONPath expressions.",
    )


class ScenarioConfig(BaseModel):
    """Defines a sequence of dependent execution steps against a target host."""

    name: str = Field(
        ...,
        description="Human-readable scenario suite name.",
    )
    base_url: HttpUrl | str | None = Field(
        default=None,
        description="Root URL target for all steps in this scenario.",
    )
    interval_seconds: int = Field(
        default=60,
        gt=0,
        description="Execution interval in seconds for daemon mode.",
    )
    steps: list[StepConfig] = Field(
        ...,
        description="Ordered sequence of steps executed within shared context memory.",
    )


class ProofConfig(BaseModel):
    """Root configuration model representing a parsed Proof YAML file."""

    version: Literal["1.0"] = Field(
        ...,
        description="Configuration schema version. Currently only '1.0' is supported.",
    )
    global_config: GlobalConfig | None = Field(
        default=None,
        alias="global",
        description="Global configuration settings applied across scenarios.",
    )
    scenarios: list[ScenarioConfig] = Field(
        ...,
        description="List of scenario workflows defined in the configuration file.",
    )
