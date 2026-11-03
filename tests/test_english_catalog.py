from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse


DATA = Path(__file__).resolve().parents[1] / "commitpoem" / "data"


def test_english_catalog_has_100_complete_unique_profiles() -> None:
    profiles = json.loads((DATA / "english_poets.json").read_text(encoding="utf-8"))

    assert len(profiles) == 100
    assert len({profile["name"].casefold() for profile in profiles}) == 100
    fields = {"name", "bio", "work", "url", "work_url", "style"}
    for profile in profiles:
        assert set(profile) == fields
        assert all(isinstance(value, str) and value.strip() for value in profile.values())
        for field in ("url", "work_url"):
            parsed = urlparse(profile[field])
            assert parsed.scheme == "https"
            assert parsed.hostname == "en.wikipedia.org"
            assert parsed.path.startswith("/wiki/")
            assert " " not in profile[field]


def test_english_catalog_retains_the_original_46_profiles() -> None:
    original = json.loads((DATA / "international_poets.json").read_text(encoding="utf-8"))
    profiles = json.loads((DATA / "english_poets.json").read_text(encoding="utf-8"))
    retained = original[:44] + [profile for profile in original if profile["name"] in {"Wole Soyinka", "Derek Walcott"}]

    assert len(retained) == 46
    assert profiles[:46] == retained
    assert len({profile["style"] for profile in profiles[46:]}) == 54
