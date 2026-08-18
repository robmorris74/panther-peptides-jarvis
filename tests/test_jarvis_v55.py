import os, importlib, pytest


def fresh(tmp_path):
    os.environ['DATABASE_PATH']=str(tmp_path/'operator.db')
    os.environ['JARVIS_CONFIG_PATH']=str(tmp_path/'jarvis.env')
    os.environ['JARVIS_BACKUP_DIR']=str(tmp_path/'backups')
    import app.db as db
    importlib.reload(db)
    db.init_db(); db.init_jarvis_schema(); db.init_v35_schema(); db.init_v40_schema(); db.init_v45_schema(); db.init_v50_schema(); db.init_v55_schema()
    return db


def test_v55_schema_and_version(tmp_path):
    db=fresh(tmp_path); con=db.connect()
    v=con.execute("SELECT value FROM company_settings WHERE key='jarvis_version'").fetchone()['value']
    tables={r['name'] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    con.close()
    assert v=='55.0.0'
    assert {'observability_snapshots','integrity_scans','automation_handoffs','decision_quality_snapshots','orchestrator_runs'} <= tables


def test_integrity_scan_detects_unverified_release(tmp_path):
    db=fresh(tmp_path)
    from app.data_integrity import scan
    assert scan()['passed'] is True
    con=db.connect(); con.execute("INSERT INTO products(category,name,sku) VALUES ('Test','Bad Release','BAD55')"); pid=con.execute("SELECT id FROM products WHERE sku='BAD55'").fetchone()['id']; con.execute("INSERT INTO lots(product_id,lot_code,received_qty,available_qty,disposition,coa_status,identity_status,purity_status) VALUES (?,?,?,?,?,?,?,?)",(pid,'BAD55-L',1,1,'released','missing','pending','pending')); con.commit(); con.close()
    r=scan(); assert r['passed'] is False and r['checks']['release_controls']['ok'] is False


def test_high_risk_handoff_cannot_authorize_without_owner_approval(tmp_path):
    db=fresh(tmp_path)
    from app.automation_handoff import create,complete
    h=create('release_lot','Lot X',{'lot_id':1})
    assert h['execution_class']=='approval' and h['approval_id']
    with pytest.raises(ValueError): complete(h['handoff_id'])
    con=db.connect(); con.execute("UPDATE approvals SET status='approved',decided_at=CURRENT_TIMESTAMP WHERE id=?",(h['approval_id'],)); con.commit(); con.close()
    assert complete(h['handoff_id'])['status']=='authorized'


def test_decision_quality_is_persisted_and_side_effect_free(tmp_path):
    db=fresh(tmp_path)
    from app.decision_quality import snapshot,history
    con=db.connect(); con.execute("INSERT INTO decision_journal(kind,subject,recommendation,outcome,decided_at) VALUES ('ops','A','do A','accepted',CURRENT_TIMESTAMP)"); con.execute("INSERT INTO decision_journal(kind,subject,recommendation,outcome,corrected_action,decided_at) VALUES ('ops','B','do B','corrected','do C',CURRENT_TIMESTAMP)"); con.commit(); con.close()
    r=snapshot(); assert r['decided']==2 and r['external_side_effects'] is False and 0 <= r['score'] <= 100
    assert history(1)[0]['id']==r['snapshot_id']


def test_orchestrator_never_claims_external_side_effects(tmp_path):
    fresh(tmp_path)
    from app.production_orchestrator import run,recent
    r=run(0)
    assert r['external_side_effects'] is False
    assert r['integrity_passed'] is True
    assert recent(1)[0]['external_side_effects']==0
