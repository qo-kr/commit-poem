from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from commitpoem.backends import LLMBackend
from commitpoem.catalog import select_daily, select_daily_poets
from commitpoem.poem import generate_poem, generate_publication


@pytest.fixture
def backend() -> MagicMock:
    backend = MagicMock(spec=LLMBackend)
    backend.generate_poem.return_value = json.dumps({
        'anchor': 'cache', 'title_en': 'The cache at dawn', 'title_ko': '새벽의 cache',
        'poem_en': 'A door opens\nThe light returns\nWe wait together\nAnd morning stays',
        'poem_ko': '문이 열리고\n빛이 돌아와\n우리는 함께 기다린다\n아침이 머문다',
        'behind_en': 'The cache fix inspires the image of a door opening.',
        'behind_ko': 'cache 수정에서 열린 문을 떠올린 창작 해석이다.',
    })
    complete = json.loads(backend.generate_poem.return_value)

    def generate(*args, **kwargs):
        keys = ('title_en', 'title_ko', 'poem_en', 'behind_en') if kwargs.get('language') == 'en' else (
            'poem_ko', 'behind_ko')
        return json.dumps({key: complete[key] for key in keys})

    backend.generate_poem.side_effect = generate
    return backend


def test_generation_uses_same_curated_profiles_and_validates_output(backend: MagicMock) -> None:
    poet, korean_poet = select_daily_poets()
    _, painter = select_daily()
    result = generate_publication(['fix: cache'], backend, 'test-model', poet=poet,
                                  korean_poet=korean_poet, painter=painter)
    assert backend.generate_poem.call_count == 2
    calls = backend.generate_poem.call_args_list
    assert calls[0].kwargs == {'poet': poet, 'korean_poet': korean_poet, 'language': 'en', 'feedback': None}
    assert calls[1].kwargs['language'] == 'ko'
    assert calls[1].kwargs['shared_title'] == ('The cache at dawn', '새벽의 cache')
    assert 'A door opens' not in str(calls[1])  # English verses never enter the Korean request.
    assert result.text.count('The cache at dawn / 새벽의 cache') == 2
    assert poet.work in result.comment and korean_poet.work in result.comment and painter.work in result.comment
    assert '열린 문' in result.comment and '열린 문' not in result.text


def test_default_generation_selects_profiles(backend: MagicMock) -> None:
    assert '오늘의 시인' in generate_publication(['fix: cache'], backend, 'test-model').comment


@pytest.mark.parametrize('raw', ['', '   ', 'not a JSON edition', None])
def test_invalid_model_output_rejected(backend: MagicMock, raw: str | None) -> None:
    backend.generate_poem.return_value = raw
    backend.generate_poem.side_effect = None
    with pytest.raises(ValueError):
        generate_poem(['fix: cache'], backend, 'test-model')


def test_empty_day_can_still_produce_an_edition(backend: MagicMock) -> None:
    data = json.loads(backend.generate_poem.return_value)
    data['anchor'] = ''
    backend.generate_poem.return_value = json.dumps(data)
    assert generate_poem([], backend, 'test-model')


def test_backend_failure_propagates(backend: MagicMock) -> None:
    backend.generate_poem.side_effect = RuntimeError('API down')
    with pytest.raises(RuntimeError, match='API down'):
        generate_poem(['fix: cache'], backend, 'test-model')


def test_invalid_first_response_gets_one_repair_attempt(backend: MagicMock) -> None:
    data = json.loads(backend.generate_poem.return_value)
    english = json.dumps({key: data[key] for key in ('title_en', 'title_ko', 'poem_en', 'behind_en')})
    korean = json.dumps({key: data[key] for key in ('poem_ko', 'behind_ko')})
    backend.generate_poem.side_effect = ['not JSON', english, korean]
    result = generate_poem(['fix: cache'], backend, 'test-model')
    assert '🇺🇸' in result
    assert backend.generate_poem.call_count == 3
    assert 'invalid edition JSON' in backend.generate_poem.call_args.kwargs['feedback']


def test_invalid_korean_response_repairs_pair_without_sharing_english_verses(backend: MagicMock) -> None:
    data = json.loads(backend.generate_poem.return_value)
    english = json.dumps({key: data[key] for key in ('title_en', 'title_ko', 'poem_en', 'behind_en')})
    korean = json.dumps({key: data[key] for key in ('poem_ko', 'behind_ko')})
    backend.generate_poem.side_effect = [english, 'not JSON', english, korean]
    assert generate_poem(['fix: cache'], backend, 'test-model')
    assert backend.generate_poem.call_count == 4
    assert all('A door opens' not in str(call) for call in backend.generate_poem.call_args_list)


def test_repair_attempt_is_bounded(backend: MagicMock) -> None:
    backend.generate_poem.return_value = 'still invalid'
    backend.generate_poem.side_effect = None
    with pytest.raises(ValueError):
        generate_poem(['fix: cache'], backend, 'test-model')
    assert backend.generate_poem.call_count == 2
