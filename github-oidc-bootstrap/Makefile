# GitHub OIDC Bootstrap - Simplified Development Commands
# Use direct uv and CDK commands for deployment

.PHONY: help install test lint format clean

# Default target
help:
	@echo "Simplified GitHub OIDC Bootstrap Commands:"
	@echo ""
	@echo "Setup:"
	@echo "  install     Install dependencies using uv"
	@echo ""
	@echo "Development:"
	@echo "  test        Run tests"
	@echo "  lint        Run linting"
	@echo "  format      Format code"
	@echo ""
	@echo "Deployment (use direct commands):"
	@echo "  uv run cdk synth                              # Synthesize templates"
	@echo "  uv run cdk deploy --profile infiquetra-root   # Deploy stack"
	@echo "  uv run cdk destroy --profile infiquetra-root  # Destroy stack"
	@echo ""
	@echo "Utilities:"
	@echo "  clean       Clean up generated files"

# Install dependencies
install:
	@echo "Installing dependencies with uv..."
	uv sync --dev
	@echo "Dependencies installed successfully"

# Run tests
test:
	@echo "Running tests..."
	uv run pytest tests/ -v --cov=github_oidc_bootstrap --cov-report=term-missing

# Run linting
lint:
	@echo "Running linting..."
	uv run ruff check .
	uv run mypy .

# Format code
format:
	@echo "Formatting code..."
	uv run ruff format .
	uv run ruff check --fix .

# Clean up generated files
clean:
	@echo "Cleaning up..."
	rm -rf cdk.out/
	rm -rf .pytest_cache/
	rm -rf __pycache__/
	rm -rf .coverage
	rm -rf .mypy_cache/
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	@echo "Clean up completed"