#!/bin/bash
# Pre-commit hook to run code quality checks
# Install: ln -s ../../scripts/pre-commit.sh .git/hooks/pre-commit

set -e

echo "🔍 Running pre-commit quality checks..."

# Get list of staged Python files
STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep '\.py$' || true)

if [ -z "$STAGED_FILES" ]; then
    echo "No Python files staged, skipping checks"
    exit 0
fi

echo "Checking ${STAGED_FILES}"

# Run black
echo "1️⃣  Formatting with black..."
uv run black $STAGED_FILES

# Run ruff
echo "2️⃣  Linting with ruff..."
uv run ruff check --fix $STAGED_FILES

# Re-add files that were formatted
git add $STAGED_FILES

echo "✅ Pre-commit checks passed!"
