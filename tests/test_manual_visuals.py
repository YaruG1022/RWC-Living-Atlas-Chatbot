import base64
import copy
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import chat_tools
import manual_visuals as visuals
from manual_knowledge import publish_bundle, read_active, rollback, build_records
from test_manual_knowledge import package, FakeIndex
from test_published_manual import Response

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j3ioAAAAASUVORK5CYII=')


def visual_package():
    manifest, bundle = package()
    # Synthetic gallery metadata augments the text-only fixture for visual contracts.
    section = bundle['sections'][0]
    section['examples'] = [{'id': section['id'] + '-example-01', 'kind': 'react-demo', 'caption': 'Sample gallery'}]
    entries = []
    for section in bundle['sections']:
        for example in [None, *section['examples']]:
            entries.append({'id': f'{section["id"]}-overview' if example is None else example['id'] + '-default',
                'sectionId': section['id'], 'exampleId': example['id'] if example else '',
                'state': 'default' if example else 'chapter-overview', 'version': manifest['version'], 'revision': manifest['revision'],
                'blockIds': [b['id'] for b in section['blocks'][:2]], 'stepIds': [], 'caption': section['title'],
                'path': f'images/{hashlib.sha256(PNG).hexdigest()}.png', 'sha256': hashlib.sha256(PNG).hexdigest(), 'bytes': len(PNG), 'width': 1, 'height': 1})
    catalog = {'schemaVersion': 1, 'version': manifest['version'], 'revision': manifest['revision'], 'entries': entries}
    raw = json.dumps(catalog).encode()
    digest = hashlib.sha256(raw).hexdigest()
    descriptor = {'schemaVersion': 1, 'path': f'visuals/{digest}.json', 'sha256': digest, 'bytes': len(raw), 'count': len(entries)}
    manifest['visuals'] = descriptor
    return manifest, bundle, catalog, raw


def test_catalog_binds_all_examples_to_real_blocks_steps_and_release():
    manifest, bundle, catalog, raw = visual_package()
    assert visuals.validate_catalog(manifest['visuals'], raw, manifest['version'], manifest['revision'], bundle) == catalog
    with pytest.raises(ValueError, match='checksum'):
        visuals.validate_catalog(manifest['visuals'], raw + b' ', manifest['version'], manifest['revision'], bundle)
    with pytest.raises(ValueError, match='version'):
        visuals.validate_catalog(manifest['visuals'], raw, 'b' * 40, manifest['revision'], bundle)
    for field, value in [('path', 'https://evil.example/image.png'), ('blockIds', ['not-a-real-block']), ('stepIds', ['invented-step'])]:
        bad = copy.deepcopy(catalog); bad['entries'][0][field] = value
        raw_bad = json.dumps(bad).encode(); digest = hashlib.sha256(raw_bad).hexdigest()
        descriptor = {**manifest['visuals'], 'path': f'visuals/{digest}.json', 'bytes': len(raw_bad), 'sha256': digest}
        with pytest.raises(ValueError):
            visuals.validate_catalog(descriptor, raw_bad, manifest['version'], manifest['revision'], bundle)


def test_pointer_and_rollback_retain_visual_identity():
    manifest, bundle, catalog, _ = visual_package()
    bundle['_visual_catalog'] = catalog
    index = FakeIndex()
    publish_bundle(index, manifest, bundle, 'https://atlas.example', activate=True, attempts=1)
    pointer = read_active(index)
    assert pointer['visuals'] == manifest['visuals']
    assert all(record['image_ids'] for record in build_records(manifest, bundle))
    next_manifest, next_bundle = package('b' * 40)
    publish_bundle(index, next_manifest, next_bundle, 'https://atlas.example', activate=True, attempts=1)
    rollback(index, manifest['version'])
    assert read_active(index)['visuals'] == pointer['visuals']


def test_selection_prefers_retrieved_control_and_requested_state():
    manifest, bundle, catalog, _ = visual_package()
    section = next(section for section in bundle['sections'] if section['examples'])
    example = next(entry for entry in catalog['entries'] if entry['sectionId'] == section['id'] and entry['state'] == 'default')
    slideshow = {**example, 'id': example['id'] + '-slideshow', 'state': 'slideshow'}
    catalog['entries'].append(slideshow)
    sources = [{'section_id': section['id'], 'block_ids': example['blockIds']}]
    chosen = visuals.select_visuals(catalog, sources, 'slideshow')
    assert chosen[0]['id'] == slideshow['id'] and len(chosen) <= 2
    assert all(entry['sectionId'] == section['id'] for entry in chosen)


