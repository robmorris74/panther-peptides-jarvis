import os, importlib
from pathlib import Path


def fresh(tmp_path):
    os.environ['DATABASE_PATH']=str(tmp_path/'operator.db')
    os.environ['JARVIS_CONFIG_PATH']=str(tmp_path/'jarvis.env')
    import app.db as db
    db.DB_PATH=os.environ['DATABASE_PATH']
    db.init_db(); db.init_jarvis_schema(); db.init_v35_schema()
    return db


def test_v35_schema_and_version(tmp_path):
    db=fresh(tmp_path)
    con=db.connect()
    v=con.execute("SELECT value FROM company_settings WHERE key='jarvis_version'").fetchone()['value']
    tables={r['name'] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    con.close()
    assert v=='35.0.0'
    assert {'business_events','scheduled_jobs','internal_work_queue','owner_digests','runtime_ticks'} <= tables


def test_capability_hard_caps_high_risk(tmp_path):
    fresh(tmp_path)
    from app.capabilities import evaluate
    r=evaluate('publish_product','auto')
    assert r['high_risk'] is True
    assert r['allowed_to_execute_automatically'] is False
    assert r['owner_approval_required'] is True


def test_work_queue_only_allows_internal_jobs_and_dedupes(tmp_path):
    fresh(tmp_path)
    from app.work_queue import enqueue, process_one, snapshot
    a=enqueue('self_test',{},80,'test-self')
    b=enqueue('self_test',{},80,'test-self')
    assert a['id']==b['id'] and b.get('deduplicated') is True
    try:
        enqueue('publish_product',{})
        assert False, 'unsafe work kind should fail'
    except ValueError:
        pass
    out=process_one('test-worker')
    assert out['status']=='completed'
    assert snapshot()['counts'].get('completed',0)>=1


def test_scheduler_queues_only_allowlisted_work(tmp_path):
    db=fresh(tmp_path)
    from app.scheduler import tick, list_jobs
    result=tick(10)
    assert result['due']>=1
    con=db.connect(); kinds={r['kind'] for r in con.execute('SELECT kind FROM internal_work_queue').fetchall()}; con.close()
    assert kinds <= {'self_test','approval_scan','readiness_snapshot','owner_digest','queue_maintenance'}
    assert all(j['last_status'] in (None,'queued') for j in list_jobs())


def test_digest_persists_and_runtime_is_internal_only(tmp_path):
    fresh(tmp_path)
    from app.daily_digest import generate_digest, latest
    from app.runtime_supervisor import run_tick, status
    d=generate_digest('2026-08-17')
    assert d['date']=='2026-08-17'
    assert 'research_only' in d['payload']
    assert latest()['digest_date']=='2026-08-17'
    out=run_tick(10)
    assert out['status']=='completed'
    assert out['side_effects']=='internal-only'
    assert status()['last_tick']['status']=='completed'
