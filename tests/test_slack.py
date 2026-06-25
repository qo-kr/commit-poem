from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from commitpoem.slack import SlackWebhookError, post_image, post_poem


WEBHOOK_URL = "https://hooks.slack.com/services/T000/B000/xxxx"
POEM = "Roses are red,\nViolets are blue,\nGit commits are here,\nAnd so are you."


def mock_response(status: int, text: str = "") -> MagicMock:
    """Create a MagicMock mimicking a requests.Response."""
    resp = MagicMock()
    resp.status_code = status
    resp.ok = 200 <= status < 300
    resp.text = text
    return resp


# ---------------------------------------------------------------------------
# 1. Happy path
# ---------------------------------------------------------------------------

class TestHappyPath:
    def test_200_ok_returns_none(self):
        resp = mock_response(200, text="ok")
        with patch("requests.post", return_value=resp) as mock_post:
            result = post_poem(WEBHOOK_URL, POEM)
        assert result is None
        mock_post.assert_called_once()

    def test_posts_exactly_once(self):
        resp = mock_response(200, text="ok")
        with patch("requests.post", return_value=resp) as mock_post:
            post_poem(WEBHOOK_URL, POEM)
        assert mock_post.call_count == 1

    def test_json_payload_contains_full_poem(self):
        resp = mock_response(200, text="ok")
        with patch("requests.post", return_value=resp) as mock_post:
            post_poem(WEBHOOK_URL, POEM)
        _, kwargs = mock_post.call_args
        assert kwargs["json"] == {"text": POEM}

    def test_posts_to_correct_url(self):
        resp = mock_response(200, text="ok")
        with patch("requests.post", return_value=resp) as mock_post:
            post_poem(WEBHOOK_URL, POEM)
        args, _ = mock_post.call_args
        assert args[0] == WEBHOOK_URL

    def test_unicode_poem_sent_verbatim(self):
        poem = "日本語の詩 🌸\nLine two — em dash"
        resp = mock_response(200, text="ok")
        with patch("requests.post", return_value=resp) as mock_post:
            post_poem(WEBHOOK_URL, poem)
        _, kwargs = mock_post.call_args
        assert kwargs["json"]["text"] == poem

    def test_multiline_poem_sent_verbatim(self):
        poem = "line1\nline2\nline3\n"
        resp = mock_response(200, text="ok")
        with patch("requests.post", return_value=resp) as mock_post:
            post_poem(WEBHOOK_URL, poem)
        _, kwargs = mock_post.call_args
        assert kwargs["json"]["text"] == poem

    def test_single_char_poem(self):
        poem = "A"
        resp = mock_response(200, text="ok")
        with patch("requests.post", return_value=resp) as mock_post:
            result = post_poem(WEBHOOK_URL, poem)
        assert result is None
        _, kwargs = mock_post.call_args
        assert kwargs["json"]["text"] == "A"

    def test_very_long_poem_not_truncated(self):
        poem = "x" * 10_000
        resp = mock_response(200, text="ok")
        with patch("requests.post", return_value=resp) as mock_post:
            post_poem(WEBHOOK_URL, poem)
        _, kwargs = mock_post.call_args
        assert kwargs["json"]["text"] == poem


# ---------------------------------------------------------------------------
# 2. HTTP errors (non-2xx responses)
# ---------------------------------------------------------------------------

class TestHTTPErrors:
    @pytest.mark.parametrize("status", [400, 403, 404, 429, 500, 503])
    def test_non_2xx_raises_slack_webhook_error(self, status: int):
        resp = mock_response(status, text="error body")
        with patch("requests.post", return_value=resp):
            with pytest.raises(SlackWebhookError):
                post_poem(WEBHOOK_URL, POEM)

    @pytest.mark.parametrize("status", [400, 403, 404, 429, 500])
    def test_error_message_contains_status_code(self, status: int):
        resp = mock_response(status, text="some error")
        with patch("requests.post", return_value=resp):
            with pytest.raises(SlackWebhookError) as exc_info:
                post_poem(WEBHOOK_URL, POEM)
        assert str(status) in str(exc_info.value)

    def test_error_message_contains_response_body(self):
        body = "channel_not_found"
        resp = mock_response(400, text=body)
        with patch("requests.post", return_value=resp):
            with pytest.raises(SlackWebhookError) as exc_info:
                post_poem(WEBHOOK_URL, POEM)
        assert body in str(exc_info.value)

    def test_500_error_body_in_message(self):
        body = "Internal Server Error — upstream failure"
        resp = mock_response(500, text=body)
        with patch("requests.post", return_value=resp):
            with pytest.raises(SlackWebhookError) as exc_info:
                post_poem(WEBHOOK_URL, POEM)
        assert "500" in str(exc_info.value)
        assert body in str(exc_info.value)


# ---------------------------------------------------------------------------
# 3. Network errors
# ---------------------------------------------------------------------------

