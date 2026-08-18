import os, importlib


def fresh(tmp_path):
    os.environ['DATABASE_PATH']=str(tmp_path/'operator.db')
    os.environ['JARVIS_CONFIG_PATH']=str(tmp_path/'jarvis.env')
    import app.db as db
    importlib.reload(db)
    db.init_db(); db.init_jarvis_schema(); db.init_v35_schema(); db.init_v40_schema(); db.init_v45_schema(); db.init_v50_schema()
    return db


def test_v50_schema_and_version(tmp_path):
    db=fresh(tmp_path); con=db.connect()
    v=con.execute("SELECT value FROM company_settings WHERE key='jarvis_version'").fetchone()['value']
    tables={r['name'] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    con.close()
    assert v=='50.0.0'
    assert {'execution_receipts','owner_policy_limits','change_control','runtime_attestations','recovery_checkpoints'} <= tables


def test_execution_receipt_hash_chain_detects_tamper(tmp_path):
    db=fresh(tmp_path)
    from app.execution_receipts import record,verify_chain
    record('test','one','completed',{'a':1},{'b':2})
    record('test','two','completed',{'c':3},{'d':4})
    assert verify_chain()['ok'] is True
    con=db.connect(); con.execute("UPDATE execution_receipts SET output_json='{}' WHERE id=1"); con.commit(); con.close()
    result=verify_chain(); assert result['ok'] is False and 1 in result['bad_receipt_ids']


def test_protected_owner_policy_cannot_disable_approval_safety(tmp_path):
    fresh(tmp_path)
    from app.owner_policy import set_limit,list_limits
    import pytest
    with pytest.raises(ValueError): set_limit('require_owner_approval_high_risk','false')
    assert list_limits()['require_owner_approval_high_risk']['value']=='true'


def test_runtime_pause_prevents_processing(tmp_path):
    fresh(tmp_path)
    from app.owner_policy import set_runtime_pause
    from app.runtime_supervisor import run_tick
    set_runtime_pause(True,'maintenance')
    r=run_tick(5); assert r['status']=='paused' and r['side_effects']=='none'


def test_high_impact_change_requires_approved_owner_approval(tmp_path):
    db=fresh(tmp_path)
    from app.change_control import register,apply
    import pytest
    c=register('deployment','move Jarvis host',{'target':'new-host'})
    assert c['status']=='awaiting_approval' and c['owner_approval_id']
    with pytest.raises(ValueError): apply(c['id'])
    con=db.connect(); con.execute("UPDATE approvals SET status='approved',decided_at=CURRENT_TIMESTAMP WHERE id=?",(c['owner_approval_id'],)); con.commit(); con.close()
    assert apply(c['id'])['status']=='applied'


def test_runtime_attestation_passes_clean_state_and_detects_bad_release(tmp_path):
    db=fresh(tmp_path)
    from app.runtime_attestation import attest
    clean=attest(); assert clean['passed'] is True and clean['score']==100 and clean['side_effects']=='internal-only'
    con=db.connect(); con.execute("INSERT INTO products(category,name,sku) VALUES ('Test','Unsafe Product','UNSAFE')"); pid=con.execute("SELECT id FROM products WHERE sku='UNSAFE'").fetchone()['id']; con.execute("INSERT INTO lots(product_id,lot_code,received_qty,available_qty,disposition,coa_status,identity_status,purity_status) VALUES (?,?,?,?,?,?,?,?)",(pid,'UNSAFE-L',1,1,'released','missing','pending','pending')); con.commit(); con.close()
    bad=attest(); assert bad['passed'] is False and bad['checks']['no_unverified_released_lots'] is False


def test_recovery_checkpoint_is_consistent_copy(tmp_path):
    db=fresh(tmp_path)
    from app.recovery_checkpoint import create,list_checkpoints
    r=create('before-change','test checkpoint')
    from pathlib import Path
    assert Path(r['path']).exists() and len(r['sha256'])==64
    assert list_checkpoints()[0]['label']=='before-change'
