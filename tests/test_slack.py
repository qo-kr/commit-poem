from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from commitpoem.slack import SlackWebhookError, post_poem


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
