"""State management for tracking scenario health transitions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Status(Enum):
    """The health status of a scenario."""

    UNKNOWN = "UNKNOWN"
    HEALTHY = "HEALTHY"
    FAILING = "FAILING"


@dataclass
class ScenarioState:
    """Tracks the historical state of a single scenario."""

    status: Status = Status.UNKNOWN
    fail_count: int = 0
    pass_count: int = 0


class StateManager:
    """Manages state across all scenarios for alerting purposes."""

    def __init__(self) -> None:
        self.states: dict[str, ScenarioState] = {}

    def update_and_check_transition(
        self, scenario_name: str, passed: bool
    ) -> tuple[Status, Status]:
        """Update scenario state and return (old_status, new_status)."""
        if scenario_name not in self.states:
            self.states[scenario_name] = ScenarioState()

        state = self.states[scenario_name]
        old_status = state.status

        if passed:
            state.pass_count += 1
            state.fail_count = 0
            state.status = Status.HEALTHY
        else:
            state.fail_count += 1
            state.pass_count = 0
            state.status = Status.FAILING

        return old_status, state.status
