from __future__ import annotations

import json

from commitpoem.backends import LLMBackend
from commitpoem.catalog import Profile
from commitpoem.edition import Edition, Publication, parse_edition, parse_fragment, render_edition
from commitpoem.selection import DailySelection, choose_daily


def generate_publication(
    commits: list[str], backend: LLMBackend, model: str,
    *, poet: Profile | None = None, korean_poet: Profile | None = None, painter: Profile | None = None,
    selection: DailySelection | None = None,
) -> Publication:
    """Generate and validate the main edition and its explanatory thread.

    Optional profiles let a caller freeze the day's selection across text generation
    and image delivery, even when processing crosses midnight. Invalid model output
    raises ValueError before any delivery occurs.
    """
    selected = selection or choose_daily(commits)
    poet = poet or selected.english_poet
    korean_poet = korean_poet or selected.korean_poet
    painter = painter or selected.painter
    def generate_pair(feedback: str | None = None) -> Edition:
        english = parse_fragment(backend.generate_poem(
            commits, model, poet=poet, korean_poet=korean_poet, language="en", feedback=feedback,
        ), "en")
        korean = parse_fragment(backend.generate_poem(
            commits, model, poet=poet, korean_poet=korean_poet, language="ko",
            shared_title=(english["title_en"], english["title_ko"]), feedback=feedback,
        ), "ko")
        return parse_edition(json.dumps({**english, **korean}, ensure_ascii=False), commits)

    try:
        edition = generate_pair()
    except ValueError as exc:
        # One bounded repair attempt; malformed content is never delivered.
        edition = generate_pair(str(exc))
    return render_edition(edition, poet, painter, selected.quote, korean_poet=korean_poet)


def generate_poem(
    commits: list[str], backend: LLMBackend, model: str,
    *, poet: Profile | None = None, korean_poet: Profile | None = None, painter: Profile | None = None,
) -> str:
    """Return the channel text; use generate_publication for its thread and artwork."""
    return generate_publication(commits, backend, model, poet=poet, korean_poet=korean_poet, painter=painter).text
