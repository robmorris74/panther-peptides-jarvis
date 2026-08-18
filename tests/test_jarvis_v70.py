import os, importlib

def fresh(tmp_path):
    os.environ['DATABASE_PATH']=str(tmp_path/'operator.db')
    os.environ['JARVIS_CONFIG_PATH']=str(tmp_path/'jarvis.env')
    os.environ['JARVIS_BACKUP_DIR']=str(tmp_path/'backups')
    import app.db as db; importlib.reload(db)
    db.init_db(); db.init_jarvis_schema(); db.init_v35_schema(); db.init_v40_schema(); db.init_v45_schema(); db.init_v50_schema(); db.init_v55_schema(); db.init_v60_schema(); db.init_v65_schema(); db.init_v70_schema()
    return db

def test_v70_schema_and_version(tmp_path):
    db=fresh(tmp_path); con=db.connect(); v=con.execute("SELECT value FROM company_settings WHERE key='jarvis_version'").fetchone()['value']; tables={r['name'] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}; con.close()
    assert v=='70.0.0'
    assert {'supplier_assurance_reviews','evidence_manifests','exception_policies','quarantined_jobs','operational_freezes','guardian_runs'} <= tables

def test_supplier_assurance_holds_unverified_supplier(tmp_path):
    db=fresh(tmp_path); con=db.connect(); con.execute("INSERT INTO suppliers(name,verified) VALUES ('Unknown Labs',0)"); sid=con.execute("SELECT id FROM suppliers WHERE name='Unknown Labs'").fetchone()['id']; con.commit(); con.close()
    from app.supplier_assurance import assess
    r=assess(sid); assert r['status']=='hold' and r['external_side_effects'] is False and r['score']<50

def test_evidence_manifest_requires_provenance_and_hashed_passed_coa(tmp_path):
    db=fresh(tmp_path); con=db.connect(); con.execute("INSERT INTO products(category,name,sku) VALUES ('Research','Manifest Product','MF70')"); pid=con.execute("SELECT id FROM products WHERE sku='MF70'").fetchone()['id']; con.execute("INSERT INTO lots(product_id,lot_code,received_qty,available_qty,disposition,identity_status,purity_status,coa_status) VALUES (?,?,?,?,?,?,?,?)",(pid,'MF70-L',1,0,'quarantine','passed','passed','passed')); lid=con.execute("SELECT id FROM lots WHERE lot_code='MF70-L'").fetchone()['id']; con.commit(); con.close()
    from app.evidence_manifest import build
    assert build(lid)['complete'] is False
    con=db.connect(); con.execute("INSERT INTO evidence_links(entity_type,entity_id,evidence_type,reference_text,verified) VALUES ('lot',?,'supplier_provenance','invoice',1)",(lid,)); con.execute("INSERT INTO coa_documents(lot_id,file_name,sha256,status) VALUES (?,?,?,'passed')",(lid,'coa.pdf','abc123')); con.commit(); con.close()
    assert build(lid)['complete'] is True

def test_job_retry_exhaustion_is_quarantined_not_executed(tmp_path):
    db=fresh(tmp_path); con=db.connect(); con.execute("INSERT INTO internal_work_queue(kind,status,attempt_count,max_attempts,payload) VALUES ('self_test','failed',3,3,'{}')"); con.commit(); con.close()
    from app.job_safety import scan
    r=scan(); assert r['quarantined_count']==1 and r['external_side_effects'] is False
    con=db.connect(); assert con.execute("SELECT status FROM internal_work_queue").fetchone()['status']=='dead'; assert con.execute("SELECT status FROM quarantined_jobs").fetchone()['status']=='quarantined'; con.close()

def test_frozen_scope_requires_exact_confirmation_to_resume(tmp_path):
    fresh(tmp_path)
    from app.recovery_controls import set_freeze,blocked
    set_freeze('outbound',True,'incident'); assert blocked('outbound') is True
    try: set_freeze('outbound',False,'','wrong')
    except ValueError: pass
    else: raise AssertionError('resume should require exact confirmation')
    set_freeze('outbound',False,'','RESUME OUTBOUND'); assert blocked('outbound') is False

def test_guardian_is_side_effect_free(tmp_path):
    fresh(tmp_path)
    from app.production_guardian import run
    r=run(); assert r['external_side_effects'] is False and 0<=r['score']<=100