class TestNetworkErrors:
    def test_connection_error_raises_slack_webhook_error(self):
        original = requests.ConnectionError("Connection refused")
        with patch("requests.post", side_effect=original):
            with pytest.raises(SlackWebhookError):
                post_poem(WEBHOOK_URL, POEM)

    def test_connection_error_preserves_cause(self):
        original = requests.ConnectionError("Connection refused")
        with patch("requests.post", side_effect=original):
            with pytest.raises(SlackWebhookError) as exc_info:
                post_poem(WEBHOOK_URL, POEM)
        assert exc_info.value.__cause__ is original

    def test_timeout_raises_slack_webhook_error(self):
        original = requests.Timeout("Request timed out")
        with patch("requests.post", side_effect=original):
            with pytest.raises(SlackWebhookError):
                post_poem(WEBHOOK_URL, POEM)

    def test_timeout_preserves_cause(self):
        original = requests.Timeout("Request timed out")
        with patch("requests.post", side_effect=original):
            with pytest.raises(SlackWebhookError) as exc_info:
                post_poem(WEBHOOK_URL, POEM)
        assert exc_info.value.__cause__ is original

    def test_ssl_error_raises_slack_webhook_error(self):
        original = requests.exceptions.SSLError("SSL certificate verify failed")
        with patch("requests.post", side_effect=original):
            with pytest.raises(SlackWebhookError):
                post_poem(WEBHOOK_URL, POEM)

    def test_ssl_error_preserves_cause(self):
        original = requests.exceptions.SSLError("SSL certificate verify failed")
        with patch("requests.post", side_effect=original):
            with pytest.raises(SlackWebhookError) as exc_info:
                post_poem(WEBHOOK_URL, POEM)
        assert exc_info.value.__cause__ is original

    def test_missing_schema_raises_slack_webhook_error(self):
        original = requests.exceptions.MissingSchema("Invalid URL: No scheme supplied")
        with patch("requests.post", side_effect=original):
            with pytest.raises(SlackWebhookError):
                post_poem("not-a-url", POEM)

    def test_missing_schema_preserves_cause(self):
        original = requests.exceptions.MissingSchema("Invalid URL: No scheme supplied")
        with patch("requests.post", side_effect=original):
            with pytest.raises(SlackWebhookError) as exc_info:
                post_poem("not-a-url", POEM)
        assert exc_info.value.__cause__ is original

    def test_network_error_message_is_descriptive(self):
        original = requests.ConnectionError("Connection refused")
        with patch("requests.post", side_effect=original):
            with pytest.raises(SlackWebhookError) as exc_info:
                post_poem(WEBHOOK_URL, POEM)
        msg = str(exc_info.value).lower()
        assert "network" in msg or "slack" in msg or "connection" in msg


# ---------------------------------------------------------------------------
# 4. Request shape verification
# ---------------------------------------------------------------------------

class TestRequestShape:
    def test_timeout_parameter_present(self):
        resp = mock_response(200, text="ok")
        with patch("requests.post", return_value=resp) as mock_post:
            post_poem(WEBHOOK_URL, POEM)
        _, kwargs = mock_post.call_args
        assert "timeout" in kwargs

    def test_timeout_value_at_least_one_second(self):
        resp = mock_response(200, text="ok")
        with patch("requests.post", return_value=resp) as mock_post:
            post_poem(WEBHOOK_URL, POEM)
        _, kwargs = mock_post.call_args
        assert kwargs["timeout"] >= 1

    def test_json_kwarg_used_not_data(self):
        resp = mock_response(200, text="ok")
        with patch("requests.post", return_value=resp) as mock_post:
            post_poem(WEBHOOK_URL, POEM)
        _, kwargs = mock_post.call_args
        assert "json" in kwargs
        assert "data" not in kwargs

    def test_text_field_is_full_poem_string(self):
        resp = mock_response(200, text="ok")
        with patch("requests.post", return_value=resp) as mock_post:
            post_poem(WEBHOOK_URL, POEM)
        _, kwargs = mock_post.call_args
        payload = kwargs["json"]
        assert payload["text"] == POEM


# ---------------------------------------------------------------------------
# 5. Exception hierarchy
# ---------------------------------------------------------------------------

class TestExceptionHierarchy:
    def test_slack_webhook_error_is_subclass_of_exception(self):
        assert issubclass(SlackWebhookError, Exception)

    def test_slack_webhook_error_importable_from_module(self):
        from commitpoem.slack import SlackWebhookError as SWE  # noqa: F401
        assert SWE is SlackWebhookError

    def test_post_poem_importable_from_module(self):
        from commitpoem.slack import post_poem as pp  # noqa: F401
        assert pp is post_poem

    def test_slack_webhook_error_can_be_instantiated(self):
        err = SlackWebhookError("test message")
        assert str(err) == "test message"

    def test_slack_webhook_error_can_be_raised_and_caught(self):
        with pytest.raises(SlackWebhookError):
            raise SlackWebhookError("boom")


# ---------------------------------------------------------------------------
# 6. post_image (Slack external upload flow)
# ---------------------------------------------------------------------------