def test_image_rejects_spa_fallback_corruption_and_oversize():
    _, _, catalog, _ = visual_package()
    entry = catalog['entries'][0]
    session = Mock()
    session.get.return_value = Response(PNG, 'image/png')
    assert visuals.fetch_image(session, 'https://atlas.example', entry['version'], entry) == PNG
    assert session.get.call_args.kwargs['allow_redirects'] is False
    for raw, mime in [(b'<html>Fallback</html>', 'text/html'), (PNG[:-1] + b'x', 'image/png'), (PNG + b' ', 'image/png')]:
        session.get.return_value = Response(raw, mime)
        with pytest.raises(ValueError):
            visuals.fetch_image(session, 'https://atlas.example', entry['version'], entry)


def test_gallery_caption_beats_unrelated_first_chapter_and_overviews():
    entries = [
        {'id': 'card-container-cover', 'sectionId': 'card-container', 'state': 'default', 'blockIds': ['cover-block'], 'caption': 'Cover Image Navigation'},
        {'id': 'card-container-overview', 'sectionId': 'card-container', 'state': 'chapter-overview', 'blockIds': ['cover-block'], 'caption': 'Card Container'},
        {'id': 'detail-view-gallery', 'sectionId': 'detail-view', 'state': 'default', 'blockIds': ['gallery-block'], 'caption': 'Image Gallery'},
        {'id': 'detail-view-slideshow', 'sectionId': 'detail-view', 'state': 'slideshow', 'blockIds': ['gallery-block'], 'caption': 'Image Gallery'},
    ]
    sources = [
        {'section_id': 'card-container', 'operation_block_ids': ['cover-block'], 'image_ids': ['card-container-cover', 'card-container-overview']},
        {'section_id': 'detail-view', 'operation_block_ids': ['gallery-block'], 'image_ids': ['detail-view-gallery', 'detail-view-slideshow']},
    ]
    result = visuals.select_visuals({'entries': entries}, sources, query='Image layout dropdown and See all images button position in gallery')
    assert [entry['id'] for entry in result] == ['detail-view-gallery']
    result = visuals.select_visuals({'entries': entries}, sources, 'slideshow', query='card image gallery slideshow layout controls arrows')
    assert [entry['id'] for entry in result] == ['detail-view-slideshow']


def test_openai_compatible_request_uses_verified_images_text_and_chinese(monkeypatch):
    manifest, bundle, catalog, _ = visual_package()
    pointer = {'base_url': 'https://atlas.example', 'version': manifest['version'], 'revision': manifest['revision'], 'visuals': manifest['visuals']}
    monkeypatch.setenv('VISION_API_KEY', 'fake-test-key'); monkeypatch.setenv('VISION_MODEL', 'test-vision')
    monkeypatch.setattr(visuals, '_cached_catalog', lambda *args: catalog)
    session = Mock(); session.__enter__ = Mock(return_value=session); session.__exit__ = Mock()
    session.get.return_value = Response(PNG, 'image/png')
    monkeypatch.setattr(visuals.requests, 'Session', lambda: session)
    client = Mock(); client.__enter__ = Mock(return_value=client); client.__exit__ = Mock()
    client.chat.completions.create.return_value = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='按钮位于工具栏。'))], usage=SimpleNamespace(prompt_tokens=123, completion_tokens=10))
    factory = Mock(return_value=client)
    monkeypatch.setattr('openai.OpenAI', factory)
    source = {'section_id': bundle['sections'][0]['id'], 'block_ids': [b['id'] for b in bundle['sections'][0]['blocks']]}
    answer, metrics = visuals.describe_visuals('这个图标在哪里？', 'Verified steps and cautions.', [source], pointer)
    assert answer == '按钮位于工具栏。' and metrics['image_count'] <= 2 and metrics['prompt_tokens'] == 123
    messages = client.chat.completions.create.call_args.kwargs['messages']
    assert '这个图标在哪里？' in messages[1]['content'][0]['text']
    assert 'Verified steps and cautions.' in messages[1]['content'][0]['text']
    image = next(item for item in messages[1]['content'] if item['type'] == 'image_url')
    assert base64.b64decode(image['image_url']['url'].split(',')[1]) == PNG
    assert factory.call_args.kwargs['max_retries'] == 0
    client.chat.completions.create.side_effect = TimeoutError('provider failed')
    assert visuals.describe_visuals('Where?', 'Text', [source], pointer)[1]['reason'] == 'vision-service-failed'


