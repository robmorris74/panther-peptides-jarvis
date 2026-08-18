from app.db import init_db, connect
from app.command_center import command_center
from app.pwa import MANIFEST_JSON, SERVICE_WORKER


def test_command_center_ranks_quarantine_as_owner_priority():
    init_db()
    con=connect()
    pid=con.execute("INSERT INTO products(category,name,sku,status,qty_on_hand) VALUES ('Test','Test Research Material','TST1','hold',10)").lastrowid
    con.execute("INSERT INTO lots(product_id,lot_code,received_qty,available_qty,disposition) VALUES (?,?,?,?,?)",(pid,'UNKNOWN',10,0,'quarantine'))
    con.commit(); con.close()
    c = command_center()
    assert c['summary']['total_items'] >= 1
    assert any('quarantined' in x['title'].lower() for x in c['owner_queue'])
    assert c['top_priority']['priority'] in {'critical','high','normal','low'}


def test_command_center_pending_high_risk_approval_is_owner_required():
    init_db(); con=connect()
    cur=con.execute("INSERT INTO approvals(kind,subject,payload,risk) VALUES ('purchase_shipping_label','Buy label','{}','high')")
    aid=cur.lastrowid; con.commit(); con.close()
    c=command_center()
    hit=[x for x in c['owner_queue'] if f'#{aid}' in x['title']]
    assert hit and hit[0]['owner_required'] is True and hit[0]['priority']=='critical'


def test_pwa_assets_exist():
    assert 'Panther Peptides' in MANIFEST_JSON
    assert 'fetch' in SERVICE_WORKER
