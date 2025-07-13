#!/bin/bash
# Setup script for Infiquetra Organizations CDK project

PYTHON="${1:-python3.12}"

# Create virtual environment
echo "Creating Python virtual environment..."
$PYTHON -m venv .env

# Activate virtual environment
source .env/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install development tools
echo "Installing development tools..."
pip install flake8 black bandit isort ipython ipdb pytest

# Install AWS and CDK dependencies
echo "Installing AWS and CDK dependencies..."
pip install aws-cdk-lib constructs boto3

# Install additional tools
echo "Installing additional tools..."
pip install cfn-lint python-dotenv aws-lambda-powertools

echo "Setup complete! Activate the environment with: source .env/bin/activate"