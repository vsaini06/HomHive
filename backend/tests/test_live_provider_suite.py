"""Network-free contract tests for explicitly billable live_provider_suite.py."""
import base64
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts import live_provider_suite as suite


@pytest.fixture
def image(tmp_path):

    path = tmp_path / 'photo.png'
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + b'test payload')
    return path


def test_json_fences_are_supported():
    assert suite._parse_json('```json\n{"visible_objects": ["sink"]}\n```')['visible_objects'] == ['sink']


def test_response_must_have_observable_items():
    with pytest.raises(ValueError, match='missing_visible_objects'):
        suite._validate_vision({'room_category': 'kitchen', 'visible_objects': []})


def test_nebius_image_payload():
    response = {'choices': [{'message': {'content': '{"room_category":"kitchen","visible_objects":["sink"]}'}}]}
    with patch.dict('os.environ', {'NEBIUS_API_KEY': 'fake', 'HOMHIVE_NEBIUS_VISION_MODEL': 'test-model'}), patch.object(suite, '_request', return_value=response) as call:
        result = suite.test_nebius_vision('image/png', 'BASE64', 12)
    assert result['object_count'] == 1
    assert call.call_args.args[1]['messages'][1]['content'][1]['image_url']['url'].startswith('data:image/png;base64,')
    assert call.call_args.args[1]['model'] == 'test-model'


def test_openai_image_payload():
    response = {'choices': [{'message': {'content': '{"room_category":"closet","visible_objects":["shelf"]}'}}]}
    with patch.dict('os.environ', {'OPENAI_API_KEY': 'fake'}), patch.object(suite, '_request', return_value=response) as call:
        assert suite.test_openai_vision('image/png', 'BASE64', 12)['room'] == 'closet'
    assert call.call_args.args[0].startswith('https://api.openai.com/')


def test_anthropic_image_payload():
    response = {'content': [{'type': 'text', 'text': '{"room_category":null,"visible_objects":["window"]}'}]}
    with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'fake'}), patch.object(suite, '_request', return_value=response) as call:
        assert suite.test_anthropic_vision('image/png', 'BASE64', 12)['room'] == 'uncertain'
    body = call.call_args.args[1]
    assert body['messages'][0]['content'][1]['source']['media_type'] == 'image/png'


def test_tavily_requires_sources():
    with patch.dict('os.environ', {'TAVILY_API_KEY': 'fake'}), patch.object(suite, '_request', return_value={'results': []}):
        with pytest.raises(ValueError, match='no_research_results'):
            suite.test_tavily('image/png', 'BASE64', 12)


def test_nebius_reasoning_must_obey_away():
    with patch.dict('os.environ', {'NEBIUS_API_KEY': 'fake', 'NEBIUS_REASONING_MODEL': 'nvidia/test'}), patch.object(suite, '_request', return_value={'choices': [{'message': {'content': '{"decision":"execute","reason":"now"}'}}]}):
        with pytest.raises(ValueError, match='away_constraint'):
            suite.test_nebius_reasoning('image/png', 'BASE64', 12)


def test_missing_key_skipped_and_strict_fails(image, capsys):
    with patch.dict('os.environ', {'OPENAI_API_KEY': ''}):
        assert suite.run_checks(image, selected={'OpenAI vision'}) == 0
        assert suite.run_checks(image, selected={'OpenAI vision'}, require_all=True) == 1
    assert '[SKIP]' in capsys.readouterr().out


def test_run_checks_does_not_print_keys(image, capsys):
    with patch.dict('os.environ', {'OPENAI_API_KEY': 'supersecret'}), patch.object(suite, '_request', side_effect=RuntimeError('http_401')):
        assert suite.run_checks(image, selected={'OpenAI vision'}) == 1
    logged = capsys.readouterr().out
    assert 'supersecret' not in logged
    assert '[FAIL] OpenAI vision: http_401' in logged
