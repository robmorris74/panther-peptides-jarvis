import os, importlib


def fresh(tmp_path):
    os.environ['DATABASE_PATH']=str(tmp_path/'operator.db')
    os.environ['JARVIS_CONFIG_PATH']=str(tmp_path/'jarvis.env')
    os.environ['JARVIS_BACKUP_DIR']=str(tmp_path/'backups')
    import app.db as db
    importlib.reload(db)
    db.init_db(); db.init_jarvis_schema(); db.init_v35_schema(); db.init_v40_schema(); db.init_v45_schema(); db.init_v50_schema(); db.init_v55_schema(); db.init_v60_schema()
    return db


def test_v60_schema_and_version(tmp_path):
    db=fresh(tmp_path); con=db.connect()
    v=con.execute("SELECT value FROM company_settings WHERE key='jarvis_version'").fetchone()['value']
    tables={r['name'] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}; con.close()
    assert v=='60.0.0'
    assert {'action_preflights','custody_events','reconciliation_runs','operational_exceptions','control_plane_runs'} <= tables


def test_preflight_blocks_unverified_lot_release(tmp_path):
    db=fresh(tmp_path); con=db.connect()
    con.execute("INSERT INTO products(category,name,sku) VALUES ('Research','Test Product','T60')"); pid=con.execute("SELECT id FROM products WHERE sku='T60'").fetchone()['id']
    con.execute("INSERT INTO lots(product_id,lot_code,received_qty,available_qty,disposition,coa_status,identity_status,purity_status) VALUES (?,?,?,?,?,?,?,?)",(pid,'T60-L',1,0,'quarantine','missing','pending','pending')); lid=con.execute("SELECT id FROM lots WHERE lot_code='T60-L'").fetchone()['id']; con.commit(); con.close()
    from app.action_preflight import preflight
    r=preflight('release_inventory_lot','Test lot',{'lot_id':lid})
    assert r['allowed_to_execute'] is False and r['requires_owner_approval'] is True and len(r['issues'])>=3 and r['external_side_effects'] is False


def test_custody_timeline_requires_received_event(tmp_path):
    db=fresh(tmp_path); con=db.connect()
    con.execute("INSERT INTO products(category,name,sku) VALUES ('Research','Custody Product','C60')"); pid=con.execute("SELECT id FROM products WHERE sku='C60'").fetchone()['id']
    con.execute("INSERT INTO lots(product_id,lot_code,supplier_name,received_qty,available_qty,disposition) VALUES (?,?,?,?,?,?)",(pid,'C60-L','Supplier',2,0,'quarantine')); lid=con.execute("SELECT id FROM lots WHERE lot_code='C60-L'").fetchone()['id']; con.commit(); con.close()
    from app.custody import custody_status,record
    assert custody_status(lid)['provenance_complete'] is False
    record(lid,'received','owner','freezer','initial receipt')
    assert custody_status(lid)['provenance_complete'] is True


def test_reconciliation_detects_sales_ledger_delta(tmp_path):
    db=fresh(tmp_path); con=db.connect()
    con.execute("INSERT INTO orders(external_id,status,subtotal,shipping,tax) VALUES ('O60','paid',100,0,0)"); con.commit(); con.close()
    from app.reconciliation import run
    r=run(); assert r['passed'] is False and r['checks']['sales_to_ledger']['delta']==100.0 and r['external_side_effects'] is False


def test_control_plane_never_claims_external_side_effects(tmp_path):
    fresh(tmp_path)
    from app.control_plane import cycle
    r=cycle(0)
    assert r['external_side_effects'] is False
    assert 'attestation_passed' in r and 'reconciliation_passed' in r