BOT_TOKEN = "xoxb-test-token"
CHANNEL = "C0123ABCD"
UPLOAD_URL = "https://files.slack.com/upload/v1/abc123"
IMAGE = b"\x89PNG\r\n\x1a\nfake"


def mock_api_response(status: int, payload: dict) -> MagicMock:
    """Mock a Slack Web API response that exposes .json()."""
    resp = MagicMock()
    resp.status_code = status
    resp.ok = 200 <= status < 300
    resp.text = json.dumps(payload)
    resp.json.return_value = payload
    return resp


def _reserve_ok() -> MagicMock:
    return mock_api_response(200, {"ok": True, "upload_url": UPLOAD_URL, "file_id": "F1"})


def _post_side_effect(upload_resp: MagicMock, complete_resp: MagicMock):
    def side_effect(url, *args, **kwargs):
        if url == UPLOAD_URL:
            return upload_resp
        if url.endswith("completeUploadExternal"):
            return complete_resp
        raise AssertionError(f"unexpected POST url: {url}")

    return side_effect


class TestPostImageHappy:
    def test_three_step_flow_succeeds(self):
        upload = mock_response(200)
        complete = mock_api_response(200, {"ok": True})
        with (
            patch("requests.get", return_value=_reserve_ok()) as mock_get,
            patch("requests.post", side_effect=_post_side_effect(upload, complete)) as mock_post,
        ):
            result = post_image(BOT_TOKEN, CHANNEL, IMAGE, initial_comment="a poem")
        assert result is None
        mock_get.assert_called_once()
        assert mock_post.call_count == 2

    def test_reserve_sends_filename_and_length(self):
        upload = mock_response(200)
        complete = mock_api_response(200, {"ok": True})
        with (
            patch("requests.get", return_value=_reserve_ok()) as mock_get,
            patch("requests.post", side_effect=_post_side_effect(upload, complete)),
        ):
            post_image(BOT_TOKEN, CHANNEL, IMAGE, filename="art.png")
        _, kwargs = mock_get.call_args
        assert kwargs["params"]["filename"] == "art.png"
        assert kwargs["params"]["length"] == str(len(IMAGE))

    def test_complete_payload_has_channel_and_comment(self):
        upload = mock_response(200)
        complete = mock_api_response(200, {"ok": True})
        captured: dict = {}

        def side_effect(url, *args, **kwargs):
            if url == UPLOAD_URL:
                return upload
            captured.update(kwargs.get("json", {}))
            return complete

        with (
            patch("requests.get", return_value=_reserve_ok()),
            patch("requests.post", side_effect=side_effect),
        ):
            post_image(BOT_TOKEN, CHANNEL, IMAGE, initial_comment="poem text")
        assert captured["channel_id"] == CHANNEL
        assert captured["initial_comment"] == "poem text"
        assert captured["files"][0]["id"] == "F1"

    def test_uploads_raw_image_bytes(self):
        upload = mock_response(200)
        complete = mock_api_response(200, {"ok": True})
        captured: dict = {}

        def side_effect(url, *args, **kwargs):
            if url == UPLOAD_URL:
                captured["data"] = kwargs.get("data")
                return upload
            return complete

        with (
            patch("requests.get", return_value=_reserve_ok()),
            patch("requests.post", side_effect=side_effect),
        ):
            post_image(BOT_TOKEN, CHANNEL, IMAGE)
        assert captured["data"] == IMAGE


class TestPostImageErrors:
    def test_reserve_api_error_raises(self):
        bad = mock_api_response(200, {"ok": False, "error": "invalid_auth"})
        with patch("requests.get", return_value=bad):
            with pytest.raises(SlackWebhookError, match="invalid_auth"):
                post_image(BOT_TOKEN, CHANNEL, IMAGE)

    def test_reserve_http_error_raises(self):
        bad = mock_api_response(500, {"ok": False})
        with patch("requests.get", return_value=bad):
            with pytest.raises(SlackWebhookError, match="500"):
                post_image(BOT_TOKEN, CHANNEL, IMAGE)

    def test_upload_non_2xx_raises(self):
        upload = mock_response(403, text="forbidden")
        with (
            patch("requests.get", return_value=_reserve_ok()),
            patch("requests.post", return_value=upload),
        ):
            with pytest.raises(SlackWebhookError, match="403"):
                post_image(BOT_TOKEN, CHANNEL, IMAGE)

    def test_complete_api_error_raises(self):
        upload = mock_response(200)
        complete = mock_api_response(200, {"ok": False, "error": "channel_not_found"})
        with (
            patch("requests.get", return_value=_reserve_ok()),
            patch("requests.post", side_effect=_post_side_effect(upload, complete)),
        ):
            with pytest.raises(SlackWebhookError, match="channel_not_found"):
                post_image(BOT_TOKEN, CHANNEL, IMAGE)

    def test_network_error_on_reserve_raises(self):
        with patch("requests.get", side_effect=requests.ConnectionError("down")):
            with pytest.raises(SlackWebhookError):
                post_image(BOT_TOKEN, CHANNEL, IMAGE)
