#!/bin/bash
# Quality assurance pipeline for bassi

set -e  # Exit on error

echo "==================================="
echo "Running Quality Assurance Pipeline"
echo "==================================="

echo ""
echo "1. Code Formatting (black)..."
uv run black .

echo ""
echo "2. Linting (ruff)..."
uv run ruff check --fix .

echo ""
echo "3. Type Checking (mypy)..."
uv run mypy bassi/

echo ""
echo "4. Running Tests (pytest)..."
uv run pytest

echo ""
echo "==================================="
echo "✅ All checks passed!"
echo "==================================="
