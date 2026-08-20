import os,hashlib,re
from pathlib import Path
from .db import execute,connect

DATA=Path(os.getenv('JARVIS_DATA_DIR','/var/data'))
UPLOADS=DATA/'inventory_docs'
UPLOADS.mkdir(parents=True,exist_ok=True)


def ensure_business_schema():
    execute('''CREATE TABLE IF NOT EXISTS pp_inventory(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      product TEXT NOT NULL,
      sku TEXT,
      vial_size TEXT,
      lot_code TEXT,
      quantity INTEGER NOT NULL DEFAULT 0,
      status TEXT NOT NULL DEFAULT 'available',
      coa_status TEXT NOT NULL DEFAULT 'missing',
      supplier TEXT,
      received_at TEXT,
      notes TEXT,
      source_table TEXT,
      source_id TEXT,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    execute('''CREATE TABLE IF NOT EXISTS pp_inventory_documents(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      inventory_id INTEGER NOT NULL,
      kind TEXT NOT NULL DEFAULT 'coa',
      original_name TEXT NOT NULL,
      stored_path TEXT NOT NULL,
      sha256 TEXT NOT NULL,
      mime_type TEXT,
      size_bytes INTEGER,
      review_status TEXT NOT NULL DEFAULT 'on_file',
      created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(inventory_id) REFERENCES pp_inventory(id)
    )''')
    execute('''CREATE TABLE IF NOT EXISTS pp_business_events(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      category TEXT NOT NULL,
      title TEXT NOT NULL,
      detail TEXT,
      severity TEXT NOT NULL DEFAULT 'info',
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    execute('CREATE INDEX IF NOT EXISTS idx_pp_inventory_status ON pp_inventory(status,product,lot_code)')
    execute('CREATE INDEX IF NOT EXISTS idx_pp_inventory_docs_inventory ON pp_inventory_documents(inventory_id,id DESC)')

def _tables():
    with connect() as con:return [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]

def _columns(table):
    with connect() as con:return [r[1] for r in con.execute(f'PRAGMA table_info("{table}")').fetchall()]

def _pick(cols,*names):
    low={c.lower():c for c in cols}
    for n in names:
        if n in low:return low[n]
    for c in cols:
        cl=c.lower()
        if any(n in cl for n in names):return c
    return None

def discover_legacy_inventory():
    result=[]
    for table in _tables():
        tl=table.lower()
        if table in ('pp_inventory','pp_inventory_documents') or not any(k in tl for k in ('inventory','lot','stock','product')):continue
        try:
            cols=_columns(table);product=_pick(cols,'product','product_name','name','peptide');qty=_pick(cols,'quantity','qty','units','count','on_hand');lot=_pick(cols,'lot_code','lot','batch','batch_id');status=_pick(cols,'status','state','disposition');sku=_pick(cols,'sku','product_code');size=_pick(cols,'vial_size','size','strength')
            if not product:continue
            chosen=[c for c in (product,sku,size,lot,qty,status) if c]
            sql='SELECT rowid AS __rid,'+','.join('"'+c.replace('"','')+'"' for c in chosen)+f' FROM "{table}" LIMIT 500'
            with connect() as con:
                for r in con.execute(sql).fetchall():
                    d=dict(r);legacy_status=str(d.get(status) or 'available') if status else 'available'
                    result.append({'legacy':True,'source_table':table,'source_id':str(d.get('__rid')),'product':str(d.get(product) or 'Unknown'),'sku':str(d.get(sku) or '') if sku else '','vial_size':str(d.get(size) or '') if size else '','lot_code':str(d.get(lot) or '') if lot else '','quantity':int(d.get(qty) or 0) if qty else 0,'status':legacy_status,'coa_status':'unknown','documents':[]})
        except Exception:continue
    return result

def inventory_rows():
    ensure_business_schema();rows=execute('SELECT * FROM pp_inventory ORDER BY product,lot_code,id',fetch=True)
    for r in rows:
        r['legacy']=False;r['documents']=execute('SELECT id,kind,original_name,mime_type,size_bytes,review_status,created_at FROM pp_inventory_documents WHERE inventory_id=? ORDER BY id DESC',(r['id'],),True)
    return rows if rows else discover_legacy_inventory()

def dashboard_summary():
    inv=inventory_rows();held=sum(int(x.get('quantity') or 0) for x in inv if str(x.get('status','')).lower() in ('quarantine','quarantined','hold','blocked'));available=sum(int(x.get('quantity') or 0) for x in inv if str(x.get('status','')).lower() in ('released','available','active'))
    missing=sum(1 for x in inv if str(x.get('coa_status','')).lower() in ('missing','unknown',''))
    return {'lots':len(inv),'units':sum(int(x.get('quantity') or 0) for x in inv),'quarantined_units':held,'released_units':available,'lots_missing_or_unknown_docs':missing}

def import_legacy():
    ensure_business_schema();created=0
    for r in discover_legacy_inventory():
        if execute('SELECT id FROM pp_inventory WHERE source_table=? AND source_id=?',(r['source_table'],r['source_id']),True):continue
        execute('INSERT INTO pp_inventory(product,sku,vial_size,lot_code,quantity,status,coa_status,source_table,source_id) VALUES(?,?,?,?,?,?,?,?,?)',(r['product'],r['sku'],r['vial_size'],r['lot_code'],r['quantity'],r['status'] or 'available','unknown',r['source_table'],r['source_id']));created+=1
    if created:execute('INSERT INTO pp_business_events(category,title,detail) VALUES(?,?,?)',('inventory','Legacy inventory imported',f'{created} record(s) imported from prior Jarvis database tables.'))
    return {'ok':True,'imported':created}

def save_document(inventory_id:int,filename:str,content:bytes,mime_type:str='application/octet-stream',kind:str='coa'):
    ensure_business_schema();row=execute('SELECT * FROM pp_inventory WHERE id=?',(inventory_id,),True)
    if not row:raise ValueError('Inventory lot not found. Import legacy inventory first if this is an older record.')
    if not content:raise ValueError('Empty file')
    if len(content)>25*1024*1024:raise ValueError('File exceeds 25 MB limit')
    safe=re.sub(r'[^A-Za-z0-9._-]+','_',filename or 'document')[:180];digest=hashlib.sha256(content).hexdigest();path=UPLOADS/f'{inventory_id}_{digest[:12]}_{safe}';path.write_bytes(content)
    doc_id=execute('INSERT INTO pp_inventory_documents(inventory_id,kind,original_name,stored_path,sha256,mime_type,size_bytes,review_status) VALUES(?,?,?,?,?,?,?,?)',(inventory_id,kind,filename,str(path),digest,mime_type,len(content),'on_file'))
    execute("UPDATE pp_inventory SET coa_status='on_file',updated_at=CURRENT_TIMESTAMP WHERE id=?",(inventory_id,));execute('INSERT INTO pp_business_events(category,title,detail,severity) VALUES(?,?,?,?)',('inventory','Document uploaded',f'{filename} attached to inventory lot #{inventory_id}. Availability was not changed.','info'))
    return {'ok':True,'document_id':doc_id,'sha256':digest,'status':'on_file'}

def review_document(doc_id:int,approved:bool):
    rows=execute('SELECT * FROM pp_inventory_documents WHERE id=?',(doc_id,),True)
    if not rows:raise ValueError('Document not found')
    doc=rows[0];state='approved' if approved else 'rejected';execute('UPDATE pp_inventory_documents SET review_status=? WHERE id=?',(state,doc_id));execute("UPDATE pp_inventory SET coa_status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(state,doc['inventory_id']));return {'ok':True,'review_status':state}

def set_inventory_status(inventory_id:int,status:str):
    status=status.lower().strip()
    if status not in ('available','quarantine','hold'):raise ValueError('Invalid inventory status')
    rows=execute('SELECT id FROM pp_inventory WHERE id=?',(inventory_id,),True)
    if not rows:raise ValueError('Inventory lot not found')
    execute('UPDATE pp_inventory SET status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',(status,inventory_id));execute('INSERT INTO pp_business_events(category,title,detail,severity) VALUES(?,?,?,?)',('inventory','Inventory status changed',f'Inventory lot #{inventory_id} changed to {status}.','info'));return {'ok':True,'status':status}

def release_inventory(inventory_id:int):
    # Availability is an owner-controlled inventory decision and is not gated by documentation.
    return set_inventory_status(inventory_id,'available')

def events():
    ensure_business_schema();return execute('SELECT * FROM pp_business_events ORDER BY id DESC LIMIT 100',fetch=True)
