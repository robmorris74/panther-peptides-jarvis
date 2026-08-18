from pathlib import Path
import app.db as db
import app.communications as comm
import app.shipping as shipping
import app.shopify_sync as sync


def reset(tmp_path):
    db.DB_PATH=Path(tmp_path)/'operator.db'
    db.init_db(); db.init_jarvis_schema()


def test_inbound_email_becomes_support_ticket(tmp_path):
    reset(tmp_path)
    r=comm.ingest_inbound_email('lab@example.com','COA request','Can you send the certificate?','msg-1')
    assert r['category']=='documentation'
    con=db.connect()
    assert con.execute('SELECT COUNT(*) n FROM email_messages').fetchone()['n']==1
    t=con.execute('SELECT category,risk FROM support_tickets WHERE id=?',(r['ticket_id'],)).fetchone(); con.close()
    assert t['category']=='documentation' and t['risk']=='low'


def test_human_use_support_reply_requires_owner_approval(tmp_path):
    reset(tmp_path)
    r=comm.ingest_inbound_email('x@example.com','How much?','How much should I inject?','msg-2')
    q=comm.queue_support_reply(r['ticket_id'])
    assert q['status']=='awaiting_approval' and q['approval_id']
    con=db.connect(); m=con.execute('SELECT body,status FROM outbound_messages WHERE id=?',(q['outbound_message_id'],)).fetchone(); con.close()
    assert 'cannot provide instructions for human use' in m['body']
    assert m['status']=='awaiting_approval'


def test_shipping_label_purchase_is_approval_gated(tmp_path):
    reset(tmp_path)
    con=db.connect()
    con.execute("INSERT INTO products(id,category,name,status,sku) VALUES (1,'Research','Example','active','EX1')")
    con.execute("INSERT INTO lots(id,product_id,lot_code,received_qty,available_qty,disposition,coa_status,identity_status,purity_status) VALUES (1,1,'L1',5,5,'released','passed','passed','passed')")
    con.commit(); con.close()
    from app.fulfillment import ingest_order
    oid=ingest_order('O1','lab@example.com',[{'product_id':1,'qty':1,'unit_price':10}])
    con=db.connect(); task=con.execute('SELECT id FROM fulfillment_tasks WHERE order_id=?',(oid,)).fetchone()['id']; con.close()
    sr=shipping.prepare_shipment(task,4.0,'small mailer')
    lr=shipping.request_label_purchase(sr['shipment_request_id'],'USPS','Ground Advantage',5.25)
    assert lr['status']=='awaiting_approval' and lr['approval_id']


def test_shopify_sync_imports_mapped_paid_order(tmp_path,monkeypatch):
    reset(tmp_path)
    con=db.connect()
    con.execute("INSERT INTO products(id,category,name,status,sku,list_price) VALUES (1,'Research','Example','active','EX1',25)")
    con.execute("INSERT INTO lots(id,product_id,lot_code,received_qty,available_qty,disposition,coa_status,identity_status,purity_status) VALUES (1,1,'L1',5,5,'released','passed','passed','passed')")
    con.commit(); con.close()
    fake={'orders':{'edges':[{'node':{'id':'gid://shopify/Order/1','name':'#1001','email':'lab@example.com','displayFinancialStatus':'PAID','totalShippingPriceSet':{'shopMoney':{'amount':'4.00'}},'totalTaxSet':{'shopMoney':{'amount':'1.00'}},'shippingAddress':{'name':'Research Lab','address1':'1 Main','city':'Test','provinceCode':'KS','zip':'00000','countryCodeV2':'US'},'lineItems':{'edges':[{'node':{'quantity':2,'sku':'EX1','originalUnitPriceSet':{'shopMoney':{'amount':'25.00'}}}}]}}}]}}
    monkeypatch.setattr(sync,'_graphql',lambda q,v: fake)
    r=sync.sync_recent_paid_orders(5)
    assert len(r['imported'])==1 and not r['blocked']
    con=db.connect(); o=con.execute('SELECT source,status FROM orders').fetchone(); f=con.execute('SELECT shipping_city FROM fulfillment_tasks').fetchone(); con.close()
    assert o['source']=='shopify-sync' and f['shipping_city']=='Test'

def test_high_risk_reply_cannot_be_overridden_with_use_instructions(tmp_path):
    reset(tmp_path)
    r=comm.ingest_inbound_email('x@example.com','Dose','How should I use this?','msg-3')
    q=comm.queue_support_reply(r['ticket_id'],'Take 1 mg daily')
    con=db.connect(); m=con.execute('SELECT body FROM outbound_messages WHERE id=?',(q['outbound_message_id'],)).fetchone(); con.close()
    assert 'Take 1 mg daily' not in m['body']
    assert 'cannot provide instructions for human use' in m['body']
