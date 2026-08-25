import os,sqlite3,json,re,datetime
from pathlib import Path
DATA=Path(os.getenv('JARVIS3_DATA_DIR','/app/data'));DATA.mkdir(parents=True,exist_ok=True)
DB=DATA/'jarvis3.db';KNOW=DATA/'knowledge';KNOW.mkdir(parents=True,exist_ok=True)

def db():
 c=sqlite3.connect(DB,timeout=10);c.row_factory=sqlite3.Row;c.execute('PRAGMA journal_mode=WAL');return c

def init():
 with db() as c:
  c.execute('''CREATE TABLE IF NOT EXISTS inventory(id INTEGER PRIMARY KEY AUTOINCREMENT,product TEXT NOT NULL,lot TEXT,quantity REAL NOT NULL DEFAULT 0,status TEXT NOT NULL DEFAULT 'available',coa_status TEXT DEFAULT 'unknown',unit_cost REAL NOT NULL DEFAULT 0,unit_price REAL NOT NULL DEFAULT 0,notes TEXT,updated_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
  for col,ddl in [('unit_cost','REAL NOT NULL DEFAULT 0'),('unit_price','REAL NOT NULL DEFAULT 0')]:
   try:c.execute(f'ALTER TABLE inventory ADD COLUMN {col} {ddl}')
   except sqlite3.OperationalError:pass
  c.execute('''CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT,order_number TEXT,order_date TEXT NOT NULL DEFAULT CURRENT_DATE,customer_name TEXT,channel TEXT DEFAULT 'manual',status TEXT NOT NULL DEFAULT 'paid',subtotal REAL NOT NULL DEFAULT 0,shipping REAL NOT NULL DEFAULT 0,tax REAL NOT NULL DEFAULT 0,total REAL NOT NULL DEFAULT 0,cogs REAL NOT NULL DEFAULT 0,notes TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
  c.execute('''CREATE TABLE IF NOT EXISTS cash_transactions(id INTEGER PRIMARY KEY AUTOINCREMENT,txn_date TEXT NOT NULL DEFAULT CURRENT_DATE,type TEXT NOT NULL,category TEXT NOT NULL,description TEXT,amount REAL NOT NULL,account TEXT DEFAULT 'Operating',status TEXT DEFAULT 'posted',created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
  c.execute('''CREATE TABLE IF NOT EXISTS customers(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,email TEXT,phone TEXT,first_order_date TEXT,last_order_date TEXT,lifetime_value REAL NOT NULL DEFAULT 0,orders_count INTEGER NOT NULL DEFAULT 0,notes TEXT,updated_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
  c.execute('''CREATE TABLE IF NOT EXISTS purchase_orders(id INTEGER PRIMARY KEY AUTOINCREMENT,po_number TEXT,supplier TEXT NOT NULL,order_date TEXT NOT NULL DEFAULT CURRENT_DATE,expected_date TEXT,status TEXT NOT NULL DEFAULT 'open',amount REAL NOT NULL DEFAULT 0,paid REAL NOT NULL DEFAULT 0,notes TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
  c.execute('''CREATE TABLE IF NOT EXISTS marketing_metrics(id INTEGER PRIMARY KEY AUTOINCREMENT,metric_date TEXT NOT NULL DEFAULT CURRENT_DATE,channel TEXT NOT NULL,spend REAL NOT NULL DEFAULT 0,revenue REAL NOT NULL DEFAULT 0,leads INTEGER NOT NULL DEFAULT 0,orders INTEGER NOT NULL DEFAULT 0,notes TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
  c.execute('''CREATE TABLE IF NOT EXISTS business_questions(id INTEGER PRIMARY KEY AUTOINCREMENT,question TEXT NOT NULL,category TEXT NOT NULL DEFAULT 'general',why TEXT,priority INTEGER NOT NULL DEFAULT 50,status TEXT NOT NULL DEFAULT 'open',answer TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,answered_at TEXT)''')
  c.execute('''CREATE TABLE IF NOT EXISTS dashboard_upgrade_requests(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL,request TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'requested',created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
  c.execute('''CREATE TABLE IF NOT EXISTS knowledge_files(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,path TEXT NOT NULL,category TEXT,tags TEXT,size_bytes INTEGER DEFAULT 0,created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
  c.execute('''CREATE TABLE IF NOT EXISTS business_notes(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL,note TEXT NOT NULL,category TEXT DEFAULT 'general',created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
  c.execute('''CREATE TABLE IF NOT EXISTS integration_registry(id INTEGER PRIMARY KEY AUTOINCREMENT,key TEXT UNIQUE NOT NULL,name TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'not_connected',detail TEXT,updated_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
  defaults=[('render','Render','connected' if os.getenv('RENDER_API_KEY') else 'not_connected','Deployment and hosting'),('openai','OpenAI','connected' if os.getenv('OPENAI_API_KEY') else 'not_connected','Reasoning and voice'),('github','GitHub','connected' if os.getenv('GITHUB_TOKEN') else 'not_connected','Self-engineering and dashboard upgrades'),('shopify','Shopify','not_connected','Store, orders and products'),('email','Email','not_connected','Customer and vendor communication'),('accounting','Accounting','not_connected','Books, bills and reconciliation'),('banking','Banking','not_connected','Cash and payments'),('suppliers','Suppliers','not_connected','Purchasing and replenishment'),('marketing','Marketing','not_connected','Campaigns and acquisition')]
  for x in defaults:c.execute('INSERT INTO integration_registry(key,name,status,detail) VALUES(?,?,?,?) ON CONFLICT(key) DO UPDATE SET status=CASE WHEN excluded.key IN ("render","openai","github") THEN excluded.status ELSE integration_registry.status END,detail=excluded.detail,updated_at=CURRENT_TIMESTAMP',x)
  seed=[('What products are we launching with, and what is the selling price for each?','products','Jarvis needs the launch catalog and pricing to measure margin and manage inventory.',100),('What is the current cash available to the business today?','finance','This establishes the opening cash position for the executive dashboard.',100),('What are the current fixed monthly expenses?','finance','Jarvis needs the baseline burn rate to forecast runway and cash flow.',90),('Who are the current suppliers and what are the normal unit costs and lead times?','purchasing','Jarvis needs supplier economics to manage purchasing and reorder timing.',90),('What sales channels should be live first?','sales','Jarvis needs to know whether Shopify, direct invoice, wholesale or other channels are the launch priority.',85),('What is the target launch date for accepting the first paid order?','launch','Jarvis uses this deadline to prioritize setup work.',85),('Who handles fulfillment and what is the standard shipping process and cost?','operations','Jarvis needs fulfillment rules before it can manage orders end-to-end.',80)]
  for q,cat,why,p in seed:
   if not c.execute('SELECT 1 FROM business_questions WHERE question=?',(q,)).fetchone():c.execute('INSERT INTO business_questions(question,category,why,priority) VALUES(?,?,?,?)',(q,cat,why,p))
init()

def _rows(sql,args=()):
 with db() as c:return [dict(r) for r in c.execute(sql,args).fetchall()]
def _one(sql,args=()):
 with db() as c:r=c.execute(sql,args).fetchone();return dict(r) if r else None

def inventory():return _rows('SELECT * FROM inventory ORDER BY product,lot,id')
def inventory_upsert(product,lot,quantity,status='available',coa_status='unknown',notes='',unit_cost=0,unit_price=0):
 with db() as c:
  r=c.execute('SELECT id FROM inventory WHERE product=? AND COALESCE(lot,"")=COALESCE(?,"")',(product,lot)).fetchone()
  if r:c.execute('UPDATE inventory SET quantity=?,status=?,coa_status=?,unit_cost=?,unit_price=?,notes=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',(quantity,status,coa_status,unit_cost,unit_price,notes,r['id']));iid=r['id']
  else:cur=c.execute('INSERT INTO inventory(product,lot,quantity,status,coa_status,unit_cost,unit_price,notes) VALUES(?,?,?,?,?,?,?,?)',(product,lot,quantity,status,coa_status,unit_cost,unit_price,notes));iid=cur.lastrowid
  return dict(c.execute('SELECT * FROM inventory WHERE id=?',(iid,)).fetchone())
def inventory_delete(iid):
 with db() as c:c.execute('DELETE FROM inventory WHERE id=?',(iid,))
 return {'ok':True}
def inventory_summary():
 rows=inventory();avail=[r for r in rows if r['status'] in ('available','released','active')]
 return {'skus':len(rows),'available_units':sum(float(r['quantity'] or 0) for r in avail),'held_units':sum(float(r['quantity'] or 0) for r in rows if r not in avail),'inventory_cost_value':sum(float(r['quantity'] or 0)*float(r['unit_cost'] or 0) for r in avail),'inventory_retail_value':sum(float(r['quantity'] or 0)*float(r['unit_price'] or 0) for r in avail)}

def add_order(d):
 with db() as c:
  cur=c.execute('INSERT INTO orders(order_number,order_date,customer_name,channel,status,subtotal,shipping,tax,total,cogs,notes) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(d.get('order_number'),d.get('order_date') or datetime.date.today().isoformat(),d.get('customer_name'),d.get('channel','manual'),d.get('status','paid'),float(d.get('subtotal') or 0),float(d.get('shipping') or 0),float(d.get('tax') or 0),float(d.get('total') or 0),float(d.get('cogs') or 0),d.get('notes','')));oid=cur.lastrowid
 return _one('SELECT * FROM orders WHERE id=?',(oid,))
def orders(limit=200):return _rows('SELECT * FROM orders ORDER BY order_date DESC,id DESC LIMIT ?',(limit,))

def add_cash(d):
 with db() as c:
  cur=c.execute('INSERT INTO cash_transactions(txn_date,type,category,description,amount,account,status) VALUES(?,?,?,?,?,?,?)',(d.get('txn_date') or datetime.date.today().isoformat(),d.get('type','expense'),d.get('category','general'),d.get('description',''),float(d.get('amount') or 0),d.get('account','Operating'),d.get('status','posted')));tid=cur.lastrowid
 return _one('SELECT * FROM cash_transactions WHERE id=?',(tid,))
def cash_transactions(limit=300):return _rows('SELECT * FROM cash_transactions ORDER BY txn_date DESC,id DESC LIMIT ?',(limit,))

def add_purchase_order(d):
 with db() as c:
  cur=c.execute('INSERT INTO purchase_orders(po_number,supplier,order_date,expected_date,status,amount,paid,notes) VALUES(?,?,?,?,?,?,?,?)',(d.get('po_number'),d.get('supplier'),d.get('order_date') or datetime.date.today().isoformat(),d.get('expected_date'),d.get('status','open'),float(d.get('amount') or 0),float(d.get('paid') or 0),d.get('notes','')));pid=cur.lastrowid
 return _one('SELECT * FROM purchase_orders WHERE id=?',(pid,))
def purchase_orders():return _rows('SELECT * FROM purchase_orders ORDER BY order_date DESC,id DESC')

def add_marketing(d):
 with db() as c:
  cur=c.execute('INSERT INTO marketing_metrics(metric_date,channel,spend,revenue,leads,orders,notes) VALUES(?,?,?,?,?,?,?)',(d.get('metric_date') or datetime.date.today().isoformat(),d.get('channel'),float(d.get('spend') or 0),float(d.get('revenue') or 0),int(d.get('leads') or 0),int(d.get('orders') or 0),d.get('notes','')));mid=cur.lastrowid
 return _one('SELECT * FROM marketing_metrics WHERE id=?',(mid,))
def marketing():return _rows('SELECT * FROM marketing_metrics ORDER BY metric_date DESC,id DESC LIMIT 200')

def questions(status='open'):return _rows('SELECT * FROM business_questions WHERE status=? ORDER BY priority DESC,id ASC',(status,))
def add_question(question,category='general',why='',priority=50):
 with db() as c:
  existing=c.execute("SELECT id FROM business_questions WHERE question=? AND status='open'",(question,)).fetchone()
  if existing:return _one('SELECT * FROM business_questions WHERE id=?',(existing['id'],))
  cur=c.execute('INSERT INTO business_questions(question,category,why,priority) VALUES(?,?,?,?)',(question[:1500],category[:80],why[:3000],int(priority)));qid=cur.lastrowid
 return _one('SELECT * FROM business_questions WHERE id=?',(qid,))
def answer_question(qid,answer):
 with db() as c:
  c.execute("UPDATE business_questions SET answer=?,status='answered',answered_at=CURRENT_TIMESTAMP WHERE id=?",(answer[:12000],qid));r=c.execute('SELECT * FROM business_questions WHERE id=?',(qid,)).fetchone()
  if r:c.execute('INSERT INTO business_notes(title,note,category) VALUES(?,?,?)',(r['question'],answer,r['category']))
 return dict(r) if r else None

def request_dashboard_upgrade(title,request):
 with db() as c:cur=c.execute('INSERT INTO dashboard_upgrade_requests(title,request) VALUES(?,?)',(title[:300],request[:8000]));rid=cur.lastrowid
 return _one('SELECT * FROM dashboard_upgrade_requests WHERE id=?',(rid,))
def dashboard_upgrades():return _rows('SELECT * FROM dashboard_upgrade_requests ORDER BY id DESC LIMIT 100')

def executive_summary():
 today=datetime.date.today();month=today.strftime('%Y-%m');year=today.strftime('%Y');today_s=today.isoformat()
 with db() as c:
  scalar=lambda q,a=():float((c.execute(q,a).fetchone()[0] or 0))
  sales_today=scalar("SELECT SUM(total) FROM orders WHERE order_date=? AND status NOT IN ('cancelled','refunded')",(today_s,));sales_mtd=scalar("SELECT SUM(total) FROM orders WHERE substr(order_date,1,7)=? AND status NOT IN ('cancelled','refunded')",(month,));sales_ytd=scalar("SELECT SUM(total) FROM orders WHERE substr(order_date,1,4)=? AND status NOT IN ('cancelled','refunded')",(year,));orders_mtd=int(scalar("SELECT COUNT(*) FROM orders WHERE substr(order_date,1,7)=? AND status NOT IN ('cancelled','refunded')",(month,)));cogs_mtd=scalar("SELECT SUM(cogs) FROM orders WHERE substr(order_date,1,7)=? AND status NOT IN ('cancelled','refunded')",(month,));cash_in=scalar("SELECT SUM(amount) FROM cash_transactions WHERE type='income' AND status='posted'");cash_out=scalar("SELECT SUM(amount) FROM cash_transactions WHERE type='expense' AND status='posted'");cash_balance=cash_in-cash_out;open_po=scalar("SELECT SUM(amount-paid) FROM purchase_orders WHERE status IN ('open','ordered','partial')");marketing_spend=scalar("SELECT SUM(spend) FROM marketing_metrics WHERE substr(metric_date,1,7)=?",(month,));marketing_rev=scalar("SELECT SUM(revenue) FROM marketing_metrics WHERE substr(metric_date,1,7)=?",(month,))
 inv=inventory_summary();gross=sales_mtd-cogs_mtd;avg=sales_mtd/orders_mtd if orders_mtd else 0;roas=marketing_rev/marketing_spend if marketing_spend else 0
 trend=_rows("SELECT order_date date,ROUND(SUM(total),2) sales,COUNT(*) orders FROM orders WHERE order_date>=date('now','-29 day') AND status NOT IN ('cancelled','refunded') GROUP BY order_date ORDER BY order_date")
 return {'sales_today':sales_today,'sales_mtd':sales_mtd,'sales_ytd':sales_ytd,'orders_mtd':orders_mtd,'average_order_value':avg,'cogs_mtd':cogs_mtd,'gross_profit_mtd':gross,'gross_margin_pct':(gross/sales_mtd*100 if sales_mtd else 0),'cash_balance':cash_balance,'cash_in_total':cash_in,'cash_out_total':cash_out,'open_po_commitment':open_po,'marketing_spend_mtd':marketing_spend,'marketing_revenue_mtd':marketing_rev,'roas':roas,'inventory':inv,'sales_trend':trend,'unanswered_questions':len(questions('open'))}

def safe_name(name):return re.sub(r'[^A-Za-z0-9._-]+','_',name or 'file')[:180]
def save_knowledge(name,data,category='general',tags=''):
 fn=safe_name(name);path=KNOW/fn;i=1
 while path.exists():path=KNOW/f'{Path(fn).stem}_{i}{Path(fn).suffix}';i+=1
 path.write_bytes(data)
 with db() as c:cur=c.execute('INSERT INTO knowledge_files(name,path,category,tags,size_bytes) VALUES(?,?,?,?,?)',(name,str(path),category,tags,len(data)));kid=cur.lastrowid;return dict(c.execute('SELECT * FROM knowledge_files WHERE id=?',(kid,)).fetchone())
def knowledge():return _rows('SELECT * FROM knowledge_files ORDER BY id DESC')
def notes():return _rows('SELECT * FROM business_notes ORDER BY id DESC LIMIT 200')
def add_note(title,note,category='general'):
 with db() as c:cur=c.execute('INSERT INTO business_notes(title,note,category) VALUES(?,?,?)',(title,note,category));nid=cur.lastrowid
 return _one('SELECT * FROM business_notes WHERE id=?',(nid,))
def integrations():return _rows('SELECT * FROM integration_registry ORDER BY CASE status WHEN "connected" THEN 0 ELSE 1 END,name')
