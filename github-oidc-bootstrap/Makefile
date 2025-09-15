# GitHub OIDC Bootstrap CDK Project
# Development and deployment automation

.PHONY: help install test lint format check deploy destroy clean synth diff

# Default target
help:
	@echo "Available commands:"
	@echo "  install    Install dependencies using uv"
	@echo "  test       Run all tests"
	@echo "  lint       Run code linting"
	@echo "  format     Format code"
	@echo "  check      Run all quality checks (lint + test + security)"
	@echo "  synth      Synthesize CDK templates"
	@echo "  diff       Show CDK diff"
	@echo "  deploy     Deploy the stack"
	@echo "  destroy    Destroy the stack"
	@echo "  clean      Clean up generated files"

# Check if uv is installed
check-uv:
	@which uv > /dev/null || (echo "Error: uv is not installed. Please install uv first." && exit 1)

# Install dependencies
install: check-uv
	uv sync --dev
	@echo "Dependencies installed successfully"

# Run tests
test: check-uv
	uv run pytest tests/ -v --cov=github_oidc_bootstrap --cov-report=term-missing
	@echo "Tests completed"

# Run linting
lint: check-uv
	uv run ruff check .
	uv run mypy .
	@echo "Linting completed"

# Format code
format: check-uv
	uv run ruff format .
	uv run ruff check --fix .
	@echo "Code formatting completed"

# Security scan
security: check-uv
	uv run bandit -r github_oidc_bootstrap/
	@echo "Security scan completed"

# Run all quality checks
check: lint test security
	@echo "All quality checks passed"

# Synthesize CDK templates
synth: check-uv
	uv run cdk synth --all
	@echo "CDK synthesis completed"

# Validate CloudFormation templates
validate: synth
	uv run cfn-lint cdk.out/*.template.json
	@echo "CloudFormation validation completed"

# Show CDK diff
diff: check-uv
	uv run cdk diff
	@echo "CDK diff completed"

# Deploy stack (with confirmation)
deploy: check validate
	@echo "WARNING: This will deploy AWS resources that may incur costs."
	@read -p "Are you sure you want to proceed? (y/N): " confirm && [ "$$confirm" = "y" ]
	uv run cdk deploy --require-approval never
	@echo "Deployment completed"

# Destroy stack (with confirmation)
destroy: check-uv
	@echo "WARNING: This will destroy the GitHub OIDC stack and all its resources."
	@read -p "Are you sure you want to proceed? (y/N): " confirm && [ "$$confirm" = "y" ]
	uv run cdk destroy --force
	@echo "Stack destroyed"

# Clean up generated files
clean:
	rm -rf cdk.out/
	rm -rf .pytest_cache/
	rm -rf __pycache__/
	rm -rf .coverage
	rm -rf .mypy_cache/
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	@echo "Clean up completed"

# Bootstrap CDK (run once per account/region)
bootstrap: check-uv
	@echo "Bootstrapping CDK in the target account/region..."
	uv run cdk bootstrap
	@echo "CDK bootstrap completed"

# Show stack outputs
outputs: check-uv
	uv run cdk list --json | jq -r '.[] | select(.name=="GitHubOIDCBootstrap") | .outputs'
	@echo "Stack outputs displayed"