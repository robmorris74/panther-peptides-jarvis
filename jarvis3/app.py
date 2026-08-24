import os, sqlite3, secrets, hmac, hashlib, time, json, urllib.request, urllib.error
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from openai import OpenAI

VERSION='3.0.0-alpha.3'
DATA=Path(os.getenv('JARVIS3_DATA_DIR','/app/data')); DATA.mkdir(parents=True,exist_ok=True)
DB=DATA/'jarvis3.db'; SECRET_FILE=DATA/'jarvis3_session_secret'
if SECRET_FILE.exists(): SECRET=SECRET_FILE.read_text().strip().encode()
else:
    SECRET=secrets.token_hex(48).encode(); SECRET_FILE.write_text(SECRET.decode())
COOKIE='jarvis3_owner'
app=FastAPI(title='Jarvis 3',version=VERSION)

def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; c.execute('PRAGMA journal_mode=WAL'); return c

def init():
    with db() as c:
        c.execute('CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY, role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)')
init()

def sign(body): return hmac.new(SECRET,body.encode(),hashlib.sha256).hexdigest()
def session():
    body=f'owner:{int(time.time())}'; return body+'.'+sign(body)
def valid(token):
    try:
        body,sig=token.rsplit('.',1); role,ts=body.split(':',1)
        return role=='owner' and hmac.compare_digest(sig,sign(body)) and 0 <= int(time.time())-int(ts) < 2592000
    except Exception:return False
def owner(req):
    if not valid(req.cookies.get(COOKIE,'')): raise HTTPException(401,'Owner authentication required')
def configured(): return bool(os.getenv('JARVIS_OWNER_PASSWORD') and os.getenv('OPENAI_API_KEY'))

