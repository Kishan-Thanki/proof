"""Unit tests for Proof CLI interface."""

from pathlib import Path

from typer.testing import CliRunner

from proof.cli import app

runner = CliRunner()


def test_cli_version_flag() -> None:
    """Verifies that --version prints the version string and exits cleanly."""
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert "Proof version" in result.stdout


def test_cli_run_successful_scenario(tmp_path: Path) -> None:
    """Verifies successful scenario execution via CLI argument."""
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


def test_cli_run_nonexistent_file() -> None:
    """Verifies CLI raises an error when target YAML file does not exist."""
    result = runner.invoke(app, ["run", "non_existent_file.yaml"])

    assert result.exit_code != 0
