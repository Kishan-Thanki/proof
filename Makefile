.PHONY: install test coverage coverage-html lint format format-check typecheck check \
	run-profile run-auth run-chain run-crud build clean

install:
	uv sync --group dev

test:
	uv run pytest -q

coverage:
	uv run pytest -q --cov=proofrun --cov-branch \
		--cov-report=term-missing \
		--cov-fail-under=100

coverage-html:
	uv run pytest -q --cov=proofrun --cov-branch \
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

run-profile:
	uv run proofrun scenarios/profile.yaml --once

run-auth:
	uv run proofrun scenarios/auth.yaml --once

run-chain:
	uv run proofrun scenarios/chain.yaml --once

run-crud:
	uv run proofrun scenarios/crud.yaml --once

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
