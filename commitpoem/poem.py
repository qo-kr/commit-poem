from __future__ import annotations

from commitpoem.backends import LLMBackend
from commitpoem.catalog import Profile, select_daily
from commitpoem.edition import Publication, parse_edition, render_edition
from commitpoem.quotations import select_quote


def generate_publication(
    commits: list[str], backend: LLMBackend, model: str,
    *, poet: Profile | None = None, painter: Profile | None = None,
) -> Publication:
    """Generate and validate the main edition and its explanatory thread.

    Optional profiles let a caller freeze the day's selection across text generation
    and image delivery, even when processing crosses midnight. Invalid model output
    raises ValueError before any delivery occurs.
    """
    if poet is None or painter is None:
        daily_poet, daily_painter = select_daily()
        poet = poet or daily_poet
        painter = painter or daily_painter
    result = backend.generate_poem(commits, model, poet=poet)
    try:
        edition = parse_edition(result, commits)
    except ValueError as exc:
        # One bounded repair attempt; malformed content is never delivered.
        result = backend.generate_poem(commits, model, poet=poet, feedback=str(exc))
        edition = parse_edition(result, commits)
    return render_edition(edition, poet, painter, select_quote(commits))


def generate_poem(
    commits: list[str], backend: LLMBackend, model: str,
    *, poet: Profile | None = None, painter: Profile | None = None,
) -> str:
    """Return the channel text; use generate_publication for its thread and artwork."""
    return generate_publication(commits, backend, model, poet=poet, painter=painter).text
