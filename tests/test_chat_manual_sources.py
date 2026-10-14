from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
import chat
import chat_tools
from main import app
from manual_knowledge import publish_bundle
from test_manual_knowledge import FakeIndex, package


@pytest.fixture
def index(monkeypatch):
    index = FakeIndex()
    manifest, bundle = package()
    publish_bundle(index, manifest, bundle, 'https://atlas.example', activate=True, attempts=1)
    monkeypatch.setattr(chat_tools, 'get_pinecone_index', lambda: index)
    monkeypatch.setattr(chat_tools, '_LAST_MANUAL_POINTER', None)
    monkeypatch.setattr(chat, 'get_atlas_facts', lambda: '')
    return index


def test_request_pins_one_version_and_live_tools_are_preserved(index, monkeypatch):
    ctx = chat_tools.ToolContext()
    first = chat_tools.search_documentation('create card', ctx=ctx)
    version = ctx.manual_pointer['version']
    manifest, bundle = package('d' * 40)
    publish_bundle(index, manifest, bundle, 'https://atlas.example', activate=True, attempts=1)
    second = chat_tools.execute_tool('search_documentation', {'query': 'creation requirements'}, ctx)
    assert first and second and all(s['version'] == version for s in ctx.manual_sources)
    assert {t['function']['name'] for t in chat_tools.tool_schemas()} == {'search_documentation', 'inspect_manual_visuals', 'search_cards', 'browse_arcgis_catalog'}
    monkeypatch.setenv('ATLAS_API_URL', 'https://backend.example')
    response = Mock(); response.json.return_value = {'context': 'Live public card records'}
    monkeypatch.setattr(chat_tools.requests, 'get', Mock(return_value=response))
    assert chat_tools.execute_tool('search_cards', {'query': 'salmon'}, ctx) == 'Live public card records'
    assert chat_tools.requests.get.call_args.kwargs['params']['force'] == 1


def test_endpoint_resolves_real_sources_and_removes_fabricated_manual_urls(index, monkeypatch):
    monkeypatch.setenv('DEEPSEEK_API', 'test-key')
    monkeypatch.setattr(chat, 'OpenAI', lambda **kwargs: object())
    message = SimpleNamespace(content='Open the form. [manual:add-card] [bad](https://invented.example/user-manual?section=missing)', tool_calls=None)
    response = SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason='stop')])
    monkeypatch.setattr(chat, '_completion', lambda *args, **kwargs: response)
    result = TestClient(app).post('/chat/ask', json={'question': 'How do I create a card?'} )
    assert result.status_code == 200
    body = result.json()
    assert 'invented' not in body['answer'] and '[manual:' not in body['answer']
    assert body['sources'] and all(source['section_id'] == 'add-card' for source in body['sources'])
    assert body['sources'][0]['url'] == 'https://atlas.example/user-manual?section=add-card'


def test_no_active_manual_never_queries_legacy_namespace(monkeypatch):
    index = FakeIndex()
    index.data['__default__'] = {'old': {'content': 'Category required; PNG only'}}
    monkeypatch.setattr(chat_tools, 'get_pinecone_index', lambda: index)
    monkeypatch.setattr(chat_tools, '_LAST_MANUAL_POINTER', None)
    result = chat_tools.search_documentation('create card')
    assert 'not been activated' in result
    assert 'Category required' not in result


def test_failed_pointer_read_can_use_last_validated_version(index, monkeypatch):
    first = chat_tools.search_documentation('create card')
    assert 'Card Creation' in first
    monkeypatch.setattr(chat_tools, 'read_active', Mock(side_effect=RuntimeError('temporarily unavailable')))
    assert 'Card Creation' in chat_tools.search_documentation('create card')
