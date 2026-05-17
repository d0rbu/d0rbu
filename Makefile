.DEFAULT_GOAL := help
.PHONY: help setup lint format typecheck test cov check build clean precommit

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n",$$1,$$2}'

setup: ## Create the venv and install dev deps + hooks
	uv sync --extra dev
	uv run pre-commit install --install-hooks

lint: ## Ruff lint
	uv run ruff check .

format: ## Ruff format (write)
	uv run ruff format .

typecheck: ## ty type check
	uv run ty check

test: ## Run tests
	uv run pytest

cov: ## Tests with coverage (already enforced via addopts)
	uv run pytest

precommit: ## Run all pre-commit hooks
	uv run pre-commit run --all-files

check: lint typecheck test ## Lint + type + test (the CI gate)
	uv run ruff format --check .

build: ## Build sdist + wheel
	uv build

clean: ## Remove build/coverage artifacts
	rm -rf dist build .coverage coverage.xml htmlcov .pytest_cache .ruff_cache
