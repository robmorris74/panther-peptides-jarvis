import importlib

def fresh(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'operator.db')); monkeypatch.setenv('JARVIS_DATA_DIR',str(tmp_path/'data'))
    import app.db as db; importlib.reload(db); db.init_db(); db.init_jarvis_schema(); return db

def test_v25_schema(tmp_path,monkeypatch):
    db=fresh(tmp_path,monkeypatch); con=db.connect(); v=con.execute("SELECT value FROM company_settings WHERE key='jarvis_version'").fetchone()['value']; tables={r['name'] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}; con.close(); assert v=='30.0.0' and 'readiness_snapshots' in tables

def test_audit_export_hash(tmp_path,monkeypatch):
    db=fresh(tmp_path,monkeypatch); con=db.connect(); con.execute("INSERT INTO security_audit(event,detail) VALUES ('x','y')"); con.commit(); con.close(); import app.audit_export as a; importlib.reload(a); x=a.export_audit(); assert x['count']==1 and len(x['sha256'])==64

def test_retention_dry_run(tmp_path,monkeypatch):
    db=fresh(tmp_path,monkeypatch); con=db.connect(); con.execute("INSERT INTO security_audit(event,created_at) VALUES ('old',datetime('now','-400 days'))"); con.commit(); con.close(); import app.retention as r; importlib.reload(r); assert r.prune(True)['eligible']['security_audit']==1; con=db.connect(); assert con.execute('SELECT COUNT(*) n FROM security_audit').fetchone()['n']==1; con.close()

def test_rate_limit():
    import app.rate_limit as r; key='test-unique'; assert r.allow(key,2,60); assert r.allow(key,2,60); assert not r.allow(key,2,60)

def test_readiness_snapshot(tmp_path,monkeypatch):
    fresh(tmp_path,monkeypatch); import app.readiness_history as r; importlib.reload(r); x=r.snapshot(); assert 'ready' in x; assert len(r.history())==1

def test_self_test_no_side_effects(tmp_path,monkeypatch):
    fresh(tmp_path,monkeypatch); import app.self_test as s; importlib.reload(s); x=s.run_self_test(); assert x['ok'] and x['side_effects']=='none'
