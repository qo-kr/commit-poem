from __future__ import annotations

import threading
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from commitpoem.cli import _parse_datetime, main
from commitpoem.config import ConfigError
from commitpoem.github_client import GitHubAPIError, GitHubAuthError
from commitpoem.slack import SlackWebhookError

SINCE = "2024-01-01T00:00:00Z"
UNTIL = "2024-01-02T00:00:00Z"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BASE_ARGS = ["--repo", "owner/repo", "--since", SINCE, "--until", UNTIL]


def _invoke(runner: CliRunner, args: list[str], env: dict | None = None) -> object:
    return runner.invoke(main, args, env=env, catch_exceptions=False)


def _full_env() -> dict[str, str]:
    return {
        "GITHUB_TOKEN": "ghp_test",
        "SLACK_WEBHOOK_URL": "https://hooks.slack.com/services/test",
        "LLM_API_KEY": "sk-test",
    }


# ---------------------------------------------------------------------------
# 1. Help & usage
# ---------------------------------------------------------------------------


def test_help_exits_zero(runner: CliRunner) -> None:
    result = runner.invoke(main, ["--help"], catch_exceptions=False)
    assert result.exit_code == 0


def test_help_contains_all_flags(runner: CliRunner) -> None:
    result = runner.invoke(main, ["--help"], catch_exceptions=False)
    output = result.output
    for flag in [
        "--repo",
        "--since",
        "--until",
        "--github-token",
        "--slack-webhook-url",
        "--llm-api-key",
        "--llm-backend",
        "--llm-model",
        "--schedule",
    ]:
        assert flag in output, f"Flag {flag!r} not found in --help output"


def test_missing_repo_exits_2(runner: CliRunner) -> None:
    result = runner.invoke(main, ["--since", SINCE, "--until", UNTIL], catch_exceptions=True)
    assert result.exit_code == 2
    combined = (result.output or "") + (result.stderr or "")
    assert "--help" in combined


def test_missing_since_exits_2(runner: CliRunner) -> None:
    result = runner.invoke(main, ["--repo", "owner/repo", "--until", UNTIL], catch_exceptions=True)
    assert result.exit_code == 2
    combined = (result.output or "") + (result.stderr or "")
    assert "--help" in combined


def test_missing_until_exits_2(runner: CliRunner) -> None:
    result = runner.invoke(main, ["--repo", "owner/repo", "--since", SINCE], catch_exceptions=True)
    assert result.exit_code == 2
    combined = (result.output or "") + (result.stderr or "")
    assert "--help" in combined


def test_unrecognized_flag_exits_2(runner: CliRunner) -> None:
    result = runner.invoke(main, BASE_ARGS + ["--foo"], catch_exceptions=True)
    assert result.exit_code == 2
    combined = (result.output or "") + (result.stderr or "")
    assert "--help" in combined


# ---------------------------------------------------------------------------
# 2. Happy-path one-shot
# ---------------------------------------------------------------------------


def test_oneshot_success(runner: CliRunner) -> None:
    mock_backend = MagicMock()
    mock_backend.generate_poem.return_value = "roses are red"

    with (
        patch("commitpoem.cli.fetch_commits", return_value=["fix bug"]) as mock_fetch,
        patch("commitpoem.cli.get_backend", return_value=mock_backend) as mock_gb,
        patch("commitpoem.cli.generate_poem", return_value="roses are red") as mock_gen,
        patch("commitpoem.cli.post_poem") as mock_post,
    ):
        result = runner.invoke(main, BASE_ARGS, env=_full_env(), catch_exceptions=False)

    assert result.exit_code == 0
    mock_fetch.assert_called_once()
    mock_gen.assert_called_once()
    mock_post.assert_called_once()


# ---------------------------------------------------------------------------
# 3. Scheduled mode
# ---------------------------------------------------------------------------


def test_schedule_calls_run_scheduler(runner: CliRunner) -> None:
    with (
        patch("commitpoem.cli.run_scheduler") as mock_sched,
    ):
        result = runner.invoke(
            main, BASE_ARGS + ["--schedule", "5m"], env=_full_env(), catch_exceptions=False
        )

    assert result.exit_code == 0
    mock_sched.assert_called_once()
    call_args = mock_sched.call_args
    assert call_args[0][0] == "5m"


def test_schedule_keyboard_interrupt_exits_zero(runner: CliRunner) -> None:
    def raise_ki(*args, **kwargs) -> None:
        raise KeyboardInterrupt

    with patch("commitpoem.cli.run_scheduler", side_effect=raise_ki):
        result = runner.invoke(
            main, BASE_ARGS + ["--schedule", "5m"], env=_full_env(), catch_exceptions=True
        )

    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# 4. Config errors
# ---------------------------------------------------------------------------


def test_missing_github_token_exits_1(runner: CliRunner) -> None:
    env = _full_env()
    del env["GITHUB_TOKEN"]
    result = runner.invoke(main, BASE_ARGS, env=env, catch_exceptions=True)
    assert result.exit_code == 1
    assert result.stderr  # error goes to stderr


