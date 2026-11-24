from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from openai import OpenAIError

import card_description
from main import app


SOURCE = {'label': 'Monitoring report', 'text': 'The project measured stream temperature at four sites.'}
IMAGE = {'label': 'Field photo', 'data_url': 'data:image/jpeg;base64,/9j/4A=='}
HEADERS = {'X-Atlas-Description-Token': 'local-test-token-32-characters-long'}


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setenv('ATLAS_DESCRIPTION_TOKEN', HEADERS['X-Atlas-Description-Token'])
    monkeypatch.setenv('DEEPSEEK_API', 'mock-text-key')
    monkeypatch.setenv('DEEPSEEK_MODEL', 'text-test-model')
    monkeypatch.setenv('VISION_API_KEY', 'mock-vision-key')
    monkeypatch.setenv('VISION_MODEL', 'vision-test-model')
    monkeypatch.setenv('VISION_BASE_URL', 'https://vision.example.com/v1')
    mock_openai = MagicMock()
    generate = mock_openai.return_value.__enter__.return_value.chat.completions.create
    generate.return_value = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='Draft.'))])
    monkeypatch.setattr(card_description, 'OpenAI', mock_openai)
    return mock_openai, generate


def request_draft(payload, headers=HEADERS):
    return TestClient(app).post('/internal/cards/description', json=payload, headers=headers)


def test_authorize_before_parsing_or_calling_provider(provider):
    response = request_draft('invalid body containing private evidence', headers={})
    assert response.status_code == 401
    assert 'private evidence' not in response.text
    provider[0].assert_not_called()


def test_reject_short_shared_token(provider, monkeypatch):
    token = 'a' * 31
    monkeypatch.setenv('ATLAS_DESCRIPTION_TOKEN', token)
    response = request_draft({'sources': [SOURCE]}, headers={'X-Atlas-Description-Token': token})
    assert response.status_code == 503
    provider[0].assert_not_called()


@pytest.mark.parametrize('images', [[], [IMAGE]])
def test_use_existing_provider_without_tools(provider, images):
    mock_openai, generate = provider
    response = request_draft({'title': 'Field survey', 'sources': [SOURCE], 'images': images})

    assert response.status_code == 200
    assert response.json() == {'description': 'Draft.'}
    options = generate.call_args.kwargs
    assert 'tools' not in options
    prompt = options['messages'][1]['content']
    if images:
        mock_openai.assert_called_once_with(
            api_key='mock-vision-key', base_url='https://vision.example.com/v1', timeout=25, max_retries=0,
        )
        assert options['model'] == 'vision-test-model'
        assert 'extra_body' not in options
        assert SOURCE['text'] in prompt[0]['text']
        assert any(part.get('image_url', {}).get('url') == IMAGE['data_url'] for part in prompt)
    else:
        mock_openai.assert_called_once_with(
            api_key='mock-text-key', base_url='https://api.deepseek.com', timeout=25, max_retries=0,
        )
        assert options['model'] == 'text-test-model'
        assert options['extra_body'] == {'thinking': {'type': 'disabled'}}
        assert SOURCE['text'] in prompt


@pytest.mark.parametrize(('base_url', 'expected'), [
    ('https://api.deepseek.com', {'thinking': {'type': 'disabled'}}),
    ('https://api.deepseek.com.example.org', None),
])
def test_vision_disables_thinking_only_on_deepseek(provider, monkeypatch, base_url, expected):
    monkeypatch.setenv('VISION_BASE_URL', base_url)
    response = request_draft({'sources': [SOURCE], 'images': [IMAGE]})

    assert response.status_code == 200
    assert provider[1].call_args.kwargs.get('extra_body') == expected


@pytest.mark.parametrize(('payload', 'status_code'), [
    ({'title': 'A title alone'}, 422),
    ({'sources': [{'label': 'Too long', 'text': 'z' * 12001}]}, 422),
    ({'sources': [{'label': 'Source', 'text': 'x' * 12000}] * 6}, 413),
    ({'images': [{'label': 'Remote', 'data_url': 'https://vision.example.com/photo.jpg'}]}, 422),
    ({'images': [IMAGE] * 9}, 422),
])
def test_reject_invalid_or_oversize_evidence(provider, payload, status_code):
    assert request_draft(payload).status_code == status_code
    provider[0].assert_not_called()


def test_reject_oversize_request_before_json_parsing(provider, monkeypatch):
    monkeypatch.setattr(card_description, 'MAX_REQUEST_BYTES', 64)
    assert request_draft({'sources': [SOURCE]}).status_code == 413
    provider[0].assert_not_called()


def test_missing_vision_configuration_does_not_discard_images(provider, monkeypatch):
    monkeypatch.delenv('VISION_API_KEY')
    response = request_draft({'sources': [SOURCE], 'images': [IMAGE]})
    assert response.status_code == 503
    assert response.json()['detail'] == 'Card description generation from images is not configured.'
    provider[0].assert_not_called()


def test_provider_failure_does_not_expose_error_data(provider, caplog):
    provider[1].side_effect = OpenAIError('provider response contains private evidence')
    response = request_draft({'sources': [SOURCE]})
    assert response.status_code == 502
    assert 'private evidence' not in response.text
    assert 'private evidence' not in caplog.text


def test_draft_respects_editor_length_without_splitting_surrogate_pair(provider):
    provider[1].return_value.choices[0].message.content = 'a' + '😀' * 1000
    response = request_draft({'sources': [SOURCE]})
    assert response.json()['description'] == 'a' + '😀' * 999
