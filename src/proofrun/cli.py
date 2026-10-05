"""Command Line Interface for Proofrun synthetic API monitoring daemon.

Provides terminal rendering and workflow orchestration for running synthetic
monitoring scenarios using Typer and Rich.
"""

from __future__ import annotations

import asyncio
import random
from pathlib import Path
from typing import Annotated

import httpx
import typer
import uvloop
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from proofrun import __version__
from proofrun.core.engine import ScenarioResult, ScenarioRunner
from proofrun.core.notifier import (
    NotificationEvent,
    Notifier,
    WebhookNotifier,
)
from proofrun.core.provider import ConfigProvider
from proofrun.core.state import StateManager, Status

app = typer.Typer(
    name="proofrun",
    help="Synthetic API monitoring as code daemon.",
    add_completion=False,
)

console = Console()


def version_callback(value: bool) -> None:
    """Print the Proofrun version and exit."""
    if value:
        console.print(
            f"[bold cyan]Proofrun[/bold cyan] "
            f"version [bold green]{__version__}[/bold green]"
        )
        raise typer.Exit(code=0)


def render_scenario_result(result: ScenarioResult) -> None:
    """Render a scenario result using Rich."""
    status_style = "bold green" if result.passed else "bold red"
    status_text = "PASSED" if result.passed else "FAILED"

    table = Table(
        title=f"Scenario: [bold white]{result.scenario_name}[/bold white]",
        title_style="bold cyan",
        show_header=True,
        header_style="bold magenta",
        expand=True,
    )

    table.add_column("Step Name", style="dim", min_width=25)
    table.add_column("Status", justify="center", width=10)
    table.add_column("HTTP Code", justify="right", width=10)
    table.add_column("Latency", justify="right", width=12)
    table.add_column("Error Details", style="red", min_width=20)

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
    summary_text.append("Status: ", style="bold")
    summary_text.append(status_text, style=status_style)
    summary_text.append("    Total Latency: ", style="bold")
    summary_text.append(
        f"{result.total_latency_ms:.2f} ms",
        style="cyan",
    )

    panel = Panel(
        summary_text,
        title="[bold]Summary[/bold]",
        border_style="green" if result.passed else "red",
        expand=False,
    )

    console.print(panel)
    console.print()


async def execute_config(
    config_provider: ConfigProvider,
    client: httpx.AsyncClient,
    state_manager: StateManager | None = None,
    notifier: Notifier | None = None,
) -> tuple[bool, int]:
    """Load and execute all scenarios concurrently.

    Args:
        config_provider: Cached configuration provider.
        client: Reusable HTTP client for connection pooling.
        state_manager: Tracks historical health across execution cycles.
        notifier: Optional notification destination for state transitions.

    Returns:
        A tuple containing (all_passed, smallest_configured_interval).
    """
    proofrun_config, config_error = config_provider.load()

    if config_error is not None:
        console.print(f"[bold red]Configuration Error:[/bold red] {config_error}")

        if proofrun_config is None:
            return False, 60

        console.print("[yellow]Using last known-good configuration.[/yellow]")

    if proofrun_config is None:
        console.print("[bold red]No valid configuration is available.[/bold red]")
        return False, 60

    if state_manager is not None:
        active_scenario_names = {s.name for s in proofrun_config.scenarios}
        state_manager.sync(active_scenario_names)

    runners = [ScenarioRunner(scenario) for scenario in proofrun_config.scenarios]
    tasks = [runner.run(client) for runner in runners]

    results = await asyncio.gather(*tasks)

    all_passed = True
    scenario_intervals: list[int] = []

    for result, scenario in zip(
        results,
        proofrun_config.scenarios,
        strict=True,
    ):
        scenario_intervals.append(scenario.interval_seconds)

        render_scenario_result(result)

        if not result.passed:
            all_passed = False

        if state_manager is None:
            continue

        transition = state_manager.update(
            scenario.name,
            result.passed,
        )

        if notifier is None or not transition.changed:
            continue

        if transition.new_status == Status.FAILING:
            errors = [
                f"- {step.step_name}: {step.error}"
                for step in result.step_results
                if not step.passed
            ]

            event = NotificationEvent(
                scenario_name=transition.scenario_name,
                old_status=transition.old_status,
                new_status=transition.new_status,
                details="\n".join(errors),
            )

            await notifier.notify(event)

        elif (
            transition.old_status == Status.FAILING
            and transition.new_status == Status.HEALTHY
        ):
            event = NotificationEvent(
                scenario_name=transition.scenario_name,
                old_status=transition.old_status,
                new_status=transition.new_status,
                details="All steps passing.",
            )

            await notifier.notify(event)

    interval = min(scenario_intervals) if scenario_intervals else 60

    return all_passed, interval


@app.command()
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
            help="Run scenarios once and exit, or loop continuously in daemon mode.",
        ),
    ] = True,
    interval: Annotated[
        int | None,
        typer.Option(
            "--interval",
            "-i",
            min=1,
            help="Override configured scenario interval in seconds for daemon mode.",
        ),
    ] = None,
    webhook_url: Annotated[
        str | None,
        typer.Option(
            "--webhook-url",
            envvar="PROOF_WEBHOOK_URL",
            help="HTTP webhook URL for state transition alerts.",
        ),
    ] = None,
    _show_version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            "-v",
            help="Show Proofrun version and exit.",
            callback=version_callback,
            is_eager=True,
        ),
    ] = None,
) -> None:
    """Execute synthetic monitoring scenarios defined in YAML."""
    console.print(
        f"[bold cyan]Proofrun[/bold cyan] executing config: "
        f"[bold yellow]{config_path}[/bold yellow]\n"
    )

    async def _run_loop() -> int:
        config_provider = ConfigProvider(config_path)
        state_manager = StateManager()

        async with httpx.AsyncClient() as client:
            notifier: Notifier | None = None

            if webhook_url is not None:
                notifier = WebhookNotifier(
                    client=client,
                    webhook_url=webhook_url,
                )

            if once:
                passed, _ = await execute_config(
                    config_provider,
                    client,
                )

                return 0 if passed else 1

            console.print(
                "[bold green]Starting daemon mode... "
                "Press Ctrl+C to stop.[/bold green]\n"
            )

            while True:
                _, config_interval = await execute_config(
                    config_provider,
                    client,
                    state_manager,
                    notifier,
                )

                base_sleep = interval if interval is not None else config_interval

                sleep_time = base_sleep * random.uniform(
                    0.85,
                    1.15,
                )

                console.print(
                    f"[dim]Sleeping for {sleep_time:.1f}s "
                    "(incl. jitter) before next execution cycle..."
                    "[/dim]\n"
                )

                await asyncio.sleep(sleep_time)

    try:
        exit_code = uvloop.run(_run_loop())
    except KeyboardInterrupt:
        console.print("\n[yellow]Daemon execution stopped by user.[/yellow]")
        raise typer.Exit(code=0) from None

    raise typer.Exit(code=exit_code)  # pragma: no cover


def main() -> None:
    """Run the Proofrun CLI."""
    app()