def test_missing_slack_webhook_exits_1(runner: CliRunner) -> None:
    env = _full_env()
    del env["SLACK_WEBHOOK_URL"]
    result = runner.invoke(main, BASE_ARGS, env=env, catch_exceptions=True)
    assert result.exit_code == 1
    assert result.stderr


def test_missing_llm_api_key_exits_1(runner: CliRunner) -> None:
    env = _full_env()
    del env["LLM_API_KEY"]
    result = runner.invoke(main, BASE_ARGS, env=env, catch_exceptions=True)
    assert result.exit_code == 1
    assert result.stderr


# ---------------------------------------------------------------------------
# 5. Bad backend
# ---------------------------------------------------------------------------


def test_bad_backend_exits_1_with_supported_list(runner: CliRunner) -> None:
    result = runner.invoke(
        main, BASE_ARGS + ["--llm-backend", "gemini"], env=_full_env(), catch_exceptions=True
    )
    assert result.exit_code == 1
    stderr = result.stderr
    assert "anthropic" in stderr
    assert "openai" in stderr


# ---------------------------------------------------------------------------
# 6. Bad schedule format
# ---------------------------------------------------------------------------


def test_bad_schedule_uppercase_exits_1(runner: CliRunner) -> None:
    result = runner.invoke(
        main, BASE_ARGS + ["--schedule", "5M"], env=_full_env(), catch_exceptions=True
    )
    assert result.exit_code == 1
    assert result.stderr


def test_bad_schedule_invalid_pattern_exits_1(runner: CliRunner) -> None:
    result = runner.invoke(
        main, BASE_ARGS + ["--schedule", "abc"], env=_full_env(), catch_exceptions=True
    )
    assert result.exit_code == 1
    assert result.stderr


# ---------------------------------------------------------------------------
# 7. GitHub errors
# ---------------------------------------------------------------------------


def test_github_auth_error_exits_1(runner: CliRunner) -> None:
    with patch("commitpoem.cli.fetch_commits", side_effect=GitHubAuthError("bad token")):
        result = runner.invoke(main, BASE_ARGS, env=_full_env(), catch_exceptions=True)

    # run_once catches Exception; but GitHubAuthError IS an Exception, so it gets logged
    # We need to verify the exit code and stderr behaviour.
    # run_once suppresses Exception — but acceptance criteria says exit 1 on GitHubAuthError.
    # So _make_pipeline itself must propagate and the CLI must catch it before run_once.
    # Per implementation: run_once catches exceptions internally, so we need the pipeline
    # errors to surface. Let's check how the code handles this.
    # Since run_once swallows Exception, in one-shot mode we still exit 0.
    # But the acceptance criteria says exit 1 for these errors.
    # We need to handle these errors at the pipeline level, not inside run_once.
    # Looking at the implementation: the errors propagate from inside the pipeline closure.
    # run_once catches them and logs. Exit code is 0 in that case.
    # The acceptance criteria requires exit 1 for these errors.
    # This means we need to restructure: in one-shot mode, we should not use run_once
    # but instead call pipeline directly with explicit error handling.
    # For now, let's verify the actual behavior and adjust the test/implementation.
    # The test should match the acceptance criteria: exit 1.
    assert result.exit_code == 1
    assert result.stderr


def test_github_api_error_exits_1(runner: CliRunner) -> None:
    with patch("commitpoem.cli.fetch_commits", side_effect=GitHubAPIError("API failure")):
        result = runner.invoke(main, BASE_ARGS, env=_full_env(), catch_exceptions=True)
    assert result.exit_code == 1
    assert result.stderr


# ---------------------------------------------------------------------------
# 8. Slack errors
# ---------------------------------------------------------------------------


def test_slack_webhook_error_exits_1(runner: CliRunner) -> None:
    with (
        patch("commitpoem.cli.fetch_commits", return_value=["fix bug"]),
        patch("commitpoem.cli.generate_poem", return_value="a poem"),
        patch("commitpoem.cli.post_poem", side_effect=SlackWebhookError("webhook failed")),
    ):
        result = runner.invoke(main, BASE_ARGS, env=_full_env(), catch_exceptions=True)
    assert result.exit_code == 1
    assert result.stderr


# ---------------------------------------------------------------------------
# 9. Datetime parsing
# ---------------------------------------------------------------------------


def test_parse_datetime_with_timezone() -> None:
    dt = _parse_datetime("2024-01-01T00:00:00Z")
    assert dt.tzinfo is not None
    assert dt == datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


def test_parse_datetime_naive_coerced_to_utc() -> None:
    dt = _parse_datetime("2024-06-15T12:00:00")
    assert dt.tzinfo is not None
    assert dt.tzinfo == timezone.utc
    assert dt.year == 2024
    assert dt.month == 6
    assert dt.day == 15


def test_parse_datetime_with_offset() -> None:
    dt = _parse_datetime("2024-01-01T08:00:00+05:00")
    assert dt.tzinfo is not None


