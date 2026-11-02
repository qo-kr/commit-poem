from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date


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


QUOTATIONS: tuple[Quotation, ...] = (
    Quotation(
        "Helen Keller · 작가·활동가",
        "Alone we can do so little; together we can do so much.",
        "혼자서는 할 수 있는 일이 적지만, 함께라면 많은 일을 할 수 있다.",
        "Helen Keller·Anne Sullivan의 vaudeville 공연 대본 · 한국어는 자체 번역",
        "https://afb.org/about-afb/history/helen-keller/helen-keller-quotes/helen-keller-quotes-progress",
        ("team", "collaboration", "collaborate", "협업", "협력"),
        "시청각장애인의 교육과 권리를 위해 활동한 미국의 작가이자 활동가입니다.",
        "https://en.wikipedia.org/wiki/Helen_Keller",
    ),
    Quotation(
        "Charlie Chaplin · 배우·코미디언",
        "We think too much and feel too little.",
        "우리는 너무 많이 생각하고 너무 적게 느낀다.",
        "영화 The Great Dictator(1940)의 이발사 연설 대사 · 한국어는 자체 번역",
        "https://www.charliechaplin.com/en/quotes/158",
        ("accessibility", "a11y", "empathy", "human", "접근성", "배려"),
        "몸짓과 유머로 인간의 존엄을 그린 배우·감독으로, 떠돌이 캐릭터로 널리 알려져 있습니다.",
        "https://en.wikipedia.org/wiki/Charlie_Chaplin",
    ),
    Quotation(
        "Abraham Lincoln · 정치인",
        "the better angels of our nature",
        "우리 본성의 더 선한 천사들",
        "1861년 첫 취임사 중 화해를 호소하는 구절 · 한국어는 자체 번역",
        "https://www.loc.gov/collections/abraham-lincoln-papers/articles-and-essays/"
        "frequently-requested-documents/",
        ("reconcile", "reconciliation", "conflict", "화해", "충돌"),
        "미국 제16대 대통령으로, 남북전쟁 시기 연방의 유지와 노예 해방을 이끌었습니다.",
        "https://en.wikipedia.org/wiki/Abraham_Lincoln",
    ),
    Quotation(
        "Epictetus · 철학가",
        "Men are disturbed, not by things, but by the principles and notions which they form concerning things.",
        "사람을 흔드는 것은 사물 자체가 아니라, 사물에 대해 스스로 품는 판단과 생각이다.",
        "Enchiridion 5 · Elizabeth Carter 영문 번역, 한국어는 자체 번역",
        "https://classics.mit.edu/Epictetus/epicench.html",
        ("resilience", "retry", "recovery", "recover", "회복", "재시도"),
        "로마 제국 시대의 스토아 철학자로, 외부 사건과 그에 대한 자신의 판단을 구분하도록 가르쳤습니다.",
        "https://en.wikipedia.org/wiki/Epictetus",
    ),
    Quotation(
        "Thucydides · 역사가",
        "a possession for all time",
        "모든 시대를 위한 자산",
        "History of the Peloponnesian War 1.22 · Richard Crawley 영문 번역의 발췌, 한국어는 자체 번역",
        "https://classics.mit.edu/Thucydides/pelopwar.1.first.html",
        ("docs", "documentation", "archive", "history", "문서", "기록"),
        "펠로폰네소스 전쟁을 기록한 고대 그리스 역사가로, 사건의 원인과 근거를 탐구했습니다.",
        "https://en.wikipedia.org/wiki/Thucydides",
    ),
    Quotation(
        "John F. Kennedy · 정치인",
        "We choose to go to the moon",
        "우리는 달에 가기로 선택했다",
        "1962년 Rice University 연설의 발췌 · 한국어는 자체 번역",
        "https://www.presidency.ucsb.edu/documents/"
        "address-rice-university-houston-the-nations-space-effort",
        ("moon", "space", "ambition", "challenge", "도전", "우주"),
        "미국 제35대 대통령으로, 달 탐사를 국가적 목표로 제시한 연설로도 알려져 있습니다.",
        "https://en.wikipedia.org/wiki/John_F._Kennedy",
    ),
)


def select_quote(commits: list[str], day: date | None = None) -> Quotation | None:
    """Select a sourced quotation only when a complete thematic keyword matches."""
    text = "\n".join(commits).casefold()
    matches = [
        quote for quote in QUOTATIONS
        if any(re.search(r"(?<!\w)" + re.escape(word) + r"(?!\w)", text) for word in quote.keywords)
    ]
    if not matches:
        return None
    if day is None:
        from datetime import datetime
        from zoneinfo import ZoneInfo

        day = datetime.now(ZoneInfo("Asia/Seoul")).date()
    return matches[day.toordinal() % len(matches)]
