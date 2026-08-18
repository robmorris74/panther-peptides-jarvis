import os
from pathlib import Path
os.environ['DATABASE_PATH']='./data/test_jarvis_v3.db'
from app.db import init_db,init_jarvis_schema,connect
from app.seed_panther import seed
from app.setup_service import save_first_run,setup_summary
from app.jarvis import chat
from app.documents import register_document,search_documents

def reset():
    p=Path(os.environ['DATABASE_PATH'])
    try:p.unlink()
    except FileNotFoundError:pass
    init_db();init_jarvis_schema();seed()

def test_first_run_creates_owner_tasks_without_releasing_inventory():
    reset();save_first_run(owner_name='Owner',domain='pantherpeptides.test')
    con=connect(); tasks=con.execute("SELECT COUNT(*) n FROM jarvis_tasks WHERE status='open'").fetchone()['n']; avail=con.execute("SELECT COALESCE(SUM(available_qty),0) n FROM lots WHERE lot_code LIKE 'UNVERIFIED-%-START'").fetchone()['n']; con.close()
    assert tasks>=4
    assert avail==0
    assert setup_summary()['onboarding_complete'] is True

def test_local_jarvis_operates_without_api_key():
    reset();os.environ.pop('OPENAI_API_KEY',None)
    r=chat('what inventory do we have?','test')
    assert r['mode']=='local-control'
    assert 'quarant' in r['reply'].lower()

def test_document_inbox_extracts_and_searches_text():
    reset();r=register_document('pricing.csv',b'SKU,Price\nABC,12.50\n','supplier-pricing')
    assert r['text_chars']>0
    hits=search_documents('ABC Price')
    assert hits and hits[0]['file_name']=='pricing.csv'
