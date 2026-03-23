<!-- dokkaebi:generated -->
# CLAUDE.md — commitpoem

Claude companion notes. Follow AGENTS.md and the human. Keep changes small. Read before editing.

## Project Snapshot
- Project: `commitpoem`
- Language: Python (`python`)
- Manifest: `pyproject.toml`
- Build tool: `hatchling`
- Package manager: `pip`
- Test framework: `pytest`

## Project Map
- Source code lives in `commitpoem/`
- Use these source roots only. Do not add new top-level packages.

## Entry Points
- `commitpoem`: `commitpoem.cli:main`

## Frameworks
- None detected

## Coding Conventions
- Preserve the repository's existing style and naming.
- Keep diffs small, targeted, and reviewable.
- Add or update tests with every behavior change.
- Reuse existing modules and utilities before adding abstractions.

Language-specific conventions:
- Style: PEP 8, 120 char line limit
- Type hints: required on all public APIs
- Imports: `from __future__ import annotations` at top
- Packaging: pyproject.toml (PEP 621)
- Test: pytest with fixtures
- Lint/format: ruff

## Development Workflow
- Read existing files before editing them.
- Preserve human instructions unless explicitly asked to replace them.
- Use the smallest safe change that satisfies the task.
- Verify with targeted tests and lint before claiming completion.
- Refresh generated files only when the marker is present.

## Testing Checklist
- Test directory: `tests/`
- Test framework: `pytest`
- Run targeted tests first, then the broader suite.
- Cover new behavior with tests before handoff.
- Suggested checks: `pytest -q` and `ruff check .`

## Helpful Commands
- `uv venv`
- `uv pip install -e '.[dev]'`
- `pytest`
- `dokkaebi scan`
- `dokkaebi intake <requirements-file>`
- `dokkaebi reconcile`

## Update Policy
- Generated files include the `<!-- dokkaebi:generated -->` marker.
- Dokkaebi may refresh these files during `scan` when the marker is present.
- Remove the marker to opt out of future refreshes.
