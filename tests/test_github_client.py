from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest
import requests

from commitpoem.github_client import (
    GitHubAuthError,
    GitHubAPIError,
    fetch_commits,
    _format_dt,
    _parse_next_link,
    _extract_messages,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def utc_dt(year: int, month: int, day: int, hour: int = 0, minute: int = 0, second: int = 0) -> datetime:
    """Return a timezone-aware UTC datetime."""
    return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)


def commit_item(msg: str) -> dict:
    """Build a minimal GitHub API commit dict."""
    return {"commit": {"message": msg}}


def mock_response(
    status: int,
    json_body=None,
    headers: dict | None = None,
    text: str = "",
) -> MagicMock:
    """Create a MagicMock mimicking a requests.Response."""
    resp = MagicMock()
    resp.status_code = status
    resp.ok = 200 <= status < 300
    resp.text = text if text else (json.dumps(json_body) if json_body is not None else "")
    resp.headers = headers or {}
    if json_body is not None:
        resp.json.return_value = json_body
    else:
        resp.json.side_effect = ValueError("No JSON")
    return resp


def page_response(msgs: list[str], next_url: str | None = None) -> MagicMock:
    """Build a mock response for a page of commits, with optional Link header."""
    items = [commit_item(m) for m in msgs]
    headers: dict = {}
    if next_url:
        headers["Link"] = f'<{next_url}>; rel="next", <https://api.github.com/last>; rel="last"'
    return mock_response(200, items, headers=headers)


SINCE = utc_dt(2026, 3, 1)
UNTIL = utc_dt(2026, 3, 31)
TOKEN = "ghp_test_token"
REPO = "owner/repo"


# ---------------------------------------------------------------------------
# 1. Happy-path / single page
# ---------------------------------------------------------------------------

class TestHappyPath:
    def test_single_commit(self):
        with patch("requests.get", return_value=page_response(["fix: bug"])) as mock_get:
            result = fetch_commits(TOKEN, REPO, SINCE, UNTIL)
        assert result == ["fix: bug"]
        mock_get.assert_called_once()

    def test_three_commits_preserves_order(self):
        msgs = ["commit C", "commit B", "commit A"]
        with patch("requests.get", return_value=page_response(msgs)):
            result = fetch_commits(TOKEN, REPO, SINCE, UNTIL)
        assert result == msgs

    def test_empty_array_returns_empty_list(self):
        with patch("requests.get", return_value=page_response([])):
            result = fetch_commits(TOKEN, REPO, SINCE, UNTIL)
        assert result == []

    def test_empty_string_message_preserved(self):
        with patch("requests.get", return_value=page_response([""])):
            result = fetch_commits(TOKEN, REPO, SINCE, UNTIL)
        assert result == [""]

    def test_unicode_and_newlines_in_message(self):
        msg = "feat: 日本語\n\nBroken newlines 🎉"
        with patch("requests.get", return_value=page_response([msg])):
            result = fetch_commits(TOKEN, REPO, SINCE, UNTIL)
        assert result == [msg]


# ---------------------------------------------------------------------------
# 2. Pagination
# ---------------------------------------------------------------------------

class TestPagination:
    def test_two_pages_101_commits(self):
        page1_msgs = [f"commit {i}" for i in range(100)]
        page2_msgs = ["commit 100"]
        next_url = "https://api.github.com/repos/owner/repo/commits?page=2&per_page=100"

        page1 = page_response(page1_msgs, next_url=next_url)
        page2 = page_response(page2_msgs)

        with patch("requests.get", side_effect=[page1, page2]) as mock_get:
            result = fetch_commits(TOKEN, REPO, SINCE, UNTIL)

        assert len(result) == 101
        assert result == page1_msgs + page2_msgs
        assert mock_get.call_count == 2

    def test_exactly_100_commits_no_link_header_single_call(self):
        msgs = [f"commit {i}" for i in range(100)]
        with patch("requests.get", return_value=page_response(msgs)) as mock_get:
            result = fetch_commits(TOKEN, REPO, SINCE, UNTIL)
        assert len(result) == 100
        mock_get.assert_called_once()

    def test_link_with_only_rel_last_terminates(self):
        items = [commit_item("only commit")]
        headers = {"Link": '<https://api.github.com/last>; rel="last"'}
        resp = mock_response(200, items, headers=headers)
        with patch("requests.get", return_value=resp) as mock_get:
            result = fetch_commits(TOKEN, REPO, SINCE, UNTIL)
        assert result == ["only commit"]
        mock_get.assert_called_once()


