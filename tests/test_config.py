from __future__ import annotations

import pytest

from commitpoem.config import AppConfig, ConfigError, resolve_config


# ---------------------------------------------------------------------------
# Happy-path: env-only resolution
# ---------------------------------------------------------------------------


def test_env_only_resolution(full_env: dict[str, str]) -> None:
    cfg = resolve_config()
    assert cfg.github_token == full_env["GITHUB_TOKEN"]
    assert cfg.slack_webhook_url == full_env["SLACK_WEBHOOK_URL"]
    assert cfg.llm_api_key == full_env["LLM_API_KEY"]
    assert cfg.llm_backend == "anthropic"
    assert isinstance(cfg.llm_model, str) and cfg.llm_model != ""


def test_returns_app_config_instance(full_env: dict[str, str]) -> None:
    cfg = resolve_config()
    assert isinstance(cfg, AppConfig)


def test_llm_backend_env_openai(full_env: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    cfg = resolve_config()
    assert cfg.llm_backend == "openai"
    assert isinstance(cfg.llm_model, str) and cfg.llm_model != ""


def test_llm_model_env(full_env: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_MODEL", "custom-model-v1")
    cfg = resolve_config()
    assert cfg.llm_model == "custom-model-v1"


# ---------------------------------------------------------------------------
# CLI override precedence
# ---------------------------------------------------------------------------


def test_github_token_cli_overrides_env(full_env: dict[str, str]) -> None:
    cfg = resolve_config(github_token="cli-token")
    assert cfg.github_token == "cli-token"
    assert cfg.github_token != full_env["GITHUB_TOKEN"]


def test_slack_webhook_cli_overrides_env(full_env: dict[str, str]) -> None:
    cfg = resolve_config(slack_webhook_url="https://cli.example.com/hook")
    assert cfg.slack_webhook_url == "https://cli.example.com/hook"
    assert cfg.slack_webhook_url != full_env["SLACK_WEBHOOK_URL"]


def test_llm_api_key_cli_overrides_env(full_env: dict[str, str]) -> None:
    cfg = resolve_config(llm_api_key="cli-api-key")
    assert cfg.llm_api_key == "cli-api-key"
    assert cfg.llm_api_key != full_env["LLM_API_KEY"]


def test_llm_backend_cli_overrides_env(full_env: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    cfg = resolve_config(llm_backend="anthropic")
    assert cfg.llm_backend == "anthropic"


def test_llm_model_cli_overrides_env(full_env: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_MODEL", "env-model")
    cfg = resolve_config(llm_model="cli-model")
    assert cfg.llm_model == "cli-model"


# ---------------------------------------------------------------------------
# Empty-string CLI flag falls through to env
# ---------------------------------------------------------------------------


def test_empty_string_cli_github_token_falls_through_to_env(full_env: dict[str, str]) -> None:
    cfg = resolve_config(github_token="")
    assert cfg.github_token == full_env["GITHUB_TOKEN"]


def test_empty_string_cli_slack_webhook_falls_through_to_env(full_env: dict[str, str]) -> None:
    cfg = resolve_config(slack_webhook_url="")
    assert cfg.slack_webhook_url == full_env["SLACK_WEBHOOK_URL"]


def test_empty_string_cli_llm_api_key_falls_through_to_env(full_env: dict[str, str]) -> None:
    cfg = resolve_config(llm_api_key="")
    assert cfg.llm_api_key == full_env["LLM_API_KEY"]


def test_empty_string_cli_llm_backend_falls_through_to_default(full_env: dict[str, str]) -> None:
    cfg = resolve_config(llm_backend="")
    assert cfg.llm_backend == "anthropic"


# ---------------------------------------------------------------------------
# Missing required credentials
# ---------------------------------------------------------------------------


def test_missing_github_token_raises(full_env: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN")
    with pytest.raises(ConfigError, match="GITHUB_TOKEN"):
        resolve_config()


def test_missing_slack_webhook_raises(full_env: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SLACK_WEBHOOK_URL")
    with pytest.raises(ConfigError, match="SLACK_WEBHOOK_URL"):
        resolve_config()


def test_missing_llm_api_key_raises(full_env: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_API_KEY")
    with pytest.raises(ConfigError, match="LLM_API_KEY"):
        resolve_config()


def test_missing_all_required_raises_single_error(
    full_env: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("GITHUB_TOKEN")
    monkeypatch.delenv("SLACK_WEBHOOK_URL")
    monkeypatch.delenv("LLM_API_KEY")
    with pytest.raises(ConfigError) as exc_info:
        resolve_config()
    msg = str(exc_info.value)
    assert "GITHUB_TOKEN" in msg
    assert "SLACK_WEBHOOK_URL" in msg
    assert "LLM_API_KEY" in msg


def test_config_error_is_not_system_exit(full_env: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN")
    with pytest.raises(ConfigError) as exc_info:
        resolve_config()
    assert type(exc_info.value) is ConfigError
    assert not isinstance(exc_info.value, SystemExit)


# ---------------------------------------------------------------------------
# Empty-string env var treated as absent
# ---------------------------------------------------------------------------


def test_empty_string_github_token_env_raises(
    full_env: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "")
    with pytest.raises(ConfigError, match="GITHUB_TOKEN"):
        resolve_config()


def test_empty_string_llm_backend_env_defaults_to_anthropic(
    full_env: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLM_BACKEND", "")
    cfg = resolve_config()
    assert cfg.llm_backend == "anthropic"


# ---------------------------------------------------------------------------
# LLM_BACKEND absent: defaults to 'anthropic'
# ---------------------------------------------------------------------------


def test_llm_backend_absent_defaults_to_anthropic(full_env: dict[str, str]) -> None:
    # full_env fixture already deletes LLM_BACKEND
    cfg = resolve_config()
    assert cfg.llm_backend == "anthropic"


# ---------------------------------------------------------------------------
# LLM_BACKEND validation
# ---------------------------------------------------------------------------


def test_invalid_llm_backend_raises(full_env: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "gemini")
    with pytest.raises(ConfigError) as exc_info:
        resolve_config()
    msg = str(exc_info.value)
    assert "gemini" in msg
    assert "anthropic" in msg
    assert "openai" in msg


def test_mixed_case_llm_backend_raises(full_env: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "Anthropic")
    with pytest.raises(ConfigError):
        resolve_config()


def test_valid_openai_backend(full_env: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_BACKEND", "openai")
    cfg = resolve_config()
    assert cfg.llm_backend == "openai"


def test_invalid_backend_via_cli_raises(full_env: dict[str, str]) -> None:
    with pytest.raises(ConfigError, match="badbackend"):
        resolve_config(llm_backend="badbackend")


# ---------------------------------------------------------------------------
# LLM_MODEL defaults
# ---------------------------------------------------------------------------


def test_llm_model_absent_defaults_non_empty(full_env: dict[str, str]) -> None:
    cfg = resolve_config()
    assert cfg.llm_model is not None
    assert cfg.llm_model != ""


def test_llm_model_env_value(full_env: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_MODEL", "my-special-model")
    cfg = resolve_config()
    assert cfg.llm_model == "my-special-model"


def test_llm_model_cli_value(full_env: dict[str, str]) -> None:
    cfg = resolve_config(llm_model="cli-model-x")
    assert cfg.llm_model == "cli-model-x"


# ---------------------------------------------------------------------------
# Idempotency: no caching across calls
# ---------------------------------------------------------------------------


def test_idempotency_no_caching(full_env: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    cfg1 = resolve_config()
    assert cfg1.github_token == "ghp_test"

    monkeypatch.setenv("GITHUB_TOKEN", "ghp_different")
    cfg2 = resolve_config()
    assert cfg2.github_token == "ghp_different"

    # First call result should not have changed
    assert cfg1.github_token == "ghp_test"
