.PHONY: install test coverage coverage-html lint format typecheck check \
	run-example run-sample run-exhaustive build clean

install:
	uv sync --group dev

test:
	uv run pytest -q

coverage:
	uv run pytest -q --cov=proof --cov-branch \
		--cov-report=term-missing \
		--cov-fail-under=100

coverage-html:
	uv run pytest -q --cov=proof --cov-branch \
		--cov-report=html
	@echo "Coverage report generated: htmlcov/index.html"

lint:
	uv run ruff check src/ tests/

format:
	uv run ruff format src/ tests/
	uv run ruff check --fix src/ tests/

format-check:
	uv run ruff format --check src/ tests/

typecheck:
	uv run pyright

check: lint format-check typecheck coverage

run-example:
	uv run proof run scenarios/example.yaml --once

run-sample:
	uv run proof run scenarios/sample.yaml --once

run-exhaustive:
	uv run proof run scenarios/exhaustive.yaml --once

build:
	uv build

clean:
	rm -rf dist/ \
		.ruff_cache/ \
		.pytest_cache/ \
		.pyright_cache/ \
		.coverage \
		.coverage.* \
		htmlcov/ \
		__pycache__/ \
		*.egg-info/