def test_parse_datetime_invalid_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Invalid datetime"):
        _parse_datetime("not-a-date")


def test_naive_datetime_string_in_cli_coerced_to_utc(runner: CliRunner) -> None:
    """A naive ISO string (no timezone) should be accepted and coerced to UTC."""
    naive_since = "2024-01-01T00:00:00"
    naive_until = "2024-01-02T00:00:00"

    with (
        patch("commitpoem.cli.fetch_commits", return_value=[]) as mock_fetch,
        patch("commitpoem.cli.generate_poem", return_value="poem"),
        patch("commitpoem.cli.post_poem"),
    ):
        result = runner.invoke(
            main,
            ["--repo", "owner/repo", "--since", naive_since, "--until", naive_until],
            env=_full_env(),
            catch_exceptions=False,
        )

    assert result.exit_code == 0
    # Verify the datetime passed to fetch_commits is timezone-aware
    call_args = mock_fetch.call_args[0]
    since_arg = call_args[2]
    until_arg = call_args[3]
    assert since_arg.tzinfo is not None
    assert until_arg.tzinfo is not None


# ---------------------------------------------------------------------------
# 10. CLI flag precedence over env vars
# ---------------------------------------------------------------------------


def test_cli_flag_overrides_env_github_token(runner: CliRunner) -> None:
    env = _full_env()
    env["GITHUB_TOKEN"] = "env-token"

    with patch("commitpoem.cli.fetch_commits", return_value=[]) as mock_fetch, patch(
        "commitpoem.cli.generate_poem", return_value="poem"
    ), patch("commitpoem.cli.post_poem"):
        runner.invoke(
            main,
            BASE_ARGS + ["--github-token", "cli-token"],
            env=env,
            catch_exceptions=False,
        )

    call_args = mock_fetch.call_args[0]
    assert call_args[0] == "cli-token"


def test_cli_flag_overrides_env_llm_backend(runner: CliRunner) -> None:
    env = _full_env()
    env["LLM_BACKEND"] = "openai"

    captured_backend = {}

    def fake_get_backend(name: str, api_key: str):
        captured_backend["name"] = name
        m = MagicMock()
        m.generate_poem.return_value = "poem"
        return m

    with (
        patch("commitpoem.cli.fetch_commits", return_value=[]),
        patch("commitpoem.cli.get_backend", side_effect=fake_get_backend),
        patch("commitpoem.cli.generate_poem", return_value="poem"),
        patch("commitpoem.cli.post_poem"),
    ):
        runner.invoke(
            main,
            BASE_ARGS + ["--llm-backend", "anthropic"],
            env=env,
            catch_exceptions=False,
        )

    assert captured_backend.get("name") == "anthropic"


# ---------------------------------------------------------------------------
# 11. Default backend is 'anthropic'
# ---------------------------------------------------------------------------


def test_default_backend_is_anthropic(runner: CliRunner) -> None:
    env = _full_env()
    # No LLM_BACKEND in env
    env.pop("LLM_BACKEND", None)

    captured_backend = {}

    def fake_get_backend(name: str, api_key: str):
        captured_backend["name"] = name
        m = MagicMock()
        m.generate_poem.return_value = "poem"
        return m

    with (
        patch("commitpoem.cli.fetch_commits", return_value=[]),
        patch("commitpoem.cli.get_backend", side_effect=fake_get_backend),
        patch("commitpoem.cli.generate_poem", return_value="poem"),
        patch("commitpoem.cli.post_poem"),
    ):
        result = runner.invoke(main, BASE_ARGS, env=env, catch_exceptions=False)

    assert result.exit_code == 0
    assert captured_backend.get("name") == "anthropic"


# ---------------------------------------------------------------------------
# 12. Empty string credentials treated as absent (fall through to env)
# ---------------------------------------------------------------------------


def test_empty_github_token_flag_falls_through_to_env(runner: CliRunner) -> None:
    env = _full_env()
    env["GITHUB_TOKEN"] = "env-token"

    with patch("commitpoem.cli.fetch_commits", return_value=[]) as mock_fetch, patch(
        "commitpoem.cli.generate_poem", return_value="poem"
    ), patch("commitpoem.cli.post_poem"):
        runner.invoke(
            main,
            BASE_ARGS + ["--github-token", ""],
            env=env,
            catch_exceptions=False,
        )

    call_args = mock_fetch.call_args[0]
    assert call_args[0] == "env-token"


# ---------------------------------------------------------------------------
# 13. All errors written to stderr, not stdout
# ---------------------------------------------------------------------------


def test_error_messages_on_stderr_not_stdout(runner: CliRunner) -> None:
    env = _full_env()
    del env["GITHUB_TOKEN"]

    result = runner.invoke(main, BASE_ARGS, env=env, catch_exceptions=True)

    assert result.exit_code == 1
    assert result.stderr  # error is on stderr
    # stdout should be clean (empty or whitespace only)
    assert not result.stdout.strip()
