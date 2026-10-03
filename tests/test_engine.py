"""Integration test suite executing a live multi-step scenario using the engine."""

from __future__ import annotations

import pytest

from proof.core.config import ExpectConfig, RequestConfig, ScenarioConfig, StepConfig
from proof.core.engine import ScenarioRunner


@pytest.mark.asyncio
async def test_live_scenario_execution() -> None:
    """Constructs and executes a live 3-step scenario against JSONPlaceholder."""
    step1 = StepConfig(
        name="1. Fetch Post & Extract User ID",
        request=RequestConfig(
            method="GET",
            path="/posts/1",
            timeout=10.0,
        ),
        expect=ExpectConfig(status=200, max_latency_ms=2000),
        extract={"target_user_id": "$.userId", "post_title": "$.title"},
    )

    step2 = StepConfig(
        name="2. Fetch User Profile using Extracted ID",
        request=RequestConfig(
            method="GET",
            path="/users/${target_user_id}",
            timeout=10.0,
        ),
        expect=ExpectConfig(status=200, max_latency_ms=2000),
        extract={"user_email": "$.email"},
    )

    step3 = StepConfig(
        name="3. Create Dependent Post with Dynamic UUID",
        request=RequestConfig(
            method="POST",
            path="/posts",
            timeout=10.0,
            json={
                "title": "Proof Synthetic Test ${$uuid}",
                "body": "Author email: ${user_email}",
                "userId": "${target_user_id}",
            },
        ),
        expect=ExpectConfig(status=201, max_latency_ms=2000),
    )

    scenario = ScenarioConfig(
        name="Live Multi-Step Identity Workflow",
        base_url="https://jsonplaceholder.typicode.com",
        steps=[step1, step2, step3],
    )

    runner = ScenarioRunner(scenario)
    result = await runner.run()

    assert result.passed is True
    assert len(result.step_results) == 3

    assert result.step_results[0].passed is True
    assert result.step_results[1].passed is True
    assert result.step_results[2].passed is True

    assert runner.context.get("target_user_id") == 1
    assert (
        runner.context.get("post_title")
        == "sunt aut facere repellat provident occaecati excepturi optio reprehenderit"
    )
    assert runner.context.get("user_email") == "Sincere@april.biz"
