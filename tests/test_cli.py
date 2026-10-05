"""Unit tests for Proofrun CLI interface."""

from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from typer.testing import CliRunner

from proofrun.cli import app, execute_config, render_scenario_result
from proofrun.core.config import ProofrunConfig
from proofrun.core.engine import ScenarioResult, StepResult
from proofrun.core.state import StateManager, Status

runner = CliRunner()


class _LocalAPIHandler(BaseHTTPRequestHandler):
    """Tiny deterministic API so CLI tests never touch the internet."""

    def do_GET(self) -> None:  # noqa: N802
        body = json.dumps({"id": 1, "title": "hello"}).encode()

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        """Silence request logging."""


@pytest.fixture
def local_api() -> Iterator[str]:
    """Serve a local HTTP API on a free port and yield its base URL."""
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        _LocalAPIHandler,
    )
    thread = threading.Thread(
        target=server.serve_forever,
        daemon=True,
    )
    thread.start()

    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_cli_version_flag() -> None:
    """Verifies that --version prints the version string and exits cleanly."""
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert "Proofrun version" in result.stdout


def test_cli_run_successful_scenario(
    tmp_path: Path,
    local_api: str,
) -> None:
    """Verifies successful scenario execution via CLI argument."""
    yaml_content = f"""
version: "1.0"

global:
  base_url: "{local_api}"

scenarios:
  - name: "CLI Integration Scenario"
    steps:
      - name: "Dummy Step"
        request:
          method: "GET"
          path: "/posts/1"
        expect:
          status: 200
"""

    config_file = tmp_path / "test_scenario.yaml"
    config_file.write_text(
        yaml_content,
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [str(config_file)],
    )

    assert result.exit_code == 0
    assert "CLI Integration Scenario" in result.stdout
    assert "PASSED" in result.stdout


def test_cli_run_failing_scenario(
    tmp_path: Path,
    local_api: str,
) -> None:
    """Verifies single-run mode returns exit code 1 when assertions fail."""
    yaml_content = f"""
version: "1.0"

global:
  base_url: "{local_api}"

scenarios:
  - name: "Failing Scenario"
    steps:
      - name: "Expect 404 on valid post"
        request:
          method: "GET"
          path: "/posts/1"
        expect:
          status: 404
"""

    config_file = tmp_path / "failing_scenario.yaml"
    config_file.write_text(
        yaml_content,
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [str(config_file)],
    )

    assert result.exit_code == 1
    assert "Failing Scenario" in result.stdout
    assert "FAILED" in result.stdout


def test_cli_run_nonexistent_file() -> None:
    """Verifies CLI raises an error when target YAML file does not exist."""
    result = runner.invoke(
        app,
        ["non_existent_file.yaml"],
    )

    assert result.exit_code != 0


def test_cli_run_daemon_mode(
    tmp_path: Path,
    local_api: str,
) -> None:
    """Verifies daemon loop execution and graceful KeyboardInterrupt exit."""
    yaml_content = f"""
version: "1.0"

global:
  base_url: "{local_api}"

scenarios:
  - name: "Daemon Test Scenario"
    interval_seconds: 15
    steps:
      - name: "Health check"
        request:
          method: "GET"
          path: "/posts/1"
        expect:
          status: 200
"""

    config_file = tmp_path / "daemon_scenario.yaml"
    config_file.write_text(
        yaml_content,
        encoding="utf-8",
    )

    async def mock_sleep(seconds: float) -> None:
        raise KeyboardInterrupt

    with (
        patch(
            "proofrun.cli.asyncio.sleep",
            side_effect=mock_sleep,
        ),
        patch(
            "proofrun.cli.random.uniform",
            return_value=1.0,
        ),
    ):
        result = runner.invoke(
            app,
            [str(config_file), "--daemon"],
        )

    assert result.exit_code == 0
    assert "Starting daemon mode..." in result.stdout
    assert "Sleeping for 15.0s (incl. jitter)" in result.stdout
    assert "Daemon execution stopped by user." in result.stdout


