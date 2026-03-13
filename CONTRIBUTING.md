# Contributing to py-unifiapi

## Development Setup

```bash
# Clone the repo
git clone https://github.com/seidnerj/py-unifiapi.git
cd py-unifiapi

# Install dependencies (requires uv)
uv sync --group dev

# Install pre-commit hooks
uv run pre-commit install
```

## Code Style

- Formatting is enforced by [ruff](https://docs.astral.sh/ruff/) (line-length=150, single quotes)
- All imports at the top of the file (stdlib, then third-party, then local)
- Type hints for function parameters and return values
- Constants in ALL_CAPS, classes in CamelCase, functions/variables in snake_case

## Testing

Every change must include corresponding tests:

```bash
# Run all tests
uv run pytest tests/ -v

# Run a specific test file
uv run pytest tests/ssh/test_session.py -v
```

Tests use `pytest` with `pytest-asyncio` (auto mode). Mock external dependencies with `unittest.mock.AsyncMock`.

## Pre-commit Hooks

The following checks run automatically on commit:

- **ruff lint** - Python linting with auto-fix
- **ruff format** - Code formatting
- **detect-secrets** - Scan for accidentally committed secrets
- **trailing-whitespace** - Trim trailing whitespace
- **end-of-file-fixer** - Ensure files end with newline
- **mixed-line-ending** - Normalize to LF
- **check-merge-conflict** - Check for merge conflict strings
- **check-added-large-files** - Prevent large files from being committed
- **check-ast** - Validate Python syntax
- **check-builtin-literals** - Forbid builtin type constructor calls when literals are available
- **debug-statements** - Check for debugger imports and breakpoint() calls
- **check-json** - Verify JSON syntax
- **check-yaml** - Verify YAML syntax
- **pretty-format-json** - Auto-format JSON files
- **mypy** - Type checking
- **basedpyright** - Type checking
- **check-claude-attribution** - Prevent commits with Claude attribution (commit-msg stage)

Run all hooks manually:

```bash
uv run pre-commit run --all-files
```

## Pull Requests

1. Create a feature branch from `main`
2. Make your changes with tests
3. Ensure all pre-commit hooks pass
4. Submit a PR with a clear description of the change
