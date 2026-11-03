from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch
from urllib.parse import urlparse

import pytest

from commitpoem.catalog import PAINTERS, POETS, Profile, select_daily


def test_catalog_preserves_all_existing_poets() -> None:
    from commitpoem.backends import _POETS

    assert len(POETS) == 200
    assert [profile.name for profile in POETS] == _POETS


@pytest.mark.parametrize("profiles,size", [(POETS, 200), (PAINTERS, 100)])
def test_catalog_has_complete_unique_profiles(profiles: tuple[Profile, ...], size: int) -> None:
    assert isinstance(profiles, tuple)
    assert len(profiles) == size
    assert len({profile.name for profile in profiles}) == size
    for profile in profiles:
        assert all(getattr(profile, field).strip() for field in Profile.__dataclass_fields__)
        for url in (profile.url, profile.work_url):
            parsed = urlparse(url)
            assert parsed.scheme == "https"
            if profile.name == "윤석산 (Yun Seok-san)":
                # This poet has no Wikipedia biography; use the official LTI entry.
                assert url == "https://library.ltikorea.or.kr/writer/201077"
            else:
                assert parsed.hostname in {"en.wikipedia.org", "ko.wikipedia.org"}
                assert parsed.path.startswith("/wiki/")
            assert " " not in url


def test_profiles_are_immutable() -> None:
    with pytest.raises(FrozenInstanceError):
        POETS[0].name = "changed"  # type: ignore[misc]


def test_daily_selection_is_stable_and_cycles_without_repetition() -> None:
    start = date(2026, 1, 1)
    selections = [select_daily(start + timedelta(days=offset)) for offset in range(400)]
    assert len({poet.name for poet, _ in selections[:200]}) == 200
    assert len({painter.name for _, painter in selections[:100]}) == 100
    assert selections[:200] == selections[200:]
    assert select_daily(start) == select_daily(start)


def test_rotation_mixes_korean_and_international_poets() -> None:
    start = date(2026, 1, 1)
    for offset in range(0, 200, 20):
        names = [select_daily(start + timedelta(days=offset + step))[0].name for step in range(20)]
        assert any("(" in name for name in names)
        assert any("(" not in name for name in names)


def test_default_day_uses_seoul_even_before_utc_midnight() -> None:
    instant = datetime(2026, 11, 2, 16, 0, tzinfo=timezone.utc)
    with patch("commitpoem.catalog.datetime") as clock:
        clock.now.side_effect = lambda zone: instant.astimezone(zone)
        assert select_daily() == select_daily(date(2026, 11, 3))
        assert clock.now.call_args.args[0].key == "Asia/Seoul"


def test_historical_dates_are_supported() -> None:
    poet, painter = select_daily(date(1, 1, 1))
    assert poet in POETS
    assert painter in PAINTERS


def test_each_language_selects_its_own_poet_without_repeats() -> None:
    from commitpoem.catalog import ENGLISH_POETS, KOREAN_POETS, select_daily_poets

    assert len(KOREAN_POETS) == 100
    assert len(ENGLISH_POETS) == 100
    assert not set(ENGLISH_POETS) & set(KOREAN_POETS)
    start = date(2026, 11, 3)
    selections = [select_daily_poets(start + timedelta(days=i)) for i in range(200)]
    assert all(english in ENGLISH_POETS and korean in KOREAN_POETS for english, korean in selections)
    assert len({english for english, _ in selections[:100]}) == 100
    assert len({korean for _, korean in selections[:100]}) == 100
    assert selections[0][0] == selections[100][0]
    assert selections[0][1] == selections[100][1]


def test_language_poets_use_seoul_date() -> None:
    from commitpoem.catalog import select_daily_poets

    instant = datetime(2026, 11, 2, 16, 0, tzinfo=timezone.utc)
    with patch("commitpoem.catalog.datetime") as clock:
        clock.now.side_effect = lambda zone: instant.astimezone(zone)
        assert select_daily_poets() == select_daily_poets(date(2026, 11, 3))
