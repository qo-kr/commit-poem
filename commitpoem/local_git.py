from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)


class LocalGitError(Exception):
    """A local repository could not be read or its inputs were invalid."""


@dataclass(frozen=True)
class LocalRepository:
    """Pair a local checkout with its canonical GitHub owner/repository."""

    path: Path
    remote: str


def _git(path: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", "-C", str(path), *args], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=60,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0", **(env or {})},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise LocalGitError(f"Local git command failed for {path}: {type(exc).__name__}") from exc


def _github_name(remote: str) -> str | None:
    if remote.startswith("git@github.com:"):
        name = remote.removeprefix("git@github.com:")
    else:
        parsed = urlsplit(remote)
        if parsed.hostname != "github.com":
            return None
        name = parsed.path.lstrip("/")
    name = name.rstrip("/").removesuffix(".git")
    return name if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", name) else None


def discover_repositories(roots: list[Path]) -> list[LocalRepository]:
    """Pair each root or its immediate Git checkout children with GitHub origin.

    Linked worktrees (.git files) are supported. No traversal into source trees,
    dependency folders or arbitrary directories is needed.
    """
    repositories: list[LocalRepository] = []
    seen: set[Path] = set()
    for root in roots:
        root = root.expanduser().resolve()
        if not root.is_dir():
            raise LocalGitError(f"Local repository root does not exist: {root}")
        # A parent checkout (e.g. work-oq) can contain independent nested repos.
        candidates = [root, *sorted(path for path in root.iterdir() if path.name != ".git")]
        for path in candidates:
            path = path.resolve()
            if path in seen or not (path / ".git").exists():
                continue
            seen.add(path)
            result = _git(path, "config", "--get", "remote.origin.url")
            remote = _github_name(result.stdout.strip()) if result.returncode == 0 else None
            if remote is None:
                logger.info("Skipping checkout without a GitHub origin: %s", path)
                continue
            repositories.append(LocalRepository(path, remote))
    return repositories


def update_main(repository: LocalRepository) -> bool:
    """Fast-forward a clean main checkout only; never stash, rebase or resolve conflicts.

    Dirty, detached and other-branch worktrees are skipped before any network call.
    Fetch/fast-forward failures leave local commits intact and are reported for review.
    """
    path = repository.path

    def clean_main() -> bool:
        for state in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply", "BISECT_LOG"):
            result = _git(path, "rev-parse", "--git-path", state)
            state_path = Path(result.stdout.strip())
            if result.returncode != 0 or (state_path if state_path.is_absolute() else path / state_path).exists():
                return False
        branch = _git(path, "symbolic-ref", "--quiet", "--short", "HEAD")
        status = _git(path, "status", "--porcelain", "--untracked-files=all", "--ignore-submodules=none")
        return (
            branch.returncode == 0 and branch.stdout.strip() == "main"
            and status.returncode == 0 and not status.stdout
        )

    if not clean_main():
        logger.info("main update skipped (requires clean main checkout): %s", repository.remote)
        return False
    try:
        fetched = _git(path, "fetch", "--no-tags", "origin", "refs/heads/main:refs/remotes/origin/main")
        if fetched.returncode != 0 or not clean_main():
            logger.warning("main update skipped after fetch/access or checkout-state change: %s", repository.remote)
            return False
        index_result = _git(path, "rev-parse", "--git-path", "index")
        index = Path(index_result.stdout.strip())
        index = index if index.is_absolute() else path / index
        if index_result.returncode != 0 or not index.is_file():
            logger.warning("main update skipped: cannot locate checkout index for %s", repository.remote)
            return False
        lock = index.with_name(index.name + ".lock")
        try:
            lock_file = lock.open("xb")
        except FileExistsError:
            logger.warning("main update skipped: another Git command holds the index for %s", repository.remote)
            return False
        attempted = False
        try:
            with lock_file, index.open("rb") as source:
                shutil.copyfileobj(source, lock_file)
            if not clean_main():
                logger.warning("main update skipped: checkout changed before lock acquisition: %s", repository.remote)
                return False
            # Ordinary checkout/switch/commit commands must take index.lock, so they
            # cannot change this checkout while merging. Git operates on our copied
            # index and locks index.lock.lock; publish its final index atomically.
            attempted = True
            merged = _git(path, "-c", "core.hooksPath=/dev/null", "merge", "--ff-only", "--no-autostash",
                          "--no-edit", "refs/remotes/origin/main", env={"GIT_INDEX_FILE": str(lock)})
        finally:
            if attempted and lock.exists():
                os.replace(lock, index)
            else:
                lock.unlink(missing_ok=True)
        if merged.returncode != 0:
            logger.warning("main needs manual review (divergence or fast-forward failure): %s", repository.remote)
            return False
    except LocalGitError:
        logger.warning("main update could not complete; retaining local history: %s", repository.remote)
        return False
    logger.info("main fast-forward verified: %s", repository.remote)
    return True


def fetch_local_commits(
    roots: list[Path], since: datetime, until: datetime,
    *, organizations: tuple[str, ...] = (), sync_main: bool = False,
) -> list[str]:
    """Read local/remote-tracking branch history, deduplicated by repository and SHA."""
    if since.tzinfo is None or until.tzinfo is None or since > until:
        raise LocalGitError("Local commit dates must be aware and ordered")
    repositories = discover_repositories(roots)
    allowed = {org.casefold() for org in organizations}
    repositories = [repo for repo in repositories if not allowed or repo.remote.split("/")[0].casefold() in allowed]
    for org in organizations:
        count = sum(repo.remote.split("/")[0].casefold() == org.casefold() for repo in repositories)
        logger.info("Local organization %s: %d paired checkouts", org, count)
        if count == 0:
            logger.warning("No local checkout found for organization %s", org)
    if not repositories:
        raise LocalGitError("No paired GitHub repositories matched the configured local roots/organizations")
    messages: list[str] = []
    seen: set[tuple[str, str]] = set()
    for repo in repositories:
        if sync_main:
            update_main(repo)
        # Include detached worktree HEADs as well as branch and origin history.
        head = _git(repo.path, "rev-parse", "--verify", "HEAD")
        refs = ["--branches", "--remotes=origin"]
        if head.returncode == 0:
            refs.append("HEAD")
        result = _git(repo.path, "log", *refs, f"--since-as-filter={since.isoformat()}",
                      f"--until={until.isoformat()}", "--format=%H%x00%B%x00")
        if result.returncode != 0:
            raise LocalGitError(f"Cannot read commit history for {repo.remote} at {repo.path}")
        parts = result.stdout.split("\x00")
        for index in range(0, len(parts) - 1, 2):
            sha, message = parts[index].strip(), parts[index + 1].strip()
            key = (repo.remote.casefold(), sha)
            if key not in seen:
                seen.add(key)
                messages.append(f"[{repo.remote}] {message}")
    logger.info("Collected %d unique commits from %d local checkouts", len(messages), len(repositories))
    return messages
