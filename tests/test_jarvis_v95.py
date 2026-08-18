import os, importlib

def fresh(tmp_path):
    os.environ['DATABASE_PATH']=str(tmp_path/'operator.db'); os.environ['JARVIS_CONFIG_PATH']=str(tmp_path/'jarvis.env'); os.environ['JARVIS_BACKUP_DIR']=str(tmp_path/'backups')
    import app.db as db; importlib.reload(db); db.init_db(); db.init_jarvis_schema(); db.init_v35_schema(); db.init_v40_schema(); db.init_v45_schema(); db.init_v50_schema(); db.init_v55_schema(); db.init_v60_schema(); db.init_v65_schema(); db.init_v70_schema(); db.init_v75_schema(); db.init_v80_schema(); db.init_v85_schema(); db.init_v90_schema(); db.init_v95_schema(); return db

def test_v95_schema_and_version(tmp_path):
    db=fresh(tmp_path); con=db.connect(); v=con.execute("SELECT value FROM company_settings WHERE key='jarvis_version'").fetchone()['value']; tables={r['name'] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}; con.close(); assert v=='95.0.0'; assert {'security_events_v95','secret_rotation_reviews','access_reviews','audit_checkpoints_v95','security_posture_runs'}<=tables

def test_security_event_is_internal_only(tmp_path):
    fresh(tmp_path); from app.security_posture import record_event; r=record_event('test','warning','x'); assert r['external_side_effects'] is False

def test_secret_review_missing_config_is_safe(tmp_path):
    fresh(tmp_path); from app.security_posture import secret_rotation_review; r=secret_rotation_review(); assert r['status'] in {'missing','ok','rotate'} and r['external_side_effects'] is False

def test_audit_checkpoint_is_hash_stamped(tmp_path):
    fresh(tmp_path); from app.security_posture import audit_checkpoint; r=audit_checkpoint(); assert len(r['checkpoint_hash'])==64 and r['external_side_effects'] is False

def test_security_posture_run_is_side_effect_free(tmp_path):
    fresh(tmp_path); from app.security_posture import run; r=run(); assert 0<=r['score']<=100 and r['external_side_effects'] is False
