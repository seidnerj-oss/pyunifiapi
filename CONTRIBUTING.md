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
- **trailing-whitespace** - Trim trailing whitespace
- **end-of-file-fixer** - Ensure files end with newline
- **mixed-line-ending** - Normalize to LF
- **check-ast** - Validate Python syntax
- **mypy** - Type checking

Run all hooks manually:

```bash
uv run pre-commit run --all-files
```

## Pull Requests

1. Create a feature branch from `main`
2. Make your changes with tests
3. Ensure all pre-commit hooks pass
4. Submit a PR with a clear description of the change
