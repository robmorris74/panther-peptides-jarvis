import os,json,urllib.request,urllib.error,sqlite3
from pathlib import Path

DATA=Path(os.getenv('JARVIS3_DATA_DIR','/app/data'))
DB=DATA/'jarvis3.db'

def _db():
    c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;return c

def ensure_ops_schema():
    with _db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS business_tasks(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'open',notes TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
        c.execute('''CREATE TABLE IF NOT EXISTS business_decisions(id INTEGER PRIMARY KEY AUTOINCREMENT,decision TEXT NOT NULL,rationale TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
        c.execute('''CREATE TABLE IF NOT EXISTS action_evidence(id INTEGER PRIMARY KEY AUTOINCREMENT,objective_id INTEGER,tool TEXT NOT NULL,detail TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
ensure_ops_schema()

def render_request(path,method='GET',payload=None):
    key=os.getenv('RENDER_API_KEY','').strip()
    if not key:return 0,{'error':'RENDER_API_KEY is not configured'}
    data=None if payload is None else json.dumps(payload).encode()
    req=urllib.request.Request('https://api.render.com/v1/'+path.lstrip('/'),data=data,method=method,headers={'Authorization':f'Bearer {key}','Accept':'application/json','Content-Type':'application/json','User-Agent':'Jarvis3'})
    try:
        with urllib.request.urlopen(req,timeout=25) as r:
            raw=r.read().decode('utf-8','replace');return r.status,(json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw=e.read().decode('utf-8','replace')
        try:body=json.loads(raw)
        except:body={'error':raw[:2000]}
        return e.code,body
    except Exception as e:return 0,{'error':str(e)}

def render_services():
    st,body=render_request('services?limit=50');out=[]
    if st==200 and isinstance(body,list):
        for item in body:
            s=item.get('service',item) if isinstance(item,dict) else {}
            d=s.get('serviceDetails') or {}
            out.append({'id':s.get('id'),'name':s.get('name'),'type':s.get('type'),'url':d.get('url'),'region':d.get('region'),'suspended':s.get('suspended')})
    return {'ok':st==200,'status':st,'services':out,'error':None if st==200 else body}

def render_deploy(service_id,clear_cache=False):
    payload={'clearCache':'clear'} if clear_cache else {}
    st,body=render_request(f'services/{service_id}/deploys','POST',payload)
    return {'ok':st in (200,201,202),'status':st,'service_id':service_id,'deploy':body}

def create_task(title,notes=''):
    with _db() as c:
        cur=c.execute('INSERT INTO business_tasks(title,notes) VALUES(?,?)',(title[:500],notes[:5000]));tid=cur.lastrowid
        row=c.execute('SELECT * FROM business_tasks WHERE id=?',(tid,)).fetchone()
    return {'ok':True,'task':dict(row)}

def update_task(task_id,status,notes=None):
    with _db() as c:
        row=c.execute('SELECT * FROM business_tasks WHERE id=?',(task_id,)).fetchone()
        if not row:return {'ok':False,'error':'Task not found'}
        c.execute('UPDATE business_tasks SET status=?,notes=COALESCE(?,notes),updated_at=CURRENT_TIMESTAMP WHERE id=?',(status,notes,task_id))
        row=c.execute('SELECT * FROM business_tasks WHERE id=?',(task_id,)).fetchone()
    return {'ok':True,'task':dict(row)}

def list_tasks():
    with _db() as c:return {'ok':True,'tasks':[dict(r) for r in c.execute('SELECT * FROM business_tasks ORDER BY id DESC LIMIT 100').fetchall()]}

def record_decision(decision,rationale=''):
    with _db() as c:
        cur=c.execute('INSERT INTO business_decisions(decision,rationale) VALUES(?,?)',(decision[:4000],rationale[:6000]));did=cur.lastrowid
    return {'ok':True,'decision_id':did}

def evidence(objective_id,tool,detail):
    with _db() as c:c.execute('INSERT INTO action_evidence(objective_id,tool,detail) VALUES(?,?,?)',(objective_id,tool,json.dumps(detail,default=str)[:12000]))

def tool_specs():
    return [
      {'type':'function','function':{'name':'render_services','description':'List live Render services and URLs. Read-only verification tool.','parameters':{'type':'object','properties':{}}}},
      {'type':'function','function':{'name':'render_deploy','description':'Trigger a Render deployment for a specific service. This changes infrastructure.','parameters':{'type':'object','properties':{'service_id':{'type':'string'},'clear_cache':{'type':'boolean'}},'required':['service_id']}}},
      {'type':'function','function':{'name':'create_business_task','description':'Create a persistent business task Jarvis can track.','parameters':{'type':'object','properties':{'title':{'type':'string'},'notes':{'type':'string'}},'required':['title']}}},
      {'type':'function','function':{'name':'update_business_task','description':'Update a persistent business task after real work or verification.','parameters':{'type':'object','properties':{'task_id':{'type':'integer'},'status':{'type':'string','enum':['open','in_progress','blocked','completed']},'notes':{'type':'string'}},'required':['task_id','status']}}},
      {'type':'function','function':{'name':'list_business_tasks','description':'Read current persistent business tasks.','parameters':{'type':'object','properties':{}}}},
      {'type':'function','function':{'name':'record_business_decision','description':'Record an owner/business decision for future operational continuity.','parameters':{'type':'object','properties':{'decision':{'type':'string'},'rationale':{'type':'string'}},'required':['decision']}}}
    ]

def run_tool(name,args):
    if name=='render_services':return render_services()
    if name=='render_deploy':return render_deploy(args['service_id'],bool(args.get('clear_cache',False)))
    if name=='create_business_task':return create_task(args['title'],args.get('notes',''))
    if name=='update_business_task':return update_task(int(args['task_id']),args['status'],args.get('notes'))
    if name=='list_business_tasks':return list_tasks()
    if name=='record_business_decision':return record_decision(args['decision'],args.get('rationale',''))
    raise ValueError('Unknown tool: '+name)

MUTATING={'render_deploy','create_business_task','update_business_task','record_business_decision'}
VERIFYING={'render_services','list_business_tasks'}
