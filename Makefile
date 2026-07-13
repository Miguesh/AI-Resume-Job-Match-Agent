.DEFAULT_GOAL := help

.PHONY: help install format lint typecheck test test-unit test-integration coverage ci run migrate docker-up docker-down

help: ## Show available commands
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make <target>\n\nTargets:\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  %-18s %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

install: ## Install runtime and development dependencies
	uv sync --all-groups

format: ## Format source and tests
	uv run ruff format src tests alembic
	uv run ruff check --fix src tests alembic

lint: ## Run static lint checks
	uv run ruff format --check src tests alembic
	uv run ruff check src tests alembic

typecheck: ## Run strict type checking
	uv run mypy src

test: ## Run all tests that do not require external credentials
	uv run pytest -m "not external"

test-unit: ## Run unit tests
	uv run pytest tests/unit

test-integration: ## Run integration tests
	uv run pytest -m integration

coverage: ## Run tests with the coverage quality gate
	uv run pytest -m "not external" --cov --cov-report=term-missing --cov-report=xml

ci: lint typecheck coverage ## Run the complete local CI suite

run: ## Start the development server
	uv run uvicorn resume_matcher.main:app --reload

migrate: ## Apply database migrations
	uv run alembic upgrade head

docker-up: ## Build and start the application stack
	docker compose up --build -d

docker-down: ## Stop the application stack
	docker compose down
