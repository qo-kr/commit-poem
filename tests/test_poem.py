from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from commitpoem.backends import LLMBackend
from commitpoem.catalog import select_daily
from commitpoem.poem import generate_poem


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
    return backend


def test_generation_uses_same_curated_profiles_and_validates_output(backend: MagicMock) -> None:
    poet, painter = select_daily()
    result = generate_poem(['fix: cache'], backend, 'test-model', poet=poet, painter=painter)
    backend.generate_poem.assert_called_once_with(['fix: cache'], 'test-model', poet=poet)
    assert result.count('The cache at dawn / 새벽의 cache') == 2
    assert poet.work in result and painter.work in result
    assert '열린 문' in result


def test_default_generation_selects_profiles(backend: MagicMock) -> None:
    assert '오늘의 시인' in generate_poem(['fix: cache'], backend, 'test-model')


@pytest.mark.parametrize('raw', ['', '   ', 'not a JSON edition', None])
def test_invalid_model_output_rejected(backend: MagicMock, raw: str | None) -> None:
    backend.generate_poem.return_value = raw
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
    valid = backend.generate_poem.return_value
    backend.generate_poem.side_effect = ['not JSON', valid]
    result = generate_poem(['fix: cache'], backend, 'test-model')
    assert '🇺🇸' in result
    assert backend.generate_poem.call_count == 2
    assert 'invalid edition JSON' in backend.generate_poem.call_args.kwargs['feedback']


def test_repair_attempt_is_bounded(backend: MagicMock) -> None:
    backend.generate_poem.return_value = 'still invalid'
    with pytest.raises(ValueError):
        generate_poem(['fix: cache'], backend, 'test-model')
    assert backend.generate_poem.call_count == 2
