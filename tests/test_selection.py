from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from commitpoem import catalog, quotations
from commitpoem.catalog import Profile
from commitpoem.quotations import Quotation


def profile(name: str, style: str = "quiet observation") -> Profile:
    return Profile(name, "An artist", "Work", "https://example.org", "https://example.org/work", style)


def quote(author: str, keywords: tuple[str, ...] = ("team", "connection")) -> Quotation:
    return Quotation(author, "Together", "함께", "Context", "https://example.org", keywords, "Bio", "https://example.org")


@pytest.fixture
def pools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(catalog, "ENGLISH_POETS", tuple(profile(f"English {i}") for i in range(3)), raising=False)
    monkeypatch.setattr(catalog, "KOREAN_POETS", tuple(profile(f"한국 시인 {i}") for i in range(3)), raising=False)
    monkeypatch.setattr(catalog, "PAINTERS", tuple(profile(f"Painter {i}") for i in range(3)))
    monkeypatch.setattr(quotations, "QUOTATIONS", tuple(quote(f"Author {i}") for i in range(3)))


def test_choose_is_deterministic_and_never_creates_history(pools: None, tmp_path: Path) -> None:
    from commitpoem.selection import choose_daily

    path = tmp_path / "missing" / "history.json"
    selected = choose_daily(["team"], day=date(2026, 11, 3), state_path=path)
    assert selected == choose_daily(["team"], day=date(2026, 11, 3), state_path=path)
    assert selected.day == date(2026, 11, 3)
    assert not path.parent.exists()


