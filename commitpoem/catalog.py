"""Curated references and a shared, repeat-free daily artist rotation.

The packaged catalog stays in a fixed order so a given Seoul calendar date
selects the same profiles across machines, providers, and repeated runs.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import date, datetime
from importlib.resources import files
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Profile:
    """An artist introduction with a representative work and reference links."""

    name: str
    bio: str
    work: str
    url: str
    work_url: str
    style: str


def _load_profiles(filename: str) -> tuple[Profile, ...]:
    source = files("commitpoem").joinpath("data", filename).read_text(encoding="utf-8")
    return tuple(Profile(**entry) for entry in json.loads(source))


POETS: tuple[Profile, ...] = _load_profiles("korean_poets.json") + _load_profiles("international_poets.json")
PAINTERS: tuple[Profile, ...] = _load_profiles("painters.json")


def _rotation(profiles: tuple[Profile, ...], seed: str) -> tuple[Profile, ...]:
    ordered = list(profiles)
    random.Random(seed).shuffle(ordered)
    return tuple(ordered)


# Separate fixed seeds mix eras and regions without touching global random state.
_POET_ROTATION = _rotation(POETS, "commitpoem-poets-v1")
_PAINTER_ROTATION = _rotation(PAINTERS, "commitpoem-painters-v1")


def select_daily(day: date | None = None) -> tuple[Profile, Profile]:
    """Return the poet and painter for *day*, defaulting to today's Seoul date.

    Consecutive dates advance through fixed shuffled catalogs, visiting every
    artist before repeating. The date ordinal supplies a stable, timezone-free
    index when an explicit date is supplied.
    """
    if day is None:
        day = datetime.now(ZoneInfo("Asia/Seoul")).date()
    index = day.toordinal() - 1
    return _POET_ROTATION[index % len(POETS)], _PAINTER_ROTATION[index % len(PAINTERS)]