def test_cli_run_daemon_mode_interval_override(
    tmp_path: Path,
    local_api: str,
) -> None:
    """Verifies daemon mode respects the --interval CLI override."""
    yaml_content = f"""
version: "1.0"

global:
  base_url: "{local_api}"

scenarios:
  - name: "Interval Override Scenario"
    interval_seconds: 60
    steps:
      - name: "Ping Step"
        request:
          method: "GET"
          path: "/posts/1"
        expect:
          status: 200
"""

    config_file = tmp_path / "override_scenario.yaml"
    config_file.write_text(
        yaml_content,
        encoding="utf-8",
    )

    slept_durations: list[float] = []

    async def mock_sleep(seconds: float) -> None:
        slept_durations.append(seconds)
        raise KeyboardInterrupt

    with (
        patch(
            "proofrun.cli.asyncio.sleep",
            side_effect=mock_sleep,
        ),
        patch(
            "proofrun.cli.random.uniform",
            return_value=1.0,
        ),
    ):
        result = runner.invoke(
            app,
            [str(config_file), "--daemon", "-i", "5"],
        )

    assert result.exit_code == 0
    assert slept_durations[0] == pytest.approx(5.0)
    assert "Sleeping for 5.0s (incl. jitter)" in result.stdout


def test_cli_daemon_mode_jitter(
    tmp_path: Path,
    local_api: str,
) -> None:
    """Verifies daemon mode applies the ±15% sleep jitter."""
    yaml_content = f"""
version: "1.0"

global:
  base_url: "{local_api}"

scenarios:
  - name: "Jitter Test"
    interval_seconds: 100
    steps:
      - name: "Ping"
        request:
          method: "GET"
          path: "/posts/1"
        expect:
          status: 200
"""

    config_file = tmp_path / "jitter_scenario.yaml"
    config_file.write_text(
        yaml_content,
        encoding="utf-8",
    )

    slept_durations: list[float] = []

    async def mock_sleep(seconds: float) -> None:
        slept_durations.append(seconds)
        raise KeyboardInterrupt

    with (
        patch(
            "proofrun.cli.asyncio.sleep",
            side_effect=mock_sleep,
        ),
        patch(
            "proofrun.cli.random.uniform",
            return_value=1.15,
        ),
    ):
        result = runner.invoke(
            app,
            [str(config_file), "--daemon"],
        )

    assert result.exit_code == 0
    assert slept_durations[0] == pytest.approx(115.0)


def test_cli_daemon_with_webhook_flag(
    tmp_path: Path,
    local_api: str,
) -> None:
    """Verifies daemon mode dispatches a webhook on failure transition."""
    yaml_content = f"""
version: "1.0"

global:
  base_url: "{local_api}"

scenarios:
  - name: "Webhook Scenario"
    steps:
      - name: "Ping"
        request:
          method: "GET"
          path: "/"
        expect:
          status: 500
"""

    config_file = tmp_path / "webhook_scenario.yaml"
    config_file.write_text(
        yaml_content,
        encoding="utf-8",
    )

    async def mock_sleep(seconds: float) -> None:
        raise KeyboardInterrupt

    with (
        patch(
            "proofrun.cli.WebhookNotifier.notify",
            new_callable=AsyncMock,
        ) as mock_notify,
        patch(
            "proofrun.cli.asyncio.sleep",
            side_effect=mock_sleep,
        ),
    ):
        result = runner.invoke(
            app,
            [
                str(config_file),
                "--daemon",
                "--webhook-url",
                "https://hooks.discord.com/123",
            ],
        )

    assert result.exit_code == 0
    assert mock_notify.call_count == 1

    event = mock_notify.call_args.args[0]

    assert event.scenario_name == "Webhook Scenario"
    assert event.old_status == Status.UNKNOWN
    assert event.new_status == Status.FAILING
    assert "Ping" in event.details


