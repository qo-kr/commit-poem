# commitpoem

A Python project

## Project Snapshot
- Project: `commitpoem`
- Language: Python (`python`)
- Manifest: `pyproject.toml`
- Build tool: `hatchling`
- Package manager: `pip`
- Test framework: `pytest`

## Layout
- Source code lives in `commitpoem/`
- Use these source roots only. Do not add new top-level packages.

## Entry Points
- `commitpoem`: `commitpoem.cli:main`

## Frameworks
- None detected

## Quick Commands
- `uv venv`
- `uv pip install -e '.[dev]'`
- `pytest`
- `dokkaebi scan`
- `dokkaebi intake <requirements-file>`
- `dokkaebi reconcile`

## Testing
- Test directory: `tests/`
- Test framework: `pytest`
- Run targeted tests first, then the broader suite.
- Cover new behavior with tests before handoff.
- Suggested checks: `pytest -q` and `ruff check .`
