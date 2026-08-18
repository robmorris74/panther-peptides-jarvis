import importlib

def fresh(tmp_path,monkeypatch):
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'v30.db'))
    import app.db as db; importlib.reload(db); db.init_db(); db.init_jarvis_schema(); return db

def test_v30_schema_and_version(tmp_path,monkeypatch):
    db=fresh(tmp_path,monkeypatch); con=db.connect();
    v=con.execute("SELECT value FROM company_settings WHERE key='jarvis_version'").fetchone()['value']
    tables={r['name'] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}; con.close()
    assert v=='30.0.0'; assert {'operating_cycles','cycle_steps','integration_checks','simulation_drills'} <= tables

def test_planner_never_auto_executes_owner_work(tmp_path,monkeypatch):
    fresh(tmp_path,monkeypatch)
    import app.planner as planner; importlib.reload(planner)
    p=planner.build_plan(); assert p['cycle_id']>0
    r=planner.run_safe_cycle(); assert r['side_effects']=='internal-only'

def test_simulation_has_no_side_effects(tmp_path,monkeypatch):
    fresh(tmp_path,monkeypatch)
    import app.simulation as sim; importlib.reload(sim)
    r=sim.business_simulation(); assert r['mode']=='simulation' and r['side_effects']=='none'
    d=sim.create_drill('shopify_down'); assert d['side_effects']=='none'

def test_integration_health_snapshot(tmp_path,monkeypatch):
    fresh(tmp_path,monkeypatch)
    import app.integration_health as ih; importlib.reload(ih)
    r=ih.integration_health(); assert len(r['providers'])==4
    x=ih.record_integration_result('shopify',False,'test outage',123); assert x['ok'] is False

def test_operator_status(tmp_path,monkeypatch):
    fresh(tmp_path,monkeypatch)
    import app.production_ops as po; importlib.reload(po)
    r=po.operator_status(); assert r['version']=='30.0.0' and r['agent']=='Jarvis'
