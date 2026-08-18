import importlib
from pathlib import Path


def fresh(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'operator.db'))
    monkeypatch.setenv('JARVIS_DATA_DIR',str(tmp_path/'data'))
    import app.db as dbm; importlib.reload(dbm); dbm.init_db(); dbm.init_jarvis_schema()
    return dbm


def test_incident_dedupe_and_resolve(tmp_path,monkeypatch):
    fresh(tmp_path,monkeypatch)
    import app.incidents as inc; importlib.reload(inc)
    a=inc.create_incident('shopify','Shopify sync failed','boom','high','shopify-sync')
    b=inc.create_incident('shopify','Shopify sync failed','boom again','high','shopify-sync')
    assert a['id']==b['id'] and b['occurrence_count']==2
    assert inc.incident_summary()['open']==1
    assert inc.resolve_incident(a['id'],'fixed')['status']=='resolved'


def test_restore_requires_safe_mode(tmp_path,monkeypatch):
    db=fresh(tmp_path,monkeypatch)
    import app.recovery as rec; importlib.reload(rec)
    blob,_=rec.create_recovery_bundle('this-is-a-long-passphrase')
    try:
        rec.restore_recovery_bundle(blob,'this-is-a-long-passphrase','RESTORE PANTHER PEPTIDES')
        assert False
    except ValueError as e:
        assert 'Safe Mode' in str(e)


def test_restore_roundtrip(tmp_path,monkeypatch):
    db=fresh(tmp_path,monkeypatch)
    import app.recovery as rec; importlib.reload(rec)
    import app.operating_state as ops; importlib.reload(ops)
    con=db.connect(); con.execute("INSERT INTO owner_memory(key,value) VALUES ('test','before')"); con.commit(); con.close()
    blob,_=rec.create_recovery_bundle('this-is-a-long-passphrase')
    con=db.connect(); con.execute("UPDATE owner_memory SET value='after' WHERE key='test'"); con.commit(); con.close()
    ops.set_safe_mode(True,'restore test')
    result=rec.restore_recovery_bundle(blob,'this-is-a-long-passphrase','RESTORE PANTHER PEPTIDES')
    assert result['ok']
    con=db.connect(); row=con.execute("SELECT value FROM owner_memory WHERE key='test'").fetchone(); con.close()
    assert row['value']=='before'