def test_missing_configuration_or_images_never_calls_provider(monkeypatch):
    monkeypatch.delenv('VISION_API_KEY', raising=False)
    provider = Mock(); monkeypatch.setattr('openai.OpenAI', provider)
    assert visuals.describe_visuals('Where?', 'Text', [], {})[1]['status'] == 'unavailable'
    provider.assert_not_called()
    monkeypatch.setenv('VISION_API_KEY', 'fake-test-key'); monkeypatch.setenv('VISION_MODEL', 'test-model')
    manifest, _, catalog, _ = visual_package()
    monkeypatch.setattr(visuals, '_cached_catalog', lambda *args: catalog)
    pointer = {'base_url': 'https://atlas.example', 'version': manifest['version'], 'revision': manifest['revision'], 'visuals': manifest['visuals']}
    assert visuals.describe_visuals('Where?', 'Text', [], pointer)[1]['reason'] == 'images-unavailable'
    provider.assert_not_called()


def test_visual_tool_reuses_pinned_version_and_runs_once(monkeypatch):
    index = FakeIndex(); manifest, bundle = package()
    publish_bundle(index, manifest, bundle, 'https://atlas.example', activate=True, attempts=1)
    monkeypatch.setattr(chat_tools, 'get_pinecone_index', lambda: index)
    monkeypatch.setattr(chat_tools, '_LAST_MANUAL_POINTER', None)
    ctx = chat_tools.ToolContext(user_question='这个图标在哪里？')
    chat_tools.search_documentation('create card', ctx=ctx)
    original = ctx.manual_pointer['version']
    new, new_bundle = package('c' * 40)
    publish_bundle(index, new, new_bundle, 'https://atlas.example', activate=True, attempts=1)
    describe = Mock(return_value=(None, {'status': 'unavailable', 'reason': 'images-unavailable'}))
    monkeypatch.setattr(visuals, 'describe_visuals', describe)
    result = chat_tools.execute_tool('inspect_manual_visuals', {'query': 'card creation'}, ctx)
    assert 'could not be inspected' in result and 'Card Creation' in result
    assert ctx.manual_pointer['version'] == original
    assert describe.call_args.args[0] == '这个图标在哪里？'
    assert chat_tools.execute_tool('inspect_manual_visuals', {'query': 'again'}, ctx) == result
    assert describe.call_count == 1


def test_eager_text_fallback_never_calls_vision(monkeypatch):
    describe = Mock(); monkeypatch.setattr(visuals, 'describe_visuals', describe)
    monkeypatch.setattr(chat_tools, 'search_documentation', lambda *args, **kwargs: 'Manual text')
    monkeypatch.setattr(chat_tools, 'search_cards', lambda *args: 'Live cards')
    monkeypatch.setattr(chat_tools, 'browse_arcgis_catalog', lambda *args: 'Live ArcGIS')
    assert 'Manual text' in chat_tools.gather_all_context('How to add a card?', chat_tools.ToolContext())
    describe.assert_not_called()


def test_procedural_question_cannot_be_upgraded_to_a_billed_visual_call(monkeypatch):
    describe = Mock(); monkeypatch.setattr(visuals, 'describe_visuals', describe)
    monkeypatch.setattr(chat_tools, 'search_documentation', lambda *args, **kwargs: 'Verified gallery reorder steps')
    ctx = chat_tools.ToolContext(user_question='如何修改图片顺序，并让第二张图片变成封面？')
    assert chat_tools.execute_tool('inspect_manual_visuals', {'query': 'gallery reorder icons'}, ctx) == 'Verified gallery reorder steps'
    assert ctx.visual_status == {'status': 'not-requested'}
    describe.assert_not_called()


def test_rendered_delete_label_blocks_false_slideshow_close_but_allows_real_close():
    answer = '- Previous/next arrows navigate images.\n- **Close (×)** — exits the slideshow view.\n- The × deletes the image.'
    labels = {'control_labels': ['Previous gallery image', 'Next gallery image', 'Delete image 1', 'Image layout']}
    result = visuals.guard_gallery_close_claim(answer, labels)
    assert 'exits the slideshow' not in result and 'navigate images' in result and 'deletes the image' in result
    assert visuals.guard_gallery_close_claim(answer, {'control_labels': ['Delete image 1', 'Close slideshow']}) == answer


def test_catalog_rejects_invalid_control_observations():
    manifest, bundle, catalog, _ = visual_package()
    catalog['entries'][0]['controls'] = [{'role': 'button', 'label': 'Delete image 1', 'icon': 'xmark', 'bounds': [1, 2, 3]}]
    raw = json.dumps(catalog).encode(); digest = hashlib.sha256(raw).hexdigest()
    descriptor = {**manifest['visuals'], 'path': f'visuals/{digest}.json', 'sha256': digest, 'bytes': len(raw)}
    with pytest.raises(ValueError, match='control metadata'):
        visuals.validate_catalog(descriptor, raw, manifest['version'], manifest['revision'], bundle)
