import os, importlib

def fresh(tmp_path):
    os.environ['DATABASE_PATH']=str(tmp_path/'operator.db'); os.environ['JARVIS_CONFIG_PATH']=str(tmp_path/'jarvis.env'); os.environ['JARVIS_BACKUP_DIR']=str(tmp_path/'backups')
    import app.db as db; importlib.reload(db); db.init_db(); db.init_jarvis_schema(); db.init_v35_schema(); db.init_v40_schema(); db.init_v45_schema(); db.init_v50_schema(); db.init_v55_schema(); db.init_v60_schema(); db.init_v65_schema(); db.init_v70_schema(); db.init_v75_schema(); return db

def test_v75_schema_and_version(tmp_path):
    db=fresh(tmp_path); con=db.connect(); v=con.execute("SELECT value FROM company_settings WHERE key='jarvis_version'").fetchone()['value']; tables={r['name'] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}; con.close(); assert v=='75.0.0'; assert {'inventory_reservations','lot_expiry_reviews','support_sla_checks','supplier_review_schedule','service_assurance_runs'}<=tables

def test_reservation_requires_released_inventory(tmp_path):
    db=fresh(tmp_path); con=db.connect(); con.execute("INSERT INTO products(category,name,sku) VALUES ('Research','Reserve Product','RV75')"); pid=con.execute("SELECT id FROM products WHERE sku='RV75'").fetchone()['id']; con.execute("INSERT INTO lots(product_id,lot_code,received_qty,available_qty,disposition) VALUES (?,?,?,?,?)",(pid,'RV75-L',10,10,'quarantine')); lid=con.execute("SELECT id FROM lots WHERE lot_code='RV75-L'").fetchone()['id']; con.commit(); con.close(); from app.service_assurance import reserve_inventory
    try: reserve_inventory(pid,1,'test',lid)
    except ValueError: pass
    else: raise AssertionError('quarantined stock must not be reservable')

def test_expiry_scan_flags_expired_lot(tmp_path):
    db=fresh(tmp_path); con=db.connect(); con.execute("INSERT INTO products(category,name,sku) VALUES ('Research','Expiry Product','EX75')"); pid=con.execute("SELECT id FROM products WHERE sku='EX75'").fetchone()['id']; con.execute("INSERT INTO lots(product_id,lot_code,received_qty,available_qty,disposition,expiry_date) VALUES (?,?,?,?,?,?)",(pid,'EX75-L',1,0,'quarantine','2020-01-01')); con.commit(); con.close(); from app.service_assurance import lot_expiry_scan; r=lot_expiry_scan(); assert any(i['status']=='expired' for i in r['items']) and r['external_side_effects'] is False

def test_support_sla_is_side_effect_free(tmp_path):
    db=fresh(tmp_path); con=db.connect(); con.execute("INSERT INTO support_tickets(subject,body,created_at) VALUES ('old','x',datetime('now','-2 days'))"); con.commit(); con.close(); from app.service_assurance import support_sla_scan; r=support_sla_scan(24); assert r['breached']==1 and r['external_side_effects'] is False

def test_service_assurance_run_persists_result(tmp_path):
    db=fresh(tmp_path); from app.service_assurance import run; r=run(); assert 0<=r['score']<=100 and r['external_side_effects'] is False; con=db.connect(); assert con.execute('SELECT COUNT(*) c FROM service_assurance_runs').fetchone()['c']==1; con.close()
