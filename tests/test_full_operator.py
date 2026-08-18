import os,tempfile
fd,path=tempfile.mkstemp(suffix='.db'); os.close(fd)
os.environ['DATABASE_PATH']=path
from app.db import init_db,connect
from app.operations import receive_lot,mark_test_status,release_lot
from app.scoring import refresh_scores
from app.storefront import build_draft,request_publish,mark_published
from app.fulfillment import ingest_order,mark_packed,mark_shipped
from app.support import create_ticket
from app.suppliers import upsert_supplier,request_supplier_verification,verify_supplier

def approve(aid):
    con=connect(); con.execute('UPDATE approvals SET status="approved" WHERE id=?',(aid,)); con.commit(); con.close()

def seed(name='Example Peptide'):
    init_db(); con=connect(); con.execute('INSERT INTO products(category,name,source_text,supplier_hint,unit_cost,list_price) VALUES (?,?,?,?,?,?)',('Analytical',name,'reference material','Example Supplier',10,40)); con.commit(); i=con.execute('SELECT id FROM products WHERE name=?',(name,)).fetchone()['id']; con.close(); return i

def test_end_to_end_controlled_lifecycle():
    pid=seed()
    sid=upsert_supplier('Example Supplier'); aid=request_supplier_verification(sid); approve(aid); verify_supplier(sid,aid)
    lot=receive_lot(pid,'FULL-LOT-001',10,'Example Supplier',10,'F1'); mark_test_status(lot,'passed','passed','passed')
    con=connect(); cur=con.execute('INSERT INTO approvals(kind,subject,payload,risk,status) VALUES ("lot_release",?,"ok","high","approved")',(f'lot:{lot}',)); ra=cur.lastrowid; con.commit(); con.close(); release_lot(lot,ra)
    refresh_scores(); d=build_draft(pid,40); assert d['compliance_status']=='passed'
    pa=request_publish(pid); approve(pa); mark_published(pid,pa,'test-product')
    oid=ingest_order('FULL-ORDER-1','researcher@example.org',[{'product_id':pid,'qty':2,'unit_price':40}]); assert oid>0
    con=connect(); task=con.execute('SELECT id FROM fulfillment_tasks WHERE order_id=?',(oid,)).fetchone()['id']; qty=con.execute('SELECT qty_on_hand FROM products WHERE id=?',(pid,)).fetchone()['qty_on_hand']; con.close(); assert qty==8
    mark_packed(task); mark_shipped(task,'UPS','1ZTEST')
    con=connect(); status=con.execute('SELECT status FROM orders WHERE id=?',(oid,)).fetchone()['status']; con.close(); assert status=='shipped'

def test_high_risk_support_is_not_answered_with_usage_instructions():
    seed('Example Peptide 2'); tid=create_ticket('x@example.org','How do I use it?','What dose should I inject for weight loss?')
    con=connect(); t=con.execute('SELECT * FROM support_tickets WHERE id=?',(tid,)).fetchone(); con.close()
    assert t['risk']=='high'; assert 'cannot provide' in t['draft_reply']; assert 'dosing' in t['draft_reply']

def test_shipping_requires_pack():
    pid=seed('Pack First Peptide')
    con=connect(); con.execute('UPDATE products SET status="active",qty_on_hand=2,list_price=10 WHERE id=?',(pid,)); con.execute('INSERT INTO lots(product_id,lot_code,received_qty,available_qty,disposition,coa_status,identity_status,purity_status) VALUES (?,"PACK-LOT",2,2,"released","passed","passed","passed")',(pid,)); con.commit(); con.close()
    oid=ingest_order('PACK-ORDER','r@example.org',[{'product_id':pid,'qty':1,'unit_price':10}])
    con=connect(); tid=con.execute('SELECT id FROM fulfillment_tasks WHERE order_id=?',(oid,)).fetchone()['id']; con.close()
    import pytest
    with pytest.raises(ValueError): mark_shipped(tid,'UPS','X')


def test_procurement_budget_and_approval():
    from app.procurement import create_purchase_order,approve_purchase_order
    pid=seed('Budget Peptide'); sid=upsert_supplier('Budget Supplier'); a=request_supplier_verification(sid); approve(a); verify_supplier(sid,a)
    po=create_purchase_order(sid,[{'product_id':pid,'qty':10,'unit_cost':20}]); assert po['total']==200
    import pytest
    with pytest.raises(ValueError): approve_purchase_order(po['purchase_order_id'],po['approval_id'])
    approve(po['approval_id']); approve_purchase_order(po['purchase_order_id'],po['approval_id'])
    with pytest.raises(ValueError): create_purchase_order(sid,[{'product_id':pid,'qty':200,'unit_cost':20}])


def test_economics_calculation():
    from app.economics import set_economics
    pid=seed('Margin Peptide'); out=set_economics(pid,10,40,2,1,.03,.30,0)
    assert out['contribution']>20 and out['contribution_margin_percent']>50


def test_coa_metadata_record():
    from app.quality import add_coa_record
    pid=seed('COA Peptide'); lot=receive_lot(pid,'COA-LOT',5)
    i=add_coa_record(lot,'coa.pdf',lab_name='Independent Lab',purity_percent=99.1,status='passed')
    assert i>0
