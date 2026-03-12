# Development Scripts

This directory contains scripts for code quality and development workflows.

## Available Scripts

### Code Quality

- **format.sh** - Format code with black
- **lint.sh** - Run ruff linter (check only)
- **lint-fix.sh** - Run ruff linter with auto-fix
- **typecheck.sh** - Run mypy type checker
- **quality.sh** - Run all quality checks (format + lint + typecheck + tests)

### Git Hooks

- **pre-commit.sh** - Pre-commit hook that auto-formats and lints staged files

## Usage

All scripts should be run from the project root:

```bash
# Run individual checks
./scripts/format.sh
./scripts/lint.sh
./scripts/typecheck.sh

# Run all checks
./scripts/quality.sh
```

## Installing Pre-commit Hook

To automatically format and lint code before each commit:

```bash
ln -s ../../scripts/pre-commit.sh .git/hooks/pre-commit
```

This will:
1. Format staged Python files with black
2. Lint and auto-fix issues with ruff
3. Re-stage the formatted files
4. Prevent commit if there are unfixable issues