# ---------------------------------------------------------------------------
# 3. Input validation (no network calls)
# ---------------------------------------------------------------------------

class TestInputValidation:
    def test_repo_without_slash_raises_value_error(self):
        with pytest.raises(ValueError, match="owner/repo"):
            fetch_commits(TOKEN, "badrepo", SINCE, UNTIL)

    def test_repo_with_two_slashes_raises_value_error(self):
        with pytest.raises(ValueError):
            fetch_commits(TOKEN, "a/b/c", SINCE, UNTIL)

    def test_repo_empty_owner_raises_value_error(self):
        with pytest.raises(ValueError):
            fetch_commits(TOKEN, "/repo", SINCE, UNTIL)

    def test_repo_empty_name_raises_value_error(self):
        with pytest.raises(ValueError):
            fetch_commits(TOKEN, "owner/", SINCE, UNTIL)

    def test_since_after_until_raises_value_error(self):
        with pytest.raises(ValueError):
            fetch_commits(TOKEN, REPO, UNTIL, SINCE)

    def test_naive_since_raises(self):
        naive = datetime(2026, 3, 1)
        with pytest.raises((ValueError, TypeError)):
            fetch_commits(TOKEN, REPO, naive, UNTIL)

    def test_naive_until_raises(self):
        naive = datetime(2026, 3, 31)
        with pytest.raises((ValueError, TypeError)):
            fetch_commits(TOKEN, REPO, SINCE, naive)

    def test_token_none_raises_type_error(self):
        with pytest.raises(TypeError):
            fetch_commits(None, REPO, SINCE, UNTIL)  # type: ignore[arg-type]

    def test_repo_none_raises_type_error(self):
        with pytest.raises(TypeError):
            fetch_commits(TOKEN, None, SINCE, UNTIL)  # type: ignore[arg-type]

    def test_no_network_call_on_validation_error(self):
        with patch("requests.get") as mock_get:
            with pytest.raises(ValueError):
                fetch_commits(TOKEN, "badrepo", SINCE, UNTIL)
        mock_get.assert_not_called()


# ---------------------------------------------------------------------------
# 4. Auth errors
# ---------------------------------------------------------------------------

class TestAuthErrors:
    def test_http_401_raises_github_auth_error(self):
        resp = mock_response(401, text="Unauthorized")
        with patch("requests.get", return_value=resp):
            with pytest.raises(GitHubAuthError) as exc_info:
                fetch_commits(TOKEN, REPO, SINCE, UNTIL)
        assert REPO in str(exc_info.value)

    def test_http_401_message_contains_description(self):
        resp = mock_response(401, text="Bad credentials")
        with patch("requests.get", return_value=resp):
            with pytest.raises(GitHubAuthError) as exc_info:
                fetch_commits(TOKEN, REPO, SINCE, UNTIL)
        msg = str(exc_info.value).lower()
        assert "authentication" in msg or "token" in msg

    def test_empty_token_401_raises_github_auth_error(self):
        resp = mock_response(401, text="Requires authentication")
        with patch("requests.get", return_value=resp):
            with pytest.raises(GitHubAuthError):
                fetch_commits("", REPO, SINCE, UNTIL)

    def test_github_auth_error_not_subclass_of_api_error(self):
        assert not issubclass(GitHubAuthError, GitHubAPIError)
        assert not issubclass(GitHubAPIError, GitHubAuthError)


# ---------------------------------------------------------------------------
# 5. API errors
# ---------------------------------------------------------------------------

class TestAPIErrors:
    def test_http_404_raises_github_api_error(self):
        resp = mock_response(404, text="Not Found")
        with patch("requests.get", return_value=resp):
            with pytest.raises(GitHubAPIError) as exc_info:
                fetch_commits(TOKEN, REPO, SINCE, UNTIL)
        assert "not found" in str(exc_info.value).lower() or REPO in str(exc_info.value)

    def test_http_403_raises_github_api_error(self):
        resp = mock_response(
            403,
            text="rate limit exceeded",
            headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1711929600"},
        )
        with patch("requests.get", return_value=resp):
            with pytest.raises(GitHubAPIError):
                fetch_commits(TOKEN, REPO, SINCE, UNTIL)

    def test_http_422_raises_github_api_error_with_status(self):
        resp = mock_response(422, text="Unprocessable Entity")
        with patch("requests.get", return_value=resp):
            with pytest.raises(GitHubAPIError) as exc_info:
                fetch_commits(TOKEN, REPO, SINCE, UNTIL)
        assert "422" in str(exc_info.value)

    def test_http_500_raises_github_api_error_with_status(self):
        resp = mock_response(500, text="Internal Server Error")
        with patch("requests.get", return_value=resp):
            with pytest.raises(GitHubAPIError) as exc_info:
                fetch_commits(TOKEN, REPO, SINCE, UNTIL)
        assert "500" in str(exc_info.value)

    def test_http_500_body_included_in_message(self):
        body = "Something went very wrong"
        resp = mock_response(500, text=body)
        with patch("requests.get", return_value=resp):
            with pytest.raises(GitHubAPIError) as exc_info:
                fetch_commits(TOKEN, REPO, SINCE, UNTIL)
        assert body in str(exc_info.value)


