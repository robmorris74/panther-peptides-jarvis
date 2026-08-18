import os, importlib
from pathlib import Path

def fresh(tmp_path):
    os.environ['DATABASE_PATH']=str(tmp_path/'operator.db'); os.environ['JARVIS_CONFIG_PATH']=str(tmp_path/'jarvis.env'); os.environ['JARVIS_BACKUP_DIR']=str(tmp_path/'backups')
    import app.db as db; importlib.reload(db); db.init_db(); db.init_jarvis_schema(); db.init_v35_schema(); db.init_v40_schema(); db.init_v45_schema(); db.init_v50_schema(); db.init_v55_schema(); db.init_v60_schema(); db.init_v65_schema(); db.init_v70_schema(); db.init_v75_schema(); db.init_v80_schema(); db.init_v85_schema(); db.init_v90_schema(); return db

def test_v90_schema_and_version(tmp_path):
    db=fresh(tmp_path); con=db.connect(); v=con.execute("SELECT value FROM company_settings WHERE key='jarvis_version'").fetchone()['value']; tables={r['name'] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}; deps=con.execute('SELECT COUNT(*) c FROM dependency_inventory').fetchone()['c']; con.close(); assert v=='90.0.0'; assert deps>=5; assert {'dependency_inventory','recovery_drills','backup_verifications','continuity_plans','continuity_runs'}<=tables

def test_recovery_drill_never_restores_live_data(tmp_path):
    fresh(tmp_path); from app.continuity import recovery_drill; r=recovery_drill('database_restore_plan'); assert r['result']['actual_restore_performed'] is False and r['external_side_effects'] is False

def test_continuity_plan_has_database_loss_scenario(tmp_path):
    fresh(tmp_path); from app.continuity import continuity_plan; r=continuity_plan(); assert any(x['scenario']=='database_loss' for x in r['items'])

def test_backup_verification_handles_missing_backup_safely(tmp_path):
    fresh(tmp_path); from app.continuity import verify_latest_backup; r=verify_latest_backup(); assert r['exists'] is False and r['external_side_effects'] is False

def test_continuity_run_side_effect_free(tmp_path):
    fresh(tmp_path); from app.continuity import run; r=run(); assert 0<=r['score']<=100 and r['external_side_effects'] is False