def test_cli_invalid_config_in_daemon_mode(
    tmp_path: Path,
) -> None:
    """Verifies daemon mode handles invalid configuration gracefully."""
    config_file = tmp_path / "invalid.yaml"

    config_file.write_text(
        """
version: "1.0"

global:
  base_url: "https://example.com"

scenarios:
  - name: "Invalid Scenario"
    steps:
      - invalid
""",
        encoding="utf-8",
    )

    async def mock_sleep(seconds: float) -> None:
        raise KeyboardInterrupt

    with patch(
        "proofrun.cli.asyncio.sleep",
        side_effect=mock_sleep,
    ):
        result = runner.invoke(
            app,
            [str(config_file), "--daemon"],
        )

    assert result.exit_code == 0
    assert "Configuration Error" in result.stdout
    assert "Sleeping for" in result.stdout
    assert "Daemon execution stopped by user." in result.stdout


def test_cli_daemon_uses_last_known_good_config(
    tmp_path: Path,
    local_api: str,
) -> None:
    """Verifies daemon mode retains a previously valid configuration."""
    config_file = tmp_path / "reload.yaml"

    valid_yaml = f"""
version: "1.0"

global:
  base_url: "{local_api}"

scenarios:
  - name: "Known Good Scenario"
    interval_seconds: 10
    steps:
      - name: "Ping"
        request:
          method: "GET"
          path: "/"
        expect:
          status: 200
"""

    config_file.write_text(
        valid_yaml,
        encoding="utf-8",
    )

    async def mock_sleep(seconds: float) -> None:
        raise KeyboardInterrupt

    with (
        patch(
            "proofrun.cli.asyncio.sleep",
            side_effect=mock_sleep,
        ),
        patch(
            "proofrun.cli.random.uniform",
            return_value=1.0,
        ),
    ):
        result = runner.invoke(
            app,
            [str(config_file), "--daemon"],
        )

    assert result.exit_code == 0
    assert "Known Good Scenario" in result.stdout


def test_execute_config_no_valid_config() -> None:
    """Verifies execution fails when no valid configuration is available."""
    config_manager = Mock()
    config_manager.load.return_value = (
        None,
        Exception("Invalid configuration"),
    )

    async def run_test() -> tuple[bool, int]:
        async with httpx.AsyncClient() as client:
            return await execute_config(
                config_manager,
                client,
            )

    with patch("proofrun.cli.console.print") as mock_print:
        result = asyncio.run(run_test())

    assert result == (False, 60)
    assert mock_print.call_count == 1
    assert "Configuration Error" in mock_print.call_args.args[0]


def test_execute_config_config_error_with_last_known_good() -> None:
    """Verifies execution continues with the last known-good configuration."""
    proofrun_config = ProofrunConfig.model_validate(
        {
            "version": "1.0",
            "global": {
                "base_url": "https://example.com",
            },
            "scenarios": [
                {
                    "name": "Known Good",
                    "interval_seconds": 30,
                    "steps": [
                        {
                            "name": "Ping",
                            "request": {
                                "method": "GET",
                                "path": "/",
                            },
                            "expect": {
                                "status": 200,
                            },
                        }
                    ],
                }
            ],
        }
    )

    config_manager = Mock()
    config_manager.load.return_value = (
        proofrun_config,
        Exception("Reload failed"),
    )

    result = ScenarioResult(
        scenario_name="Known Good",
        passed=True,
        step_results=[],
        total_latency_ms=1.0,
    )

    with (
        patch(
            "proofrun.cli.ScenarioRunner.run",
            new_callable=AsyncMock,
            return_value=result,
        ),
        patch("proofrun.cli.render_scenario_result"),
        patch("proofrun.cli.console.print") as mock_print,
    ):

        async def run_test() -> tuple[bool, int]:
            async with httpx.AsyncClient() as client:
                return await execute_config(
                    config_manager,
                    client,
                )

        actual = asyncio.run(run_test())

    assert actual == (True, 30)
    mock_print.assert_any_call("[yellow]Using last known-good configuration.[/yellow]")


