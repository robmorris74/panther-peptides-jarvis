import os
from pathlib import Path
import pytest

@pytest.fixture()
def fresh(tmp_path,monkeypatch):
    db=tmp_path/'operator.db'; cfg=tmp_path/'jarvis.env'
    monkeypatch.setenv('DATABASE_PATH',str(db)); monkeypatch.setenv('JARVIS_CONFIG_PATH',str(cfg))
    import app.db as dbm; dbm.DB_PATH=str(db); dbm.init_db(); dbm.init_jarvis_schema()
    return dbm,cfg

def test_v10_schema_version(fresh):
    dbm,cfg=fresh; con=dbm.connect(); v=con.execute("SELECT value FROM company_settings WHERE key='jarvis_version'").fetchone()['value']; con.close()
    assert tuple(map(int,v.split('.'))) >= (10,0,0)

def test_persistent_connection_config(fresh,monkeypatch):
    dbm,cfg=fresh
    from app.setup_service import save_connections,setup_summary
    save_connections({'SHOPIFY_STORE_DOMAIN':'panther-test.myshopify.com','SHOPIFY_ADMIN_TOKEN':'secret-test','EASYPOST_API_KEY':'ez-test','SHIP_FROM_ADDRESS1':'1 Test St','SHIP_FROM_CITY':'Testville','SHIP_FROM_REGION':'KS','SHIP_FROM_POSTAL':'66000'})
    assert cfg.exists()
    text=cfg.read_text()
    assert 'SHOPIFY_STORE_DOMAIN=panther-test.myshopify.com' in text
    assert setup_summary()['shopify_connected'] is True
    assert setup_summary()['ship_from_configured'] is True

def test_deployment_readiness_keeps_quarantine_blocker(fresh):
    dbm,cfg=fresh
    con=dbm.connect(); pid=con.execute("INSERT INTO products(category,name,sku,qty_on_hand) VALUES ('Research','Test','T1',10)").lastrowid; con.execute("INSERT INTO lots(product_id,lot_code,received_qty,available_qty,disposition) VALUES (?,?,?,?,?)",(pid,'UNKNOWN',10,0,'quarantine')); con.commit(); con.close()
    from app.deployment import readiness
    r=readiness()
    assert r['version']=='30.0.0'
    assert any('quarantined' in x.lower() for x in r['blockers'])
    assert any(x['key']=='inventory_release' and x['ok'] is False for x in r['checks'])

def test_connection_secrets_not_returned(fresh):
    dbm,cfg=fresh
    from app.setup_service import save_connections,setup_summary
    save_connections({'OPENAI_API_KEY':'super-secret-key','SHOPIFY_ADMIN_TOKEN':'shop-secret'})
    out=str(setup_summary())
    assert 'super-secret-key' not in out and 'shop-secret' not in out