# ---------------------------------------------------------------------------
# 6. Network errors
# ---------------------------------------------------------------------------

class TestNetworkErrors:
    def test_connection_error_raises_github_api_error_chained(self):
        original = requests.ConnectionError("Connection refused")
        with patch("requests.get", side_effect=original):
            with pytest.raises(GitHubAPIError) as exc_info:
                fetch_commits(TOKEN, REPO, SINCE, UNTIL)
        assert exc_info.value.__cause__ is original

    def test_timeout_raises_github_api_error_chained(self):
        original = requests.Timeout("Request timed out")
        with patch("requests.get", side_effect=original):
            with pytest.raises(GitHubAPIError) as exc_info:
                fetch_commits(TOKEN, REPO, SINCE, UNTIL)
        assert exc_info.value.__cause__ is original

    def test_ssl_error_raises_github_api_error_chained(self):
        original = requests.exceptions.SSLError("SSL certificate error")
        with patch("requests.get", side_effect=original):
            with pytest.raises(GitHubAPIError) as exc_info:
                fetch_commits(TOKEN, REPO, SINCE, UNTIL)
        assert exc_info.value.__cause__ is original

    def test_network_error_mid_pagination_raises_api_error(self):
        page1_msgs = [f"commit {i}" for i in range(100)]
        next_url = "https://api.github.com/repos/owner/repo/commits?page=2"
        page1 = page_response(page1_msgs, next_url=next_url)
        network_error = requests.ConnectionError("Connection lost")

        with patch("requests.get", side_effect=[page1, network_error]):
            with pytest.raises(GitHubAPIError) as exc_info:
                fetch_commits(TOKEN, REPO, SINCE, UNTIL)
        assert exc_info.value.__cause__ is network_error


# ---------------------------------------------------------------------------
# 7. Malformed responses
# ---------------------------------------------------------------------------

class TestMalformedResponses:
    def test_200_non_json_body_raises_api_error(self):
        resp = MagicMock()
        resp.status_code = 200
        resp.ok = True
        resp.headers = {}
        resp.json.side_effect = ValueError("No JSON object could be decoded")
        with patch("requests.get", return_value=resp):
            with pytest.raises(GitHubAPIError):
                fetch_commits(TOKEN, REPO, SINCE, UNTIL)

    def test_200_item_missing_commit_key_raises_api_error(self):
        items = [{"sha": "abc123", "author": "someone"}]  # no "commit" key
        resp = mock_response(200, items)
        with patch("requests.get", return_value=resp):
            with pytest.raises(GitHubAPIError):
                fetch_commits(TOKEN, REPO, SINCE, UNTIL)

    def test_200_item_missing_message_key_raises_api_error(self):
        items = [{"commit": {"author": "someone"}}]  # "commit" present, "message" missing
        resp = mock_response(200, items)
        with patch("requests.get", return_value=resp):
            with pytest.raises(GitHubAPIError):
                fetch_commits(TOKEN, REPO, SINCE, UNTIL)


# ---------------------------------------------------------------------------
# 8. Request shape verification
# ---------------------------------------------------------------------------

