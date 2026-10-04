"""Unit tests for the Proof CLI entrypoint."""

import runpy
from unittest.mock import patch


def test_main_execution() -> None:
    """Verifies that the module entrypoint installs uvloop and starts the CLI."""
    with (
        patch("uvloop.install") as mock_install,
        patch("proof.cli.app") as mock_app,
    ):
        runpy.run_module(
            "proof.__main__",
            run_name="__main__",
        )

    mock_install.assert_called_once()
    mock_app.assert_called_once()
