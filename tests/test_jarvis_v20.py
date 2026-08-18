import importlib


def fresh(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'operator.db'))
    monkeypatch.setenv('JARVIS_DATA_DIR',str(tmp_path/'data'))
    import app.db as dbm; importlib.reload(dbm); dbm.init_db(); dbm.init_jarvis_schema()
    return dbm


def test_v20_schema_and_version(tmp_path,monkeypatch):
    db=fresh(tmp_path,monkeypatch)
    con=db.connect(); v=con.execute("SELECT value FROM company_settings WHERE key='jarvis_version'").fetchone()['value']
    tables={r['name'] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}; con.close()
    assert v=='30.0.0'
    assert {'idempotency_keys','job_runs','privacy_actions'} <= tables


def test_idempotency_duplicate_protection(tmp_path,monkeypatch):
    fresh(tmp_path,monkeypatch)
    import app.idempotency as i; importlib.reload(i)
    assert i.begin('evt-1','shopify')['accepted'] is True
    assert i.begin('evt-1','shopify')['duplicate'] is True
    assert i.complete('evt-1','shopify','order:9')['status']=='complete'


def test_job_single_active_lock(tmp_path,monkeypatch):
    fresh(tmp_path,monkeypatch)
    import app.jobs as j; importlib.reload(j)
    a=j.acquire('heartbeat'); b=j.acquire('heartbeat')
    assert a['acquired'] is True and b['acquired'] is False
    j.finish(a['job_run_id'],'success','ok')
    assert j.acquire('heartbeat')['acquired'] is True


def test_approval_health_ages_pending(tmp_path,monkeypatch):
    db=fresh(tmp_path,monkeypatch)
    con=db.connect(); con.execute("INSERT INTO approvals(kind,subject,payload,risk,created_at) VALUES ('test','x','x','high',datetime('now','-4 days'))"); con.commit(); con.close()
    import app.approval_health as a; importlib.reload(a)
    h=a.approval_health(); assert h['critical']==1
    s=a.scan_stale_approvals(); assert s['created_tasks']==1
    assert a.scan_stale_approvals()['created_tasks']==0


def test_runbook_security_requires_owner(tmp_path,monkeypatch):
    fresh(tmp_path,monkeypatch)
    import app.runbooks as r; importlib.reload(r)
    x=r.runbook('security','credential concern')
    assert x['owner_required'] is True and 'Enable Safe Mode.' in x['steps']


def test_privacy_purge_requires_safe_mode(tmp_path,monkeypatch):
    db=fresh(tmp_path,monkeypatch)
    con=db.connect(); con.execute("INSERT INTO orders(external_id,customer_email) VALUES ('o1','a@example.com')"); con.commit(); con.close()
    import app.privacy as p; importlib.reload(p)
    try:
        p.purge_customer_email('a@example.com','PURGE CUSTOMER DATA'); assert False
    except ValueError as e: assert 'Safe Mode' in str(e)


def test_privacy_purge_pseudonymizes_in_safe_mode(tmp_path,monkeypatch):
    db=fresh(tmp_path,monkeypatch)
    con=db.connect(); con.execute("INSERT INTO orders(external_id,customer_email) VALUES ('o1','a@example.com')"); con.commit(); con.close()
    import app.operating_state as os_; importlib.reload(os_); os_.set_safe_mode(True,'privacy request')
    import app.privacy as p; importlib.reload(p)
    out=p.purge_customer_email('a@example.com','PURGE CUSTOMER DATA'); assert out['ok']
    con=db.connect(); email=con.execute("SELECT customer_email FROM orders WHERE external_id='o1'").fetchone()['customer_email']; con.close()
    assert email.endswith('@redacted.invalid')


def test_executive_brief_research_only(tmp_path,monkeypatch):
    fresh(tmp_path,monkeypatch)
    import app.executive as e; importlib.reload(e)
    b=e.executive_brief(); assert b['agent']=='Jarvis' and 'RESEARCH USE ONLY' in b['research_only']
