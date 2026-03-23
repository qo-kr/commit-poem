from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from datetime import datetime, timezone

import click

from commitpoem.backends import LLMBackend, get_backend
from commitpoem.config import AppConfig, ConfigError, resolve_config
from commitpoem.github_client import GitHubAPIError, GitHubAuthError, fetch_commits
from commitpoem.poem import generate_poem
from commitpoem.scheduler import run_scheduler
from commitpoem.slack import SlackWebhookError, post_poem

__all__ = ["main"]


def _load_dotenv() -> None:
    """Load .env file if python-dotenv is installed."""
    try:
        from dotenv import load_dotenv

        load_dotenv(override=False)
    except ImportError:
        pass

logger = logging.getLogger(__name__)


def _parse_datetime(value: str) -> datetime:
    """Parse an ISO 8601 datetime string into a timezone-aware datetime.

    If the parsed datetime is naive (no tzinfo), it is coerced to UTC.

    Args:
        value: An ISO 8601 datetime string.

    Returns:
        A timezone-aware datetime.

    Raises:
        ValueError: If the string cannot be parsed as a datetime.
    """
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        raise ValueError(
            f"Invalid datetime {value!r}. Expected an ISO 8601 string like '2024-01-01T00:00:00Z'."
        )
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _make_pipeline(
    config: AppConfig,
    repo: str,
    since: datetime,
    until: datetime,
) -> Callable[[], None]:
    """Create a zero-argument pipeline callable that runs the full commit-poem workflow.

    Args:
        config: Resolved application configuration.
        repo: Repository in 'owner/repo' format.
        since: Start of the time range (timezone-aware).
        until: End of the time range (timezone-aware).

    Returns:
        A callable that fetches commits, generates a poem, and posts it to Slack.
    """

    def pipeline() -> None:
        commits = fetch_commits(config.github_token, repo, since, until)
        backend: LLMBackend = get_backend(config.llm_backend, config.llm_api_key)
        poem = generate_poem(commits, backend, config.llm_model)
        post_poem(config.slack_webhook_url, poem)

    return pipeline


def _run_once_with_error_handling(pipeline: Callable[[], None]) -> None:
    """Run the pipeline once, handling known error types with exit-1 and logging others.

    - GitHubAuthError, GitHubAPIError, SlackWebhookError → print to stderr, sys.exit(1).
    - Other Exception → logged at ERROR level (no traceback printed to user), exit 0.
    - KeyboardInterrupt / SystemExit → propagate normally.

    Args:
        pipeline: Zero-argument callable to invoke.
    """
    try:
        pipeline()
    except GitHubAuthError as exc:
        click.echo(f"Error: GitHub authentication failed: {exc}", err=True)
        sys.exit(1)
    except GitHubAPIError as exc:
        click.echo(f"Error: GitHub API error: {exc}", err=True)
        sys.exit(1)
    except SlackWebhookError as exc:
        click.echo(f"Error: Slack delivery failed: {exc}", err=True)
        sys.exit(1)
    except Exception:
        logger.error("Pipeline raised an exception", exc_info=True)


@click.command()
@click.option("--repo", required=True, help="GitHub repository in 'owner/repo' format.")
@click.option("--since", "since_str", required=True, help="Start of time range (ISO 8601).")
@click.option("--until", "until_str", required=True, help="End of time range (ISO 8601).")
@click.option("--github-token", default=None, help="GitHub personal access token (env: GITHUB_TOKEN).")
@click.option("--slack-webhook-url", default=None, help="Slack incoming webhook URL (env: SLACK_WEBHOOK_URL).")
@click.option("--llm-api-key", default=None, help="LLM API key (env: LLM_API_KEY).")
@click.option(
    "--llm-backend",
    default=None,
    help="LLM backend to use: 'anthropic' or 'openai' (env: LLM_BACKEND, default: anthropic).",
)
@click.option("--llm-model", default=None, help="LLM model name (env: LLM_MODEL).")
@click.option(
    "--schedule",
    default=None,
    help="Run on a recurring interval, e.g. '30s', '5m', '1h'. Omit for one-shot mode.",
)
def main(
    repo: str,
    since_str: str,
    until_str: str,
    github_token: str | None,
    slack_webhook_url: str | None,
    llm_api_key: str | None,
    llm_backend: str | None,
    llm_model: str | None,
    schedule: str | None,
) -> None:
    """Generate a poem from recent GitHub commits and post it to Slack."""
    _load_dotenv()

    # Parse datetimes
    try:
        since = _parse_datetime(since_str)
    except ValueError as exc:
        click.echo(f"Error: --since: {exc}", err=True)
        sys.exit(1)

    try:
        until = _parse_datetime(until_str)
    except ValueError as exc:
        click.echo(f"Error: --until: {exc}", err=True)
        sys.exit(1)

    # Resolve configuration (handles env-var fallback and validation)
    try:
        config = resolve_config(
            github_token=github_token,
            slack_webhook_url=slack_webhook_url,
            llm_api_key=llm_api_key,
            llm_backend=llm_backend,
            llm_model=llm_model,
        )
    except ConfigError as exc:
        msg = str(exc)
        # Normalise backend error messages so they always list 'anthropic, openai'
        if "allowed:" in msg or "backend" in msg.lower():
            click.echo(
                "Error: Unsupported LLM backend. Supported backends: anthropic, openai", err=True
            )
        else:
            click.echo(f"Error: {msg}", err=True)
        sys.exit(1)

    pipeline = _make_pipeline(config, repo, since, until)

    if schedule is not None:
        # Scheduled (looping) mode
        try:
            run_scheduler(schedule, pipeline)
        except ValueError as exc:
            click.echo(f"Error: Invalid --schedule value: {exc}", err=True)
            sys.exit(1)
        except KeyboardInterrupt:
            pass  # Clean exit — no non-zero code
    else:
        # One-shot mode: handle known errors explicitly; log generic exceptions
        _run_once_with_error_handling(pipeline)
