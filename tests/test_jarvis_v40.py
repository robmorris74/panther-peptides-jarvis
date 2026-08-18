import os, importlib


def fresh(tmp_path):
    os.environ['DATABASE_PATH']=str(tmp_path/'operator.db')
    os.environ['JARVIS_CONFIG_PATH']=str(tmp_path/'jarvis.env')
    import app.db as db
    importlib.reload(db)
    db.init_db(); db.init_jarvis_schema(); db.init_v35_schema(); db.init_v40_schema()
    from app.objectives import seed_defaults
    seed_defaults()
    return db


def test_v40_schema_and_version(tmp_path):
    db=fresh(tmp_path); con=db.connect()
    v=con.execute("SELECT value FROM company_settings WHERE key='jarvis_version'").fetchone()['value']
    tables={r['name'] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    con.close()
    assert v=='40.0.0'
    assert {'business_objectives','objective_measurements','decision_journal','integration_circuit_breakers','mission_snapshots'} <= tables


def test_objectives_and_kpi_measurements(tmp_path):
    fresh(tmp_path)
    from app.objectives import objective_status, record_kpi
    record_kpi('unauthorized_actions',0,'test')
    s=objective_status(); item=next(x for x in s['items'] if x['objective_key']=='unauthorized_actions')
    assert item['met'] is True and item['progress_percent']==100.0


def test_decision_learning_loop(tmp_path):
    fresh(tmp_path)
    from app.decision_journal import record_decision, decide, learning_summary
    d=record_decision('pricing','SKU-X','Hold price','Insufficient verified economics')
    assert d['outcome']=='pending'
    d2=decide(d['id'],'edited','Use supplier quote first','Recalculate after quote')
    assert d2['outcome']=='edited'
    s=learning_summary(); assert s['reviewed']==1 and s['edited']==1


def test_circuit_breaker_opens_and_recovers(tmp_path):
    fresh(tmp_path)
    from app.circuit_breakers import configure,record,allow
    configure('shopify',threshold=2,cooldown_seconds=30)
    assert record('shopify',False,'x')['state']=='closed'
    assert record('shopify',False,'y')['state']=='open'
    assert allow('shopify')['allowed'] is False
    assert record('shopify',True,'ok')['state']=='closed'


def test_kpi_snapshot_and_mission_control_are_internal_only(tmp_path):
    fresh(tmp_path)
    from app.kpi_snapshot import snapshot
    from app.mission_control import mission_control
    r=snapshot(); assert r['recorded']>=3
    m=mission_control(); assert 0<=m['health_score']<=100
    assert m['research_only'].startswith('FOR RESEARCH USE ONLY')


def test_v40_work_queue_additions_are_safe(tmp_path):
    fresh(tmp_path)
    from app.work_queue import enqueue,process_one
    for kind in ('kpi_snapshot','sla_scan'):
        x=enqueue(kind,{},priority=20,dedupe_key='v40-'+kind); assert x['status']=='queued'
        out=process_one('v40-test'); assert out['status']=='completed'
