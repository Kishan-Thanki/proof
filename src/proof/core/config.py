from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RequestConfig(BaseModel):
    """Defines the outgoing HTTP request parameters."""

    method: str = Field(default="GET", pattern="^(GET|POST|PUT|PATCH|DELETE)$")
    path: str = Field(..., description="API path, supports ${var} interpolation")
    headers: dict[str, str] = Field(default_factory=dict)

    json_payload: dict[str, Any] | None = Field(default=None, alias="json")


class ExpectConfig(BaseModel):
    """Defines the assertions to run against the HTTP response."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    status: int = Field(default=200, ge=100, le=599)
    max_latency_ms: int | None = Field(default=None, gt=0)

    json_schema: dict[str, Any] | None = Field(default=None, alias="schema")

    compiled_schema: Any = Field(default=None, exclude=True)


class StepConfig(BaseModel):
    """A single transactional step within a scenario."""

    name: str
    request: RequestConfig
    expect: ExpectConfig

    extract: dict[str, str] = Field(default_factory=dict)


class ScenarioConfig(BaseModel):
    """A sequence of steps that run on a specific interval."""

    name: str
    interval_seconds: int = Field(..., gt=0)
    steps: list[StepConfig] = Field(..., min_length=1)


class GlobalConfig(BaseModel):
    """Global parameters applied across all scenarios."""

    base_url: str = Field(..., pattern="^https?://")
    timeout_seconds: int = Field(default=5, gt=0)
    headers: dict[str, str] = Field(
        default_factory=lambda: {"X-Synthetic-Request": "true"}
    )


class ProofConfig(BaseModel):
    """The root model representing the entire proof.yaml file."""

    version: str

    global_config: GlobalConfig = Field(..., alias="global")
    scenarios: list[ScenarioConfig] = Field(..., min_length=1)
