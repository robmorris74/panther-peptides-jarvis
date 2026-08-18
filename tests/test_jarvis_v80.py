import os, importlib

def fresh(tmp_path):
    os.environ['DATABASE_PATH']=str(tmp_path/'operator.db'); os.environ['JARVIS_CONFIG_PATH']=str(tmp_path/'jarvis.env'); os.environ['JARVIS_BACKUP_DIR']=str(tmp_path/'backups')
    import app.db as db; importlib.reload(db); db.init_db(); db.init_jarvis_schema(); db.init_v35_schema(); db.init_v40_schema(); db.init_v45_schema(); db.init_v50_schema(); db.init_v55_schema(); db.init_v60_schema(); db.init_v65_schema(); db.init_v70_schema(); db.init_v75_schema(); db.init_v80_schema(); return db

def test_v80_schema_and_version(tmp_path):
    db=fresh(tmp_path); con=db.connect(); v=con.execute("SELECT value FROM company_settings WHERE key='jarvis_version'").fetchone()['value']; tables={r['name'] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}; con.close(); assert v=='80.0.0'; assert {'policy_versions','release_dossiers','document_validations','risk_budgets','governance_v2_runs'}<=tables

def test_policy_snapshot_keeps_research_only_hard_rule(tmp_path):
    fresh(tmp_path); from app.governance_v2 import policy_snapshot; r=policy_snapshot(); assert r['policy']['research_only'] is True and r['policy']['no_human_dosing'] is True and 'inventory_release' in r['policy']['never_auto']

def test_release_dossier_blocks_incomplete_evidence(tmp_path):
    db=fresh(tmp_path); con=db.connect(); con.execute("INSERT INTO products(category,name,sku) VALUES ('Research','Dossier Product','DS80')"); pid=con.execute("SELECT id FROM products WHERE sku='DS80'").fetchone()['id']; con.execute("INSERT INTO lots(product_id,lot_code,received_qty,available_qty,disposition,identity_status,purity_status,coa_status) VALUES (?,?,?,?,?,?,?,?)",(pid,'DS80-L',1,0,'quarantine','passed','passed','passed')); lid=con.execute("SELECT id FROM lots WHERE lot_code='DS80-L'").fetchone()['id']; con.commit(); con.close(); from app.governance_v2 import release_dossier; r=release_dossier(lid); assert r['ready'] is False and r['external_side_effects'] is False

def test_zero_default_risk_budget_never_authorizes_spend(tmp_path):
    fresh(tmp_path); from app.governance_v2 import risk_budget; r=risk_budget('procurement',1); assert r['allowed'] is False and r['requires_owner_approval'] is True

def test_governance_v2_run_side_effect_free(tmp_path):
    fresh(tmp_path); from app.governance_v2 import run; r=run(); assert r['external_side_effects'] is False and 0<=r['score']<=100
