"""Choose relevant daily references and remember successfully delivered editions."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import TypeVar
from zoneinfo import ZoneInfo

from . import catalog, quotations
from .catalog import Profile
from .quotations import Quotation


@dataclass(frozen=True)
class DailySelection:
    """The references shared by every part of one daily edition."""

    day: date
    english_poet: Profile
    korean_poet: Profile
    painter: Profile
    quote: Quotation | None


class HistoryError(ValueError):
    """The existing delivery history cannot be safely read or restored."""


# Commit vocabulary opens onto human themes instead of prescribing technical imagery.
_THEMES = (
    (("retry", "retries", "recovery", "recover", "repair", "resilience", "재시도", "회복"),
     ("resilience", "hope", "endurance", "renewal", "희망", "회복")),
    (("docs", "documentation", "readme", "archive", "history", "문서", "기록"),
     ("memory", "history", "witness", "remembrance", "기억", "역사")),
    (("team", "collaboration", "collaborate", "community", "협업", "협력"),
     ("connection", "community", "friendship", "solidarity", "연결", "공동체")),
    (("security", "auth", "authentication", "permission", "privacy", "보안", "인증"),
     ("trust", "boundary", "boundaries", "protection", "신뢰", "경계")),
    (("test", "tests", "testing", "verify", "validation", "테스트", "검증"),
     ("truth", "doubt", "certainty", "inquiry", "진실", "의심")),
    (("refactor", "refactoring", "simplify", "리팩터링", "개선"),
     ("change", "simplicity", "transformation", "renewal", "변화", "단순")),
    (("remove", "delete", "deletion", "deprecate", "삭제", "제거"),
     ("absence", "loss", "farewell", "silence", "부재", "상실")),
    (("accessibility", "a11y", "empathy", "접근성", "배려"),
     ("empathy", "dignity", "care", "humanity", "공감", "존엄")),
    (("performance", "optimize", "latency", "speed", "성능", "최적화"),
     ("time", "rhythm", "motion", "시간", "리듬")),
    (("bug", "error", "failure", "fix", "버그", "오류"),
     ("repair", "imperfection", "healing", "치유", "불완전")),
    (("feature", "create", "launch", "build", "출시", "생성"),
     ("creation", "beginning", "possibility", "시작", "가능성")),
)
_RECORD_KEYS = {"day", "english_poet", "korean_poet", "painter", "quote_author"}
_Reference = TypeVar("_Reference", Profile, Quotation)
_STOPWORDS = frozenset("""
    about above across after again against all almost along already also although always among amount
    and another any anyhow anyone anything anyway anywhere are around back became because become becomes
    becoming been before beforehand behind being below beside besides between beyond both but can cannot
    could did does doing done down during each either else elsewhere enough even ever every everyone
    everything everywhere few first for former formerly from further get gets getting had has have having
    hence her here hereafter hereby herein hereupon hers herself him himself his how however indeed
    into its itself just last latter latterly least less made make many may might mine more moreover
    most mostly much must myself namely neither never nevertheless next nobody none nor nothing now
    nowhere often once one only onto other others otherwise our ours ourselves out over own per perhaps
    rather same several shall she should since some somehow someone something sometime sometimes
    somewhere still such than that the their theirs them themselves then thence there thereafter
    thereby therefore therein thereupon these they this those though through throughout thus together
    too toward towards under unless until upon very via was were what whatever when whence whenever
    where whereafter whereas whereby wherein whereupon wherever whether which while who whoever whom
    whose why will with within without would yet you your yours yourself yourselves
    feat fix chore commit commits committed merge merges merged add adds added adding update updates
    updated updating function functions file files code repo repository module modules class classes
    method methods component components variable variables object objects parameter parameters argument
    arguments import imports export exports config configs configuration option options value values
    result results default defaults return returns returned use used uses using handle handles handling
    support supports supported enable enabled disable disabled new old current existing
