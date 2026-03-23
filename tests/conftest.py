from __future__ import annotations

from unittest.mock import patch

import pytest
from click.testing import CliRunner

FULL_ENV: dict[str, str] = {
    "GITHUB_TOKEN": "ghp_test",
    "SLACK_WEBHOOK_URL": "https://hooks.slack.com/services/test",
    "LLM_API_KEY": "sk-test",
}

SINCE = "2024-01-01T00:00:00Z"
UNTIL = "2024-01-02T00:00:00Z"


@pytest.fixture(autouse=True)
def _no_dotenv(monkeypatch: pytest.MonkeyPatch):
    """Prevent .env file from affecting tests."""
    monkeypatch.setattr("commitpoem.cli._load_dotenv", lambda: None)
    for key in ("LLM_BACKEND", "LLM_MODEL", "LLM_API_KEY", "GITHUB_TOKEN", "SLACK_WEBHOOK_URL"):
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def full_env(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    for k, v in FULL_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("LLM_BACKEND", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    return FULL_ENV


@pytest.fixture
def runner() -> CliRunner:
    """Return a Click CliRunner with stderr separated from stdout."""
    return CliRunner()