class TestRequestShape:
    def test_authorization_header(self):
        with patch("requests.get", return_value=page_response([])) as mock_get:
            fetch_commits(TOKEN, REPO, SINCE, UNTIL)
        _, kwargs = mock_get.call_args
        headers = kwargs.get("headers", {})
        assert headers.get("Authorization") == f"Bearer {TOKEN}"

    def test_accept_header(self):
        with patch("requests.get", return_value=page_response([])) as mock_get:
            fetch_commits(TOKEN, REPO, SINCE, UNTIL)
        _, kwargs = mock_get.call_args
        headers = kwargs.get("headers", {})
        assert headers.get("Accept") == "application/vnd.github+json"

    def test_since_param_z_suffix(self):
        with patch("requests.get", return_value=page_response([])) as mock_get:
            fetch_commits(TOKEN, REPO, SINCE, UNTIL)
        _, kwargs = mock_get.call_args
        params = kwargs.get("params", {})
        assert params["since"] == "2026-03-01T00:00:00Z"

    def test_until_param_z_suffix(self):
        with patch("requests.get", return_value=page_response([])) as mock_get:
            fetch_commits(TOKEN, REPO, SINCE, UNTIL)
        _, kwargs = mock_get.call_args
        params = kwargs.get("params", {})
        assert params["until"] == "2026-03-31T00:00:00Z"

    def test_per_page_is_100(self):
        with patch("requests.get", return_value=page_response([])) as mock_get:
            fetch_commits(TOKEN, REPO, SINCE, UNTIL)
        _, kwargs = mock_get.call_args
        params = kwargs.get("params", {})
        assert params["per_page"] == 100

    def test_non_utc_datetime_converted_to_utc(self):
        # UTC+9 datetime 2026-03-01 09:00:00+09:00 == 2026-03-01 00:00:00Z
        from datetime import timezone as tz
        jst = tz(timedelta(hours=9))
        since_jst = datetime(2026, 3, 1, 9, 0, 0, tzinfo=jst)
        until_jst = datetime(2026, 3, 31, 9, 0, 0, tzinfo=jst)
        with patch("requests.get", return_value=page_response([])) as mock_get:
            fetch_commits(TOKEN, REPO, since_jst, until_jst)
        _, kwargs = mock_get.call_args
        params = kwargs.get("params", {})
        assert params["since"] == "2026-03-01T00:00:00Z"
        assert params["until"] == "2026-03-31T00:00:00Z"


# ---------------------------------------------------------------------------
# Unit tests for helpers
# ---------------------------------------------------------------------------

class TestFormatDt:
    def test_utc_datetime(self):
        dt = utc_dt(2026, 3, 1, 12, 30, 45)
        assert _format_dt(dt) == "2026-03-01T12:30:45Z"

    def test_naive_datetime_raises(self):
        naive = datetime(2026, 3, 1)
        with pytest.raises(ValueError):
            _format_dt(naive)

    def test_non_utc_converted(self):
        jst = timezone(timedelta(hours=9))
        dt = datetime(2026, 3, 1, 9, 0, 0, tzinfo=jst)
        assert _format_dt(dt) == "2026-03-01T00:00:00Z"


class TestParseNextLink:
    def test_none_returns_none(self):
        assert _parse_next_link(None) is None

    def test_empty_string_returns_none(self):
        assert _parse_next_link("") is None

    def test_link_with_next(self):
        header = '<https://api.github.com/repos/o/r/commits?page=2>; rel="next", <https://api.github.com/repos/o/r/commits?page=5>; rel="last"'
        result = _parse_next_link(header)
        assert result == "https://api.github.com/repos/o/r/commits?page=2"

    def test_link_without_next(self):
        header = '<https://api.github.com/repos/o/r/commits?page=5>; rel="last"'
        assert _parse_next_link(header) is None

    def test_link_with_only_next(self):
        header = '<https://api.github.com/repos/o/r/commits?page=3>; rel="next"'
        assert _parse_next_link(header) == "https://api.github.com/repos/o/r/commits?page=3"


class TestExtractMessages:
    def test_empty_list(self):
        assert _extract_messages([]) == []

    def test_multiple_items(self):
        items = [commit_item("msg1"), commit_item("msg2")]
        assert _extract_messages(items) == ["msg1", "msg2"]

    def test_missing_commit_key_raises(self):
        with pytest.raises(GitHubAPIError):
            _extract_messages([{"sha": "abc"}])

    def test_missing_message_key_raises(self):
        with pytest.raises(GitHubAPIError):
            _extract_messages([{"commit": {}}])


class TestExceptionHierarchy:
    def test_both_importable(self):
        from commitpoem.github_client import GitHubAuthError, GitHubAPIError  # noqa: F401

    def test_both_inherit_from_exception(self):
        assert issubclass(GitHubAuthError, Exception)
        assert issubclass(GitHubAPIError, Exception)

    def test_distinct_not_related(self):
        assert not issubclass(GitHubAuthError, GitHubAPIError)
        assert not issubclass(GitHubAPIError, GitHubAuthError)
