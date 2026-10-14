import copy
import hashlib
import json
from pathlib import Path

import pytest
from manual_knowledge import (ACTIVE_ID, CONTROL_NAMESPACE, build_records, namespace_for,
    publish_bundle, read_active, rollback, search_manual, validate_bundle)

FIXTURE = Path(__file__).parent / 'fixtures/manual'


def package(revision=None):
    manifest = json.loads((FIXTURE / 'manifest.json').read_bytes())
    raw = (FIXTURE / 'manual.json').read_bytes()
    if revision:
        bundle = json.loads(raw)
        bundle['revision'] = revision
        raw = (json.dumps(bundle, separators=(',', ':'), ensure_ascii=False) + '\n').encode()
        checksum = hashlib.sha256(raw).hexdigest()
        version = revision + '-' + checksum[:12]
        manifest.update(revision=revision, version=version, bundlePath=f'/manual/releases/{version}/manual.json',
            manifestPath=f'/manual/releases/{version}/manifest.json', files=[{'path': 'manual.json', 'sha256': checksum, 'bytes': len(raw)}])
    return manifest, validate_bundle(manifest, raw)


class FakeIndex:
    def __init__(self):
        self.data = {}
        self.fail_upsert = False
        self.unsearchable = False
        self.calls = []

    def upsert_records(self, *, namespace, records):
        self.calls.append((namespace, len(records)))
        if self.fail_upsert:
            raise RuntimeError('upsert failed')
        target = self.data.setdefault(namespace, {})
        for record in records:
            target[record['_id']] = copy.deepcopy({k: v for k, v in record.items() if k != '_id'})

    def fetch(self, *, namespace, ids):
        return {'vectors': {id: {'metadata': self.data.get(namespace, {})[id]} for id in ids if id in self.data.get(namespace, {})}}

    def describe_index_stats(self):
        return {'namespaces': {key: {'vector_count': len(value)} for key, value in self.data.items()}}

    def search(self, *, namespace, query, fields):
        if self.unsearchable:
            return {'result': {'hits': []}}
        section = query.get('filter', {}).get('section_id', {}).get('$eq')
        records = [(id, data) for id, data in self.data.get(namespace, {}).items() if not section or data.get('section_id') == section]
        # Deterministic retrieval fixture; live semantic relevance is a separate evaluation.
        if not section and 'card' in query.get('inputs', {}).get('text', '').lower():
            records.sort(key=lambda item: item[1].get('section_id') != 'add-card')
        return {'result': {'hits': [{'_id': id, 'fields': {k: v for k, v in data.items() if k in fields}}
            for id, data in records[:query['top_k']]]}}


def test_real_app_export_validates_and_preserves_operations():
    manifest, bundle = package()
    records = build_records(manifest, bundle)
    assert set(r['section_id'] for r in records) == {'add-card', 'chatbot'}
    required = next(r for r in records if 'Author Name' in r['content'] and '255-character limit' in r['content'])
    assert 'Category is optional' in required['content']
    assert 'four corners' in required['content']
    assert required['block_ids']
    assert all(r['version'] == manifest['version'] for r in records)


def test_modified_payload_fails_before_index_writes():
    manifest, _ = package()
    with pytest.raises(ValueError, match='checksum'):
        validate_bundle(manifest, (FIXTURE / 'manual.json').read_bytes() + b' ')


def test_operation_records_keep_shared_prerequisites_without_duplicate_blocks():
    manifest, bundle = package()
    section = next(section for section in bundle['sections'] if section['id'] == 'add-card')
    section['contextBlockIds'] = ['add-card-004', 'add-card-006']
    records = [record for record in build_records(manifest, bundle) if record['section_id'] == 'add-card']
    assert all('Login is required' in record['content'] and 'Category is optional' in record['content'] for record in records)
    assert all(set(section['contextBlockIds']) <= set(record['block_ids']) for record in records)
    assert all(len(record['block_ids']) == len(set(record['block_ids'])) for record in records)


def test_same_app_release_reindexes_into_new_schema_without_mutating_old_namespace():
    index = FakeIndex(); manifest, bundle = package()
    publish_bundle(index, manifest, bundle, 'https://atlas.example', activate=True, attempts=1)
    pointer = index.data[CONTROL_NAMESPACE][ACTIVE_ID]
    old_namespace = namespace_for(manifest['version'], 1)
    index.data[old_namespace] = index.data.pop(pointer['namespace'])
    pointer['namespace'] = old_namespace; pointer.pop('record_schema')
    old_records = copy.deepcopy(index.data[old_namespace])
    assert read_active(index)['namespace'] == old_namespace
    assert publish_bundle(index, manifest, bundle, 'https://atlas.example', activate=True, attempts=1)['status'] == 'activated'
    assert read_active(index)['namespace'] == namespace_for(manifest['version'], 2)
    assert index.data[old_namespace] == old_records


def test_stage_failure_keeps_old_active_version_and_legacy_namespace():
    index = FakeIndex()
    first, bundle = package()
    publish_bundle(index, first, bundle, 'https://atlas.example', activate=True, attempts=1)
    index.data['__default__'] = {'legacy': {'content': 'obsolete instructions'}}
    index.fail_upsert = True
    new, new_bundle = package('b' * 40)
    with pytest.raises(RuntimeError, match='upsert'):
        publish_bundle(index, new, new_bundle, 'https://atlas.example', activate=True, attempts=1)
    assert read_active(index)['version'] == first['version']
    assert index.data['__default__']['legacy']['content'] == 'obsolete instructions'


def test_unsearchable_stage_cannot_activate_and_retry_is_idempotent():
    index = FakeIndex()
    manifest, bundle = package()
    index.unsearchable = True
    with pytest.raises(RuntimeError, match='validation failed'):
        publish_bundle(index, manifest, bundle, 'https://atlas.example', activate=True, attempts=1)
    assert read_active(index) is None
    index.unsearchable = False
    assert publish_bundle(index, manifest, bundle, 'https://atlas.example', activate=True, attempts=1)['status'] == 'activated'
    calls = list(index.calls)
    assert publish_bundle(index, manifest, bundle, 'https://atlas.example', activate=True, attempts=1)['status'] == 'already-active'
    assert index.calls == calls


def test_advancing_app_during_sync_does_not_activate_stale_release():
    index = FakeIndex()
    manifest, bundle = package()
    def advanced():
        raise RuntimeError('newer app deployed')
    with pytest.raises(RuntimeError, match='newer app'):
        publish_bundle(index, manifest, bundle, 'https://atlas.example', activate=True, attempts=1, before_activate=advanced)
    assert read_active(index) is None


def test_search_sources_are_verified_and_rollback_is_explicit():
    index = FakeIndex()
    old, old_bundle = package()
    new, new_bundle = package('c' * 40)
    publish_bundle(index, old, old_bundle, 'https://atlas.example', activate=True, attempts=1)
    old_pointer = read_active(index)
    publish_bundle(index, new, new_bundle, 'https://atlas.example', activate=True, attempts=1)
    passages, sources = search_manual(index, 'how to create a card', old_pointer)
    assert passages and all(source['version'] == old['version'] for source in sources)
    assert all(source['url'] == 'https://atlas.example/user-manual?section=' + source['section_id'] for source in sources)
    assert rollback(index, old['version'])['status'] == 'rolled-back'
    assert read_active(index)['version'] == old['version']
    del index.data[namespace_for(new['version'])][next(iter(index.data[namespace_for(new['version'])]))]
    with pytest.raises(ValueError, match='incomplete'):
        rollback(index, new['version'])
    assert read_active(index)['version'] == old['version']
