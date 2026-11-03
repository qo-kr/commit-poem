from __future__ import annotations

import datetime
from datetime import date, timedelta, timezone

import pytest

from commitpoem.quotations import QUOTATIONS, select_quote


@pytest.fixture
def all_themes() -> list[str]:
    return [" ".join(keyword for quote in QUOTATIONS for keyword in quote.keywords)]


def test_daily_rotation_visits_the_full_catalog_before_repeating(all_themes: list[str]) -> None:
    selected = [select_quote(all_themes, date.min + timedelta(days=offset)) for offset in range(len(QUOTATIONS) * 2)]

    assert selected == list(QUOTATIONS) * 2


def test_catalog_contains_one_hundred_distinct_real_authors() -> None:
    assert len(QUOTATIONS) == 100
    assert len({quote.author.split(" · ")[0] for quote in QUOTATIONS}) == 100


def test_every_record_has_translation_attribution_and_thematic_keywords() -> None:
    for quote in QUOTATIONS:
        assert quote.text and quote.translation and quote.bio and quote.context
        assert quote.source.startswith("https://")
        assert quote.url.startswith("https://")
        assert quote.keywords and all(keyword.strip() for keyword in quote.keywords)
        assert any("가" <= char <= "힣" for char in quote.translation)


def test_anthology_sources_identify_the_consulted_edition_and_original_work() -> None:
    for quote in QUOTATIONS[6:]:
        assert "Bartlett" in quote.context and "1891" in quote.context
        assert "자체 번역" in quote.context
        assert quote.source.startswith("https://www.gutenberg.org/files/27889/27889-h/27889-h.htm#")


def test_changing_matching_themes_cannot_repeat_yesterdays_quote() -> None:
    yesterday = select_quote(["feat: team"], date.min)
    today = select_quote(["feat: team empathy"], date.min + timedelta(days=1))

    assert yesterday == QUOTATIONS[0]
    assert today == QUOTATIONS[1]
    assert today != yesterday


def test_irrelevant_daily_quote_is_omitted_without_falling_back() -> None:
    assert select_quote(["feat: empathy"], date.min) is None


@pytest.mark.parametrize("commits", [[], ["chore: bump zzzpackage"], ["fix: steam renderer"]])
def test_daily_quote_requires_a_complete_keyword(commits: list[str]) -> None:
    assert select_quote(commits, date.min) is None


@pytest.mark.parametrize("keyword", ["TEAM", "(collaboration)", "협업"])
def test_daily_quote_accepts_complete_casefolded_and_korean_keywords(keyword: str) -> None:
    assert select_quote([f"feat: {keyword}"], date.min) == QUOTATIONS[0]


def test_first_supported_date_selects_the_first_quote() -> None:
    assert select_quote(["feat: team"], date.min) == QUOTATIONS[0]


def test_default_day_uses_seoul_after_the_utc_date_boundary(
    monkeypatch: pytest.MonkeyPatch, all_themes: list[str],
) -> None:
    instant = datetime.datetime(2026, 11, 2, 15, 1, tzinfo=timezone.utc)

    class FrozenDatetime(datetime.datetime):
        @classmethod
        def now(cls, tz: datetime.tzinfo | None = None) -> datetime.datetime:
            return instant.astimezone(tz) if tz is not None else instant.replace(tzinfo=None)

    monkeypatch.setattr(datetime, "datetime", FrozenDatetime)

    assert select_quote(all_themes) == select_quote(all_themes, date(2026, 11, 3))
    assert select_quote(all_themes) != select_quote(all_themes, date(2026, 11, 2))


def test_explicit_day_is_independent_of_the_current_clock(
    monkeypatch: pytest.MonkeyPatch, all_themes: list[str],
) -> None:
    class NoClockDatetime(datetime.datetime):
        @classmethod
        def now(cls, tz: datetime.tzinfo | None = None) -> datetime.datetime:
            raise AssertionError("Explicit dates must not read the clock")

    monkeypatch.setattr(datetime, "datetime", NoClockDatetime)

    assert select_quote(all_themes, date.min) == QUOTATIONS[0]
