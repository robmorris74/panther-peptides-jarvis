import os,sqlite3,json,re
from pathlib import Path
DATA=Path(os.getenv('JARVIS3_DATA_DIR','/app/data'));DATA.mkdir(parents=True,exist_ok=True)
DB=DATA/'jarvis3.db';KNOW=DATA/'knowledge';KNOW.mkdir(parents=True,exist_ok=True)

def db():
 c=sqlite3.connect(DB,timeout=10);c.row_factory=sqlite3.Row;c.execute('PRAGMA journal_mode=WAL');return c

def init():
 with db() as c:
  c.execute('''CREATE TABLE IF NOT EXISTS inventory(id INTEGER PRIMARY KEY AUTOINCREMENT,product TEXT NOT NULL,lot TEXT,quantity REAL NOT NULL DEFAULT 0,status TEXT NOT NULL DEFAULT 'available',coa_status TEXT DEFAULT 'unknown',notes TEXT,updated_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
  c.execute('''CREATE TABLE IF NOT EXISTS knowledge_files(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,path TEXT NOT NULL,category TEXT,tags TEXT,size_bytes INTEGER DEFAULT 0,created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
  c.execute('''CREATE TABLE IF NOT EXISTS business_notes(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL,note TEXT NOT NULL,category TEXT DEFAULT 'general',created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
  c.execute('''CREATE TABLE IF NOT EXISTS integration_registry(id INTEGER PRIMARY KEY AUTOINCREMENT,key TEXT UNIQUE NOT NULL,name TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'not_connected',detail TEXT,updated_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
  defaults=[('render','Render','connected' if os.getenv('RENDER_API_KEY') else 'not_connected','Deployment and hosting'),('openai','OpenAI','connected' if os.getenv('OPENAI_API_KEY') else 'not_connected','Reasoning and voice'),('shopify','Shopify','not_connected','Store, orders and products'),('email','Email','not_connected','Customer and vendor communication'),('accounting','Accounting','not_connected','Books, bills and reconciliation'),('banking','Banking','not_connected','Cash and payments'),('suppliers','Suppliers','not_connected','Purchasing and replenishment'),('marketing','Marketing','not_connected','Campaigns and acquisition')]
  for x in defaults:c.execute('INSERT INTO integration_registry(key,name,status,detail) VALUES(?,?,?,?) ON CONFLICT(key) DO UPDATE SET status=CASE WHEN excluded.key IN ("render","openai") THEN excluded.status ELSE integration_registry.status END,detail=excluded.detail,updated_at=CURRENT_TIMESTAMP',x)
init()

def inventory():
 with db() as c:return [dict(r) for r in c.execute('SELECT * FROM inventory ORDER BY product,lot,id').fetchall()]
def inventory_upsert(product,lot,quantity,status='available',coa_status='unknown',notes=''):
 with db() as c:
  r=c.execute('SELECT id FROM inventory WHERE product=? AND COALESCE(lot,"")=COALESCE(?,"")',(product,lot)).fetchone()
  if r:c.execute('UPDATE inventory SET quantity=?,status=?,coa_status=?,notes=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',(quantity,status,coa_status,notes,r['id']));iid=r['id']
  else:cur=c.execute('INSERT INTO inventory(product,lot,quantity,status,coa_status,notes) VALUES(?,?,?,?,?,?)',(product,lot,quantity,status,coa_status,notes));iid=cur.lastrowid
  return dict(c.execute('SELECT * FROM inventory WHERE id=?',(iid,)).fetchone())
def inventory_delete(iid):
 with db() as c:c.execute('DELETE FROM inventory WHERE id=?',(iid,))
 return {'ok':True}
def inventory_summary():
 rows=inventory();return {'skus':len(rows),'available_units':sum(float(r['quantity'] or 0) for r in rows if r['status'] in ('available','released','active')),'held_units':sum(float(r['quantity'] or 0) for r in rows if r['status'] not in ('available','released','active'))}

def safe_name(name):return re.sub(r'[^A-Za-z0-9._-]+','_',name or 'file')[:180]
def save_knowledge(name,data,category='general',tags=''):
 fn=safe_name(name);path=KNOW/fn;i=1
 while path.exists():path=KNOW/f'{Path(fn).stem}_{i}{Path(fn).suffix}';i+=1
 path.write_bytes(data)
 with db() as c:cur=c.execute('INSERT INTO knowledge_files(name,path,category,tags,size_bytes) VALUES(?,?,?,?,?)',(name,str(path),category,tags,len(data)));kid=cur.lastrowid;return dict(c.execute('SELECT * FROM knowledge_files WHERE id=?',(kid,)).fetchone())
def knowledge():
 with db() as c:return [dict(r) for r in c.execute('SELECT * FROM knowledge_files ORDER BY id DESC').fetchall()]

def notes():
 with db() as c:return [dict(r) for r in c.execute('SELECT * FROM business_notes ORDER BY id DESC LIMIT 200').fetchall()]
def add_note(title,note,category='general'):
 with db() as c:cur=c.execute('INSERT INTO business_notes(title,note,category) VALUES(?,?,?)',(title,note,category));nid=cur.lastrowid;return dict(c.execute('SELECT * FROM business_notes WHERE id=?',(nid,)).fetchone())

def integrations():
 with db() as c:return [dict(r) for r in c.execute('SELECT * FROM integration_registry ORDER BY CASE status WHEN "connected" THEN 0 ELSE 1 END,name').fetchall()]
