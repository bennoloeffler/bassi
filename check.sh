#!/bin/bash
# Quality assurance pipeline for bassi


echo "============================================="
echo "Running Quality Assurance Pipeline"
echo "============================================="

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
echo "4. Running All Tests (pytest)..."
echo "   • V1 tests: tests/"
echo "   • V3 tests: bassi/core_v3/tests/"
uv run pytest

echo ""
echo "============================================="
echo "✅ All quality checks passed!"
echo "============================================="
echo ""
echo "Test Summary:"
uv run pytest --collect-only -q | tail -5
