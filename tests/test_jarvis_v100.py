import os, importlib

def fresh(tmp_path):
    os.environ['DATABASE_PATH']=str(tmp_path/'operator.db'); os.environ['JARVIS_CONFIG_PATH']=str(tmp_path/'jarvis.env'); os.environ['JARVIS_BACKUP_DIR']=str(tmp_path/'backups')
    import app.db as db; importlib.reload(db); db.init_db(); db.init_jarvis_schema(); db.init_v35_schema(); db.init_v40_schema(); db.init_v45_schema(); db.init_v50_schema(); db.init_v55_schema(); db.init_v60_schema(); db.init_v65_schema(); db.init_v70_schema(); db.init_v75_schema(); db.init_v80_schema(); db.init_v85_schema(); db.init_v90_schema(); db.init_v95_schema(); db.init_v100_schema(); return db

def test_v100_schema_version_and_contracts(tmp_path):
    db=fresh(tmp_path); con=db.connect(); v=con.execute("SELECT value FROM company_settings WHERE key='jarvis_version'").fetchone()['value']; tables={r['name'] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}; gated=con.execute("SELECT COUNT(*) c FROM autonomy_contracts WHERE requires_approval=1").fetchone()['c']; con.close(); assert v=='100.0.0' and gated>=6; assert {'autonomy_contracts','go_live_certifications','maturity_snapshots','self_evaluations','governor_runs','owner_brief_snapshots_v100'}<=tables

def test_hard_gated_contracts_cannot_auto_execute(tmp_path):
    fresh(tmp_path); from app.governor_v100 import contracts; r=contracts(); by={x['scope']:x for x in r['items']};
    for scope in r['hard_gated']: assert by[scope]['requires_approval']==1 and by[scope]['external_side_effects_allowed']==0

def test_go_live_certification_blocks_without_released_inventory(tmp_path):
    fresh(tmp_path); from app.governor_v100 import certify_go_live; r=certify_go_live(); assert r['status']=='blocked' and any('released inventory' in x for x in r['blockers']) and r['external_side_effects'] is False

def test_self_evaluation_reports_zero_high_risk_auto_actions(tmp_path):
    fresh(tmp_path); from app.governor_v100 import self_evaluate; r=self_evaluate(); assert r['status']=='passed' and r['findings']['external_high_risk_auto_actions_allowed']==0

def test_governor_run_has_no_external_side_effects(tmp_path):
    fresh(tmp_path); from app.governor_v100 import run; r=run(0); assert r['external_side_effects'] is False and r['high_risk_auto_actions']==0

def test_owner_brief_persists_snapshot(tmp_path):
    db=fresh(tmp_path); from app.governor_v100 import owner_brief; r=owner_brief(); assert 'Jarvis v100' in r['summary']; con=db.connect(); assert con.execute('SELECT COUNT(*) c FROM owner_brief_snapshots_v100').fetchone()['c']==1; con.close()
