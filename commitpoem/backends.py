from __future__ import annotations

from typing import Protocol

from anthropic import Anthropic
from openai import OpenAI


class LLMBackend(Protocol):
    """Structural protocol all LLM backend classes must satisfy."""

    def generate_poem(self, commits: list[str], model: str) -> str:
        """Generate a poem from a list of commit messages using the given model."""
        ...


def _build_prompt(commits: list[str]) -> str:
    """Format a list of commit message strings into a single prompt string."""
    if not commits:
        commits_text = "(no commits)"
    else:
        commits_text = "\n".join(f"- {c}" for c in commits)
    return (
        "Write a short, creative poem inspired by the following git commit messages:\n\n"
        f"{commits_text}\n\n"
        "The poem should capture the essence of the work done."
    )


class AnthropicBackend:
    """LLM backend that uses the Anthropic API to generate poems."""

    def __init__(self, api_key: str) -> None:
        """Initialise with the given Anthropic API key."""
        self._api_key = api_key

    def generate_poem(self, commits: list[str], model: str) -> str:
        """Generate a poem from commit messages using the specified Anthropic model."""
        prompt = _build_prompt(commits)
        client = Anthropic(api_key=self._api_key)
        resp = client.messages.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
        )
        return resp.content[0].text


class OpenAIBackend:
    """LLM backend that uses the OpenAI API to generate poems."""

    def __init__(self, api_key: str) -> None:
        """Initialise with the given OpenAI API key."""
        self._api_key = api_key

    def generate_poem(self, commits: list[str], model: str) -> str:
        """Generate a poem from commit messages using the specified OpenAI model."""
        prompt = _build_prompt(commits)
        client = OpenAI(api_key=self._api_key)
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content


_BACKENDS: dict[str, type] = {
    "anthropic": AnthropicBackend,
    "openai": OpenAIBackend,
}


def get_backend(name: str, api_key: str) -> LLMBackend:
    """Return an LLMBackend instance for the given backend name and API key.

    Raises:
        ValueError: If *name* is not a supported backend name.
    """
    if name not in _BACKENDS:
        supported = ", ".join(sorted(_BACKENDS.keys()))
        raise ValueError(
            f"Unsupported backend {name!r}. Supported backends: {supported}"
        )
    backend_cls = _BACKENDS[name]
    return backend_cls(api_key=api_key)
