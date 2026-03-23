from __future__ import annotations

from commitpoem.backends import LLMBackend


def generate_poem(commits: list[str], backend: LLMBackend, model: str) -> str:
    """Generate a poem from commit messages using the given backend and model.

    Delegates unconditionally to ``backend.generate_poem(commits, model)``.  When
    *commits* is empty the backend's prompt builder substitutes ``(no commits)``
    automatically, so no special branching is required here.

    Args:
        commits: List of git commit message strings (may be empty).
        backend: An :class:`~commitpoem.backends.LLMBackend` implementation.
        model:   Model identifier forwarded as-is to the backend.

    Returns:
        A non-empty poem string produced by the backend.

    Raises:
        ValueError: If the backend returns an empty or whitespace-only string.
    """
    result: str = backend.generate_poem(commits, model)
    if not result.strip():
        raise ValueError("backend returned an empty poem")
    return result
