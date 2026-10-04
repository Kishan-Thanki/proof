"""Unit tests for Proof CLI interface."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from proof.cli import app

runner = CliRunner()


def test_cli_version_flag() -> None:
    """Verifies that --version prints the version string and exits cleanly."""
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert "Proof version" in result.stdout


def test_cli_run_successful_scenario(tmp_path: Path) -> None:
    """Verifies successful scenario execution via CLI argument in single-run mode."""
    yaml_content = """
version: "1.0"

global:
  base_url: "https://jsonplaceholder.typicode.com"

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
    config_file.write_text(yaml_content, encoding="utf-8")

    result = runner.invoke(app, ["run", str(config_file)])

    assert result.exit_code == 0
    assert "CLI Integration Scenario" in result.stdout
    assert "PASSED" in result.stdout


def test_cli_run_failing_scenario(tmp_path: Path) -> None:
    """Verifies single-run mode returns exit code 1 when assertions fail."""
    yaml_content = """
version: "1.0"

global:
  base_url: "https://jsonplaceholder.typicode.com"

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
    config_file.write_text(yaml_content, encoding="utf-8")

    result = runner.invoke(app, ["run", str(config_file)])

    assert result.exit_code == 1
    assert "Failing Scenario" in result.stdout
    assert "FAILED" in result.stdout


def test_cli_run_nonexistent_file() -> None:
    """Verifies CLI raises an error when target YAML file does not exist."""
    result = runner.invoke(app, ["run", "non_existent_file.yaml"])

    assert result.exit_code != 0


def test_cli_run_daemon_mode(tmp_path: Path) -> None:
    """Verifies persistent daemon loop execution and graceful KeyboardInterrupt exit."""
    yaml_content = """
version: "1.0"

global:
  base_url: "https://jsonplaceholder.typicode.com"

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
    config_file.write_text(yaml_content, encoding="utf-8")

    async def mock_sleep(seconds: float) -> None:
        raise KeyboardInterrupt

    with patch("proof.cli.asyncio.sleep", side_effect=mock_sleep):
        with patch("proof.cli.random.uniform", return_value=1.0):
            result = runner.invoke(
                app,
                ["run", str(config_file), "--daemon"],
            )

    assert result.exit_code == 0
    assert "Starting daemon mode..." in result.stdout
    assert "Sleeping for 15.0s (incl. jitter)" in result.stdout
    assert "Daemon execution stopped by user." in result.stdout


def test_cli_run_daemon_mode_interval_override(
    tmp_path: Path,
) -> None:
    """Verifies daemon mode respects the --interval CLI override."""
    yaml_content = """
version: "1.0"

global:
  base_url: "https://jsonplaceholder.typicode.com"

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
    config_file.write_text(yaml_content, encoding="utf-8")

    slept_durations: list[float] = []

    async def mock_sleep(seconds: float) -> None:
        slept_durations.append(seconds)
        raise KeyboardInterrupt

    with patch("proof.cli.asyncio.sleep", side_effect=mock_sleep):
        with patch("proof.cli.random.uniform", return_value=1.0):
            result = runner.invoke(
                app,
                ["run", str(config_file), "--daemon", "-i", "5"],
            )

    assert result.exit_code == 0
    assert slept_durations[0] == pytest.approx(5.0)
    assert "Sleeping for 5.0s (incl. jitter)" in result.stdout


def test_cli_daemon_mode_jitter(tmp_path: Path) -> None:
    """Verifies daemon mode applies the ±15% sleep jitter."""
    yaml_content = """
version: "1.0"

global:
  base_url: "https://jsonplaceholder.typicode.com"

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
    config_file.write_text(yaml_content, encoding="utf-8")

    slept_durations: list[float] = []

    async def mock_sleep(seconds: float) -> None:
        slept_durations.append(seconds)
        raise KeyboardInterrupt

    with patch("proof.cli.asyncio.sleep", side_effect=mock_sleep):
        with patch("proof.cli.random.uniform", return_value=1.15):
            result = runner.invoke(
                app,
                ["run", str(config_file), "--daemon"],
            )

    assert result.exit_code == 0
    assert slept_durations[0] == pytest.approx(115.0)


def test_cli_daemon_with_webhook_flag(
    tmp_path: Path,
) -> None:
    """Verifies daemon mode dispatches a webhook on failure transition."""
    yaml_content = """
version: "1.0"

global:
  base_url: "https://example.com"

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
    config_file.write_text(yaml_content, encoding="utf-8")

    async def mock_sleep(seconds: float) -> None:
        raise KeyboardInterrupt

    with patch(
        "proof.cli.WebhookNotifier.notify",
        new_callable=AsyncMock,
    ) as mock_notify:
        with patch(
            "proof.cli.asyncio.sleep",
            side_effect=mock_sleep,
        ):
            result = runner.invoke(
                app,
                [
                    "run",
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
    assert event.old_status.value == "UNKNOWN"
    assert event.new_status.value == "FAILING"
    assert "Ping" in event.details


def test_cli_invalid_config_in_daemon_mode(
    tmp_path: Path,
) -> None:
    """Verifies daemon mode handles an invalid configuration gracefully."""
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
        "proof.cli.asyncio.sleep",
        side_effect=mock_sleep,
    ):
        result = runner.invoke(
            app,
            ["run", str(config_file), "--daemon"],
        )

    assert result.exit_code == 0
    assert "Configuration Error" in result.stdout
    assert "Sleeping for" in result.stdout
    assert "Daemon execution stopped by user." in result.stdout


def test_cli_daemon_uses_last_known_good_config(
    tmp_path: Path,
) -> None:
    """Verifies daemon mode retains a previously valid configuration."""
    config_file = tmp_path / "reload.yaml"

    valid_yaml = """
version: "1.0"

global:
  base_url: "https://example.com"

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

    config_file.write_text(valid_yaml, encoding="utf-8")

    async def mock_sleep(seconds: float) -> None:
        raise KeyboardInterrupt

    with patch(
        "proof.cli.asyncio.sleep",
        side_effect=mock_sleep,
    ):
        with patch(
            "proof.cli.random.uniform",
            return_value=1.0,
        ):
            result = runner.invoke(
                app,
                ["run", str(config_file), "--daemon"],
            )

    assert result.exit_code == 0
    assert "Known Good Scenario" in result.stdout