def test_execute_config_empty_scenarios() -> None:
    """Verifies execution returns the default interval for no scenarios."""
    proofrun_config = ProofrunConfig.model_validate(
        {
            "version": "1.0",
            "global": {
                "base_url": "https://example.com",
            },
            "scenarios": [],
        }
    )

    config_manager = Mock()
    config_manager.load.return_value = (
        proofrun_config,
        None,
    )

    async def run_test() -> tuple[bool, int]:
        async with httpx.AsyncClient() as client:
            return await execute_config(
                config_manager,
                client,
            )

    with patch("proofrun.cli.render_scenario_result"):
        result = asyncio.run(run_test())

    assert result == (True, 60)


def test_execute_config_state_manager_without_transition() -> None:
    """Verifies state updates do not notify without a transition."""
    proofrun_config = ProofrunConfig.model_validate(
        {
            "version": "1.0",
            "global": {
                "base_url": "https://example.com",
            },
            "scenarios": [
                {
                    "name": "Healthy Scenario",
                    "interval_seconds": 20,
                    "steps": [
                        {
                            "name": "Ping",
                            "request": {
                                "method": "GET",
                                "path": "/",
                            },
                            "expect": {
                                "status": 200,
                            },
                        }
                    ],
                }
            ],
        }
    )

    config_manager = Mock()
    config_manager.load.return_value = (
        proofrun_config,
        None,
    )

    result = ScenarioResult(
        scenario_name="Healthy Scenario",
        passed=True,
        step_results=[],
        total_latency_ms=1.0,
    )

    state_manager = StateManager()

    with (
        patch(
            "proofrun.cli.ScenarioRunner.run",
            new_callable=AsyncMock,
            return_value=result,
        ),
        patch("proofrun.cli.render_scenario_result"),
    ):
        notifier = Mock()
        notifier.notify = AsyncMock()

        async def run_test() -> tuple[bool, int]:
            async with httpx.AsyncClient() as client:
                return await execute_config(
                    config_manager,
                    client,
                    state_manager,
                    notifier,
                )

        actual = asyncio.run(run_test())

    assert actual == (True, 20)
    notifier.notify.assert_not_awaited()


def test_render_scenario_result_passed() -> None:
    """Verifies successful scenario rendering."""
    result = ScenarioResult(
        scenario_name="Passing Scenario",
        passed=True,
        step_results=[
            StepResult(
                step_name="GET /health",
                passed=True,
                status_code=200,
                latency_ms=12.34,
                error=None,
            )
        ],
        total_latency_ms=12.34,
    )

    with patch("proofrun.cli.console.print") as mock_print:
        render_scenario_result(result)

    assert mock_print.call_count == 3

    table = mock_print.call_args_list[0].args[0]
    panel = mock_print.call_args_list[1].args[0]

    assert table.title == ("Scenario: [bold white]Passing Scenario[/bold white]")
    assert panel.border_style == "green"


def test_render_scenario_result_failed() -> None:
    """Verifies failed scenario rendering and error details."""
    result = ScenarioResult(
        scenario_name="Failed Scenario",
        passed=False,
        step_results=[
            StepResult(
                step_name="GET /health",
                passed=False,
                status_code=500,
                latency_ms=45.67,
                error="Internal Server Error",
            )
        ],
        total_latency_ms=45.67,
    )

    with patch("proofrun.cli.console.print") as mock_print:
        render_scenario_result(result)

    assert mock_print.call_count == 3

    table = mock_print.call_args_list[0].args[0]
    panel = mock_print.call_args_list[1].args[0]

    assert table.title == ("Scenario: [bold white]Failed Scenario[/bold white]")
    assert panel.border_style == "red"


