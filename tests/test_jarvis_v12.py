import importlib
from pathlib import Path
import pytest

@pytest.fixture
def fresh(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'operator.db'))
    monkeypatch.setenv('JARVIS_CONFIG_PATH',str(tmp_path/'jarvis.env'))
    monkeypatch.delenv('JARVIS_MASTER_KEY',raising=False)
    for key in ['OPENAI_API_KEY','SHOPIFY_ADMIN_TOKEN','SHOPIFY_WEBHOOK_SECRET','SMTP_PASSWORD','EASYPOST_API_KEY','JARVIS_INBOUND_EMAIL_SECRET']:
        monkeypatch.delenv(key,raising=False)
    import app.db as dbm; importlib.reload(dbm); dbm.init_db(); dbm.init_jarvis_schema()
    import app.config_store as cfg; importlib.reload(cfg)
    import app.operating_state as ops; importlib.reload(ops); ops.connect=dbm.connect
    yield dbm,cfg,ops,tmp_path

def test_v12_schema_version(fresh):
    dbm,*_=fresh; con=dbm.connect(); v=con.execute("SELECT value FROM company_settings WHERE key='jarvis_version'").fetchone()['value']; con.close(); assert v=='30.0.0'

def test_secrets_are_encrypted_not_plaintext(fresh):
    dbm,cfg,ops,tmp=fresh
    cfg.write_config({'SHOPIFY_STORE_DOMAIN':'store.myshopify.com','SHOPIFY_ADMIN_TOKEN':'shpat_secret-token','OPENAI_API_KEY':'sk-example-secret'})
    public=(tmp/'jarvis.env').read_text(); encrypted=(tmp/'jarvis.secrets.enc').read_bytes()
    assert 'store.myshopify.com' in public
    assert 'shpat_secret-token' not in public and b'shpat_secret-token' not in encrypted
    assert 'sk-example-secret' not in public and b'sk-example-secret' not in encrypted
    assert cfg.read_config()['SHOPIFY_ADMIN_TOKEN']=='shpat_secret-token'
    assert (tmp/'jarvis.key').exists()

def test_plaintext_secret_migrates_on_load(fresh, monkeypatch):
    dbm,cfg,ops,tmp=fresh
    (tmp/'jarvis.env').write_text('SHOPIFY_STORE_DOMAIN=store.myshopify.com\nSHOPIFY_ADMIN_TOKEN=legacy-secret\n')
    cfg.load_persistent_config()
    assert 'legacy-secret' not in (tmp/'jarvis.env').read_text()
    assert cfg.read_config()['SHOPIFY_ADMIN_TOKEN']=='legacy-secret'
    assert (tmp/'jarvis.secrets.enc').exists()

def test_safe_mode_blocks_external_actions(fresh):
    dbm,cfg,ops,tmp=fresh
    assert ops.safe_mode_enabled() is False
    ops.set_safe_mode(True,'owner requested pause')
    assert ops.operating_state()['safe_mode'] is True
    with pytest.raises(RuntimeError,match='Safe Mode'):
        ops.require_external_actions_allowed()
    ops.set_safe_mode(False,'resolved')
    ops.require_external_actions_allowed()

def test_launch_checklist_reports_safe_mode_and_secret_storage(fresh, monkeypatch):
    dbm,cfg,ops,tmp=fresh
    import app.backups as backups; importlib.reload(backups); backups.DB_PATH=dbm.DB_PATH; backups.BACKUP_DIR=tmp/'backups'; backups.BACKUP_DIR.mkdir(exist_ok=True); backups.connect=dbm.connect
    backups.create_backup('test')
    import app.setup_service as ss; importlib.reload(ss); ss.connect=dbm.connect
    import app.deployment as dep; importlib.reload(dep); dep.connect=dbm.connect; dep.list_backups=backups.list_backups
    import app.launch_control as lc; importlib.reload(lc); lc.readiness=dep.readiness; lc.list_backups=backups.list_backups
    result=lc.launch_checklist()
    assert result['version']=='30.0.0'
    assert result['safe_mode']['safe_mode'] is False
    assert any(x['key']=='safe_mode' and x['ok'] for x in result['items'])

def test_shopify_client_credentials_mode_is_configured(fresh, monkeypatch):
    dbm,cfg,ops,tmp=fresh
    cfg.write_config({'SHOPIFY_STORE_DOMAIN':'store.myshopify.com','SHOPIFY_CLIENT_ID':'client-id','SHOPIFY_CLIENT_SECRET':'client-secret'})
    import app.shopify_auth as auth; importlib.reload(auth)
    assert auth.configured() is True
    assert auth.auth_mode()=='client_credentials'

def test_shopify_client_credentials_token_is_cached(fresh, monkeypatch):
    dbm,cfg,ops,tmp=fresh
    cfg.write_config({'SHOPIFY_STORE_DOMAIN':'store.myshopify.com','SHOPIFY_CLIENT_ID':'client-id','SHOPIFY_CLIENT_SECRET':'client-secret'})
    import app.shopify_auth as auth; importlib.reload(auth)
    calls=[]
    class Resp:
        def __enter__(self): return self
        def __exit__(self,*a): pass
        def read(self): return b'{"access_token":"short-lived-token","expires_in":86399}'
    def fake(req,timeout=20): calls.append(req.full_url); return Resp()
    monkeypatch.setattr(auth.urllib.request,'urlopen',fake)
    assert auth.get_access_token()=='short-lived-token'
    assert auth.get_access_token()=='short-lived-token'
    assert len(calls)==1 and calls[0].endswith('/admin/oauth/access_token')
