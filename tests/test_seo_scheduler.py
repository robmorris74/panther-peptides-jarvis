from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import pytest
from app223 import db, seo, seo_scheduler

@pytest.fixture
def store(monkeypatch, tmp_path):
    monkeypatch.setattr(db, 'DB_PATH', tmp_path / 'seo.db')

def fetch(url, root):
    if url.endswith('/robots.txt'):
        return 200, 'User-agent: *\nAllow: /', {}, url
    if url.endswith('/sitemap.xml'):
        return 200, '<urlset></urlset>', {}, url
    return 200, '<title>Research catalog</title><h1>Catalog</h1>', {'Content-Type': 'text/html'}, url

def test_daily_audit_runs_then_survives_restart_without_duplicate(store):
    with patch.object(seo, '_fetch', side_effect=fetch):
        first = seo_scheduler.run_if_due()
        assert first['ran'] and first['ok']
        created = datetime.fromisoformat(first['report']['created_at'])
        # No in-memory timestamps: a new invocation relies on persisted reports.
        assert not seo_scheduler.run_if_due(created + timedelta(hours=23))['ran']
        assert seo_scheduler.run_if_due(created + timedelta(hours=25))['ran']
    assert len(db.execute('SELECT id FROM seo_reports', fetch=True)) == 2

def test_failed_crawl_is_saved_and_not_retried_each_minute(store):
    with patch.object(seo, '_fetch', side_effect=RuntimeError('unreachable')):
        failed = seo_scheduler.run_if_due()
        assert failed['ran'] and not failed['ok']
        assert not seo_scheduler.run_if_due()['ran']
    assert seo.latest_report()['report']['state'] == 'blocked'

def test_production_default_and_explicit_pause(monkeypatch):
    monkeypatch.setenv('JARVIS_ENV', 'production')
    monkeypatch.delenv('JARVIS_SEO_ENABLED', raising=False)
    assert seo_scheduler.enabled()
    monkeypatch.setenv('JARVIS_SEO_ENABLED', '0')
    assert not seo_scheduler.enabled()

def test_reports_and_scheduler_require_owner_and_public_health_has_no_report(store):
    from fastapi.testclient import TestClient
    from app223.main import app
    client = TestClient(app)
    assert client.get('/seo/scheduler').status_code == 401
    health = client.get('/health').json()['seo_service']
    assert set(health) == {'revision', 'enabled', 'worker_alive'}
