import os
import pytest
from pathlib import Path

@pytest.fixture()
def fresh(tmp_path,monkeypatch):
    db=tmp_path/'v8.db'; monkeypatch.setenv('DATABASE_PATH',str(db))
    import app.db as dbm; dbm.DB_PATH=str(db); dbm.init_db(); dbm.init_jarvis_schema()
    return dbm

def test_v8_schema_and_version(fresh):
    con=fresh.connect()
    v=con.execute("SELECT value FROM company_settings WHERE key='jarvis_version'").fetchone()['value']
    cols={r['name'] for r in con.execute('PRAGMA table_info(shipment_requests)').fetchall()}
    con.close()
    assert tuple(map(int,v.split('.'))) >= (8,0,0)
    assert {'external_shipment_id','external_rate_id'} <= cols

def test_pending_approval_notification_dedupes(fresh):
    con=fresh.connect(); con.execute("INSERT INTO approvals(kind,subject,payload,risk) VALUES ('test','Approve test','{}','high')"); con.commit(); con.close()
    from app.notifications import notify_pending_approvals,list_notifications
    notify_pending_approvals(False); notify_pending_approvals(False)
    rows=list_notifications()
    assert len([x for x in rows if x['kind']=='approval_required'])==1

def test_easypost_not_configured(fresh,monkeypatch):
    monkeypatch.delenv('EASYPOST_API_KEY',raising=False)
    from app.easypost import configured
    assert configured() is False

def test_label_purchase_requires_approval(fresh,monkeypatch):
    con=fresh.connect()
    con.execute("INSERT INTO products(category,name,sku) VALUES ('x','Test Product','T1')")
    pid=con.execute("SELECT id FROM products WHERE sku='T1'").fetchone()['id']
    con.execute("INSERT INTO orders(external_id,status) VALUES ('O1','paid')"); oid=con.execute("SELECT id FROM orders WHERE external_id='O1'").fetchone()['id']
    con.execute("INSERT INTO fulfillment_tasks(order_id,status) VALUES (?,'queued')",(oid,)); tid=con.execute('SELECT last_insert_rowid() id').fetchone()['id']
    con.execute("INSERT INTO shipment_requests(fulfillment_task_id,status,weight_oz,external_shipment_id) VALUES (?,'rated',8,'shp_test')",(tid,)); sid=con.execute('SELECT last_insert_rowid() id').fetchone()['id']
    con.commit(); con.close()
    from app.easypost import buy_approved_label
    with pytest.raises(ValueError,match='approval'):
        buy_approved_label(sid,'rate_test')

def test_heartbeat_creates_approval_notification(fresh):
    con=fresh.connect(); con.execute("INSERT INTO approvals(kind,subject,payload,risk) VALUES ('x','Owner decision','{}','medium')"); con.commit(); con.close()
    from app.heartbeat import run_heartbeat
    run_heartbeat()
    con=fresh.connect(); n=con.execute("SELECT COUNT(*) n FROM notification_events WHERE kind='approval_required'").fetchone()['n']; con.close()
    assert n==1