def test_execute_config_failure_transition_notifies() -> None:
    """Verifies failing state transitions dispatch notifications."""
    proofrun_config = ProofrunConfig.model_validate(
        {
            "version": "1.0",
            "global": {
                "base_url": "https://example.com",
            },
            "scenarios": [
                {
                    "name": "Failing Scenario",
                    "interval_seconds": 15,
                    "steps": [
                        {
                            "name": "Ping",
                            "request": {
                                "method": "GET",
                                "path": "/",
                            },
                            "expect": {
                                "status": 200,
                            },
                        }
                    ],
                }
            ],
        }
    )

    config_manager = Mock()
    config_manager.load.return_value = (
        proofrun_config,
        None,
    )

    result = ScenarioResult(
        scenario_name="Failing Scenario",
        passed=False,
        step_results=[
            StepResult(
                step_name="Ping",
                passed=False,
                status_code=500,
                latency_ms=10.0,
                error="Server error",
            )
        ],
        total_latency_ms=10.0,
    )

    notifier = Mock()
    notifier.notify = AsyncMock()

    state_manager = StateManager()

    with (
        patch(
            "proofrun.cli.ScenarioRunner.run",
            new_callable=AsyncMock,
            return_value=result,
        ),
        patch("proofrun.cli.render_scenario_result"),
    ):

        async def run_test() -> tuple[bool, int]:
            async with httpx.AsyncClient() as client:
                return await execute_config(
                    config_manager,
                    client,
                    state_manager,
                    notifier,
                )

        actual = asyncio.run(run_test())

    assert actual == (False, 15)
    notifier.notify.assert_awaited_once()

    event = notifier.notify.call_args.args[0]

    assert event.scenario_name == "Failing Scenario"
    assert event.old_status == Status.UNKNOWN
    assert event.new_status == Status.FAILING
    assert "Ping: Server error" in event.details


def test_execute_config_recovery_transition_notifies() -> None:
    """Verifies failing-to-healthy transitions dispatch notifications."""
    proofrun_config = ProofrunConfig.model_validate(
        {
            "version": "1.0",
            "global": {
                "base_url": "https://example.com",
            },
            "scenarios": [
                {
                    "name": "Recovery Scenario",
                    "interval_seconds": 15,
                    "steps": [
                        {
                            "name": "Ping",
                            "request": {
                                "method": "GET",
                                "path": "/",
                            },
                            "expect": {
                                "status": 200,
                            },
                        }
                    ],
                }
            ],
        }
    )

    config_manager = Mock()
    config_manager.load.return_value = (
        proofrun_config,
        None,
    )

    result = ScenarioResult(
        scenario_name="Recovery Scenario",
        passed=True,
        step_results=[
            StepResult(
                step_name="Ping",
                passed=True,
                status_code=200,
                latency_ms=10.0,
                error=None,
            )
        ],
        total_latency_ms=10.0,
    )

    notifier = Mock()
    notifier.notify = AsyncMock()

    state_manager = StateManager()
    state_manager.update(
        "Recovery Scenario",
        False,
    )

    with (
        patch(
            "proofrun.cli.ScenarioRunner.run",
            new_callable=AsyncMock,
            return_value=result,
        ),
        patch("proofrun.cli.render_scenario_result"),
    ):

        async def run_test() -> tuple[bool, int]:
            async with httpx.AsyncClient() as client:
                return await execute_config(
                    config_manager,
                    client,
                    state_manager,
                    notifier,
                )

        actual = asyncio.run(run_test())

    assert actual == (True, 15)
    notifier.notify.assert_awaited_once()

    event = notifier.notify.call_args.args[0]

    assert event.scenario_name == "Recovery Scenario"
    assert event.old_status == Status.FAILING
    assert event.new_status == Status.HEALTHY
    assert event.details == "All steps passing."


def test_execute_config_without_any_config_reports_failure() -> None:
    """Verifies the defensive path when no config and no error are available."""
    config_manager = Mock()
    config_manager.load.return_value = (
        None,
        None,
    )

    async def run_test() -> tuple[bool, int]:
        async with httpx.AsyncClient() as client:
            return await execute_config(
                config_manager,
                client,
            )

    passed, interval = asyncio.run(run_test())

    assert passed is False
    assert interval == 60
