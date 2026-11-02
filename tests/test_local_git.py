from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from commitpoem.local_git import LocalGitError, LocalRepository, discover_repositories, fetch_local_commits, update_main


def git(path: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    path = tmp_path / "project"
    path.mkdir()
    git(path, "init", "-b", "main")
    git(path, "config", "user.email", "test@example.org")
    git(path, "config", "user.name", "Test")
    git(path, "remote", "add", "origin", "git@github.com:qo-kr/project.git")
    (path / "tracked.txt").write_text("initial")
    git(path, "add", "tracked.txt")
    git(path, "commit", "--allow-empty", "-m", "feat: cache for team collaboration")
    return path


def test_pairs_local_path_with_github_origin(repository: Path) -> None:
    repos = discover_repositories([repository.parent])
    assert [(repo.path, repo.remote) for repo in repos] == [(repository, "qo-kr/project")]


def test_repository_root_also_discovers_nested_checkouts(repository: Path) -> None:
    nested = repository / "nested"
    nested.mkdir()
    git(nested, "init")
    git(nested, "remote", "add", "origin", "https://github.com/qo-kr/nested.git")
    assert {repo.remote for repo in discover_repositories([repository])} == {"qo-kr/project", "qo-kr/nested"}


def test_local_collection_filters_orgs_and_deduplicates_clones(repository: Path, tmp_path: Path) -> None:
    clone = tmp_path / "clone"
    git(tmp_path, "clone", str(repository), str(clone))
    git(clone, "remote", "set-url", "origin", "https://github.com/qo-kr/project.git")
    since, until = datetime(2000, 1, 1, tzinfo=timezone.utc), datetime(2035, 1, 1, tzinfo=timezone.utc)
    messages = fetch_local_commits([tmp_path], since, until, organizations=("qo-kr",))
    assert messages == ["[qo-kr/project] feat: cache for team collaboration"]
    with pytest.raises(LocalGitError, match="No paired"):
        fetch_local_commits([tmp_path], since, until, organizations=("k-gen-food",))


def test_uncommitted_work_is_untouched(repository: Path) -> None:
    dirty = repository / "unfinished.txt"
    dirty.write_text("do not change me")
    before = git(repository, "status", "--porcelain")
    fetch_local_commits([repository], datetime(2000, 1, 1, tzinfo=timezone.utc),
                       datetime(2035, 1, 1, tzinfo=timezone.utc))
    assert git(repository, "status", "--porcelain") == before
    assert dirty.read_text() == "do not change me"


def test_commits_on_feature_branches_are_included(repository: Path) -> None:
    git(repository, "checkout", "-b", "feature")
    git(repository, "commit", "--allow-empty", "-m", "fix: separate branch")
    git(repository, "checkout", "main")
    messages = fetch_local_commits([repository], datetime(2000, 1, 1, tzinfo=timezone.utc),
                                  datetime(2035, 1, 1, tzinfo=timezone.utc))
    assert any("separate branch" in message for message in messages)
    assert git(repository, "branch", "--show-current") == "main"


def test_empty_repository_has_no_commits(tmp_path: Path) -> None:
    git(tmp_path, "init")
    git(tmp_path, "remote", "add", "origin", "https://github.com/k-gen-food/new.git")
    assert fetch_local_commits([tmp_path], datetime(2000, 1, 1, tzinfo=timezone.utc),
                               datetime(2035, 1, 1, tzinfo=timezone.utc)) == []


def test_local_window_filters_commits(repository: Path) -> None:
    assert fetch_local_commits([repository], datetime(1990, 1, 1, tzinfo=timezone.utc),
                               datetime(1991, 1, 1, tzinfo=timezone.utc)) == []


@pytest.fixture
def upstream(repository: Path, tmp_path: Path) -> Path:
    bare = tmp_path / 'upstream.git'
    git(tmp_path, 'init', '--bare', '--initial-branch=main', str(bare))
    git(repository, 'remote', 'set-url', 'origin', str(bare))
    git(repository, 'push', '-u', 'origin', 'main')
    contributor = tmp_path / 'contributor'
    git(tmp_path, 'clone', str(bare), str(contributor))
    git(contributor, 'config', 'user.email', 'test@example.org')
    git(contributor, 'config', 'user.name', 'Test')
    (contributor / 'tracked.txt').write_text('upstream content')
    git(contributor, 'add', 'tracked.txt')
    git(contributor, 'commit', '--allow-empty', '-m', 'feat: upstream work')
    git(contributor, 'push', 'origin', 'main')
    return contributor


def test_clean_main_fast_forwards(repository: Path, upstream: Path) -> None:
    assert update_main(LocalRepository(repository, 'qo-kr/project'))
    assert git(repository, 'rev-parse', 'HEAD') == git(upstream, 'rev-parse', 'HEAD')
    assert git(repository, 'branch', '--show-current') == 'main'
    assert (repository / 'tracked.txt').read_text() == 'upstream content'
    assert git(repository, 'status', '--porcelain') == ''


def test_dirty_main_is_never_updated(repository: Path, upstream: Path) -> None:
    (repository / 'unfinished.txt').write_text('keep this')
    before = git(repository, 'rev-parse', 'HEAD')
    assert not update_main(LocalRepository(repository, 'qo-kr/project'))
    assert git(repository, 'rev-parse', 'HEAD') == before
    assert (repository / 'unfinished.txt').read_text() == 'keep this'


def test_diverged_main_keeps_both_histories_and_no_merge_state(repository: Path, upstream: Path) -> None:
    git(repository, 'commit', '--allow-empty', '-m', 'local unique work')
    before = git(repository, 'rev-parse', 'HEAD')
    assert not update_main(LocalRepository(repository, 'qo-kr/project'))
    assert git(repository, 'rev-parse', 'HEAD') == before
    assert not (repository / '.git/MERGE_HEAD').exists()
    assert git(repository, 'status', '--porcelain') == ''
    assert git(repository, 'rev-parse', 'origin/main') == git(upstream, 'rev-parse', 'HEAD')


def test_feature_checkout_is_not_switched(repository: Path, upstream: Path) -> None:
    git(repository, 'checkout', '-b', 'feature')
    before = git(repository, 'rev-parse', 'HEAD')
    assert not update_main(LocalRepository(repository, 'qo-kr/project'))
    assert git(repository, 'branch', '--show-current') == 'feature'
    assert git(repository, 'rev-parse', 'HEAD') == before


def test_in_progress_git_operation_is_skipped(repository: Path, upstream: Path) -> None:
    from unittest.mock import patch
    from commitpoem import local_git
    (repository / '.git/CHERRY_PICK_HEAD').write_text(git(repository, 'rev-parse', 'HEAD') + '\n')
    before = git(repository, 'rev-parse', 'HEAD')
    with patch('commitpoem.local_git._git', wraps=local_git._git) as command:
        assert not update_main(LocalRepository(repository, 'qo-kr/project'))
    assert git(repository, 'rev-parse', 'HEAD') == before
    assert not any('fetch' in call.args for call in command.call_args_list)


def test_git_config_cannot_hide_untracked_changes_from_main_guard(repository: Path, upstream: Path) -> None:
    git(repository, 'config', 'status.showUntrackedFiles', 'no')
    (repository / 'unfinished.txt').write_text('keep this')
    before = git(repository, 'rev-parse', 'HEAD')
    assert not update_main(LocalRepository(repository, 'qo-kr/project'))
    assert git(repository, 'rev-parse', 'HEAD') == before


def test_backdated_tip_does_not_hide_in_window_ancestor(repository: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for stamp, message in [('2026-11-01T12:00:00+00:00', 'actual window commit'),
                           ('2020-01-01T12:00:00+00:00', 'backdated tip')]:
        monkeypatch.setenv('GIT_AUTHOR_DATE', stamp)
        monkeypatch.setenv('GIT_COMMITTER_DATE', stamp)
        git(repository, 'commit', '--allow-empty', '-m', message)
    messages = fetch_local_commits([repository], datetime(2026, 11, 1, tzinfo=timezone.utc),
                                   datetime(2026, 11, 1, 23, 59, 59, tzinfo=timezone.utc))
    assert any('actual window commit' in message for message in messages)
    assert not any('backdated tip' in message for message in messages)


def test_main_update_serializes_concurrent_git_checkout(repository: Path, upstream: Path) -> None:
    from unittest.mock import patch
    from commitpoem import local_git
    git(repository, 'branch', 'feature')
    feature_before = git(repository, 'rev-parse', 'feature')
    real_git = local_git._git
    attempts = []

    def attempt_switch(path, *args, **kwargs):
        if 'merge' in args:
            attempts.append(subprocess.run(['git', '-C', str(repository), 'checkout', 'feature'],
                                           capture_output=True, text=True))
        return real_git(path, *args, **kwargs)

    with patch('commitpoem.local_git._git', side_effect=attempt_switch):
        assert update_main(LocalRepository(repository, 'qo-kr/project'))
    assert attempts and attempts[0].returncode != 0
    assert git(repository, 'branch', '--show-current') == 'main'
    assert git(repository, 'rev-parse', 'feature') == feature_before
    assert git(repository, 'rev-parse', 'main') == git(upstream, 'rev-parse', 'HEAD')
    assert (repository / 'tracked.txt').read_text() == 'upstream content'
    assert git(repository, 'status', '--porcelain') == ''
    assert not (repository / '.git/index.lock').exists()


def test_existing_index_lock_skips_main_update(repository: Path, upstream: Path) -> None:
    lock = repository / '.git/index.lock'
    lock.write_text('another git command owns this')
    before = git(repository, 'rev-parse', 'HEAD')
    assert not update_main(LocalRepository(repository, 'qo-kr/project'))
    assert git(repository, 'rev-parse', 'HEAD') == before
    assert lock.read_text() == 'another git command owns this'
