import os, importlib


def fresh(tmp_path):
    os.environ['DATABASE_PATH']=str(tmp_path/'operator.db')
    os.environ['JARVIS_CONFIG_PATH']=str(tmp_path/'jarvis.env')
    import app.db as db
    importlib.reload(db)
    db.init_db(); db.init_jarvis_schema(); db.init_v35_schema(); db.init_v40_schema(); db.init_v45_schema()
    from app.objectives import seed_defaults
    seed_defaults()
    return db


def test_v45_schema_and_version(tmp_path):
    db=fresh(tmp_path); con=db.connect()
    v=con.execute("SELECT value FROM company_settings WHERE key='jarvis_version'").fetchone()['value']
    tables={r['name'] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    con.close()
    assert v=='45.0.0'
    assert {'anomaly_events','financial_snapshots','strategic_plans','strategic_plan_items','compliance_audits','control_attestations'} <= tables


def test_anomaly_scan_flags_bad_released_lot_without_external_effect(tmp_path):
    db=fresh(tmp_path); con=db.connect()
    con.execute("INSERT INTO products(category,name,sku) VALUES ('Test','Control Product','CTRL')")
    pid=con.execute("SELECT id FROM products WHERE sku='CTRL'").fetchone()['id']
    con.execute("INSERT INTO lots(product_id,lot_code,received_qty,available_qty,disposition,coa_status,identity_status,purity_status) VALUES (?,?,?,?,?,?,?,?)",
                (pid,'BAD-LOT',1,1,'released','missing','pending','pending'))
    con.commit(); con.close()
    from app.anomaly_detection import scan
    r=scan(); assert r['critical']>=1 and r['side_effects']=='internal-only'
    assert any(x['kind']=='release_control_breach' for x in r['items'])


def test_financial_snapshot_estimates_margin_and_never_moves_money(tmp_path):
    db=fresh(tmp_path); con=db.connect()
    con.execute("INSERT INTO products(category,name,sku,unit_cost) VALUES ('Test','Finance Product','FIN',10)")
    pid=con.execute("SELECT id FROM products WHERE sku='FIN'").fetchone()['id']
    con.execute("INSERT INTO lots(product_id,lot_code,received_qty,available_qty,unit_cost,disposition,coa_status,identity_status,purity_status) VALUES (?,?,?,?,?,'released','passed','passed','passed')",(pid,'FIN-LOT',10,8,10))
    lot=con.execute("SELECT id FROM lots WHERE lot_code='FIN-LOT'").fetchone()['id']
    con.execute("INSERT INTO orders(external_id,status,subtotal,shipping,tax) VALUES ('FIN-O','paid',100,0,0)")
    oid=con.execute("SELECT id FROM orders WHERE external_id='FIN-O'").fetchone()['id']
    con.execute("INSERT INTO order_items(order_id,product_id,qty,unit_price,lot_id) VALUES (?,?,?,?,?)",(oid,pid,2,50,lot))
    con.commit(); con.close()
    from app.financial_controls import snapshot
    r=snapshot(); assert r['revenue']==100 and r['estimated_cogs']==20 and round(r['gross_margin'],2)==0.80


def test_compliance_audit_blocks_nonpublished_bad_copy(tmp_path):
    db=fresh(tmp_path); con=db.connect()
    con.execute("INSERT INTO products(category,name,sku) VALUES ('Test','Copy Product','COPY')")
    pid=con.execute("SELECT id FROM products WHERE sku='COPY'").fetchone()['id']
    con.execute("INSERT INTO storefront_drafts(product_id,title,handle,body,sku,compliance_status) VALUES (?,?,?,?,?,'pending')",(pid,'Copy Product','copy-product','Designed for weight loss and injection.','COPY'))
    con.commit(); con.close()
    from app.compliance_governance import audit_storefront
    r=audit_storefront(); assert r['passed'] is False and r['issue_count']==1
    con=db.connect(); status=con.execute('SELECT compliance_status FROM storefront_drafts WHERE product_id=?',(pid,)).fetchone()['compliance_status']; con.close()
    assert status=='blocked'


def test_strategic_plan_is_advisory_only(tmp_path):
    fresh(tmp_path)
    from app.strategic_planner import build
    r=build(); assert r['external_side_effects'] is False
    assert all(x['execution_class'] in {'owner','recommend'} for x in r['items'])


def test_v45_work_queue_intelligence_jobs_are_safe(tmp_path):
    fresh(tmp_path)
    from app.work_queue import enqueue,process_one
    for kind in ('anomaly_scan','financial_snapshot','compliance_audit','strategic_plan','intelligence_cycle'):
        x=enqueue(kind,{},priority=20,dedupe_key='v45-'+kind); assert x['status']=='queued'
        out=process_one('v45-test'); assert out['status']=='completed'
