from __future__ import annotations

import requests


class SlackWebhookError(Exception):
    """Raised on all Slack delivery failures (network errors, HTTP errors, or invalid URLs)."""


def post_poem(webhook_url: str, poem: str) -> None:
    """Post a poem string to a Slack channel via an incoming webhook URL.

    Args:
        webhook_url: The Slack incoming webhook URL to POST to.
        poem: The poem string to send as the message text.

    Returns:
        None on success.

    Raises:
        SlackWebhookError: If the HTTP request fails (network error, timeout, invalid URL)
            or if Slack returns a non-2xx HTTP status code.
    """
    try:
        response = requests.post(webhook_url, json={"text": poem}, timeout=10)
    except requests.exceptions.RequestException as e:
        raise SlackWebhookError(f"Network error posting to Slack: {e}") from e

    if not response.ok:
        raise SlackWebhookError(
            f"Slack webhook returned HTTP {response.status_code} — {response.text}"
        )
