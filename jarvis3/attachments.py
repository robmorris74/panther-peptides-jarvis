import os,sqlite3,re,mimetypes,uuid
from pathlib import Path
DATA=Path(os.getenv('JARVIS3_DATA_DIR','/app/data'));DB=DATA/'jarvis3.db';ROOT=DATA/'attachments';ROOT.mkdir(parents=True,exist_ok=True)

def db():
 c=sqlite3.connect(DB,timeout=10);c.row_factory=sqlite3.Row;c.execute('PRAGMA journal_mode=WAL');return c

def init():
 with db() as c:
  c.execute('''CREATE TABLE IF NOT EXISTS attachments(id INTEGER PRIMARY KEY AUTOINCREMENT,stored_name TEXT NOT NULL,original_name TEXT NOT NULL,path TEXT NOT NULL,mime_type TEXT,size_bytes INTEGER NOT NULL DEFAULT 0,context_type TEXT NOT NULL DEFAULT 'general',context_id TEXT,caption TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
init()

def safe_name(name):return re.sub(r'[^A-Za-z0-9._-]+','_',name or 'file')[:160]
def save(original_name,data,mime_type='',context_type='general',context_id='',caption=''):
 ext=Path(original_name or '').suffix[:12];stored=f'{uuid.uuid4().hex}{ext}';path=ROOT/stored;path.write_bytes(data)
 mime=mime_type or mimetypes.guess_type(original_name or '')[0] or 'application/octet-stream'
 with db() as c:
  cur=c.execute('INSERT INTO attachments(stored_name,original_name,path,mime_type,size_bytes,context_type,context_id,caption) VALUES(?,?,?,?,?,?,?,?)',(stored,original_name or stored,str(path),mime,len(data),(context_type or 'general')[:80],(context_id or '')[:120],(caption or '')[:2000]));aid=cur.lastrowid
  return dict(c.execute('SELECT * FROM attachments WHERE id=?',(aid,)).fetchone())
def list_all(limit=200):
 with db() as c:return [dict(r) for r in c.execute('SELECT * FROM attachments ORDER BY id DESC LIMIT ?',(limit,)).fetchall()]
def get(aid):
 with db() as c:r=c.execute('SELECT * FROM attachments WHERE id=?',(aid,)).fetchone();return dict(r) if r else None
def delete(aid):
 a=get(aid)
 if not a:return False
 try:Path(a['path']).unlink(missing_ok=True)
 except:pass
 with db() as c:c.execute('DELETE FROM attachments WHERE id=?',(aid,))
 return True
def is_image(a):return bool(a and str(a.get('mime_type','')).startswith('image/'))
