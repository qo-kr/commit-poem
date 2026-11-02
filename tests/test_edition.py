from __future__ import annotations

import json

import pytest

from commitpoem.edition import parse_edition, render_edition
from commitpoem.quotations import select_quote


@pytest.fixture
def content() -> dict[str, str]:
    return {
        "anchor": "cache", "title_en": "The cache at dawn", "title_ko": "새벽의 cache",
        "poem_en": "A door opens\nThe light returns\nWe wait together\nAnd morning stays",
        "poem_ko": "문이 열리고\n빛이 돌아와\n우리는 함께 기다린다\n아침이 머문다",
        "behind_en": "The cache fix suggests a door opening; this is a creative interpretation.",
        "behind_ko": "cache 수정에서 열린 문을 떠올렸다. 실제 의도를 단정하지 않은 창작 해석이다.",
    }


def test_shared_title_repeated_verbatim_for_both_languages(content: dict[str, str]) -> None:
    from commitpoem.catalog import select_daily

    edition = parse_edition(json.dumps(content), ["fix: cache"])
    poet, painter = select_daily()
    result = render_edition(edition, poet, painter)
    title = "The cache at dawn / 새벽의 cache"
    assert result.count(title) == 2
    assert content["behind_ko"] in result and content["behind_en"] in result
    for person in (poet, painter):
        assert person.name in result and person.work in result
        assert person.url in result and person.work_url in result
    assert "AI" in result


@pytest.mark.parametrize("raw", ["not JSON", "[]", "null", '{"title_en":"alone"}'])
def test_invalid_content_is_rejected(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_edition(raw, ["fix: cache"])


@pytest.mark.parametrize("key", ["title_en", "title_ko", "poem_en", "poem_ko", "behind_en", "behind_ko"])
def test_required_fields_cannot_be_blank(content: dict[str, str], key: str) -> None:
    content[key] = " "
    with pytest.raises(ValueError):
        parse_edition(json.dumps(content), ["fix: cache"])


def test_anchor_must_come_from_commits(content: dict[str, str]) -> None:
    edition = parse_edition(json.dumps(content), ["docs: readme"])
    assert edition.anchor == "readme"
    assert "readme" in edition.title_en and "readme" in edition.title_ko


def test_model_does_not_need_to_supply_a_factual_anchor(content: dict[str, str]) -> None:
    del content["anchor"]
    assert parse_edition(json.dumps(content), ["fix: cache"]).anchor == "cache"


@pytest.mark.parametrize("model_anchor", ["invented image", "", "x" * 81])
def test_invented_model_anchor_cannot_stop_delivery(content: dict[str, str], model_anchor: str) -> None:
    content["anchor"] = model_anchor
    assert parse_edition(json.dumps(content), ["fix: cache"]).anchor == "cache"


@pytest.mark.parametrize("commits,expected", [
    (["[qo-kr/repo] fix(cache): repair cache.py"], "cache.py"),
    (["feat: 한글검색 지원"], "한글검색"),
    (["fix: " + "x" * 120], "x" * 80),
    (["🚀"], "🚀"),
    (["", "  "], ""),
    ([], ""),
])
def test_anchor_selection_is_literal_bounded_and_repeatable(commits: list[str], expected: str) -> None:
    from commitpoem.edition import select_anchor

    assert select_anchor(commits) == expected
    assert select_anchor(commits) == select_anchor(commits)
    assert len(expected) <= 80
    assert not expected or any(expected in commit for commit in commits)


def test_both_titles_keep_literal_anchor(content: dict[str, str]) -> None:
    content["title_ko"] = "새벽"
    edition = parse_edition(json.dumps(content), ["fix: cache"])
    assert edition.title_ko == "cache · 새벽"


def test_model_line_arrays_are_rendered_as_lines(content: dict[str, str]) -> None:
    data = dict(content)
    data["poem_en"] = content["poem_en"].splitlines()
    data["poem_ko"] = content["poem_ko"].splitlines()
    assert parse_edition(json.dumps(data), ["fix: cache"]).poem_en == content["poem_en"]


def test_stanza_breaks_do_not_reject_valid_model_poems(content: dict[str, str]) -> None:
    data = dict(content)
    lines = content["poem_ko"].splitlines()
    data["poem_ko"] = [*lines[:2], "", *lines[2:]]
    assert parse_edition(json.dumps(data), ["fix: cache"]).poem_ko == "\n".join(data["poem_ko"])


def test_empty_day_does_not_invent_anchor(content: dict[str, str]) -> None:
    content["anchor"] = ""
    assert parse_edition(json.dumps(content), []).anchor == ""


def test_code_fenced_json_is_accepted(content: dict[str, str]) -> None:
    assert parse_edition("```json\n" + json.dumps(content) + "\n```", ["fix: cache"]).anchor == "cache"


def test_no_matching_quote_is_omitted() -> None:
    assert select_quote(["chore: bump zzzpackage"]) is None
    assert select_quote([]) is None


def test_matching_quote_has_source_and_translation() -> None:
    quote = select_quote(["feat: collaboration workflow for team members"])
    assert quote is not None
    assert quote.source.startswith("https://") and quote.text and quote.translation and quote.author


def test_keywords_do_not_match_inside_unrelated_words() -> None:
    assert select_quote(["fix: steam renderer"]) is None  # team is not steam


def test_quote_source_context_matches_the_curated_record() -> None:
    from commitpoem.quotations import QUOTATIONS
    keller = next(quote for quote in QUOTATIONS if quote.author.startswith('Helen Keller'))
    assert 'vaudeville' in keller.context
    assert '1927' not in keller.context
