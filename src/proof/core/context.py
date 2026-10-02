import random
import re
import time
import uuid
from typing import Any

from jsonpath_ng import parse


class ContextError(Exception):
    """Raised when variable extraction or string interpolation fails."""


class ExecutionContext:
    """Manages runtime state variables, dynamic variable generation ($uuid, $timestamp),

    string/payload interpolation, and JSONPath extraction across scenario steps.
    """

    VAR_PATTERN = re.compile(r"\$\{([a-zA-Z0-9_.\$]+)\}")

    def __init__(self, initial_vars: dict[str, Any] | None = None) -> None:
        self.variables: dict[str, Any] = initial_vars or {}

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
        elif var_name == "$timestamp":
            return int(time.time())
        elif var_name == "$random_int":
            return random.randint(1000, 9999)
        return None

    def extract_variables(
        self, payload: dict[str, Any] | list[Any], rules: dict[str, str]
    ) -> None:
        """Extracts values from a JSON payload using JSONPath expressions."""
        for var_name, jsonpath_expr in rules.items():
            try:
                expr = parse(jsonpath_expr)
                matches = [match.value for match in expr.find(payload)]
            except Exception as e:
                raise ContextError(
                    f"Invalid JSONPath expression '{jsonpath_expr}' for variable '{var_name}': {e}"
                ) from e

            if not matches:
                raise ContextError(
                    f"JSONPath extraction failed: Path '{jsonpath_expr}' did not match any value in response."
                )

            self.variables[var_name] = matches[0]

    def interpolate_string(self, text: str) -> Any:
        """Interpolates variables inside a string. Handles both state variables

        and built-in dynamic variables ($uuid, $timestamp, $random_int).
        """
        exact_match = self.VAR_PATTERN.fullmatch(text.strip())
        if exact_match:
            var_name = exact_match.group(1)

            if var_name.startswith("$"):
                dyn_val = self._get_dynamic_variable(var_name)
                if dyn_val is not None:
                    return dyn_val

            if var_name not in self.variables:
                raise ContextError(f"Missing required context variable: '${{{var_name}}}'")
            return self.variables[var_name]

        def replace_var(match: re.Match[str]) -> str:
            var_name = match.group(1)

            if var_name.startswith("$"):
                dyn_val = self._get_dynamic_variable(var_name)
                if dyn_val is not None:
                    return str(dyn_val)

            if var_name not in self.variables:
                raise ContextError(f"Missing required context variable: '${{{var_name}}}'")
            return str(self.variables[var_name])

        return self.VAR_PATTERN.sub(replace_var, text)

    def interpolate_data(self, data: Any) -> Any:
        """Recursively traverses dictionaries, lists, and strings to interpolate variables."""
        if isinstance(data, str):
            return self.interpolate_string(data)
        elif isinstance(data, dict):
            return {k: self.interpolate_data(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self.interpolate_data(item) for item in data]
        else:
            return data
