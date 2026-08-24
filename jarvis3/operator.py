import os,json,sqlite3,threading,time,urllib.request,urllib.error
from pathlib import Path
from .ops import tool_specs,run_tool,MUTATING,VERIFYING,evidence

DATA=Path(os.getenv('JARVIS3_DATA_DIR','/app/data'));DB=DATA/'jarvis3.db'
_stop=threading.Event();_wake=threading.Event();_thread=None;_current=None;_heartbeat=0.0

def _db():
    c=sqlite3.connect(DB,timeout=10);c.row_factory=sqlite3.Row;c.execute('PRAGMA journal_mode=WAL');return c

def ensure_schema():
    with _db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS objectives(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL,detail TEXT NOT NULL,state TEXT NOT NULL DEFAULT 'queued',priority INTEGER NOT NULL DEFAULT 50,step INTEGER NOT NULL DEFAULT 0,result TEXT,blocked_reason TEXT,last_error TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP,completed_at TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS objective_steps(id INTEGER PRIMARY KEY AUTOINCREMENT,objective_id INTEGER NOT NULL,cycle INTEGER NOT NULL,kind TEXT NOT NULL,tool TEXT,status TEXT NOT NULL,detail TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
        c.execute('''CREATE TABLE IF NOT EXISTS approvals(id INTEGER PRIMARY KEY AUTOINCREMENT,objective_id INTEGER NOT NULL,action TEXT NOT NULL,question TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',created_at TEXT DEFAULT CURRENT_TIMESTAMP,decided_at TEXT)''')
ensure_schema()

def _step(oid,cycle,kind,status,detail='',tool=None):
    with _db() as c:c.execute('INSERT INTO objective_steps(objective_id,cycle,kind,tool,status,detail) VALUES(?,?,?,?,?,?)',(oid,cycle,kind,tool,status,str(detail)[:12000]))

def create_objective(detail,priority=50):
    text=(detail or '').strip()
    if not text:raise ValueError('Objective is required')
    title=text.split('\n')[0][:160]
    with _db() as c:
        cur=c.execute('INSERT INTO objectives(title,detail,state,priority) VALUES(?,?,?,?)',(title,text,'queued',priority));oid=cur.lastrowid
    _step(oid,0,'objective','queued',text);_wake.set();return oid

def list_objectives(limit=50):
    with _db() as c:return [dict(r) for r in c.execute('SELECT * FROM objectives ORDER BY id DESC LIMIT ?',(limit,)).fetchall()]

def list_activity(limit=50):
    with _db() as c:
        rows=c.execute('''SELECT s.*,o.title objective_title FROM objective_steps s LEFT JOIN objectives o ON o.id=s.objective_id ORDER BY s.id DESC LIMIT ?''',(limit,)).fetchall()
    return [dict(r) for r in rows]

def get_objective(oid):
    with _db() as c:
        r=c.execute('SELECT * FROM objectives WHERE id=?',(oid,)).fetchone();steps=c.execute('SELECT * FROM objective_steps WHERE objective_id=? ORDER BY id ASC',(oid,)).fetchall()
    return {'objective':dict(r) if r else None,'steps':[dict(x) for x in steps]}

def pending_approval():
    with _db() as c:r=c.execute("SELECT a.*,o.title objective_title FROM approvals a LEFT JOIN objectives o ON o.id=a.objective_id WHERE a.status='pending' ORDER BY a.id ASC LIMIT 1").fetchone()
    return dict(r) if r else None

def decide_approval(aid,approved):
    status='approved' if approved else 'denied'
    with _db() as c:
        r=c.execute("SELECT * FROM approvals WHERE id=? AND status='pending'",(aid,)).fetchone()
        if not r:raise ValueError('Pending approval not found')
        c.execute('UPDATE approvals SET status=?,decided_at=CURRENT_TIMESTAMP WHERE id=?',(status,aid));c.execute("UPDATE objectives SET state='queued',blocked_reason=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=?",(r['objective_id'],))
    _wake.set();return {'ok':True,'decision':status,'objective_id':r['objective_id']}

def _claim():
    with _db() as c:
        r=c.execute("SELECT * FROM objectives WHERE state='queued' ORDER BY priority DESC,id ASC LIMIT 1").fetchone()
        if not r:return None
        c.execute("UPDATE objectives SET state='running',updated_at=CURRENT_TIMESTAMP WHERE id=?",(r['id'],));return dict(r)

def _approved_actions(oid):
    with _db() as c:return [dict(r) for r in c.execute("SELECT action,status FROM approvals WHERE objective_id=? AND status IN ('approved','denied') ORDER BY id",(oid,)).fetchall()]

def _model(messages,tools):
    key=os.getenv('OPENAI_API_KEY','').strip()
    if not key:raise RuntimeError('OPENAI_API_KEY is not configured')
    payload={'model':os.getenv('JARVIS_MODEL','gpt-5-mini'),'messages':messages,'tools':tools,'tool_choice':'auto'}
    req=urllib.request.Request('https://api.openai.com/v1/chat/completions',data=json.dumps(payload).encode(),headers={'Authorization':f'Bearer {key}','Content-Type':'application/json','User-Agent':'Jarvis3-Operator'})
    try:
        with urllib.request.urlopen(req,timeout=120) as r:
            d=json.loads(r.read());m=d['choices'][0]['message'];return {'content':m.get('content') or '','tool_calls':m.get('tool_calls') or []}
    except urllib.error.HTTPError as e:raise RuntimeError(f'OpenAI HTTP {e.code}: '+e.read().decode('utf-8','replace')[:2000])

def _request_approval(oid,action,question):
    with _db() as c:
        existing=c.execute("SELECT id FROM approvals WHERE objective_id=? AND action=? AND status='pending'",(oid,action)).fetchone()
        if existing:return existing['id']
        cur=c.execute('INSERT INTO approvals(objective_id,action,question) VALUES(?,?,?)',(oid,action,question[:1000]));aid=cur.lastrowid;c.execute("UPDATE objectives SET state='awaiting_approval',blocked_reason='owner_approval',updated_at=CURRENT_TIMESTAMP WHERE id=?",(oid,))
    return aid

def _run(obj):
    global _current,_heartbeat
    oid=obj['id'];_current=oid
    system='''You are Jarvis 3, an execution-first business operating agent. The owner gives objectives, not questions. Your job is to use available tools to perform real work, record operational tasks, and verify results. A prose answer is never completion when an action is possible. Continue until the objective is accomplished or an exact missing connector/credential/owner approval blocks execution. Current tools are intentionally limited. Use them fully, but never claim capabilities you do not have. You can currently operate Render infrastructure and persistent business tasks/decisions. If the objective needs Shopify, banking, email, accounting, inventory purchasing, marketing platforms, supplier portals, customer support systems, or another missing system, create concrete persistent business tasks for the missing setup, then finish as BLOCKED with the exact connector required rather than pretending the business action occurred. For infrastructure changes such as render_deploy, require owner approval first unless the approval history explicitly contains approval for that exact action. For internal reversible task creation/update and business decision recording, proceed without approval. After every mutation, use an appropriate verification tool. Do not mark complete without post-action verification evidence. When truly complete, respond with COMPLETE: followed by a concise outcome. When execution cannot continue because a capability is missing, respond with BLOCKED: followed by the exact connector, credential, or owner decision required.'''
    messages=[{'role':'system','content':system+'\nApproval history: '+json.dumps(_approved_actions(oid))},{'role':'user','content':obj['detail']}];mutations=0;verified=False
    for cycle in range(1,31):
        _heartbeat=time.time()
        with _db() as c:c.execute('UPDATE objectives SET step=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',(cycle,oid))
        try:out=_model(messages,tool_specs())
        except Exception as e:
            with _db() as c:c.execute("UPDATE objectives SET state='blocked',last_error=?,blocked_reason='model_error',updated_at=CURRENT_TIMESTAMP WHERE id=?",(str(e)[:4000],oid))
            _step(oid,cycle,'model','error',str(e));_current=None;return
        calls=out['tool_calls']
        if calls:
            messages.append({'role':'assistant','content':out['content'],'tool_calls':calls})
            for tc in calls:
                name=tc['function']['name']
                try:args=json.loads(tc['function'].get('arguments') or '{}')
                except:args={}
                _step(oid,cycle,'tool','started',json.dumps(args),name)
                if name=='render_deploy':
                    action='render_deploy:'+str(args.get('service_id') or '');approvals=_approved_actions(oid);approved=any(x['action']==action and x['status']=='approved' for x in approvals);denied=any(x['action']==action and x['status']=='denied' for x in approvals)
                    if denied:result={'ok':False,'error':'Owner denied '+action}
                    elif not approved:
                        aid=_request_approval(oid,action,'Approve Jarvis deploying Render service '+str(args.get('service_id'))+'?');_step(oid,cycle,'approval','pending',json.dumps({'approval_id':aid,'action':action}),name);_current=None;return
                    else:result=run_tool(name,args)
                else:
                    try:result=run_tool(name,args)
                    except Exception as e:result={'ok':False,'error':str(e)}
                ok=not (isinstance(result,dict) and result.get('ok') is False)
                if ok:
                    evidence(oid,name,result)
                    if name in MUTATING:mutations+=1;verified=False
                    elif mutations and name in VERIFYING:verified=True
                _step(oid,cycle,'tool','success' if ok else 'failed',json.dumps(result,default=str),name);messages.append({'role':'tool','tool_call_id':tc['id'],'content':json.dumps(result,default=str)})
            continue
        text=(out['content'] or '').strip()
        if text.startswith('COMPLETE:'):
            if mutations and not verified:messages.extend([{'role':'assistant','content':text},{'role':'user','content':'Verification is still required after the last mutation. Use a verification tool before completing.'}]);continue
            with _db() as c:c.execute("UPDATE objectives SET state='completed',result=?,completed_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE id=?",(text[9:].strip(),oid))
            _step(oid,cycle,'objective','completed',text);_current=None;return
        if text.startswith('BLOCKED:'):
            reason=text[8:].strip()
            with _db() as c:c.execute("UPDATE objectives SET state='blocked',blocked_reason=?,result=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(reason[:500],reason[:4000],oid))
            _step(oid,cycle,'objective','blocked',reason);_current=None;return
        messages.extend([{'role':'assistant','content':text},{'role':'user','content':'Continue executing. Use tools. If no available tool can perform the needed action, create concrete business tasks for the missing setup and then return BLOCKED with the exact connector required.'}])
    with _db() as c:c.execute("UPDATE objectives SET state='blocked',blocked_reason='max_steps',updated_at=CURRENT_TIMESTAMP WHERE id=?",(oid,));_current=None

def _loop():
    global _heartbeat
    while not _stop.is_set():
        _heartbeat=time.time();obj=_claim()
        if obj:_run(obj)
        else:_wake.wait(2);_wake.clear()

def start():
    global _thread
    ensure_schema();_stop.clear()
    if not _thread or not _thread.is_alive():_thread=threading.Thread(target=_loop,name='jarvis3-operator',daemon=True);_thread.start()

def status():
    with _db() as c:counts={s:c.execute('SELECT COUNT(*) n FROM objectives WHERE state=?',(s,)).fetchone()['n'] for s in ['queued','running','awaiting_approval','blocked','completed']}
    return {'worker_alive':bool(_thread and _thread.is_alive()),'current_objective':_current,'heartbeat_age':round(time.time()-_heartbeat,1) if _heartbeat else None,**counts}
