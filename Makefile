.PHONY: install test lint typecheck run-example run-sample build clean

install:
	uv sync --group dev

test:
	uv run pytest tests/

lint:
	uv run ruff check src/ tests/

typecheck:
	uv run pyright

run-example:
	uv run proof run scenarios/example.yaml --once

run-sample:
	uv run proof run scenarios/sample.yaml --once

build:
	uv build

clean:
	rm -rf dist/ .ruff_cache/ .pytest_cache/
