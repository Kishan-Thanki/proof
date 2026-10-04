.PHONY: install test coverage coverage-html lint format typecheck check run-example run-sample build clean

install:
	uv sync --group dev

test:
	uv run pytest tests/

coverage:
	uv run pytest --cov=proof --cov-report=term-missing --cov-fail-under=100

coverage-html:
	uv run pytest --cov=proof --cov-report=html
	@echo "Coverage report generated: htmlcov/index.html"

lint:
	uv run ruff check src/ tests/

format:
	uv run ruff format src/ tests/
	uv run ruff check --fix src/ tests/

typecheck:
	uv run pyright

check: lint typecheck test

run-example:
	uv run proof run scenarios/example.yaml --once

run-sample:
	uv run proof run scenarios/sample.yaml --once

build:
	uv build

clean:
	rm -rf dist/ .ruff_cache/ .pytest_cache/ .pyright_cache/ .coverage htmlcov/ .coverage.*
