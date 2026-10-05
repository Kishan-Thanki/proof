"""AOT Schema Compiler for Proofrun scenario configurations.

This module loads YAML configuration, validates it using Pydantic, resolves
global defaults, and pre-compiles JSON schemas into executable validators.
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import fastjsonschema
import yaml
from pydantic import ValidationError

from proofrun.core.config import GlobalConfig, ProofrunConfig


class ConfigCompilerError(Exception):
    """Raised when configuration loading or compilation fails."""


def load_and_compile_config(config_path: str | Path) -> ProofrunConfig:
    """Load, validate, resolve, and compile a Proofrun configuration.

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        A validated and executable ProofrunConfig.

    Raises:
        ConfigCompilerError: If loading, validation, inheritance, or schema
            compilation fails.
    """
    path = Path(config_path).resolve()

    if not path.exists():
        raise ConfigCompilerError(f"Configuration file not found: {path}")

    try:
        with path.open("r", encoding="utf-8") as file:
            raw_data = yaml.safe_load(file)
    except yaml.YAMLError as err:
        raise ConfigCompilerError(f"Invalid YAML syntax in {path}: {err}") from err
    except OSError as err:
        raise ConfigCompilerError(
            f"Failed to read configuration file {path}: {err}"
        ) from err

    if not isinstance(raw_data, dict):
        raise ConfigCompilerError(
            f"Invalid format in {path}. Expected a top-level YAML mapping."
        )

    try:
        config = ProofrunConfig.model_validate(raw_data)
    except ValidationError as err:
        raise ConfigCompilerError(f"Config validation failed:\n{err}") from err

    global_config = config.global_config or GlobalConfig()

    global_base_url = global_config.base_url
    global_timeout = global_config.timeout_seconds
    global_headers = global_config.headers

    for scenario in config.scenarios:
        if scenario.base_url is None:
            if global_base_url is None:
                raise ConfigCompilerError(
                    f"Scenario '{scenario.name}' is missing 'base_url' "
                    "and no global 'base_url' is defined."
                )

            scenario.base_url = global_base_url

        for step in scenario.steps:
            if step.request.timeout is None:
                step.request.timeout = global_timeout

            step.request.headers = {
                **global_headers,
                **step.request.headers,
            }

            if step.expect.schema_data is None:
                continue

            raw_schema: dict[str, Any] | None = None

            if isinstance(step.expect.schema_data, dict):
                raw_schema = step.expect.schema_data

            elif isinstance(step.expect.schema_data, str):
                schema_file = path.parent / step.expect.schema_data

                if not schema_file.exists():
                    schema_file = Path(step.expect.schema_data)

                if not schema_file.exists():
                    raise ConfigCompilerError(
                        f"JSON Schema file not found: "
                        f"'{step.expect.schema_data}' "
                        f"(referenced in scenario '{scenario.name}', "
                        f"step '{step.name}')"
                    )

                try:
                    with schema_file.open("r", encoding="utf-8") as file:
                        raw_schema = json.load(file)
                except (OSError, json.JSONDecodeError) as err:
                    raise ConfigCompilerError(
                        f"Failed to read JSON schema file "
                        f"'{step.expect.schema_data}': {err}"
                    ) from err

            if raw_schema is None:  # pragma: no cover
                raise ConfigCompilerError(
                    f"Invalid schema configuration in scenario "
                    f"'{scenario.name}', step '{step.name}'."
                )

            try:
                compiled = fastjsonschema.compile(raw_schema)
                step.expect._compiled_schema = cast(
                    Callable[[Any], Any],
                    compiled,
                )
            except Exception as err:
                raise ConfigCompilerError(
                    f"Failed to compile JSON schema in "
                    f"scenario '{scenario.name}', "
                    f"step '{step.name}': {err}"
                ) from err

    return config
