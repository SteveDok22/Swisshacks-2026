.PHONY: help install dev test lint format clean

help:
	@echo "Available commands:"
	@echo "  install   - Install dependencies via uv"
	@echo "  dev       - Run dev server with auto-reload"
	@echo "  test      - Run tests"
	@echo "  lint      - Check code quality"
	@echo "  format    - Auto-format code"
	@echo "  clean     - Remove cache and build artifacts"

install:
	uv venv
	uv pip install -r pyproject.toml --extra dev

dev:
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	uv run pytest -v

lint:
	uv run ruff check app/
	uv run mypy app/

format:
	uv run ruff format app/
	uv run ruff check --fix app/

clean:
	rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
