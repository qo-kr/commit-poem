from __future__ import annotations

import logging
import time

import requests

_SLACK_API = "https://slack.com/api"
logger = logging.getLogger(__name__)


class SlackWebhookError(Exception):
    """Raised on all Slack delivery failures (network errors, HTTP errors, or invalid URLs)."""


class SlackThreadError(SlackWebhookError):
    """The parent exists; retrying the whole publication would duplicate it."""

    def __init__(self, parent_ts: str) -> None:
        super().__init__(f"Slack parent {parent_ts} was posted, but its thread reply failed")
        self.parent_ts = parent_ts


class SlackAPIError(SlackWebhookError):
    """Slack explicitly rejected a request, so it did not create a message."""

    def __init__(self, code: str, details: list[str]) -> None:
        super().__init__(f"Slack API error: {code}; details: {details}")
        self.code = code
        self.details = details


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
        details = data.get("response_metadata", {}).get("messages", [])
        raise SlackAPIError(data.get("error", "unknown"), details)
    return data


def _upload_image(
    bot_token: str,
    channel: str | None,
    image: bytes,
    *,
    filename: str = "poem.png",
    initial_comment: str | None = None,
) -> str:
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
    }
    if channel is not None:
        payload["channel_id"] = channel
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
    return file_id


def post_image(
    bot_token: str, channel: str, image: bytes, *, filename: str = "poem.png", initial_comment: str | None = None,
) -> None:
    """Upload an image as a conventional channel file message."""
    _upload_image(bot_token, channel, image, filename=filename, initial_comment=initial_comment)


def _text_blocks(text: str) -> list[dict]:
    chunks: list[str] = []
    current = ""
    for paragraph in text.split("\n\n"):
        if not paragraph:
            continue
        for start in range(0, len(paragraph), 3000):
            part = paragraph[start:start + 3000]
            combined = current + "\n\n" + part if current else part
            if len(combined) > 3000:
                chunks.append(current)
                current = part
            else:
                current = combined
    if current:
        chunks.append(current)
    return [{"type": "section", "text": {"type": "mrkdwn", "text": chunk}} for chunk in chunks]


def _post_message(bot_token: str, payload: dict) -> str:
    try:
        response = requests.post(
            f"{_SLACK_API}/chat.postMessage", headers={"Authorization": f"Bearer {bot_token}"},
            json={"unfurl_links": False, "unfurl_media": False, **payload}, timeout=15,
        )
    except requests.exceptions.RequestException as exc:
        raise SlackWebhookError("Network error posting Slack message") from exc
    data = _slack_api_json(response)
    ts = data.get("ts")
    if not isinstance(ts, str) or not ts:
        raise SlackWebhookError("Slack did not return the posted message timestamp")
    return ts


def post_publication(
    bot_token: str, channel: str, text: str, comment: str, *, image: bytes | None = None, title: str = "시화",
) -> str:
    """Post ordered image/text blocks, then reply with notes to the returned parent."""
    blocks: list[dict] = []
    text_blocks = _text_blocks(text)
    comment_blocks = _text_blocks(comment)
    if len(text_blocks) + (image is not None) > 50 or len(comment_blocks) > 50:
        raise SlackWebhookError("Publication exceeds Slack's 50-block message limit")
    if image is not None:
        try:
            file_id = _upload_image(bot_token, None, image)
        except SlackWebhookError as exc:
            logger.error("Image upload failed; publishing text with threaded notes: %s", exc)
        else:
            blocks.append({"type": "image", "slack_file": {"id": file_id}, "alt_text": title or "시화"})
    blocks.extend(text_blocks)
    for attempt in range(5):
        try:
            parent_ts = _post_message(bot_token, {"channel": channel, "text": text, "blocks": blocks})
            break
        except SlackAPIError as exc:
            pending_image = bool(blocks) and blocks[0]["type"] == "image" and exc.code == "invalid_blocks" and any(
                "invalid slack file" in detail for detail in exc.details
            )
            if not pending_image or attempt == 4:
                raise
            # Slack may acknowledge an upload before image blocks can reference it.
            # Only retry this explicit rejection; an ambiguous network failure may
            # already have created a parent and must never be retried blindly.
            logger.info("Slack image is still processing; retrying the same file in %ss", 2 ** attempt)
            time.sleep(2 ** attempt)
    logger.info("Slack parent posted; parent_ts=%s", parent_ts)
    if comment:
        try:
            _post_message(bot_token, {"channel": channel, "text": comment, "thread_ts": parent_ts,
                                      "blocks": comment_blocks})
        except SlackWebhookError as exc:
            raise SlackThreadError(parent_ts) from exc
    return parent_ts
