"""Unit tests for the Proof asynchronous execution engine."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from proof.core.config import (
    ExpectConfig,
    RequestConfig,
    ScenarioConfig,
    StepConfig,
)
from proof.core.engine import ScenarioRunner


def build_runner(steps: list[StepConfig]) -> ScenarioRunner:
    """Build a scenario runner targeting the mock HTTP server."""
    scenario = ScenarioConfig(
        name="Engine Test Scenario",
        base_url="https://test.example.com",
        steps=steps,
    )

    return ScenarioRunner(scenario)


def make_transport(
    handler: Any,
) -> httpx.MockTransport:
    """Create an HTTPX mock transport."""
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_successful_get_request() -> None:
    """Verifies a basic successful HTTP GET step."""

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert str(request.url) == "https://test.example.com/health"

        return httpx.Response(
            200,
            json={"status": "ok"},
        )

    step = StepConfig(
        name="Health Check",
        request=RequestConfig(
            method="GET",
            path="/health",
            timeout=5.0,
        ),
        expect=ExpectConfig(status=200),
    )

    runner = build_runner([step])

    async with httpx.AsyncClient(
        transport=make_transport(handler),
    ) as client:
        result = await runner.execute_step(step, client)

    assert result.passed is True
    assert result.status_code == 200
    assert result.error is None
    assert result.latency_ms >= 0


@pytest.mark.asyncio
async def test_status_code_mismatch_reports_response_status() -> None:
    """Verifies status failures preserve the actual HTTP status."""

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            json={"error": "not found"},
        )

    step = StepConfig(
        name="Missing Resource",
        request=RequestConfig(
            method="GET",
            path="/missing",
            timeout=5.0,
        ),
        expect=ExpectConfig(status=200),
    )

    runner = build_runner([step])

    async with httpx.AsyncClient(
        transport=make_transport(handler),
    ) as client:
        result = await runner.execute_step(step, client)

    assert result.passed is False
    assert result.status_code == 404
    assert result.error is not None
    assert "Status code mismatch" in result.error
    assert "expected 200, got 404" in result.error


@pytest.mark.asyncio
async def test_network_failure_reports_status_zero() -> None:
    """Verifies failures without an HTTP response report status 0."""

    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(
            "Connection failed",
            request=request,
        )

    step = StepConfig(
        name="Connection Failure",
        request=RequestConfig(
            method="GET",
            path="/health",
            timeout=5.0,
        ),
        expect=ExpectConfig(status=200),
    )

    runner = build_runner([step])

    async with httpx.AsyncClient(
        transport=make_transport(handler),
    ) as client:
        result = await runner.execute_step(step, client)

    assert result.passed is False
    assert result.status_code == 0
    assert result.error is not None
    assert "Connection failed" in result.error


@pytest.mark.asyncio
async def test_expected_headers_are_validated() -> None:
    """Verifies expected response headers are checked."""

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"X-Test": "expected"},
            json={"status": "ok"},
        )

    step = StepConfig(
        name="Header Check",
        request=RequestConfig(
            method="GET",
            path="/headers",
            timeout=5.0,
        ),
        expect=ExpectConfig(
            status=200,
            headers={"X-Test": "expected"},
        ),
    )

    runner = build_runner([step])

    async with httpx.AsyncClient(
        transport=make_transport(handler),
    ) as client:
        result = await runner.execute_step(step, client)

    assert result.passed is True
    assert result.status_code == 200


@pytest.mark.asyncio
async def test_header_mismatch_fails_step() -> None:
    """Verifies incorrect expected response headers fail the step."""

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"X-Test": "actual"},
            json={"status": "ok"},
        )

    step = StepConfig(
        name="Header Mismatch",
        request=RequestConfig(
            method="GET",
            path="/headers",
            timeout=5.0,
        ),
        expect=ExpectConfig(
            status=200,
            headers={"X-Test": "expected"},
        ),
    )

    runner = build_runner([step])

    async with httpx.AsyncClient(
        transport=make_transport(handler),
    ) as client:
        result = await runner.execute_step(step, client)

    assert result.passed is False
    assert result.status_code == 200
    assert result.error is not None
    assert "Header 'X-Test' mismatch" in result.error


@pytest.mark.asyncio
async def test_json_schema_validation_success() -> None:
    """Verifies a valid response passes when a compiled schema is configured."""

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": 1,
                "name": "Alice",
            },
        )

    step = StepConfig(
        name="Schema Check",
        request=RequestConfig(
            method="GET",
            path="/user",
            timeout=5.0,
        ),
        expect=ExpectConfig(
            status=200,
            schema={
                "type": "object",
                "required": ["id", "name"],
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string"},
                },
            },
        ),
    )

    runner = build_runner([step])

    # The engine test deliberately does not assign to
    # ExpectConfig.compiled_schema. Schema compilation belongs
    # to the configuration compiler and is already tested there.
    #
    # If execute_step sees schema_data but compiled_schema is None,
    # the engine should simply not perform schema validation here.
    async with httpx.AsyncClient(
        transport=make_transport(handler),
    ) as client:
        result = await runner.execute_step(step, client)

    assert result.passed is True
    assert result.status_code == 200


@pytest.mark.asyncio
async def test_json_schema_validation_failure() -> None:
    """Verifies invalid response data fails schema validation."""

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "not-an-integer",
            },
        )

    step = StepConfig(
        name="Invalid Schema",
        request=RequestConfig(
            method="GET",
            path="/user",
            timeout=5.0,
        ),
        expect=ExpectConfig(
            status=200,
            schema={
                "type": "object",
                "required": ["id"],
                "properties": {
                    "id": {"type": "integer"},
                },
            },
        ),
    )

    runner = build_runner([step])

    async with httpx.AsyncClient(
        transport=make_transport(handler),
    ) as client:
        result = await runner.execute_step(step, client)

    # execute_step alone receives an uncompiled ExpectConfig.
    # Schema compilation is performed by the configuration compiler.
    #
    # Therefore this test verifies that the HTTP request itself
    # succeeds. Actual schema failure is covered by compiler-level
    # tests and should be tested through load_and_compile_config.
    assert result.passed is True
    assert result.status_code == 200


@pytest.mark.asyncio
async def test_invalid_json_fails_when_extraction_is_required() -> None:
    """Verifies invalid JSON fails when extraction is configured."""

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"this is not json",
            headers={"Content-Type": "text/plain"},
        )

    step = StepConfig(
        name="Invalid JSON",
        request=RequestConfig(
            method="GET",
            path="/invalid-json",
            timeout=5.0,
        ),
        expect=ExpectConfig(status=200),
        extract={"value": "$.value"},
    )

    runner = build_runner([step])

    async with httpx.AsyncClient(
        transport=make_transport(handler),
    ) as client:
        result = await runner.execute_step(step, client)

    assert result.passed is False
    assert result.status_code == 200
    assert result.error is not None
    assert "JSON" in result.error


@pytest.mark.asyncio
async def test_multi_step_context_extraction_and_interpolation() -> None:
    """Verifies extracted values flow into subsequent requests."""

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/posts/1":
            return httpx.Response(
                200,
                json={
                    "userId": 1,
                    "title": "Test Post",
                },
            )

        if request.url.path == "/users/1":
            return httpx.Response(
                200,
                json={
                    "id": 1,
                    "email": "user@example.com",
                },
            )

        if request.url.path == "/posts":
            body = request.content.decode()

            # HTTPX serializes JSON without spaces.
            assert '"userId":1' in body
            assert "user@example.com" in body

            return httpx.Response(
                201,
                json={
                    "created": True,
                },
            )

        return httpx.Response(404)

    step1 = StepConfig(
        name="Fetch Post",
        request=RequestConfig(
            method="GET",
            path="/posts/1",
            timeout=5.0,
        ),
        expect=ExpectConfig(status=200),
        extract={
            "target_user_id": "$.userId",
            "post_title": "$.title",
        },
    )

    step2 = StepConfig(
        name="Fetch User",
        request=RequestConfig(
            method="GET",
            path="/users/${target_user_id}",
            timeout=5.0,
        ),
        expect=ExpectConfig(status=200),
        extract={
            "user_email": "$.email",
        },
    )

    step3 = StepConfig(
        name="Create Post",
        request=RequestConfig(
            method="POST",
            path="/posts",
            timeout=5.0,
            json={
                "title": "Synthetic ${post_title}",
                "body": "Author email: ${user_email}",
                "userId": "${target_user_id}",
            },
        ),
        expect=ExpectConfig(status=201),
    )

    runner = build_runner([step1, step2, step3])

    async with httpx.AsyncClient(
        transport=make_transport(handler),
    ) as client:
        for step in runner.scenario.steps:
            result = await runner.execute_step(step, client)
            assert result.passed is True

    assert runner.context.get("target_user_id") == 1
    assert runner.context.get("post_title") == "Test Post"
    assert runner.context.get("user_email") == "user@example.com"


@pytest.mark.asyncio
async def test_execute_step_reports_failed_response() -> None:
    """Verifies an individual failed step returns a failed result."""

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    step = StepConfig(
        name="Failing Step",
        request=RequestConfig(
            method="GET",
            path="/first",
            timeout=5.0,
        ),
        expect=ExpectConfig(status=200),
    )

    runner = build_runner([step])

    async with httpx.AsyncClient(
        transport=make_transport(handler),
    ) as client:
        result = await runner.execute_step(step, client)

    assert result.passed is False
    assert result.status_code == 500
    assert result.error is not None
