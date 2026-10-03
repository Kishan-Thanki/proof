"""Execution context and dynamic variable interpolation module for Proof.

This module manages runtime state persistence across scenario steps, JSONPath
variable extraction from API responses, string/nested payload interpolation,
and built-in dynamic generators ($uuid, $timestamp, $timestamp_ms,
$iso_timestamp, $random_int).
"""

import random
import re
import time
import uuid
from typing import Any

from jsonpath_ng import parse


class ContextError(Exception):
    """Raised when variable extraction or string interpolation fails."""


class ExecutionContext:
    """Manages runtime state variables and payload interpolation.

    The context persists variables across scenario steps, supports JSONPath
    extraction from response payloads, and resolves both stored and dynamic
    variables during request construction.
    """

    VAR_PATTERN = re.compile(r"\$\{([a-zA-Z0-9_.$]+)\}")

    def __init__(self, initial_vars: dict[str, Any] | None = None) -> None:
        """Initializes execution context with optional pre-defined variables.

        Args:
            initial_vars: Initial dictionary of state variables. A copy is
                created so later context mutations do not modify the caller's
                dictionary.
        """
        self.variables: dict[str, Any] = (
            dict(initial_vars) if initial_vars is not None else {}
        )

    def set(self, key: str, value: Any) -> None:
        """Sets a state variable manually."""
        self.variables[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieves a state variable."""
        return self.variables.get(key, default)

    def _get_dynamic_variable(self, var_name: str) -> Any | None:
        """Evaluates built-in dynamic generators starting with '$'."""
        if var_name == "$uuid":
            return str(uuid.uuid4())

        if var_name == "$timestamp":
            return int(time.time())

        if var_name == "$timestamp_ms":
            return int(time.time() * 1000)

        if var_name == "$iso_timestamp":
            return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        if var_name == "$random_int":
            return random.randint(1000, 9999)

        return None

    def extract_variables(
        self, payload: dict[str, Any] | list[Any], rules: dict[str, str]
    ) -> None:
        """Extracts values from a JSON payload using JSONPath expressions.

        Args:
            payload: JSON response payload (dict or list).
            rules: Mapping of variable names to JSONPath expressions.

        Raises:
            ContextError: If a JSONPath expression is invalid or matches no
                values.
        """
        for var_name, jsonpath_expr in rules.items():
            try:
                expr = parse(jsonpath_expr)
                matches = [match.value for match in expr.find(payload)]
            except Exception as err:
                raise ContextError(
                    f"Invalid JSONPath expression '{jsonpath_expr}' "
                    f"for variable '{var_name}': {err}"
                ) from err

            if not matches:
                raise ContextError(
                    f"JSONPath extraction failed: Path '{jsonpath_expr}' "
                    "did not match any value in response."
                )

            self.variables[var_name] = matches[0]

    def interpolate_string(self, text: str) -> Any:
        """Interpolates variables inside a string.

        Handles state variables and dynamic generators
        ($uuid, $timestamp, $timestamp_ms, $iso_timestamp, $random_int).

        If the entire string is a single variable reference such as
        ``${user_id}``, the original typed value is returned. Embedded
        variables inside a larger string are converted to strings.

        Args:
            text: Input string containing possible ``${var}`` patterns.

        Returns:
            The original typed value for an exact variable reference, or
            an interpolated string for embedded references.

        Raises:
            ContextError: If a required variable is missing from the context.
        """
        exact_match = self.VAR_PATTERN.fullmatch(text.strip())

        if exact_match:
            var_name = exact_match.group(1)

            if var_name.startswith("$"):
                dynamic_value = self._get_dynamic_variable(var_name)
                if dynamic_value is not None:
                    return dynamic_value

            if var_name not in self.variables:
                raise ContextError(
                    f"Missing required context variable: '${{{var_name}}}'"
                )

            return self.variables[var_name]

        def replace_var(match: re.Match[str]) -> str:
            var_name = match.group(1)

            if var_name.startswith("$"):
                dynamic_value = self._get_dynamic_variable(var_name)
                if dynamic_value is not None:
                    return str(dynamic_value)

            if var_name not in self.variables:
                raise ContextError(
                    f"Missing required context variable: '${{{var_name}}}'"
                )

            return str(self.variables[var_name])

        return self.VAR_PATTERN.sub(replace_var, text)

    def interpolate_data(self, data: Any) -> Any:
        """Recursively traverses data and interpolates string values.

        Dictionaries and lists are traversed recursively. Primitive values
        other than strings are returned unchanged.
        """
        if isinstance(data, str):
            return self.interpolate_string(data)

        if isinstance(data, dict):
            return {key: self.interpolate_data(value) for key, value in data.items()}

        if isinstance(data, list):
            return [self.interpolate_data(item) for item in data]

        return data
