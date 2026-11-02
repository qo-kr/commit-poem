from __future__ import annotations

import json
import re
from dataclasses import dataclass, fields

from commitpoem.catalog import Profile
from commitpoem.quotations import Quotation

EDITION_SCHEMA: dict = {
    "type": "object",
    "properties": {
        key: {"type": "array", "items": {"type": "string"}} if key.startswith("poem_") else {"type": "string"}
        for key in ("title_en", "title_ko", "poem_en", "poem_ko", "behind_en", "behind_ko")
    },
    "required": ["title_en", "title_ko", "poem_en", "poem_ko", "behind_en", "behind_ko"],
    "additionalProperties": False,
}

_GENERIC_WORDS = frozenset({
    "add", "added", "fix", "fixed", "update", "updated", "remove", "removed", "repair", "merge",
    "branch", "bump", "the", "and", "for", "with", "from", "into", "to", "of", "a", "in", "on",
    "feat", "chore", "docs", "test", "refactor", "build", "main", "master",
})


def select_anchor(commits: list[str]) -> str:
    """Pick a bounded literal keyword from source subjects without trusting model output."""
    fallback = ""
    for commit in commits:
        if not commit.strip():
            continue
        subject = commit.strip().splitlines()[0]
        subject = re.sub(r"^\[[^\]]+\]\s*", "", subject)
        subject = re.sub(
            r"^(?:feat|fix|refactor|perf|docs|test|build|ci|chore|style|revert)(?:\([^)]*\))?!?:\s*",
            "", subject, flags=re.IGNORECASE,
        )
        tokens = re.findall(r"\w[\w./-]*", subject)
        if not fallback:
            fallback = tokens[0][:80] if tokens else next((char for char in subject if char.isprintable()
                                                         and not char.isspace()), "")
        for token in tokens:
            if token.casefold() not in _GENERIC_WORDS:
                return token[:80]
    return fallback


@dataclass(frozen=True)
class Edition:
    """One poem and its translation, with one canonical bilingual title."""

    anchor: str
    title_en: str
    title_ko: str
    poem_en: str
    poem_ko: str
    behind_en: str
    behind_ko: str


def parse_edition(raw: str, commits: list[str]) -> Edition:
    """Validate model output before any part of it can reach a delivery endpoint."""
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("backend returned an empty poem")
    text = raw.strip()
    if text.startswith("```") and text.endswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise ValueError("backend returned invalid edition JSON") from exc
    if not isinstance(data, dict):
        raise ValueError("edition must be a JSON object")
    # The application owns factual provenance. Ignore a legacy model-supplied
    # anchor and derive it from the same sources used to build the prompt.
    data["anchor"] = select_anchor(commits)
    names = {field.name for field in fields(Edition)}
    if set(data) != names:
        raise ValueError("edition JSON has missing or unexpected fields")
    for key in ("poem_en", "poem_ko"):
        if isinstance(data[key], list) and all(isinstance(line, str) for line in data[key]):
            data[key] = "\n".join(data[key])
    for key in names:
        if not isinstance(data[key], str) or (key != "anchor" and not data[key].strip()):
            raise ValueError(f"edition field {key} must be a non-empty string")
        data[key] = data[key].strip()
    for key in ("title_en", "title_ko"):
        if "\n" in data[key] or len(data[key]) > 160:
            raise ValueError(f"edition field {key} must be one short title line")
    for key in ("poem_en", "poem_ko"):
        if not 4 <= sum(bool(line.strip()) for line in data[key].splitlines()) <= 8:
            raise ValueError(f"edition field {key} must contain 4–8 lines")
    if any(len(data[key]) > 1000 for key in names - {"anchor"}):
        raise ValueError("edition fields must remain short enough for daily delivery")
    anchor = data["anchor"]
    if anchor:
        # Models sometimes translate away the literal keyword. Preserve it ourselves.
        for key in ("title_en", "title_ko"):
            if anchor not in data[key]:
                data[key] = f"{anchor} · {data[key]}"
    return Edition(**data)


def _escape(text: str) -> str:
    # Prevent generated text from becoming Slack mentions or injected links.
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_edition(edition: Edition, poet: Profile, painter: Profile, quote: Quotation | None = None) -> str:
    """Render both language editions from the exact same title and curated references."""
    title = _escape(f"{edition.title_en} / {edition.title_ko}")
    sections = [
        f"🇺🇸 *{title}*\n{_escape(edition.poem_en)}",
        f"🇰🇷 *{title}*\n{_escape(edition.poem_ko)}",
        "*Behind the poem · 영감과 해석*\n"
        f"{_escape(edition.behind_ko)}\n{_escape(edition.behind_en)}",
    ]
    for label, person in (("오늘의 시인", poet), ("오늘의 화가", painter)):
        sections.append(
            f"*{label} · {_escape(person.name)}*\n{_escape(person.bio)}\n"
            f"대표작: <{person.work_url}|{_escape(person.work)}> · <{person.url}|인물 소개 / Reference>"
        )
    if quote is not None:
        sections.append(
            f"*오늘의 한마디 · {_escape(quote.author)}*\n“{_escape(quote.text)}”\n"
            f"{_escape(quote.translation)}\n<{quote.source}|출처> · {_escape(quote.context)}"
        )
    sections.append("AI 창작 시·번역·해설 및 화풍에서 영감을 얻은 그림입니다. 인물의 실제 작품·발언이 아닙니다."
                    " 인용문은 별도 출처를 표시합니다.")
    return "\n\n".join(sections)
