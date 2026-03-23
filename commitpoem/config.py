from __future__ import annotations

import dataclasses
import os

__all__ = ["resolve_config", "AppConfig", "ConfigError"]

_VALID_BACKENDS: frozenset[str] = frozenset({"anthropic", "openai"})

_DEFAULT_MODEL: dict[str, str] = {
    "anthropic": "claude-3-5-haiku-20241022",
    "openai": "gpt-4o-mini",
}


class ConfigError(Exception):
    """Raised when required configuration is missing or invalid."""


@dataclasses.dataclass
class AppConfig:
    """Resolved application configuration."""

    github_token: str
    slack_webhook_url: str
    llm_api_key: str
    llm_backend: str
    llm_model: str


def _resolve(
    env_key: str,
    cli_value: str | None,
    *,
    required: bool = True,
    default: str | None = None,
) -> str | None:
    """Resolve a single config value using CLI > env > default precedence.

    Empty strings from both CLI and env are treated as absent.
    Returns None when nothing is found and *required* is False.
    """
    if cli_value is not None and cli_value != "":
        return cli_value

    env_val = os.environ.get(env_key, "")
    if env_val != "":
        return env_val

    if default is not None:
        return default

    return None


def resolve_config(
    *,
    github_token: str | None = None,
    slack_webhook_url: str | None = None,
    llm_api_key: str | None = None,
    llm_backend: str | None = None,
    llm_model: str | None = None,
) -> AppConfig:
    """Resolve all application configuration from CLI arguments and environment variables.

    CLI-provided keyword arguments take precedence over environment variables.
    Environment variables take precedence over built-in defaults.

    Args:
        github_token: CLI-provided GitHub personal access token.
        slack_webhook_url: CLI-provided Slack incoming webhook URL.
        llm_api_key: CLI-provided LLM API key.
        llm_backend: CLI-provided LLM backend name ('anthropic' or 'openai').
        llm_model: CLI-provided LLM model name.

    Returns:
        An AppConfig instance with all fields populated.

    Raises:
        ConfigError: When required credentials are missing or LLM_BACKEND is invalid.
    """
    missing: list[str] = []

    resolved_token = _resolve("GITHUB_TOKEN", github_token, required=True)
    if resolved_token is None:
        missing.append("GITHUB_TOKEN")

    resolved_webhook = _resolve("SLACK_WEBHOOK_URL", slack_webhook_url, required=True)
    if resolved_webhook is None:
        missing.append("SLACK_WEBHOOK_URL")

    resolved_api_key = _resolve("LLM_API_KEY", llm_api_key, required=True)
    if resolved_api_key is None:
        missing.append("LLM_API_KEY")

    if missing:
        raise ConfigError(f"Missing required config: {', '.join(missing)}")

    resolved_backend = _resolve("LLM_BACKEND", llm_backend, required=False, default="anthropic")
    assert resolved_backend is not None  # default ensures this

    if resolved_backend not in _VALID_BACKENDS:
        allowed = ", ".join(sorted(_VALID_BACKENDS))
        raise ConfigError(
            f"Invalid LLM_BACKEND {resolved_backend!r}; allowed: {allowed}"
        )

    default_model = _DEFAULT_MODEL.get(resolved_backend, "claude-3-5-haiku-20241022")
    resolved_model = _resolve("LLM_MODEL", llm_model, required=False, default=default_model)
    assert resolved_model is not None  # default ensures this

    return AppConfig(
        github_token=resolved_token,
        slack_webhook_url=resolved_webhook,
        llm_api_key=resolved_api_key,
        llm_backend=resolved_backend,
        llm_model=resolved_model,
    )
