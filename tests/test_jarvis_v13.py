import importlib
from pathlib import Path
import pytest

@pytest.fixture
def fresh(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'operator.db'))
    monkeypatch.setenv('JARVIS_CONFIG_PATH',str(tmp_path/'jarvis.env'))
    monkeypatch.delenv('JARVIS_MASTER_KEY',raising=False)
    monkeypatch.delenv('JARVIS_ENV',raising=False)
    monkeypatch.delenv('JARVIS_BOOTSTRAP_TOKEN',raising=False)
    import app.db as dbm; importlib.reload(dbm); dbm.init_db(); dbm.init_jarvis_schema()
    import app.config_store as cfg; importlib.reload(cfg)
    yield dbm,cfg,tmp_path

def test_v13_schema_version(fresh):
    dbm,*_=fresh
    con=dbm.connect(); v=con.execute("SELECT value FROM company_settings WHERE key='jarvis_version'").fetchone()['value']; con.close()
    assert v=='30.0.0'

def test_production_claim_requires_server_token(fresh, monkeypatch):
    monkeypatch.setenv('JARVIS_ENV','production')
    import app.production_claim as claim; importlib.reload(claim)
    st=claim.claim_status(False)
    assert st['claim_required'] is True and st['ready'] is False
    monkeypatch.setenv('JARVIS_BOOTSTRAP_TOKEN','host-generated-claim-code')
    assert claim.claim_status(False)['ready'] is True
    assert claim.verify_bootstrap_token('host-generated-claim-code') is True
    assert claim.verify_bootstrap_token('wrong') is False
    assert claim.claim_status(True)['claim_required'] is False

def test_recovery_bundle_roundtrip(fresh):
    dbm,cfg,tmp=fresh
    cfg.write_config({'SHOPIFY_STORE_DOMAIN':'store.myshopify.com','SHOPIFY_ADMIN_TOKEN':'private-token'})
    import app.recovery as recovery; importlib.reload(recovery); recovery.DB_PATH=dbm.DB_PATH
    blob,manifest=recovery.create_recovery_bundle('correct horse battery staple')
    assert blob.startswith(recovery.MAGIC)
    assert b'private-token' not in blob
    inspected=recovery.inspect_recovery_bundle(blob,'correct horse battery staple')
    assert inspected['jarvis_version']=='30.0.0'
    assert inspected['database_present'] is True
    assert inspected['encrypted_secrets_present'] is True
    with pytest.raises(ValueError,match='incorrect|damaged'):
        recovery.inspect_recovery_bundle(blob,'wrong password here')

def test_recovery_requires_strong_passphrase(fresh):
    dbm,cfg,tmp=fresh
    import app.recovery as recovery; importlib.reload(recovery); recovery.DB_PATH=dbm.DB_PATH
    with pytest.raises(ValueError,match='at least 12'):
        recovery.create_recovery_bundle('short')

def test_render_generates_production_claim_code():
    text=Path('render.yaml').read_text()
    assert 'JARVIS_BOOTSTRAP_TOKEN' in text
    assert 'generateValue: true' in text

def test_proxy_aware_origin_validation(fresh, monkeypatch):
    import app.security as sec; importlib.reload(sec)
    class Req:
        headers={'origin':'https://jarvis.example.com','x-forwarded-proto':'https','x-forwarded-host':'jarvis.example.com','host':'internal:8000'}
        class URL: scheme='http'; netloc='internal:8000'
        url=URL()
    assert sec.origin_allowed(Req()) is True
    Req.headers=dict(Req.headers,origin='https://evil.example')
    assert sec.origin_allowed(Req()) is False

def test_public_url_overrides_proxy_origin(fresh, monkeypatch):
    monkeypatch.setenv('JARVIS_PUBLIC_URL','https://private.panther.example')
    import app.security as sec; importlib.reload(sec)
    class Req:
        headers={'origin':'https://private.panther.example','host':'internal:8000'}
        class URL: scheme='http'; netloc='internal:8000'
        url=URL()
    assert sec.origin_allowed(Req()) is True
