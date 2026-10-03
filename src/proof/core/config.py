"""Declarative configuration models for Proof synthetic monitoring scenarios.

This module defines the Pydantic schemas used to parse, validate, and structure
YAML monitoring scenarios, including global settings, request parameters, expectations,
schema validations, and extraction rules.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class GlobalConfig(BaseModel):
    """Global default settings applied across all scenarios and steps.

    Example YAML snippet:
        ```yaml
        global:
          base_url: "[https://api.example.com](https://api.example.com)"
          timeout_seconds: 10.0
          headers:
            User-Agent: "Proof-Synthetic-Daemon/0.1.0"
            Accept: "application/json"
        ```

    Example Python Object representation:
        ```python
        GlobalConfig(
            base_url="[https://api.example.com](https://api.example.com)",
            timeout_seconds=10.0,
            headers={
                "User-Agent": "Proof-Synthetic-Daemon/0.1.0",
                "Accept": "application/json",
            },
        )
        ```
    """

    base_url: HttpUrl | str | None = Field(
        default=None, description="Default root URL target for scenarios."
    )
    timeout_seconds: float = Field(
        default=10.0,
        gt=0,
        description="Default HTTP request timeout ceiling in seconds.",
    )
    headers: dict[str, str] = Field(
        default_factory=dict, description="Default HTTP headers sent with all requests."
    )


class RequestConfig(BaseModel):
    """Defines the parameters for an outgoing HTTP request within a scenario step.

    Example YAML snippet:
        ```yaml
        request:
          method: "POST"
          path: "/v1/users"
          headers:
            Content-Type: "application/json"
          params:
            role: "admin"
          json:
            username: "synth-bot"
          timeout: 5.0
        ```

    Example Python Object representation:
        ```python
        RequestConfig(
            method="POST",
            path="/v1/users",
            headers={"Content-Type": "application/json"},
            params={"role": "admin"},
            json_payload={"username": "synth-bot"},
            timeout=5.0,
        )
        ```
    """

    method: str = Field(..., description="HTTP method (e.g., GET, POST, PUT, DELETE).")
    path: str = Field(..., description="Endpoint path relative to base_url.")
    headers: dict[str, str] = Field(
        default_factory=dict, description="Key-value pairs for HTTP request headers."
    )
    params: dict[str, Any] = Field(
        default_factory=dict, description="URL query parameters."
    )
    json_payload: Any = Field(
        default=None,
        alias="json",
        description="JSON serializable body payload for POST/PUT/PATCH requests.",
    )
    timeout: float | None = Field(
        default=None,
        gt=0,
        description="Step-specific HTTP request timeout ceiling in seconds.",
    )


class ExpectConfig(BaseModel):
    """Defines assertion criteria evaluated against the HTTP response.

    Example YAML snippet:
        ```yaml
        expect:
          status: 201
          headers:
            Content-Type: "application/json; charset=utf-8"
          max_latency_ms: 1500.0
          schema:
            type: "object"
            required: ["id", "status"]
            properties:
              id: { type: "string" }
              status: { type: "string" }
        ```

    Example Python Object representation:
        ```python
        ExpectConfig(
            status=201,
            headers={"Content-Type": "application/json; charset=utf-8"},
            max_latency_ms=1500.0,
            schema_data={
                "type": "object",
                "required": ["id", "status"],
                "properties": {
                    "id": {"type": "string"},
                    "status": {"type": "string"},
                },
            },
            compiled_schema=None,
        )
        ```
    """

    status: int = Field(..., description="Expected HTTP status code (e.g., 200, 201).")
    headers: dict[str, str] = Field(
        default_factory=dict,
        description="Expected HTTP headers and their exact values.",
    )
    max_latency_ms: float | None = Field(
        default=None, description="Maximum allowed response latency in milliseconds."
    )
    schema_data: str | dict[str, Any] | None = Field(
        default=None,
        alias="schema",
        description="Path to a JSON schema file OR inline schema dictionary.",
    )
    compiled_schema: Callable[[Any], Any] | None = Field(
        default=None,
        description="AOT-compiled fastjsonschema validation function attached at load time.",
    )


class StepConfig(BaseModel):
    """Represents an atomic execution step in a multi-step API scenario.

    Example YAML snippet:
        ```yaml
        name: "Create Ephemeral User"
        request:
          method: "POST"
          path: "/users"
          json:
            name: "Test User"
        expect:
          status: 201
          max_latency_ms: 2000
        extract:
          user_id: "$.id"
        ```

    Example Python Object representation:
        ```python
        StepConfig(
            name="Create Ephemeral User",
            request=RequestConfig(
                method="POST",
                path="/users",
                json_payload={"name": "Test User"},
            ),
            expect=ExpectConfig(
                status=201,
                max_latency_ms=2000.0,
            ),
            extract={"user_id": "$.id"},
        )
        ```
    """

    name: str = Field(
        ..., description="Human-readable identifier for the scenario step."
    )
    request: RequestConfig = Field(..., description="HTTP request specifications.")
    expect: ExpectConfig = Field(..., description="Response assertion rules.")
    extract: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of variable names to JSONPath expressions extracted from response body.",
    )


class ScenarioConfig(BaseModel):
    """Defines a sequence of dependent execution steps against a target host.

    Example YAML snippet:
        ```yaml
        name: "User Authentication & Registration Lifecycle"
        base_url: "[https://api.example.com](https://api.example.com)"
        interval_seconds: 120
        steps:
          - name: "1. Fetch Public Config"
            request:
              method: "GET"
              path: "/config"
            expect:
              status: 200
        ```

    Example Python Object representation:
        ```python
        ScenarioConfig(
            name="User Authentication & Registration Lifecycle",
            base_url="[https://api.example.com](https://api.example.com)",
            interval_seconds=120,
            steps=[
                StepConfig(
                    name="1. Fetch Public Config",
                    request=RequestConfig(method="GET", path="/config"),
                    expect=ExpectConfig(status=200),
                )
            ],
        )
        ```
    """

    name: str = Field(..., description="Human-readable scenario suite name.")
    base_url: HttpUrl | str | None = Field(
        default=None, description="Root URL target for all steps in this scenario."
    )
    interval_seconds: int = Field(
        default=60, gt=0, description="Execution interval in seconds for the scenario."
    )
    steps: list[StepConfig] = Field(
        ...,
        description="Ordered sequence of steps executed within shared context memory.",
    )


class ProofConfig(BaseModel):
    """Root configuration model representing a parsed Proof YAML scenario file.

    Example YAML snippet:
        ```yaml
        version: "1.0"
        global:
          base_url: "[https://jsonplaceholder.typicode.com](https://jsonplaceholder.typicode.com)"
          timeout_seconds: 10.0
        scenarios:
          - name: "Health Verification"
            steps:
              - name: "Ping Endpoint"
                request:
                  method: "GET"
                  path: "/posts/1"
                expect:
                  status: 200
        ```

    Example Python Object representation:
        ```python
        ProofConfig(
            version="1.0",
            global_config=GlobalConfig(
                base_url="[https://jsonplaceholder.typicode.com](https://jsonplaceholder.typicode.com)",
                timeout_seconds=10.0,
            ),
            scenarios=[
                ScenarioConfig(
                    name="Health Verification",
                    steps=[
                        StepConfig(
                            name="Ping Endpoint",
                            request=RequestConfig(method="GET", path="/posts/1"),
                            expect=ExpectConfig(status=200),
                        )
                    ],
                )
            ],
        )
        ```
    """

    version: str = Field(default="1.0", description="Configuration schema version.")
    global_config: GlobalConfig | None = Field(
        default=None,
        alias="global",
        description="Global configuration settings applied across scenarios.",
    )
    scenarios: list[ScenarioConfig] = Field(
        ..., description="List of scenario workflows defined in the configuration file."
    )