""".split())


def _state_path(path: Path | None) -> Path:
    if path is not None:
        return Path(path)
    root = os.environ.get("XDG_STATE_HOME")
    return (Path(root).expanduser() if root else Path.home() / ".local" / "state") / "commitpoem" / "history.json"


def _read_history(path: Path) -> list[dict[str, str | None]]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    except (OSError, UnicodeError) as exc:
        raise HistoryError(f"Cannot read delivery history at {path}: {exc}") from exc
    try:
        payload = json.loads(text)
        if not isinstance(payload, dict) or type(payload.get("version")) is not int or payload["version"] != 1:
            raise ValueError("expected history version 1")
        records = payload.get("records")
        if not isinstance(records, list):
            raise ValueError("records must be a list")
        allowed_names = {
            # Earlier editions could credit a Korean poet for both poems.
            "english_poet": {item.name for item in (*catalog.ENGLISH_POETS, *catalog.POETS)},
            "korean_poet": {item.name for item in catalog.KOREAN_POETS},
            "painter": {item.name for item in catalog.PAINTERS},
            "quote_author": {item.author for item in quotations.QUOTATIONS},
        }
        seen = set()
        for record in records:
            if not isinstance(record, dict) or set(record) != _RECORD_KEYS:
                raise ValueError("invalid daily record fields")
            for key in _RECORD_KEYS - {"quote_author"}:
                if not isinstance(record[key], str) or not record[key].strip():
                    raise ValueError(f"invalid {key}")
            if record["quote_author"] is not None and (
                not isinstance(record["quote_author"], str) or not record["quote_author"].strip()
            ):
                raise ValueError("invalid quote_author")
            if date.fromisoformat(record["day"]).isoformat() != record["day"] or record["day"] in seen:
                raise ValueError("invalid or duplicate day")
            for key, names in allowed_names.items():
                if record[key] is not None and record[key] not in names:
                    raise ValueError(f"unknown {key}: {record[key]!r}")
            seen.add(record["day"])
        return sorted(records, key=lambda record: record["day"])
    except (ValueError, TypeError) as exc:
        raise HistoryError(f"Invalid delivery history at {path}: {exc}") from exc


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[^\W_]+", text.casefold()))


def _interests(commits: list[str]) -> set[str]:
    words = _tokens("\n".join(commits))
    interests = {word for word in words if len(word) > 2 and word not in _STOPWORDS}
    for triggers, motifs in _THEMES:
        if words.intersection(triggers):
            interests.update(motifs)
    return interests


def _score(reference: Profile | Quotation, interests: set[str]) -> int:
    if isinstance(reference, Quotation):
        return sum(bool(_tokens(keyword)) and _tokens(keyword) <= interests for keyword in reference.keywords)
    return len(_tokens(f"{reference.style} {reference.bio} {reference.work}") & interests)


def _name(reference: Profile | Quotation) -> str:
    return reference.name if isinstance(reference, Profile) else reference.author


def _choose(
    pool: tuple[_Reference, ...], records: list[dict[str, str | None]], key: str,
    day: date, interests: set[str], *, relevant_only: bool = False,
) -> _Reference | None:
    if not pool:
        raise ValueError(f"The {key} catalog is empty")
    window = min(99, max(0, len({_name(item) for item in pool}) - 1))
    category_history = [record for record in records if record[key] is not None]
    recent = {record[key] for record in category_history[-window:]} if window else set()
    eligible = [item for item in pool if _name(item) not in recent]
    if relevant_only:
        eligible = [item for item in eligible if _score(item, interests) > 0]
    if not eligible:
        return None

    def rank(item: _Reference) -> tuple[int, str]:
        tie = hashlib.sha256(f"{day.isoformat()}:{key}:{_name(item)}".encode()).hexdigest()
        return _score(item, interests), tie

    return max(eligible, key=rank)


def _restore(pool: tuple[_Reference, ...], name: str | None, key: str) -> _Reference:
    for item in pool:
        if _name(item) == name:
            return item
    raise HistoryError(f"Cannot restore delivery history: {key} {name!r} is absent from the catalog")


def choose_daily(
    commits: list[str], *, day: date | None = None, state_path: Path | None = None,
) -> DailySelection:
    """Choose relevant references without modifying successful-delivery history.

    A previously delivered day's references remain fixed. New dates exclude the
    latest 99 delivered references per category, with a shorter window for
    smaller catalogs. Days without quotations do not expire recent authors.
    """
    day = day if day is not None else datetime.now(ZoneInfo("Asia/Seoul")).date()
    records = _read_history(_state_path(state_path))
    for record in records:
        if record["day"] == day.isoformat():
            return DailySelection(
                day,
                _restore(catalog.ENGLISH_POETS, record["english_poet"], "english_poet"),
                _restore(catalog.KOREAN_POETS, record["korean_poet"], "korean_poet"),
                _restore(catalog.PAINTERS, record["painter"], "painter"),
                _restore(quotations.QUOTATIONS, record["quote_author"], "quote_author")
                if record["quote_author"] is not None else None,
            )
    previous = [record for record in records if record["day"] < day.isoformat()]
    interests = _interests(commits)
    english = _choose(catalog.ENGLISH_POETS, previous, "english_poet", day, interests)
    korean = _choose(catalog.KOREAN_POETS, previous, "korean_poet", day, interests)
    painter = _choose(catalog.PAINTERS, previous, "painter", day, interests)
    if english is None or korean is None or painter is None:
        raise HistoryError("Delivery history leaves no unused artist in a required catalog")
    selected_quote = _choose(quotations.QUOTATIONS, previous, "quote_author", day, interests, relevant_only=True)
    return DailySelection(day, english, korean, painter, selected_quote)


def record_delivery(selection: DailySelection, *, state_path: Path | None = None) -> None:
    """Atomically record a selection after successful publication.

    The persistent lock serializes read-modify-write operations. Repeated
    deliveries for one day replace its record instead of appending duplicates.
    """
    path = _state_path(state_path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path.with_suffix(path.suffix + ".lock"), os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(descriptor, "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        records = _read_history(path)
        records = [record for record in records if record["day"] != selection.day.isoformat()]
        records.append({
            "day": selection.day.isoformat(),
            "english_poet": selection.english_poet.name,
            "korean_poet": selection.korean_poet.name,
            "painter": selection.painter.name,
            "quote_author": selection.quote.author if selection.quote is not None else None,
        })
        records.sort(key=lambda record: record["day"])
        descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump({"version": 1, "records": records}, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
