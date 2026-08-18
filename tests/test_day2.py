import os, tempfile
fd, path = tempfile.mkstemp(suffix='.db'); os.close(fd)
os.environ['DATABASE_PATH']=path

from app.db import init_db, connect
from app.operations import receive_lot, release_lot, mark_test_status
from app.scoring import refresh_scores


def seed(name):
    init_db(); con=connect()
    con.execute('INSERT INTO products(category,name,source_text,supplier_hint,status) VALUES (?,?,?,?,?)',('Research',name,'laboratory receptor-binding research','Lab Vendor','review'))
    con.commit(); pid=con.execute('SELECT id FROM products WHERE name=?',(name,)).fetchone()['id']; con.close(); return pid


def test_received_lot_is_quarantined():
    pid=seed('Test Peptide A'); lid=receive_lot(pid,'LOT-001',5,'Lab Vendor',10.0,'Q-1')
    con=connect(); r=con.execute('SELECT disposition,available_qty FROM lots WHERE id=?',(lid,)).fetchone(); con.close()
    assert r['disposition']=='quarantine' and r['available_qty']==0


def test_release_requires_passed_tests():
    pid=seed('Test Peptide B'); lid=receive_lot(pid,'LOT-002',5)
    try:
        release_lot(lid,999); assert False
    except ValueError: pass
    mark_test_status(lid,'passed','passed','passed')
    con=connect(); cur=con.execute('INSERT INTO approvals(kind,subject,payload,risk,status) VALUES (?,?,?,?,?)',('lot_release',f'lot:{lid}','test release','high','approved')); aid=cur.lastrowid; con.commit(); con.close()
    release_lot(lid,aid)
    con=connect(); r=con.execute('SELECT disposition,available_qty FROM lots WHERE id=?',(lid,)).fetchone(); con.close()
    assert r['disposition']=='released' and r['available_qty']==5


def test_unverified_supplier_stays_hold():
    pid=seed('Test Peptide C'); refresh_scores(); con=connect(); r=con.execute('SELECT launch_status FROM products WHERE id=?',(pid,)).fetchone(); con.close()
    assert r['launch_status']=='hold'
