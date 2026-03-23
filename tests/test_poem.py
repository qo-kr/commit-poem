from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from commitpoem.backends import LLMBackend
from commitpoem.poem import generate_poem


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODEL = "test-model"
COMMITS = ["feat: add login", "fix: broken navbar", "chore: bump deps"]
POEM = "roses are red, violets are blue"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGeneratePoem:
    # --- happy path: non-empty commits ---

    def test_non_empty_commits_returns_str(self) -> None:
        backend = MagicMock(spec=LLMBackend)
        backend.generate_poem.return_value = POEM
        result = generate_poem(COMMITS, backend, MODEL)
        assert isinstance(result, str)

    def test_non_empty_commits_returns_non_empty_str(self) -> None:
        backend = MagicMock(spec=LLMBackend)
        backend.generate_poem.return_value = POEM
        result = generate_poem(COMMITS, backend, MODEL)
        assert result != ""

    def test_non_empty_commits_returns_backend_value(self) -> None:
        backend = MagicMock(spec=LLMBackend)
        backend.generate_poem.return_value = POEM
        result = generate_poem(COMMITS, backend, MODEL)
        assert result == POEM

    # --- happy path: empty commits ---

    def test_empty_commits_does_not_raise(self) -> None:
        backend = MagicMock(spec=LLMBackend)
        backend.generate_poem.return_value = POEM
        result = generate_poem([], backend, MODEL)
        assert isinstance(result, str)

    def test_empty_commits_returns_non_empty_str(self) -> None:
        backend = MagicMock(spec=LLMBackend)
        backend.generate_poem.return_value = POEM
        result = generate_poem([], backend, MODEL)
        assert result != ""

    def test_empty_commits_returns_backend_value(self) -> None:
        backend = MagicMock(spec=LLMBackend)
        backend.generate_poem.return_value = POEM
        result = generate_poem([], backend, MODEL)
        assert result == POEM

    # --- delegation: backend is called exactly once ---

    def test_backend_called_exactly_once(self) -> None:
        backend = MagicMock(spec=LLMBackend)
        backend.generate_poem.return_value = POEM
        generate_poem(COMMITS, backend, MODEL)
        backend.generate_poem.assert_called_once()

    def test_backend_called_with_commits(self) -> None:
        backend = MagicMock(spec=LLMBackend)
        backend.generate_poem.return_value = POEM
        generate_poem(COMMITS, backend, MODEL)
        backend.generate_poem.assert_called_once_with(COMMITS, MODEL)

    def test_backend_called_with_empty_commits(self) -> None:
        backend = MagicMock(spec=LLMBackend)
        backend.generate_poem.return_value = POEM
        generate_poem([], backend, MODEL)
        backend.generate_poem.assert_called_once_with([], MODEL)

    def test_model_forwarded_as_is(self) -> None:
        backend = MagicMock(spec=LLMBackend)
        backend.generate_poem.return_value = POEM
        custom_model = "claude-3-haiku-20240307"
        generate_poem(COMMITS, backend, custom_model)
        _, call_model = backend.generate_poem.call_args.args
        assert call_model == custom_model

    # --- guard: backend returns empty or whitespace ---

    def test_empty_return_raises_value_error(self) -> None:
        backend = MagicMock(spec=LLMBackend)
        backend.generate_poem.return_value = ""
        with pytest.raises(ValueError):
            generate_poem(COMMITS, backend, MODEL)

    def test_whitespace_only_return_raises_value_error(self) -> None:
        backend = MagicMock(spec=LLMBackend)
        backend.generate_poem.return_value = "\n\t   "
        with pytest.raises(ValueError):
            generate_poem(COMMITS, backend, MODEL)

    # --- error propagation ---

    def test_backend_exception_propagates(self) -> None:
        backend = MagicMock(spec=LLMBackend)
        backend.generate_poem.side_effect = RuntimeError("API down")
        with pytest.raises(RuntimeError, match="API down"):
            generate_poem(COMMITS, backend, MODEL)

    def test_backend_exception_propagates_for_empty_commits(self) -> None:
        backend = MagicMock(spec=LLMBackend)
        backend.generate_poem.side_effect = RuntimeError("API down")
        with pytest.raises(RuntimeError, match="API down"):
            generate_poem([], backend, MODEL)

    # --- type errors ---

    def test_none_commits_raises_type_error(self) -> None:
        backend = MagicMock(spec=LLMBackend)
        backend.generate_poem.side_effect = TypeError("commits must be a list")
        with pytest.raises(TypeError):
            generate_poem(None, backend, MODEL)  # type: ignore[arg-type]

    # --- edge cases ---

    def test_single_commit_works(self) -> None:
        backend = MagicMock(spec=LLMBackend)
        backend.generate_poem.return_value = POEM
        result = generate_poem(["fix: typo"], backend, MODEL)
        assert result == POEM

    def test_commits_with_special_characters_passed_verbatim(self) -> None:
        backend = MagicMock(spec=LLMBackend)
        backend.generate_poem.return_value = POEM
        special = ["feat: 🚀 launch", "fix: café unicode", "chore: $path & env"]
        generate_poem(special, backend, MODEL)
        backend.generate_poem.assert_called_once_with(special, MODEL)
