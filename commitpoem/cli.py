from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

import click

from commitpoem.backends import LLMBackend, get_backend
from commitpoem.catalog import Profile, select_daily
from commitpoem.config import AppConfig, ConfigError, resolve_config
from commitpoem.edition import Publication
from commitpoem.github_client import GitHubAPIError, GitHubAuthError, fetch_commits, fetch_org_commits
from commitpoem.image import ImageGenError, generate_image
from commitpoem.local_git import fetch_local_commits
from commitpoem.poem import generate_publication
from commitpoem.scheduler import run_scheduler
from commitpoem.slack import SlackWebhookError, post_poem, post_publication

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


def _deliver(
    config: AppConfig, publication: Publication | str, *, with_image: bool, painter: Profile | None = None,
) -> None:
    """Post image-first channel content and its notes as a threaded bot reply."""
    if isinstance(publication, str):
        publication = Publication(text=publication, artwork=publication)
    if config.slack_bot_token and config.slack_channel:
        image = None
        if with_image:
            try:
                image = generate_image(publication.artwork, painter=painter)
            except ImageGenError as exc:
                logger.error("Image generation failed; publishing text with threaded notes: %s", exc)
        # Do not fall back to a second parent when posting its reply fails.
        parent_ts = post_publication(
            config.slack_bot_token, config.slack_channel, publication.text, publication.comment,
            image=image, title=publication.title,
        )
        logger.info("Daily edition delivered to Slack with threaded notes; parent_ts=%s", parent_ts)
        return

    post_poem(config.slack_webhook_url, publication.text)
    if publication.comment:
        logger.warning("Threaded notes require SLACK_BOT_TOKEN and SLACK_CHANNEL")
    logger.info("Daily edition delivered to Slack (text-only)")


def _make_pipeline(
    config: AppConfig,
    repo: str | None,
    org: tuple[str, ...],
    since: datetime,
    until: datetime,
    *,
    with_image: bool,
    local_roots: tuple[Path, ...] = (),
    update_main: bool = False,
) -> Callable[[], None]:
    """Create a zero-argument pipeline callable that runs the full commit-poem workflow.

    Args:
        config: Resolved application configuration.
        repo: Repository in 'owner/repo' format, or None if using --org.
        org: GitHub organization logins; in local mode these filter paired origins.
        since: Start of the time range (timezone-aware).
        until: End of the time range (timezone-aware).
        with_image: Whether to attempt image generation + upload (when configured).

    Returns:
        A callable that fetches commits, generates a poem, and posts it to Slack.
    """

    def pipeline() -> None:
        poet, painter = select_daily()
        if local_roots:
            commits = fetch_local_commits(list(local_roots), since, until, organizations=org, sync_main=update_main)
        elif org:
            commits = []
            for organization in dict.fromkeys(org):
                commits.extend(fetch_org_commits(config.github_token, organization, since, until))
        else:
            commits = fetch_commits(config.github_token, repo, since, until)
        backend: LLMBackend = get_backend(config.llm_backend, config.llm_api_key)
        publication = generate_publication(commits, backend, config.llm_model, poet=poet, painter=painter)
        _deliver(config, publication, with_image=with_image, painter=painter)

    return pipeline


def _run_once_with_error_handling(pipeline: Callable[[], None]) -> None:
    """Run the pipeline once, handling known error types with exit-1 and logging others.

    - GitHubAuthError, GitHubAPIError, SlackWebhookError → print to stderr, sys.exit(1).
    - Other Exception → logged at ERROR level with traceback, sys.exit(1).
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
        sys.exit(1)


@click.command()
@click.option("--repo", default=None, help="GitHub repository in 'owner/repo' format.")
@click.option("--org", multiple=True, help="GitHub organization login; repeat to combine several organizations.")
@click.option("--local-root", multiple=True, type=click.Path(exists=True, file_okay=False, path_type=Path),
              help="Read local Git checkouts under this directory; repeat for multiple roots. --org filters owners.")
@click.option("--update-main", is_flag=True,
              help="In local mode, fetch and fast-forward clean main checkouts only; skip dirty/diverged branches.")
@click.option("--since", "since_str", required=True, help="Start of time range (ISO 8601).")
@click.option("--until", "until_str", required=True, help="End of time range (ISO 8601).")
@click.option("--github-token", default=None, help="GitHub personal access token (env: GITHUB_TOKEN).")
@click.option("--slack-webhook-url", default=None, help="Slack incoming webhook URL (env: SLACK_WEBHOOK_URL).")
@click.option("--slack-bot-token", default=None, help="Slack bot token for image upload (env: SLACK_BOT_TOKEN).")
@click.option("--slack-channel", default=None, help="Slack channel ID for image upload (env: SLACK_CHANNEL).")
@click.option(
    "--with-image/--no-image",
    "with_image",
    default=True,
    help="Generate and post an image with the poem when bot token + channel are set (default: on).",
)
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
    repo: str | None,
    org: tuple[str, ...],
    local_root: tuple[Path, ...],
    update_main: bool,
    since_str: str,
    until_str: str,
    github_token: str | None,
    slack_webhook_url: str | None,
    slack_bot_token: str | None,
    slack_channel: str | None,
    with_image: bool,
    llm_api_key: str | None,
    llm_backend: str | None,
    llm_model: str | None,
    schedule: str | None,
) -> None:
    """Generate a poem from recent GitHub commits and post it to Slack."""
    _load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if repo is None and not org and not local_root:
        click.echo("Error: one of --repo, --org or --local-root is required.", err=True)
        sys.exit(1)
    if repo is not None and (org or local_root):
        click.echo("Error: --repo and --org/--local-root are mutually exclusive.", err=True)
        sys.exit(1)
    if update_main and not local_root:
        click.echo("Error: --update-main requires --local-root.", err=True)
        sys.exit(1)

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

    if since > until:
        click.echo("Error: --since must not be after --until.", err=True)
        sys.exit(1)

    # Resolve configuration (handles env-var fallback and validation)
    try:
        config = resolve_config(
            github_token=github_token,
            slack_webhook_url=slack_webhook_url,
            llm_api_key=llm_api_key,
            llm_backend=llm_backend,
            llm_model=llm_model,
            slack_bot_token=slack_bot_token,
            slack_channel=slack_channel,
            require_github=not bool(local_root),
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

    pipeline = _make_pipeline(config, repo, org, since, until, with_image=with_image,
                              local_roots=local_root, update_main=update_main)

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
