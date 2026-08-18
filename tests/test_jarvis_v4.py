import os
from pathlib import Path
os.environ['DATABASE_PATH']='./data/test_jarvis_v4.db'
from app.db import init_db,init_jarvis_schema,connect
from app.seed_panther import seed
from app.heartbeat import run_heartbeat,heartbeat_status
from app.jarvis_dashboard import JARVIS_HTML

def reset():
    p=Path(os.environ['DATABASE_PATH'])
    try:p.unlink()
    except FileNotFoundError:pass
    init_db();init_jarvis_schema();seed()

def test_heartbeat_scans_without_releasing_inventory():
    reset(); result=run_heartbeat()
    con=connect()
    avail=con.execute("SELECT COALESCE(SUM(available_qty),0) n FROM lots WHERE lot_code LIKE 'UNVERIFIED-%-START'").fetchone()['n']
    task=con.execute("SELECT COUNT(*) n FROM jarvis_tasks WHERE title='Resolve quarantined starting inventory' AND status='open'").fetchone()['n']
    con.close()
    assert result['enabled'] is True
    assert avail==0
    assert task==1

def test_heartbeat_records_activity():
    reset();run_heartbeat();d=heartbeat_status()
    assert d['heartbeat']['last_run_at']
    assert d['recent_activity']

def test_voice_controls_are_present_in_owner_console():
    assert 'SpeechRecognition' in JARVIS_HTML
    assert 'speechSynthesis' in JARVIS_HTML
    assert 'Push to talk' in JARVIS_HTML
    assert 'Speak Jarvis replies' in JARVIS_HTML
