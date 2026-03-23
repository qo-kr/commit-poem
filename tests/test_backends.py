from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from commitpoem.backends import (
    AnthropicBackend,
    OpenAIBackend,
    _BACKENDS,
    _build_prompt,
    get_backend,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

API_KEY = "test-api-key"
MODEL = "test-model"
COMMITS = ["feat: add login", "fix: broken navbar", "chore: bump deps"]


def _make_anthropic_mock() -> MagicMock:
    """Return a mock Anthropic constructor whose client returns a text response."""
    text_mock = MagicMock()
    text_mock.text = "roses are red"
    content_mock = MagicMock()
    content_mock.__getitem__ = MagicMock(return_value=text_mock)
    resp_mock = MagicMock()
    resp_mock.content = content_mock
    client_mock = MagicMock()
    client_mock.messages.create.return_value = resp_mock
    constructor_mock = MagicMock(return_value=client_mock)
    return constructor_mock


def _make_openai_mock() -> MagicMock:
    """Return a mock OpenAI constructor whose client returns a message response."""
    message_mock = MagicMock()
    message_mock.content = "violets are blue"
    choice_mock = MagicMock()
    choice_mock.message = message_mock
    resp_mock = MagicMock()
    resp_mock.choices = [choice_mock]
    client_mock = MagicMock()
    client_mock.chat.completions.create.return_value = resp_mock
    constructor_mock = MagicMock(return_value=client_mock)
    return constructor_mock


# ---------------------------------------------------------------------------
# Factory: get_backend
# ---------------------------------------------------------------------------

class TestGetBackend:
    def test_anthropic_returns_anthropic_backend(self) -> None:
        assert isinstance(get_backend("anthropic", API_KEY), AnthropicBackend)

    def test_openai_returns_openai_backend(self) -> None:
        assert isinstance(get_backend("openai", API_KEY), OpenAIBackend)

    def test_unsupported_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            get_backend("gemini", API_KEY)

    def test_unsupported_message_contains_anthropic(self) -> None:
        with pytest.raises(ValueError, match="anthropic"):
            get_backend("gemini", API_KEY)

    def test_unsupported_message_contains_openai(self) -> None:
        with pytest.raises(ValueError, match="openai"):
            get_backend("gemini", API_KEY)

    def test_empty_string_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            get_backend("", API_KEY)

    def test_none_raises_value_error(self) -> None:
        with pytest.raises((ValueError, TypeError)):
            get_backend(None, API_KEY)  # type: ignore[arg-type]

    def test_mixed_case_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            get_backend("Anthropic", API_KEY)

    def test_returns_independent_instances(self) -> None:
        b1 = get_backend("anthropic", API_KEY)
        b2 = get_backend("anthropic", API_KEY)
        assert b1 is not b2

    def test_two_calls_both_correct_type(self) -> None:
        ab = get_backend("anthropic", API_KEY)
        ob = get_backend("openai", API_KEY)
        assert isinstance(ab, AnthropicBackend)
        assert isinstance(ob, OpenAIBackend)


# ---------------------------------------------------------------------------
# _BACKENDS registry
# ---------------------------------------------------------------------------

class TestBackendsRegistry:
    def test_anthropic_in_registry(self) -> None:
        assert "anthropic" in _BACKENDS

    def test_openai_in_registry(self) -> None:
        assert "openai" in _BACKENDS

    def test_anthropic_maps_to_class(self) -> None:
        assert _BACKENDS["anthropic"] is AnthropicBackend

    def test_openai_maps_to_class(self) -> None:
        assert _BACKENDS["openai"] is OpenAIBackend


# ---------------------------------------------------------------------------
# AnthropicBackend.generate_poem
# ---------------------------------------------------------------------------

class TestAnthropicBackend:
    def test_returns_text_from_response(self) -> None:
        constructor_mock = _make_anthropic_mock()
        with patch("commitpoem.backends.Anthropic", constructor_mock):
            backend = AnthropicBackend(api_key=API_KEY)
            result = backend.generate_poem(COMMITS, MODEL)
        assert result == "roses are red"

    def test_passes_api_key_to_constructor(self) -> None:
        constructor_mock = _make_anthropic_mock()
        with patch("commitpoem.backends.Anthropic", constructor_mock):
            backend = AnthropicBackend(api_key=API_KEY)
            backend.generate_poem(COMMITS, MODEL)
        constructor_mock.assert_called_once_with(api_key=API_KEY)

    def test_calls_messages_create_with_model(self) -> None:
        constructor_mock = _make_anthropic_mock()
        with patch("commitpoem.backends.Anthropic", constructor_mock):
            backend = AnthropicBackend(api_key=API_KEY)
            backend.generate_poem(COMMITS, MODEL)
        client_mock = constructor_mock.return_value
        call_kwargs = client_mock.messages.create.call_args
        assert call_kwargs.kwargs.get("model") == MODEL or call_kwargs.args[0] == MODEL

    def test_calls_messages_create_with_user_role(self) -> None:
        constructor_mock = _make_anthropic_mock()
        with patch("commitpoem.backends.Anthropic", constructor_mock):
            backend = AnthropicBackend(api_key=API_KEY)
            backend.generate_poem(COMMITS, MODEL)
        client_mock = constructor_mock.return_value
        call_kwargs = client_mock.messages.create.call_args
        messages = call_kwargs.kwargs.get("messages", [])
        assert len(messages) >= 1
        assert messages[0]["role"] == "user"

    def test_calls_messages_create_with_max_tokens(self) -> None:
        constructor_mock = _make_anthropic_mock()
        with patch("commitpoem.backends.Anthropic", constructor_mock):
            backend = AnthropicBackend(api_key=API_KEY)
            backend.generate_poem(COMMITS, MODEL)
        client_mock = constructor_mock.return_value
        call_kwargs = client_mock.messages.create.call_args
        assert "max_tokens" in call_kwargs.kwargs

    def test_empty_commits_does_not_raise(self) -> None:
        constructor_mock = _make_anthropic_mock()
        with patch("commitpoem.backends.Anthropic", constructor_mock):
            backend = AnthropicBackend(api_key=API_KEY)
            result = backend.generate_poem([], MODEL)
        assert isinstance(result, str)

    def test_result_is_string(self) -> None:
        constructor_mock = _make_anthropic_mock()
        with patch("commitpoem.backends.Anthropic", constructor_mock):
            backend = AnthropicBackend(api_key=API_KEY)
            result = backend.generate_poem(COMMITS, MODEL)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# OpenAIBackend.generate_poem
# ---------------------------------------------------------------------------

class TestOpenAIBackend:
    def test_returns_content_from_response(self) -> None:
        constructor_mock = _make_openai_mock()
        with patch("commitpoem.backends.OpenAI", constructor_mock):
            backend = OpenAIBackend(api_key=API_KEY)
            result = backend.generate_poem(COMMITS, MODEL)
        assert result == "violets are blue"

    def test_passes_api_key_to_constructor(self) -> None:
        constructor_mock = _make_openai_mock()
        with patch("commitpoem.backends.OpenAI", constructor_mock):
            backend = OpenAIBackend(api_key=API_KEY)
            backend.generate_poem(COMMITS, MODEL)
        constructor_mock.assert_called_once_with(api_key=API_KEY)

    def test_calls_chat_completions_create_with_model(self) -> None:
        constructor_mock = _make_openai_mock()
        with patch("commitpoem.backends.OpenAI", constructor_mock):
            backend = OpenAIBackend(api_key=API_KEY)
            backend.generate_poem(COMMITS, MODEL)
        client_mock = constructor_mock.return_value
        call_kwargs = client_mock.chat.completions.create.call_args
        assert call_kwargs.kwargs.get("model") == MODEL or call_kwargs.args[0] == MODEL

    def test_calls_chat_completions_create_with_user_role(self) -> None:
        constructor_mock = _make_openai_mock()
        with patch("commitpoem.backends.OpenAI", constructor_mock):
            backend = OpenAIBackend(api_key=API_KEY)
            backend.generate_poem(COMMITS, MODEL)
        client_mock = constructor_mock.return_value
        call_kwargs = client_mock.chat.completions.create.call_args
        messages = call_kwargs.kwargs.get("messages", [])
        assert len(messages) >= 1
        assert messages[0]["role"] == "user"

    def test_empty_commits_does_not_raise(self) -> None:
        constructor_mock = _make_openai_mock()
        with patch("commitpoem.backends.OpenAI", constructor_mock):
            backend = OpenAIBackend(api_key=API_KEY)
            result = backend.generate_poem([], MODEL)
        assert isinstance(result, str)

    def test_result_is_string(self) -> None:
        constructor_mock = _make_openai_mock()
        with patch("commitpoem.backends.OpenAI", constructor_mock):
            backend = OpenAIBackend(api_key=API_KEY)
            result = backend.generate_poem(COMMITS, MODEL)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# _build_prompt helper
# ---------------------------------------------------------------------------

class TestBuildPrompt:
    def test_includes_commits(self) -> None:
        prompt = _build_prompt(["feat: login"])
        assert "feat: login" in prompt

    def test_empty_commits_no_crash(self) -> None:
        prompt = _build_prompt([])
        assert isinstance(prompt, str)

    def test_multiple_commits_all_included(self) -> None:
        commits = ["fix: bug", "chore: lint"]
        prompt = _build_prompt(commits)
        for c in commits:
            assert c in prompt
