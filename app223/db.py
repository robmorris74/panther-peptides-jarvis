import os, sqlite3, threading, time, random
from pathlib import Path
DATA_DIR=Path(os.getenv('JARVIS_DATA_DIR','/var/data'))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH=Path(os.getenv('DATABASE_PATH', str(DATA_DIR/'operator.db')))
_lock=threading.RLock()

def connect():
    con=sqlite3.connect(DB_PATH, timeout=60, check_same_thread=False, isolation_level=None)
    con.row_factory=sqlite3.Row
    con.execute('PRAGMA journal_mode=WAL'); con.execute('PRAGMA synchronous=NORMAL'); con.execute('PRAGMA foreign_keys=ON'); con.execute('PRAGMA busy_timeout=60000')
    return con

def _column_exists(con, table, column): return any(r[1]==column for r in con.execute(f'PRAGMA table_info({table})').fetchall())
def init_db():
    with _lock, connect() as con:
        con.executescript('''CREATE TABLE IF NOT EXISTS objectives(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL,detail TEXT NOT NULL,state TEXT NOT NULL DEFAULT 'queued',priority INTEGER NOT NULL DEFAULT 50,step INTEGER NOT NULL DEFAULT 0,max_steps INTEGER NOT NULL DEFAULT 30,last_error TEXT,blocked_reason TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP,completed_at TEXT); CREATE TABLE IF NOT EXISTS activity(id INTEGER PRIMARY KEY AUTOINCREMENT,objective_id INTEGER,level TEXT NOT NULL DEFAULT 'info',event TEXT NOT NULL,detail TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP); CREATE TABLE IF NOT EXISTS approvals(id INTEGER PRIMARY KEY AUTOINCREMENT,objective_id INTEGER,action TEXT NOT NULL,payload TEXT,status TEXT NOT NULL DEFAULT 'pending',created_at TEXT DEFAULT CURRENT_TIMESTAMP,decided_at TEXT); CREATE TABLE IF NOT EXISTS command_receipts(request_id TEXT PRIMARY KEY,response_json TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP); CREATE TABLE IF NOT EXISTS kv(key TEXT PRIMARY KEY,value TEXT,updated_at TEXT DEFAULT CURRENT_TIMESTAMP); CREATE TABLE IF NOT EXISTS knowledge(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,path TEXT NOT NULL,sha256 TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP);''')
        if not _column_exists(con,'knowledge','mime_type'): con.execute('ALTER TABLE knowledge ADD COLUMN mime_type TEXT')
        if not _column_exists(con,'knowledge','text_content'): con.execute('ALTER TABLE knowledge ADD COLUMN text_content TEXT')
        if not _column_exists(con,'knowledge','size_bytes'): con.execute('ALTER TABLE knowledge ADD COLUMN size_bytes INTEGER')
        con.execute('CREATE INDEX IF NOT EXISTS idx_objectives_state_priority ON objectives(state,priority DESC,id ASC)'); con.execute('CREATE INDEX IF NOT EXISTS idx_activity_objective_id ON activity(objective_id,id DESC)')
def execute(sql, params=(), fetch=False):
    last=None
    for i in range(12):
        try:
            with _lock, connect() as con:
                cur=con.execute(sql, params)
                if fetch: return [dict(r) for r in cur.fetchall()]
                return cur.lastrowid
        except sqlite3.OperationalError as e:
            last=e
            if 'locked' not in str(e).lower() and 'busy' not in str(e).lower(): raise
            time.sleep(min(1.25,.04*(2**i))+random.random()*.04)
    raise last
def one(sql, params=()):
    rows=execute(sql,params,True); return rows[0] if rows else None
def checkpoint():
    with _lock, connect() as con: return con.execute('PRAGMA wal_checkpoint(PASSIVE)').fetchone()
