import json
import pytest
from manual_knowledge import fetch_published_bundle
from test_manual_knowledge import FIXTURE


class Response:
    def __init__(self, content, mime='application/json', status=200):
        self.content, self.status_code = content, status
        self.headers = {'Content-Type': mime}
    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError('unpublished')
    def iter_content(self, size):
        yield self.content
    def close(self):
        pass


class Session:
    def __init__(self):
        self.manifest = json.loads((FIXTURE / 'manifest.json').read_bytes())
        self.raw = (FIXTURE / 'manual.json').read_bytes()
        self.marker = self.manifest
        self.bundle_mime = 'application/json'
        self.page_status = 200
    def get(self, url, **kwargs):
        assert kwargs['allow_redirects'] is False
        if url.endswith('/current.json'):
            return Response(json.dumps(self.marker).encode())
        if url.endswith('/manifest.json'):
            return Response(json.dumps(self.manifest).encode())
        if url.endswith('/manual.json'):
            return Response(self.raw, self.bundle_mime)
        return Response(b'<html>Published app</html>', 'text/html', self.page_status)


def test_only_matching_published_page_and_checksum_can_be_imported():
    session = Session()
    manifest, bundle = fetch_published_bundle(session, 'https://atlas.example', 'a' * 40)
    assert manifest['sectionCount'] == len(bundle['sections'])
    with pytest.raises(ValueError, match='not yet published'):
        fetch_published_bundle(session, 'https://atlas.example', 'b' * 40)
    session.raw += b' '
    with pytest.raises(ValueError, match='checksum'):
        fetch_published_bundle(session, 'https://atlas.example')


def test_spa_fallback_and_unpublished_manual_are_not_accepted():
    session = Session()
    session.bundle_mime = 'text/html'
    with pytest.raises(ValueError, match='JSON'):
        fetch_published_bundle(session, 'https://atlas.example')
    session.bundle_mime = 'application/json'
    session.page_status = 404
    with pytest.raises(RuntimeError, match='unpublished'):
        fetch_published_bundle(session, 'https://atlas.example')
    with pytest.raises(ValueError, match='HTTPS app origin'):
        fetch_published_bundle(session, 'https://atlas.example@evil.example/path')
