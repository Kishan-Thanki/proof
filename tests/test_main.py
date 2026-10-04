"""Unit tests for the Proof CLI entrypoint."""

import subprocess
import sys


def test_main_execution() -> None:
    """Verifies that python -m proof invokes the Typer app correctly."""
    result = subprocess.run(
        [sys.executable, "-m", "proof", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Usage:" in result.stdout
    assert "run" in result.stdout
