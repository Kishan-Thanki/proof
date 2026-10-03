"""AOT Schema Compiler for Proof scenario configurations.

This module provides functions to load YAML scenario files, validate them against
Pydantic data models, inherit global defaults, and pre-compile JSON Schema files
or inline schema dictionaries into executable Python validation functions.
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import fastjsonschema
import yaml
from pydantic import ValidationError

from proof.core.config import GlobalConfig, ProofConfig


class ConfigCompilerError(Exception):
    """Raised when configuration loading or JSON schema compilation fails."""


def load_and_compile_config(config_path: str | Path) -> ProofConfig:
    """Loads a YAML config file, validates via Pydantic, applies inheritance, and compiles schemas.

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        ProofConfig: Validated scenario configuration object with attached AOT schema functions.

    Raises:
        ConfigCompilerError: If file reading, YAML parsing, Pydantic validation,
            base_url resolution, or JSON schema compilation fails.
    """
    path = Path(config_path).resolve()

    if not path.exists():
        raise ConfigCompilerError(f"Configuration file not found: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            raw_data = yaml.safe_load(f)
    except yaml.YAMLError as err:
        raise ConfigCompilerError(f"Invalid YAML syntax in {path}: {err}") from err

    if not isinstance(raw_data, dict):
        raise ConfigCompilerError(
            f"Invalid format in {path}. Expected a top-level YAML mapping."
        )

    try:
        config = ProofConfig.model_validate(raw_data)
    except ValidationError as err:
        raise ConfigCompilerError(f"Config validation failed:\n{err}") from err

    global_config = config.global_config or GlobalConfig()

    global_base_url = str(global_config.base_url) if global_config.base_url else None
    global_timeout = global_config.timeout_seconds

    # Resolve scenario inheritance and compile JSON schemas ahead-of-time (AOT)
    for scenario in config.scenarios:
        # Inherit base_url from global if not specified on scenario
        if not scenario.base_url:
            if global_base_url:
                scenario.base_url = global_base_url
            else:
                raise ConfigCompilerError(
                    f"Scenario '{scenario.name}' is missing 'base_url' "
                    "and no global 'base_url' is defined."
                )

        for step in scenario.steps:
            # Inherit default timeout if step timeout is not set
            if step.request.timeout is None:
                step.request.timeout = global_timeout

            # Process schema compilation if schema rule exists
            if step.expect.schema_data:
                raw_schema: dict[str, Any] | None = None

                if isinstance(step.expect.schema_data, dict):
                    raw_schema = step.expect.schema_data

                elif isinstance(step.expect.schema_data, str):
                    schema_file = path.parent / step.expect.schema_data

                    if not schema_file.exists():
                        schema_file = Path(step.expect.schema_data)

                    if not schema_file.exists():
                        raise ConfigCompilerError(
                            f"JSON Schema file not found: '{step.expect.schema_data}' "
                            f"(referenced in scenario '{scenario.name}', "
                            f"step '{step.name}')"
                        )

                    try:
                        with open(schema_file, "r", encoding="utf-8") as sf:
                            raw_schema = json.load(sf)
                    except Exception as err:
                        raise ConfigCompilerError(
                            f"Failed to read JSON schema file "
                            f"'{step.expect.schema_data}': {err}"
                        ) from err

                if raw_schema:
                    try:
                        compiled = fastjsonschema.compile(raw_schema)
                        step.expect.compiled_schema = cast(
                            Callable[[Any], Any], compiled
                        )
                    except Exception as err:
                        raise ConfigCompilerError(
                            f"Failed to compile JSON schema in "
                            f"scenario '{scenario.name}', "
                            f"step '{step.name}': {err}"
                        ) from err

    return config
