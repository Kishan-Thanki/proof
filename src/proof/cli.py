"""Command Line Interface for Proof synthetic API monitoring daemon.

Provides terminal rendering and workflow orchestration for running synthetic
monitoring scenarios using Typer and Rich.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from proof.core.compiler import (
    ConfigCompilerError,
    load_and_compile_config,
)
from proof.core.engine import ScenarioResult, ScenarioRunner

__version__ = "0.1.0"

app = typer.Typer(
    name="proof",
    help="High-performance, stateless synthetic API monitoring daemon.",
    add_completion=False,
)

console = Console()


def version_callback(value: bool) -> None:
    """Print the Proof version and exit."""
    if value:
        console.print(
            f"[bold cyan]Proof[/bold cyan] "
            f"version [bold green]{__version__}[/bold green]"
        )
        raise typer.Exit(code=0)


@app.callback()
def main(
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            "-v",
            help="Show Proof version and exit.",
            callback=version_callback,
            is_eager=True,
        ),
    ] = None,
) -> None:
    """Proof - Synthetic API Monitoring Daemon."""


def render_scenario_result(
    result: ScenarioResult,
) -> None:
    """Render a scenario result using Rich."""
    status_style = "bold green" if result.passed else "bold red"
    status_text = "PASSED" if result.passed else "FAILED"

    table = Table(
        title=(f"Scenario: [bold white]{result.scenario_name}[/bold white]"),
        title_style="bold cyan",
        show_header=True,
        header_style="bold magenta",
        expand=True,
    )

    table.add_column(
        "Step Name",
        style="dim",
        min_width=25,
    )
    table.add_column(
        "Status",
        justify="center",
        width=10,
    )
    table.add_column(
        "HTTP Code",
        justify="right",
        width=10,
    )
    table.add_column(
        "Latency",
        justify="right",
        width=12,
    )
    table.add_column(
        "Error Details",
        style="red",
        min_width=20,
    )

    for step in result.step_results:
        step_status = (
            "[bold green]PASS[/bold green]"
            if step.passed
            else "[bold red]FAIL[/bold red]"
        )

        code_style = "green" if step.passed else "red"

        code_str = f"[{code_style}]{step.status_code}[/{code_style}]"

        latency_str = f"{step.latency_ms:.2f} ms"

        error_str = step.error or "-"

        table.add_row(
            step.step_name,
            step_status,
            code_str,
            latency_str,
            error_str,
        )

    console.print(table)

    summary_text = Text()
    summary_text.append(
        "Status: ",
        style="bold",
    )
    summary_text.append(
        status_text,
        style=status_style,
    )
    summary_text.append(
        "    Total Latency: ",
        style="bold",
    )
    summary_text.append(
        f"{result.total_latency_ms:.2f} ms",
        style="cyan",
    )

    panel = Panel(
        summary_text,
        title="[bold]Summary[/bold]",
        border_style=("green" if result.passed else "red"),
        expand=False,
    )

    console.print(panel)
    console.print()


async def execute_config(
    config_path: Path,
) -> tuple[bool, int]:
    """Load, compile, and execute all scenarios.

    Returns:
        A tuple containing:
            - whether all scenarios passed
            - the smallest configured scenario interval
    """
    try:
        proof_config = load_and_compile_config(config_path)
    except ConfigCompilerError as err:
        console.print(f"[bold red]Configuration Error:[/bold red] {err}")
        return False, 60

    all_passed = True

    scenario_intervals: list[int] = []

    for scenario in proof_config.scenarios:
        scenario_intervals.append(scenario.interval_seconds)

        runner = ScenarioRunner(scenario)
        result = await runner.run()

        render_scenario_result(result)

        if not result.passed:
            all_passed = False

    interval = min(scenario_intervals) if scenario_intervals else 60

    return all_passed, interval


@app.command(name="run")
def run_command(
    config_path: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Path to YAML scenario configuration file.",
        ),
    ],
    once: Annotated[
        bool,
        typer.Option(
            "--once/--daemon",
            help=("Run scenarios once and exit, or loop continuously in daemon mode."),
        ),
    ] = True,
    interval: Annotated[
        int | None,
        typer.Option(
            "--interval",
            "-i",
            min=1,
            help=(
                "Override the configured scenario interval in seconds for daemon mode."
            ),
        ),
    ] = None,
) -> None:
    """Execute synthetic monitoring scenarios defined in YAML."""

    console.print(
        f"[bold cyan]Proof[/bold cyan] executing scenario: "
        f"[bold yellow]{config_path}[/bold yellow]\n"
    )

    if once:
        passed, _ = asyncio.run(execute_config(config_path))

        raise typer.Exit(code=0 if passed else 1)

    console.print(
        "[bold green]Starting daemon mode... Press Ctrl+C to stop.[/bold green]\n"
    )

    try:
        while True:
            passed, configured_interval = asyncio.run(execute_config(config_path))

            sleep_time = interval if interval is not None else configured_interval

            console.print(
                f"[dim]Sleeping for {sleep_time}s "
                "before next execution cycle...[/dim]\n"
            )

            time.sleep(sleep_time)

    except KeyboardInterrupt:
        console.print("\n[yellow]Daemon execution stopped by user.[/yellow]")
        raise typer.Exit(code=0) from None


if __name__ == "__main__":
    app()
