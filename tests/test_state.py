"""Unit tests for the scenario state manager."""

from __future__ import annotations

from proofrun.core.state import ScenarioState, StateManager, Status


def test_scenario_state_defaults() -> None:
    """Verifies the dataclass default instantiation values."""
    state = ScenarioState()
    assert state.status == Status.UNKNOWN
    assert state.fail_count == 0
    assert state.pass_count == 0


def test_initial_to_healthy() -> None:
    """Verifies transition from unknown to healthy."""
    manager = StateManager()
    transition = manager.update("API Test", True)

    assert transition.old_status == Status.UNKNOWN
    assert transition.new_status == Status.HEALTHY
    assert transition.changed is True
    assert manager.states["API Test"].pass_count == 1
    assert manager.states["API Test"].fail_count == 0


def test_initial_to_failing() -> None:
    """Verifies transition from unknown to failing."""
    manager = StateManager()
    transition = manager.update("API Test", False)

    assert transition.old_status == Status.UNKNOWN
    assert transition.new_status == Status.FAILING
    assert transition.changed is True
    assert manager.states["API Test"].pass_count == 0
    assert manager.states["API Test"].fail_count == 1


def test_recovery_transition() -> None:
    """Verifies failing to healthy transition (Recovery)."""
    manager = StateManager()
    manager.update("API Test", False)
    manager.update("API Test", False)

    assert manager.states["API Test"].fail_count == 2

    transition = manager.update("API Test", True)

    assert transition.old_status == Status.FAILING
    assert transition.new_status == Status.HEALTHY
    assert transition.changed is True
    assert manager.states["API Test"].pass_count == 1
    assert manager.states["API Test"].fail_count == 0


def test_failure_transition() -> None:
    """Verifies healthy to failing transition."""
    manager = StateManager()
    manager.update("API Test", True)

    transition = manager.update("API Test", False)

    assert transition.old_status == Status.HEALTHY
    assert transition.new_status == Status.FAILING
    assert transition.changed is True
    assert manager.states["API Test"].pass_count == 0
    assert manager.states["API Test"].fail_count == 1


def test_continuous_healthy() -> None:
    """Verifies consecutive passes increment pass_count and maintain HEALTHY state."""
    manager = StateManager()
    manager.update("API Test", True)

    manager.update("API Test", True)
    transition = manager.update("API Test", True)

    assert transition.old_status == Status.HEALTHY
    assert transition.new_status == Status.HEALTHY
    assert transition.changed is False
    assert manager.states["API Test"].pass_count == 3
    assert manager.states["API Test"].fail_count == 0


def test_continuous_failing() -> None:
    """Verifies consecutive failures increment fail_count and maintain FAILING state."""
    manager = StateManager()
    manager.update("API Test", False)

    manager.update("API Test", False)
    transition = manager.update("API Test", False)

    assert transition.old_status == Status.FAILING
    assert transition.new_status == Status.FAILING
    assert transition.changed is False
    assert manager.states["API Test"].pass_count == 0
    assert manager.states["API Test"].fail_count == 3


def test_multiple_independent_scenarios() -> None:
    """Verifies state is isolated correctly between different scenarios."""
    manager = StateManager()

    manager.update("Scenario A", True)
    manager.update("Scenario B", False)

    # Scenario A checks
    assert manager.states["Scenario A"].status == Status.HEALTHY
    assert manager.states["Scenario A"].pass_count == 1
    assert manager.states["Scenario A"].fail_count == 0

    # Scenario B checks
    assert manager.states["Scenario B"].status == Status.FAILING
    assert manager.states["Scenario B"].pass_count == 0
    assert manager.states["Scenario B"].fail_count == 1

    # Update B to pass; A should remain unchanged
    manager.update("Scenario B", True)

    assert manager.states["Scenario A"].pass_count == 1
    assert manager.states["Scenario B"].status == Status.HEALTHY
    assert manager.states["Scenario B"].pass_count == 1


def test_sync_removes_stale_states() -> None:
    """Verifies sync removes states for scenarios no longer active."""
    manager = StateManager()
    manager.update("Scenario A", True)
    manager.update("Scenario B", True)

    assert "Scenario A" in manager.states
    assert "Scenario B" in manager.states

    manager.sync({"Scenario A"})

    assert "Scenario A" in manager.states
    assert "Scenario B" not in manager.states
