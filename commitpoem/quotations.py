from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from importlib.resources import files


@dataclass(frozen=True)
class Quotation:
    """A curated excerpt, with a Korean translation and attributable source."""

    author: str
    text: str
    translation: str
    context: str
    source: str
    keywords: tuple[str, ...]
    bio: str
    url: str


def _load_quotations() -> tuple[Quotation, ...]:
    source = files("commitpoem").joinpath("data", "quotations.json").read_text(encoding="utf-8")
    records = json.loads(source)
    return tuple(Quotation(**{**record, "keywords": tuple(record["keywords"])}) for record in records)


QUOTATIONS: tuple[Quotation, ...] = _load_quotations()


def select_quote(commits: list[str], day: date | None = None) -> Quotation | None:
    """Rotate the full catalog daily, omitting the quote if no complete keyword matches."""
    if day is None:
        from datetime import datetime
        from zoneinfo import ZoneInfo

        day = datetime.now(ZoneInfo("Asia/Seoul")).date()
    quote = QUOTATIONS[(day.toordinal() - 1) % len(QUOTATIONS)]
    text = "\n".join(commits).casefold()
    if any(re.search(r"(?<!\w)" + re.escape(word) + r"(?!\w)", text) for word in quote.keywords):
        return quote
    return None
