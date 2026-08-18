import os, importlib

def fresh(tmp_path):
    os.environ['DATABASE_PATH']=str(tmp_path/'operator.db')
    os.environ['JARVIS_CONFIG_PATH']=str(tmp_path/'jarvis.env')
    os.environ['JARVIS_BACKUP_DIR']=str(tmp_path/'backups')
    import app.db as db; importlib.reload(db)
    db.init_db(); db.init_jarvis_schema(); db.init_v35_schema(); db.init_v40_schema(); db.init_v45_schema(); db.init_v50_schema(); db.init_v55_schema(); db.init_v60_schema(); db.init_v65_schema()
    return db

def test_v65_schema_and_version(tmp_path):
    db=fresh(tmp_path); con=db.connect(); v=con.execute("SELECT value FROM company_settings WHERE key='jarvis_version'").fetchone()['value']; tables={r['name'] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}; con.close()
    assert v=='65.0.0'; assert {'worker_leases','inventory_cycle_counts','evidence_links','owner_escalations','production_sentinel_runs'} <= tables

def test_watchdog_only_recovers_internal_work(tmp_path):
    db=fresh(tmp_path); con=db.connect(); con.execute("INSERT INTO internal_work_queue(kind,status,lease_owner,lease_expires_at) VALUES ('self_test','running','dead-worker',datetime('now','-1 minute'))"); con.commit(); con.close()
    from app.worker_watchdog import scan; r=scan(); assert r['external_side_effects'] is False and len(r['recovered_internal_work'])==1
    con=db.connect(); assert con.execute('SELECT status FROM internal_work_queue').fetchone()['status']=='queued'; con.close()

def test_cycle_count_variance_creates_exception_without_changing_inventory(tmp_path):
    db=fresh(tmp_path); con=db.connect(); con.execute("INSERT INTO products(category,name,sku) VALUES ('Research','Count Product','CC65')"); pid=con.execute("SELECT id FROM products WHERE sku='CC65'").fetchone()['id']; con.execute("INSERT INTO lots(product_id,lot_code,received_qty,available_qty,disposition) VALUES (?,?,?,?,?)",(pid,'CC65-L',10,0,'quarantine')); lid=con.execute("SELECT id FROM lots WHERE lot_code='CC65-L'").fetchone()['id']; con.commit(); con.close()
    from app.cycle_counts import record; r=record(lid,8); assert r['variance']==-2 and r['external_side_effects'] is False
    con=db.connect(); lot=con.execute('SELECT received_qty,available_qty FROM lots WHERE id=?',(lid,)).fetchone(); ex=con.execute("SELECT kind FROM operational_exceptions WHERE kind='inventory_variance'").fetchone(); con.close(); assert tuple(lot)==(10,0) and ex

def test_evidence_status_requires_provenance_and_passed_coa(tmp_path):
    db=fresh(tmp_path); con=db.connect(); con.execute("INSERT INTO products(category,name,sku) VALUES ('Research','Evidence Product','EV65')"); pid=con.execute("SELECT id FROM products WHERE sku='EV65'").fetchone()['id']; con.execute("INSERT INTO lots(product_id,lot_code,received_qty,available_qty,disposition,coa_status,identity_status,purity_status) VALUES (?,?,?,?,?,?,?,?)",(pid,'EV65-L',1,1,'released','passed','passed','passed')); lid=con.execute("SELECT id FROM lots WHERE lot_code='EV65-L'").fetchone()['id']; con.commit(); con.close()
    from app.evidence_integrity import lot_evidence_status,link; assert lot_evidence_status(lid)['complete'] is False
    link('lot',lid,'supplier_provenance',reference_text='supplier invoice',verified=True); assert lot_evidence_status(lid)['complete'] is True

def test_sentinel_is_side_effect_free_and_persists_run(tmp_path):
    db=fresh(tmp_path)
    from app.production_sentinel import run; r=run(); assert r['external_side_effects'] is False
    con=db.connect(); assert con.execute('SELECT COUNT(*) n FROM production_sentinel_runs').fetchone()['n']==1; con.close()