def render_request(path,method='GET',payload=None):
    key=os.getenv('RENDER_API_KEY','').strip()
    if not key:return 0,{'error':'RENDER_API_KEY is not configured'}
    data=None if payload is None else json.dumps(payload).encode()
    req=urllib.request.Request('https://api.render.com/v1/'+path.lstrip('/'),data=data,method=method,headers={'Authorization':f'Bearer {key}','Accept':'application/json','Content-Type':'application/json','User-Agent':'Jarvis3'})
    try:
        with urllib.request.urlopen(req,timeout=20) as r:
            raw=r.read().decode('utf-8','replace');return r.status,(json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw=e.read().decode('utf-8','replace')
        try:body=json.loads(raw)
        except:body={'error':raw[:1000]}
        return e.code,body
    except Exception as e:return 0,{'error':str(e)}

class Login(BaseModel): password:str
class Chat(BaseModel): message:str
class Deploy(BaseModel): service_id:str|None=None; clear_cache:bool=False

@app.get('/health')
def health(): return {'ok':True,'service':'jarvis3','version':VERSION}
@app.get('/ready')
def ready(): return {'ok':configured(),'version':VERSION,'checks':{'owner_password':bool(os.getenv('JARVIS_OWNER_PASSWORD')),'openai':bool(os.getenv('OPENAI_API_KEY')),'database':DB.exists(),'render_key':bool(os.getenv('RENDER_API_KEY'))}}
@app.post('/api/login')
def login(x:Login):
    expected=os.getenv('JARVIS_OWNER_PASSWORD','')
    if not expected or not hmac.compare_digest(x.password,expected): raise HTTPException(401,'Invalid password')
    r=JSONResponse({'ok':True}); r.set_cookie(COOKIE,session(),httponly=True,secure=os.getenv('JARVIS_COOKIE_SECURE','1')=='1',samesite='lax',max_age=2592000); return r
@app.post('/api/logout')
def logout():
    r=JSONResponse({'ok':True}); r.delete_cookie(COOKIE); return r
@app.get('/api/status')
def status(req:Request): owner(req); return {'ok':True,'version':VERSION,'database':str(DB),'model':os.getenv('JARVIS_MODEL','gpt-5-mini'),'render_configured':bool(os.getenv('RENDER_API_KEY'))}
@app.post('/api/chat')
def chat(x:Chat,req:Request):
    owner(req); text=x.message.strip()
    if not text: raise HTTPException(400,'Message required')
    with db() as c:
        c.execute('INSERT INTO messages(role,content) VALUES(?,?)',('user',text))
        history=c.execute('SELECT role,content FROM messages ORDER BY id DESC LIMIT 20').fetchall()[::-1]
    client=OpenAI(api_key=os.environ['OPENAI_API_KEY'])
    response=client.responses.create(model=os.getenv('JARVIS_MODEL','gpt-5-mini'),input=[{'role':r['role'],'content':r['content']} for r in history],instructions='You are Jarvis, the owner operational AI. Be concise, accurate, execution-oriented, and never claim an action occurred unless verified.')
    answer=response.output_text
    with db() as c:c.execute('INSERT INTO messages(role,content) VALUES(?,?)',('assistant',answer))
    return {'ok':True,'answer':answer}

@app.get('/api/render/status')
def render_status(req:Request):
    owner(req);st,body=render_request('services?limit=20')
    services=[]
    if st==200 and isinstance(body,list):
        for item in body:
            svc=item.get('service',item) if isinstance(item,dict) else {}
            services.append({'id':svc.get('id'),'name':svc.get('name'),'type':svc.get('type'),'suspended':svc.get('suspended'),'serviceDetails':{'url':(svc.get('serviceDetails') or {}).get('url'),'region':(svc.get('serviceDetails') or {}).get('region')}})
    return {'ok':st==200,'status':st,'configured':bool(os.getenv('RENDER_API_KEY')),'services':services,'error':None if st==200 else body}

@app.post('/api/render/deploy')
def render_deploy(x:Deploy,req:Request):
    owner(req);sid=(x.service_id or os.getenv('RENDER_STAGING_SERVICE_ID','')).strip()
    if not sid:raise HTTPException(400,'No staging service ID configured')
    payload={'clearCache':'clear'} if x.clear_cache else {}
    st,body=render_request(f'services/{sid}/deploys','POST',payload)
    return JSONResponse({'ok':st in (200,201,202),'status':st,'service_id':sid,'deploy':body},status_code=200 if st in (200,201,202) else 502)

PAGE='''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Jarvis 3</title><style>body{font-family:system-ui;background:#090d12;color:#e8edf3;margin:0}main{max-width:900px;margin:60px auto;padding:24px}.card{background:#111821;border:1px solid #263241;border-radius:18px;padding:24px}input,textarea,button{font:inherit;border-radius:10px;border:1px solid #334154;padding:12px;background:#0b1118;color:#fff}textarea{width:100%;box-sizing:border-box;min-height:100px}button{cursor:pointer}.muted{color:#94a3b8}.msg{padding:12px 0;border-bottom:1px solid #202b37}#appPanel{display:none}</style></head><body><main><h1>JARVIS <span class="muted">3.0</span></h1><section id="loginPanel" class="card"><h2>Owner Login</h2><input id="pw" type="password" placeholder="Password"><button type="button" onclick="doLogin()">Sign in</button><p id="err" class="muted"></p></section><section id="appPanel" class="card"><div id="messages"></div><textarea id="text" placeholder="Tell Jarvis what you need..."></textarea><button type="button" onclick="sendMessage()">Send</button> <button type="button" onclick="doLogout()">Logout</button></section></main><script>async function doLogin(){const errEl=document.getElementById('err');errEl.textContent='Signing in...';try{const r=await fetch('/api/login',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({password:document.getElementById('pw').value})});if(r.ok){document.getElementById('loginPanel').style.display='none';document.getElementById('appPanel').style.display='block';errEl.textContent=''}else{let d={};try{d=await r.json()}catch(e){}errEl.textContent=d.detail||'Login failed'}}catch(e){errEl.textContent='Unable to reach Jarvis'}}async function sendMessage(){let el=document.getElementById('text');let v=el.value.trim();if(!v)return;document.getElementById('messages').innerHTML+='<div class="msg"><b>You</b><br>'+esc(v)+'</div>';el.value='';let r=await fetch('/api/chat',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({message:v})});let d=await r.json();document.getElementById('messages').innerHTML+='<div class="msg"><b>Jarvis</b><br>'+esc(d.answer||d.detail||'Error')+'</div>'}async function doLogout(){await fetch('/api/logout',{method:'POST'});location.reload()}function esc(s){return String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}</script></body></html>'''
@app.get('/',response_class=HTMLResponse)
def home(): return PAGE
