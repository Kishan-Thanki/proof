"""Asynchronous HTTP execution engine for Proof synthetic monitoring.

This module handles the async execution of HTTP monitoring scenarios using httpx,
evaluates response assertions (status codes, headers, latency caps, AOT schemas),
extracts runtime variables into ExecutionContext, and records high-resolution latency metrics.
"""

import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from proof.core.config import ScenarioConfig, StepConfig
from proof.core.context import ExecutionContext


class EngineError(Exception):
    """Raised when HTTP step execution or assertion evaluation fails."""


@dataclass
class StepResult:
    """Execution outcome and performance metrics for an individual scenario step."""

    step_name: str
    passed: bool
    status_code: int
    latency_ms: float
    error: str | None = None


@dataclass
class ScenarioResult:
    """Aggregated execution outcome for a complete multi-step scenario suite."""

    scenario_name: str
    passed: bool
    total_latency_ms: float
    step_results: list[StepResult] = field(default_factory=list)


class ScenarioRunner:
    """Executes multi-step HTTP monitoring scenarios asynchronously using httpx."""

    def __init__(
        self, scenario: ScenarioConfig, context: ExecutionContext | None = None
    ) -> None:
        """Initializes scenario runner with target scenario and shared execution context.

        Args:
            scenario: Compiled scenario configuration containing ordered steps.
            context: Shared execution context for state persistence across steps.
        """
        self.scenario = scenario
        self.context = context if context is not None else ExecutionContext()

    async def execute_step(
        self, step: StepConfig, client: httpx.AsyncClient
    ) -> StepResult:
        """Executes a single scenario step asynchronously.

        Interpolates request data with context variables, dispatches the HTTP request,
        evaluates response status code, headers, latency ceiling, and AOT schema assertions,
        and extracts context variables for subsequent steps.

        Args:
            step: Individual step configuration containing request and assertion rules.
            client: Shared async httpx client instance.

        Returns:
            StepResult: Detailed metrics and pass/fail outcome for the step.
        """
        if not self.scenario.base_url:
            raise EngineError(
                f"Scenario '{self.scenario.name}' is missing a valid base_url."
            )

        interpolated_path = self.context.interpolate_string(step.request.path)
        base_url = str(self.scenario.base_url).rstrip("/")
        full_url = f"{base_url}/{interpolated_path.lstrip('/')}"

        headers = self.context.interpolate_data(step.request.headers)
        params = self.context.interpolate_data(step.request.params)
        json_payload = self.context.interpolate_data(step.request.json_payload)

        if step.request.timeout is None:
            raise EngineError(
                f"Step '{step.name}' is missing a resolved request timeout."
            )

        start_time = time.perf_counter()

        try:
            response = await client.request(
                method=step.request.method,
                url=full_url,
                headers=headers,
                params=params,
                json=json_payload,
                timeout=step.request.timeout,
            )
            latency_ms = (time.perf_counter() - start_time) * 1000

            if response.status_code != step.expect.status:
                raise EngineError(
                    f"Status code mismatch: Expected {step.expect.status}, "
                    f"got {response.status_code}"
                )

            if (
                step.expect.max_latency_ms is not None
                and latency_ms > step.expect.max_latency_ms
            ):
                raise EngineError(
                    f"Latency limit exceeded: Response took {latency_ms:.2f} ms "
                    f"(max allowed: {step.expect.max_latency_ms} ms)"
                )

            if step.expect.headers:
                for expected_header, expected_val in step.expect.headers.items():
                    actual_val = response.headers.get(expected_header)
                    if actual_val != expected_val:
                        raise EngineError(
                            f"Header '{expected_header}' mismatch: "
                            f"Expected '{expected_val}', got '{actual_val}'"
                        )

            response_data: Any = None
            if step.expect.compiled_schema or step.extract:
                try:
                    response_data = response.json()
                except Exception as err:
                    raise EngineError(
                        f"Response body is not valid JSON: {err}"
                    ) from err

            if step.expect.compiled_schema and response_data is not None:
                try:
                    step.expect.compiled_schema(response_data)
                except Exception as err:
                    raise EngineError(f"Schema assertion failed: {err}") from err

            if step.extract and response_data is not None:
                self.context.extract_variables(response_data, step.extract)

            return StepResult(
                step_name=step.name,
                passed=True,
                status_code=response.status_code,
                latency_ms=round(latency_ms, 2),
            )

        except Exception as err:  # noqa: BLE001
            latency_ms = (time.perf_counter() - start_time) * 1000

            status_code = 0
            if isinstance(err, httpx.HTTPStatusError) or hasattr(err, "response"):
                resp = getattr(err, "response", None)
                if resp is not None:
                    status_code = resp.status_code

            return StepResult(
                step_name=step.name,
                passed=False,
                status_code=status_code,
                latency_ms=round(latency_ms, 2),
                error=str(err),
            )

    async def run(self) -> ScenarioResult:
        """Executes all steps sequentially within the scenario context.

        Returns:
            ScenarioResult: Aggregated result containing total latency and step results.
        """
        step_results: list[StepResult] = []
        scenario_passed = True
        total_start = time.perf_counter()

        async with httpx.AsyncClient() as client:
            for step in self.scenario.steps:
                result = await self.execute_step(step, client)
                step_results.append(result)

                if not result.passed:
                    scenario_passed = False
                    break

        total_latency_ms = (time.perf_counter() - total_start) * 1000

        return ScenarioResult(
            scenario_name=self.scenario.name,
            passed=scenario_passed,
            total_latency_ms=round(total_latency_ms, 2),
            step_results=step_results,
        )
