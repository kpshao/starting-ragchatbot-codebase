#!/bin/bash
# Run all code quality checks

set -e

echo "🚀 Running code quality checks..."
echo ""

# Format code
echo "1️⃣  Formatting code..."
uv run black backend/ main.py
echo ""

# Run linter with auto-fix
echo "2️⃣  Running linter..."
uv run ruff check --fix backend/ main.py
echo ""

echo "✅ Code quality checks passed!"
echo ""
echo "Additional checks available:"
echo "  - Type checking: ./scripts/typecheck.sh (has known issues)"
echo "  - Run tests: cd backend && uv run pytest"
