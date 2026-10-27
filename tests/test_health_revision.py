from fastapi.testclient import TestClient
import pytest

import main


@pytest.mark.parametrize('packaged_revision,render_revision,expected', [
    ('a' * 40 + '\n', 'b' * 40, 'a' * 40),
    (None, 'b' * 40, 'b' * 40),
    ('\n', 'b' * 40, 'b' * 40),
    (None, None, None),
])
def test_health_reports_the_deployed_revision(tmp_path, monkeypatch, packaged_revision, render_revision, expected):
    revision_file = tmp_path / 'deployment-revision.txt'
    if packaged_revision is not None:
        revision_file.write_text(packaged_revision, encoding='utf-8')
    monkeypatch.setattr(main, '_REVISION_FILE', revision_file)
    if render_revision is None:
        monkeypatch.delenv('RENDER_GIT_COMMIT', raising=False)
    else:
        monkeypatch.setenv('RENDER_GIT_COMMIT', render_revision)

    response = TestClient(main.app).get('/health')

    assert response.status_code == 200
    assert response.json()['status'] == 'ok'
    assert response.json()['revision'] == expected
    assert response.json()['manual_protocol'] == 'text-v1-visual-v1'
