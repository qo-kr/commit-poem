from __future__ import annotations

import re
from datetime import datetime, timezone

import requests


class GitHubAuthError(Exception):
    """Raised when GitHub returns HTTP 401 (bad or missing token)."""


class GitHubAPIError(Exception):
    """Raised on all non-auth GitHub API failures and network errors."""


_API_BASE = "https://api.github.com"


def _format_dt(dt: datetime) -> str:
    """Convert a timezone-aware datetime to ISO 8601 UTC string with 'Z' suffix."""
    if dt.tzinfo is None:
        raise ValueError(f"datetime must be timezone-aware, got naive: {dt!r}")
    utc_dt = dt.astimezone(timezone.utc)
    return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _validate_inputs(token: str, repo: str, since: datetime, until: datetime) -> None:
    """Validate all inputs before making any network call."""
    if token is None:
        raise TypeError("token must not be None")
    if repo is None:
        raise TypeError("repo must not be None")
    parts = repo.split("/")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(f"repo must be in 'owner/repo' format, got: {repo!r}")
    # Validate datetimes (raises ValueError for naive datetimes)
    _format_dt(since)
    _format_dt(until)
    if since > until:
        raise ValueError(f"since ({since!r}) must not be after until ({until!r})")


def _parse_next_link(link_header: str | None) -> str | None:
    """Parse the 'Link' header and return the URL for rel='next', or None."""
    if not link_header:
        return None
    # Link: <https://api.github.com/...?page=2>; rel="next", <...>; rel="last"
    for part in link_header.split(","):
        part = part.strip()
        match = re.match(r'<([^>]+)>\s*;\s*rel="next"', part)
        if match:
            return match.group(1)
    return None


def _extract_messages(items: list[dict]) -> list[str]:
    """Extract commit messages from a page of GitHub API commit items."""
    messages: list[str] = []
    for item in items:
        try:
            messages.append(item["commit"]["message"])
        except (KeyError, TypeError) as e:
            raise GitHubAPIError(
                f"Unexpected commit item structure; missing expected keys: {e}"
            ) from e
    return messages


def fetch_org_repos(token: str, org: str) -> list[str]:
    """Return list of 'org/repo' strings for all repos in the given org.

    Args:
        token: GitHub personal access token.
        org: GitHub organization login name.

    Returns:
        List of repo full names in 'org/repo' format.

    Raises:
        GitHubAuthError: If GitHub returns HTTP 401.
        GitHubAPIError: On any other API or network error.
    """
    url: str | None = f"{_API_BASE}/orgs/{org}/repos"
    params: dict | None = {"per_page": 100, "type": "all"}
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    repos: list[str] = []
    while url is not None:
        try:
            response = requests.get(url, headers=headers, params=params)
        except requests.exceptions.RequestException as e:
            raise GitHubAPIError(f"Network error while fetching repos for {org}: {e}") from e
        if response.status_code == 401:
            raise GitHubAuthError(f"Authentication failed for org {org}: invalid or missing token")
        if not response.ok:
            raise GitHubAPIError(
                f"GitHub API error for org {org}: HTTP {response.status_code} — {response.text}"
            )
        repos.extend(item["full_name"] for item in response.json())
        url = _parse_next_link(response.headers.get("Link"))
        params = None
    return repos


def fetch_org_commits(token: str, org: str, since: datetime, until: datetime) -> list[str]:
    """Return all commit messages across every repo in *org* between *since* and *until*.

    Args:
        token: GitHub personal access token.
        org: GitHub organization login name.
        since: Start of the time range (timezone-aware datetime, inclusive).
        until: End of the time range (timezone-aware datetime, inclusive).

    Returns:
        Flat list of commit message strings from all repos (newest-first per repo).

    Raises:
        GitHubAuthError: If GitHub returns HTTP 401.
        GitHubAPIError: On any other API or network error.
    """
    repos = fetch_org_repos(token, org)
    all_messages: list[str] = []
    for repo in repos:
        try:
            all_messages.extend(fetch_commits(token, repo, since, until))
        except GitHubAPIError:
            pass  # skip repos that are inaccessible (e.g. private without permission)
    return all_messages


def fetch_commits(token: str, repo: str, since: datetime, until: datetime) -> list[str]:
    """Return commit messages for *repo* between *since* and *until*.

    Args:
        token: GitHub personal access token.
        repo: Repository in 'owner/repo' format.
        since: Start of the time range (timezone-aware datetime, inclusive).
        until: End of the time range (timezone-aware datetime, inclusive).

    Returns:
        List of commit message strings in API response order (newest-first).

    Raises:
        TypeError: If token or repo is None.
        ValueError: If repo format is invalid, datetimes are naive, or since > until.
        GitHubAuthError: If GitHub returns HTTP 401.
        GitHubAPIError: If GitHub returns any other non-2xx status, or a network error occurs.
    """
    _validate_inputs(token, repo, since, until)

    url: str | None = f"{_API_BASE}/repos/{repo}/commits"
    params: dict | None = {
        "since": _format_dt(since),
        "until": _format_dt(until),
        "per_page": 100,
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }

    all_messages: list[str] = []

    while url is not None:
        try:
            response = requests.get(url, headers=headers, params=params)
        except requests.exceptions.RequestException as e:
            raise GitHubAPIError(f"Network error while fetching commits for {repo}: {e}") from e

        if response.status_code == 401:
            raise GitHubAuthError(
                f"Authentication failed for {repo}: invalid or missing token"
            )
        if response.status_code == 404:
            raise GitHubAPIError(f"Repository not found: {repo}")
        if not response.ok:
            raise GitHubAPIError(
                f"GitHub API error for {repo}: HTTP {response.status_code} — {response.text}"
            )

        try:
            items = response.json()
        except Exception as e:
            raise GitHubAPIError(
                f"Failed to decode JSON response from GitHub for {repo}: {e}"
            ) from e

        all_messages.extend(_extract_messages(items))

        url = _parse_next_link(response.headers.get("Link"))
        params = None  # Next URL is fully-qualified; no extra params needed

    return all_messages
