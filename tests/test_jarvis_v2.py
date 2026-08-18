import os
os.environ.setdefault('DATABASE_PATH','./data/test_jarvis.db')
from app.db import init_db,init_jarvis_schema,connect
from app.seed_panther import seed
from app.brand import BRAND_NAME,AGENT_NAME,RESEARCH_ONLY

def reset():
    p=os.environ['DATABASE_PATH']
    try: os.remove(p)
    except FileNotFoundError: pass
    init_db();init_jarvis_schema();seed()

def test_brand_identity():
    assert BRAND_NAME=='Panther Peptides'
    assert AGENT_NAME=='Jarvis'
    assert 'RESEARCH USE ONLY' in RESEARCH_ONLY

def test_starting_inventory_is_90_and_quarantined():
    reset();con=connect()
    qty=con.execute("SELECT SUM(received_qty) q FROM lots WHERE lot_code LIKE 'UNVERIFIED-%-START'").fetchone()['q']
    avail=con.execute("SELECT SUM(available_qty) q FROM lots WHERE lot_code LIKE 'UNVERIFIED-%-START'").fetchone()['q']
    nonq=con.execute("SELECT COUNT(*) n FROM lots WHERE lot_code LIKE 'UNVERIFIED-%-START' AND disposition!='quarantine'").fetchone()['n']
    con.close()
    assert qty==90
    assert avail==0
    assert nonq==0

def test_starting_inventory_cost_setting():
    reset();con=connect();v=con.execute("SELECT value FROM company_settings WHERE key='starting_inventory_cost'").fetchone()['value'];con.close()
    assert v=='855.00'

def test_consequential_autonomy_defaults_to_approval():
    reset();con=connect()
    rows={r['action']:r['mode'] for r in con.execute('SELECT action,mode FROM autonomy_rules').fetchall()};con.close()
    for action in ['publish_product','release_inventory_lot','approve_supplier','place_purchase_order']:
        assert rows[action]=='approval'