def test_commit_theme_ranks_artists_and_relevant_quote(
    pools: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from commitpoem.selection import choose_daily

    hopeful = profile("Hopeful", "resilience and hope")
    historian = profile("Historian", "memory and history")
    monkeypatch.setattr(catalog, "ENGLISH_POETS", (historian, hopeful))
    monkeypatch.setattr(catalog, "KOREAN_POETS", (historian, hopeful))
    monkeypatch.setattr(catalog, "PAINTERS", (historian, hopeful))
    wisdom = quote("Hope", ("resilience",))
    monkeypatch.setattr(quotations, "QUOTATIONS", (quote("History", ("memory",)), wisdom))
    selected = choose_daily(["fix: retry recovery"], day=date(2026, 11, 3), state_path=tmp_path / "history.json")
    assert selected.english_poet == hopeful
    assert selected.korean_poet == hopeful
    assert selected.painter == hopeful
    assert selected.quote == wisdom


@pytest.mark.parametrize("commits", [[], ["chore: bump zzzpackage"], ["fix: steam renderer"]])
def test_no_arbitrary_or_partial_keyword_quote(pools: None, tmp_path: Path, commits: list[str]) -> None:
    from commitpoem.selection import choose_daily

    assert choose_daily(commits, state_path=tmp_path / "history.json").quote is None


def test_successful_day_freezes_all_choices_and_delivery_is_idempotent(pools: None, tmp_path: Path) -> None:
    from commitpoem.selection import choose_daily, record_delivery

    path = tmp_path / "history.json"
    selected = choose_daily(["team"], day=date(2026, 11, 3), state_path=path)
    record_delivery(selected, state_path=path)
    assert choose_daily(["docs"], day=selected.day, state_path=path) == selected
    record_delivery(selected, state_path=path)
    assert len(json.loads(path.read_text())["records"]) == 1


def test_successful_day_preserves_absent_quote(pools: None, tmp_path: Path) -> None:
    from commitpoem.selection import choose_daily, record_delivery

    path = tmp_path / "history.json"
    selected = choose_daily(["unrelated"], day=date(2026, 11, 3), state_path=path)
    record_delivery(selected, state_path=path)
    assert choose_daily(["team"], day=selected.day, state_path=path).quote is None


def test_small_pool_cycles_without_repeats(pools: None, tmp_path: Path) -> None:
    from commitpoem.selection import choose_daily, record_delivery

    path = tmp_path / "history.json"
    selections = []
    for offset in range(6):
        selected = choose_daily(["team"], day=date(2026, 11, 3) + timedelta(days=offset), state_path=path)
        selections.append(selected)
        record_delivery(selected, state_path=path)
    for field in ("english_poet", "korean_poet", "painter", "quote"):
        names = [getattr(item, field) for item in selections]
        assert len(set(names[:3])) == 3
        assert names[:3] == names[3:]


def test_one_hundred_successful_days_visit_each_category_before_repeating(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from commitpoem.selection import choose_daily, record_delivery

    for attribute in ("ENGLISH_POETS", "KOREAN_POETS", "PAINTERS"):
        monkeypatch.setattr(catalog, attribute, tuple(profile(f"{attribute} {i}") for i in range(100)), raising=False)
    monkeypatch.setattr(quotations, "QUOTATIONS", tuple(quote(f"Author {i}") for i in range(100)))
    path = tmp_path / "history.json"
    selections = []
    for offset in range(101):
        selected = choose_daily(["team"], day=date(2026, 1, 1) + timedelta(days=offset), state_path=path)
        selections.append(selected)
        record_delivery(selected, state_path=path)
    for field in ("english_poet", "korean_poet", "painter", "quote"):
        values = [getattr(item, field) for item in selections]
        assert len(set(values[:100])) == 100
        assert values[100] == values[0]


def test_quotation_author_waits_for_history_window_even_when_only_relevant_match(
    pools: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from commitpoem.selection import choose_daily, record_delivery

    monkeypatch.setattr(quotations, "QUOTATIONS", (quote("Team"), quote("Docs", ("docs",)), quote("Other", ("moon",))))
    path = tmp_path / "history.json"
    first = choose_daily(["team"], day=date(2026, 11, 3), state_path=path)
    record_delivery(first, state_path=path)
    assert choose_daily(["team"], day=date(2026, 11, 4), state_path=path).quote is None


@pytest.mark.parametrize("contents", ["{", "[]", '{"version": 2, "records": []}',
                                      '{"version": 1, "records": [{}]}'])
def test_corrupt_history_fails_without_overwriting(pools: None, tmp_path: Path, contents: str) -> None:
    from commitpoem.selection import HistoryError, choose_daily, record_delivery

    path = tmp_path / "history.json"
    selection = choose_daily(["team"], state_path=path)
    path.write_text(contents)
    with pytest.raises(HistoryError, match="history"):
        choose_daily(["team"], state_path=path)
    with pytest.raises(HistoryError, match="history"):
        record_delivery(selection, state_path=path)
    assert path.read_text() == contents


def test_persistence_is_utf8_private_and_uses_atomic_replace(
    pools: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from commitpoem import selection

    path = tmp_path / "history.json"
    selected = selection.choose_daily(["team"], state_path=path)
    real_replace = selection.os.replace
    replacements = []

    def inspect_replace(source: str, destination: Path) -> None:
        temporary = Path(source)
        assert temporary.parent == path.parent
        assert temporary.stat().st_mode & 0o777 == 0o600
        assert json.loads(temporary.read_text(encoding="utf-8"))["version"] == 1
        replacements.append(destination)
        real_replace(source, destination)

    monkeypatch.setattr(selection.os, "replace", inspect_replace)
    selection.record_delivery(selected, state_path=path)
    assert replacements == [path]
    assert "한국 시인" in path.read_text(encoding="utf-8")
    assert path.stat().st_mode & 0o777 == 0o600


def test_default_day_uses_seoul_and_default_state_uses_xdg(
    pools: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from commitpoem import selection

    instant = datetime(2026, 11, 2, 15, 1, tzinfo=timezone.utc)

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz: object = None) -> datetime:
            return instant.astimezone(tz)

    monkeypatch.setattr(selection, "datetime", FrozenDatetime)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    selected = selection.choose_daily(["team"])
    assert selected.day == date(2026, 11, 3)
    selection.record_delivery(selected)
    assert (tmp_path / "commitpoem" / "history.json").is_file()


def test_concurrent_deliveries_preserve_each_days_record(pools: None, tmp_path: Path) -> None:
    from concurrent.futures import ThreadPoolExecutor

    from commitpoem.selection import choose_daily, record_delivery

    path = tmp_path / "history.json"
    selections = [
        choose_daily(["team"], day=date(2026, 11, 3) + timedelta(days=offset), state_path=path)
        for offset in range(12)
    ]
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(lambda selected: record_delivery(selected, state_path=path), selections))
    records = json.loads(path.read_text())["records"]
    assert [record["day"] for record in records] == [selection.day.isoformat() for selection in selections]


def test_atomic_write_failure_preserves_previous_history(
    pools: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from commitpoem import selection

    path = tmp_path / "history.json"
    first = selection.choose_daily(["team"], day=date(2026, 11, 3), state_path=path)
    selection.record_delivery(first, state_path=path)
    original = path.read_bytes()
    next_day = selection.choose_daily(["team"], day=date(2026, 11, 4), state_path=path)

    def fail_replace(source: str, destination: Path) -> None:
        raise OSError("disk failure")

    monkeypatch.setattr(selection.os, "replace", fail_replace)
    with pytest.raises(OSError, match="disk failure"):
        selection.record_delivery(next_day, state_path=path)
    assert path.read_bytes() == original
    assert list(tmp_path.glob("*.tmp")) == []


@pytest.mark.parametrize("mutation", ["invalid_day", "duplicate_day", "invalid_author", "invalid_artist"])
def test_invalid_history_records_fail_clearly(pools: None, tmp_path: Path, mutation: str) -> None:
    from commitpoem.selection import HistoryError, choose_daily, record_delivery

    path = tmp_path / "history.json"
    selected = choose_daily(["team"], day=date(2026, 11, 3), state_path=path)
    record_delivery(selected, state_path=path)
    payload = json.loads(path.read_text())
    record = payload["records"][0]
    if mutation == "invalid_day":
        record["day"] = "2026-99-99"
    elif mutation == "duplicate_day":
        payload["records"].append(record.copy())
    elif mutation == "invalid_author":
        record["quote_author"] = 17
    else:
        record["english_poet"] = "Missing artist"
    path.write_text(json.dumps(payload))
    with pytest.raises(HistoryError, match="history"):
        choose_daily(["team"], day=selected.day, state_path=path)


def test_default_history_falls_back_to_home_state_directory(
    pools: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from commitpoem.selection import choose_daily, record_delivery

    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    selected = choose_daily(["team"])
    record_delivery(selected)
    assert (tmp_path / ".local" / "state" / "commitpoem" / "history.json").exists()


def test_days_without_quotes_do_not_expire_recent_authors(
    pools: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from commitpoem.selection import choose_daily, record_delivery

    monkeypatch.setattr(quotations, "QUOTATIONS", (quote("Team"), quote("Docs", ("docs",)), quote("Other", ("moon",))))
    path = tmp_path / "history.json"
    for offset in range(4):
        selected = choose_daily(
            ["team"] if offset == 0 else ["unrelated"],
            day=date(2026, 11, 3) + timedelta(days=offset),
            state_path=path,
        )
        record_delivery(selected, state_path=path)
    assert choose_daily(["team"], day=date(2026, 11, 7), state_path=path).quote is None


def test_common_prose_and_code_words_cannot_create_relevance(
    pools: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from commitpoem.selection import choose_daily

    prose = "with from that this into which their function file commit merge update add the"
    common = profile("Common", prose)
    quiet = profile("Quiet", "stillness")
    for attribute in ("ENGLISH_POETS", "KOREAN_POETS", "PAINTERS"):
        monkeypatch.setattr(catalog, attribute, (common, quiet))
    monkeypatch.setattr(quotations, "QUOTATIONS", (quote("Generic", ("with", "from", "the")),))
    path = tmp_path / "history.json"
    for offset in range(10):
        day = date(2026, 11, 3) + timedelta(days=offset)
        baseline = choose_daily([], day=day, state_path=path)
        selected = choose_daily([prose], day=day, state_path=path)
        assert selected.quote is None
        assert selected == baseline


def test_repair_still_expands_to_hope_after_filtering_code_words(
    pools: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from commitpoem.selection import choose_daily

    hopeful = profile("Hopeful", "hope and resilience")
    generic = profile("Generic", "with from that this function file commit update")
    for attribute in ("ENGLISH_POETS", "KOREAN_POETS", "PAINTERS"):
        monkeypatch.setattr(catalog, attribute, (generic, hopeful))
    wisdom = quote("Hope", ("hope",))
    monkeypatch.setattr(quotations, "QUOTATIONS", (wisdom,))
    selected = choose_daily(
        ["repair function file with that this commit update"], day=date(2026, 11, 3),
        state_path=tmp_path / "history.json",
    )
    assert selected.english_poet == hopeful
    assert selected.korean_poet == hopeful
    assert selected.painter == hopeful
    assert selected.quote == wisdom


@pytest.mark.parametrize("field", ["english_poet", "korean_poet", "painter", "quote_author"])
def test_unknown_names_in_older_history_fail_before_selection_or_delivery(
    pools: None, tmp_path: Path, field: str,
) -> None:
    from commitpoem.selection import HistoryError, choose_daily, record_delivery

    path = tmp_path / "history.json"
    first = choose_daily(["team"], day=date(2026, 11, 3), state_path=path)
    record_delivery(first, state_path=path)
    following = choose_daily(["team"], day=date(2026, 11, 4), state_path=path)
    payload = json.loads(path.read_text())
    payload["records"][0][field] = "Missing artist"
    path.write_text(json.dumps(payload))
    original = path.read_bytes()
    with pytest.raises(HistoryError, match="history"):
        choose_daily(["team"], day=following.day, state_path=path)
    with pytest.raises(HistoryError, match="history"):
        record_delivery(following, state_path=path)
    assert path.read_bytes() == original


def test_recognized_legacy_english_poet_is_valid_only_for_prior_history(
    pools: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from commitpoem.selection import HistoryError, choose_daily, record_delivery

    legacy = profile("Recognized legacy Korean poet")
    monkeypatch.setattr(catalog, "POETS", (legacy,))
    path = tmp_path / "history.json"
    first = choose_daily(["team"], day=date(2026, 11, 3), state_path=path)
    record_delivery(first, state_path=path)
    payload = json.loads(path.read_text())
    payload["records"][0]["english_poet"] = legacy.name
    path.write_text(json.dumps(payload))
    following = choose_daily(["team"], day=date(2026, 11, 4), state_path=path)
    assert following.english_poet in catalog.ENGLISH_POETS
    with pytest.raises(HistoryError, match="history"):
        choose_daily(["team"], day=first.day, state_path=path)
