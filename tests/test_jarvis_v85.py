import os, importlib

def fresh(tmp_path):
    os.environ['DATABASE_PATH']=str(tmp_path/'operator.db'); os.environ['JARVIS_CONFIG_PATH']=str(tmp_path/'jarvis.env'); os.environ['JARVIS_BACKUP_DIR']=str(tmp_path/'backups')
    import app.db as db; importlib.reload(db); db.init_db(); db.init_jarvis_schema(); db.init_v35_schema(); db.init_v40_schema(); db.init_v45_schema(); db.init_v50_schema(); db.init_v55_schema(); db.init_v60_schema(); db.init_v65_schema(); db.init_v70_schema(); db.init_v75_schema(); db.init_v80_schema(); db.init_v85_schema(); return db

def test_v85_schema_and_version(tmp_path):
    db=fresh(tmp_path); con=db.connect(); v=con.execute("SELECT value FROM company_settings WHERE key='jarvis_version'").fetchone()['value']; tables={r['name'] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}; con.close(); assert v=='85.0.0'; assert {'demand_forecasts','inventory_aging_snapshots','cash_runway_snapshots','sku_concentration_snapshots','planning_v85_runs'}<=tables

def test_forecast_uses_order_history_without_side_effects(tmp_path):
    db=fresh(tmp_path); con=db.connect(); con.execute("INSERT INTO products(category,name,sku) VALUES ('Research','Forecast Product','FC85')"); pid=con.execute("SELECT id FROM products WHERE sku='FC85'").fetchone()['id']; con.execute("INSERT INTO orders(external_id,status,subtotal) VALUES ('O85','paid',100)"); oid=con.execute("SELECT id FROM orders WHERE external_id='O85'").fetchone()['id']; con.execute('INSERT INTO order_items(order_id,product_id,qty,unit_price) VALUES (?,?,?,?)',(oid,pid,9,10)); con.commit(); con.close(); from app.business_planning import demand_forecast; r=demand_forecast(30); item=next(x for x in r['items'] if x['sku']=='FC85'); assert item['predicted_units']>0 and r['external_side_effects'] is False

def test_inventory_aging_is_observational(tmp_path):
    db=fresh(tmp_path); con=db.connect(); con.execute("INSERT INTO products(category,name,sku) VALUES ('Research','Aging Product','AG85')"); pid=con.execute("SELECT id FROM products WHERE sku='AG85'").fetchone()['id']; con.execute("INSERT INTO lots(product_id,lot_code,received_qty,available_qty,disposition,received_at) VALUES (?,?,?,?,?,datetime('now','-400 days'))",(pid,'AG85-L',1,0,'quarantine')); con.commit(); con.close(); from app.business_planning import inventory_aging; r=inventory_aging(); assert r['high_risk']>=1 and r['external_side_effects'] is False

def test_cash_runway_snapshot_does_not_move_money(tmp_path):
    db=fresh(tmp_path); con=db.connect(); con.execute("INSERT INTO ledger(entry_type,category,amount) VALUES ('expense','software',-30)"); con.commit(); before=con.execute('SELECT SUM(amount) x FROM ledger').fetchone()['x']; con.close(); from app.business_planning import cash_runway; r=cash_runway(); con=db.connect(); after=con.execute('SELECT SUM(amount) x FROM ledger').fetchone()['x']; con.close(); assert before==after and r['external_side_effects'] is False

def test_planning_run_side_effect_free(tmp_path):
    fresh(tmp_path); from app.business_planning import run; r=run(); assert r['status']=='ok' and r['external_side_effects'] is False
