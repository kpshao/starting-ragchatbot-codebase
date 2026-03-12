#!/bin/bash
# Run linting checks with ruff and auto-fix issues

set -e

echo "🔧 Running ruff linter with auto-fix..."
uv run ruff check --fix backend/ main.py

echo "✅ Linting and auto-fix complete!"
