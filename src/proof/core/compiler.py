from pathlib import Path

import fastjsonschema
import yaml
from pydantic import ValidationError

from proof.core.config import ProofConfig


class ConfigCompilerError(Exception):
    """Raised when configuration loading or JSON schema compilation fails."""


def load_and_compile_config(config_path: str | Path) -> ProofConfig:
    """Loads a YAML config file, validates it via Pydantic, and pre-compiles all

    JSON Schemas ahead of runtime execution.
    """
    path = Path(config_path)

    if not path.exists():
        raise ConfigCompilerError(f"Configuration file not found: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            raw_data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigCompilerError(f"Invalid YAML syntax in {path}: {e}") from e

    if not isinstance(raw_data, dict):
        raise ConfigCompilerError(
            f"Invalid format in {path}. Expected a top-level YAML mapping."
        )

    try:
        config = ProofConfig.model_validate(raw_data)
    except ValidationError as e:
        raise ConfigCompilerError(f"Config validation failed:\n{e}") from e

    for scenario in config.scenarios:
        for step in scenario.steps:
            if step.expect.json_schema:
                try:
                    step.expect.compiled_schema = fastjsonschema.compile(
                        step.expect.json_schema
                    )
                except Exception as e:
                    raise ConfigCompilerError(
                        f"Failed to compile JSON schema in scenario '{scenario.name}', "
                        f"step '{step.name}': {e}"
                    ) from e

    return config
