from __future__ import annotations

import requests

_SLACK_API = "https://slack.com/api"


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


def _slack_api_json(response: requests.Response) -> dict:
    """Validate a Slack Web API response and return its parsed JSON body.

    Raises:
        SlackWebhookError: On a non-2xx status or a body with ``ok: false``.
    """
    if not response.ok:
        raise SlackWebhookError(
            f"Slack API returned HTTP {response.status_code} — {response.text}"
        )
    data = response.json()
    if not data.get("ok"):
        raise SlackWebhookError(f"Slack API error: {data.get('error', 'unknown')}")
    return data


def post_image(
    bot_token: str,
    channel: str,
    image: bytes,
    *,
    filename: str = "poem.png",
    initial_comment: str | None = None,
) -> None:
    """Upload an image to a Slack channel via the external-upload flow.

    Uses the modern three-step upload (``files.getUploadURLExternal`` →
    raw upload → ``files.completeUploadExternal``), since the legacy
    ``files.upload`` endpoint is retired.

    Args:
        bot_token: A Slack bot token (``xoxb-…``) with the ``files:write`` scope.
        channel: The destination channel ID (e.g. ``C0123ABCD``). The bot must be
            a member of this channel.
        image: The raw image bytes to upload.
        filename: The filename Slack should show for the upload.
        initial_comment: Optional message text posted alongside the image
            (used here to carry the poem).

    Raises:
        SlackWebhookError: On any network error, non-2xx status, or Slack API error.
    """
    headers = {"Authorization": f"Bearer {bot_token}"}

    # 1. Reserve an upload URL and file id.
    try:
        reserve = requests.get(
            f"{_SLACK_API}/files.getUploadURLExternal",
            headers=headers,
            params={"filename": filename, "length": str(len(image))},
            timeout=10,
        )
    except requests.exceptions.RequestException as e:
        raise SlackWebhookError(f"Network error reserving Slack upload URL: {e}") from e
    reserved = _slack_api_json(reserve)
    upload_url = reserved["upload_url"]
    file_id = reserved["file_id"]

    # 2. Upload the raw bytes to the reserved URL.
    try:
        upload = requests.post(upload_url, data=image, timeout=30)
    except requests.exceptions.RequestException as e:
        raise SlackWebhookError(f"Network error uploading image to Slack: {e}") from e
    if not upload.ok:
        raise SlackWebhookError(
            f"Slack upload returned HTTP {upload.status_code} — {upload.text}"
        )

    # 3. Complete the upload, attaching the file to the channel.
    payload: dict = {
        "files": [{"id": file_id, "title": filename}],
        "channel_id": channel,
    }
    if initial_comment:
        payload["initial_comment"] = initial_comment
    try:
        complete = requests.post(
            f"{_SLACK_API}/files.completeUploadExternal",
            headers={**headers, "Content-Type": "application/json; charset=utf-8"},
            json=payload,
            timeout=10,
        )
    except requests.exceptions.RequestException as e:
        raise SlackWebhookError(f"Network error completing Slack upload: {e}") from e
    _slack_api_json(complete)
