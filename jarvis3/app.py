import os,secrets,hmac,hashlib,time
from pathlib import Path
from fastapi import FastAPI,Request,HTTPException
from fastapi.responses import HTMLResponse,JSONResponse
from pydantic import BaseModel
from . import operator
from .ops import list_tasks,render_services

VERSION='3.0.0-beta.1'
DATA=Path(os.getenv('JARVIS3_DATA_DIR','/app/data'));DATA.mkdir(parents=True,exist_ok=True)
SECRET_FILE=DATA/'jarvis3_session_secret'
if SECRET_FILE.exists():SECRET=SECRET_FILE.read_text().strip().encode()
else:SECRET=secrets.token_hex(48).encode();SECRET_FILE.write_text(SECRET.decode())
COOKIE='jarvis3_owner';app=FastAPI(title='Jarvis 3 Operator',version=VERSION)

def sign(body):return hmac.new(SECRET,body.encode(),hashlib.sha256).hexdigest()
def session():
 body=f'owner:{int(time.time())}';return body+'.'+sign(body)
def valid(token):
 try:
  body,sig=token.rsplit('.',1);role,ts=body.split(':',1);return role=='owner' and hmac.compare_digest(sig,sign(body)) and 0<=int(time.time())-int(ts)<2592000
 except:return False
def owner(req):
 if not valid(req.cookies.get(COOKIE,'')):raise HTTPException(401,'Owner authentication required')

class Login(BaseModel):password:str
class Objective(BaseModel):objective:str;priority:int=50
class Decision(BaseModel):approved:bool

@app.on_event('startup')
def startup():operator.start()
@app.get('/health')
def health():return {'ok':True,'service':'jarvis3-operator','version':VERSION,'operator':operator.status()}
@app.get('/ready')
def ready():return {'ok':bool(os.getenv('JARVIS_OWNER_PASSWORD') and os.getenv('OPENAI_API_KEY')),'version':VERSION,'checks':{'owner_password':bool(os.getenv('JARVIS_OWNER_PASSWORD')),'openai':bool(os.getenv('OPENAI_API_KEY')),'render_key':bool(os.getenv('RENDER_API_KEY')),'operator':operator.status()}}
@app.post('/api/login')
def login(x:Login):
 expected=os.getenv('JARVIS_OWNER_PASSWORD','')
 if not expected or not hmac.compare_digest(x.password,expected):raise HTTPException(401,'Invalid password')
 r=JSONResponse({'ok':True});r.set_cookie(COOKIE,session(),httponly=True,secure=os.getenv('JARVIS_COOKIE_SECURE','1')=='1',samesite='lax',max_age=2592000);return r
@app.post('/api/logout')
def logout():
 r=JSONResponse({'ok':True});r.delete_cookie(COOKIE);return r
@app.get('/api/dashboard')
def dashboard(req:Request):
 owner(req);return {'ok':True,'version':VERSION,'operator':operator.status(),'objectives':operator.list_objectives(),'approval':operator.pending_approval(),'tasks':list_tasks().get('tasks',[]),'render_configured':bool(os.getenv('RENDER_API_KEY'))}
@app.post('/api/objectives')
def create_objective(x:Objective,req:Request):
 owner(req)
 try:oid=operator.create_objective(x.objective,max(1,min(100,x.priority)))
 except ValueError as e:raise HTTPException(400,str(e))
 return {'ok':True,'objective_id':oid}
@app.get('/api/objectives/{oid}')
def objective(oid:int,req:Request):owner(req);return operator.get_objective(oid)
@app.post('/api/approvals/{aid}')
def approval(aid:int,x:Decision,req:Request):
 owner(req)
 try:return operator.decide_approval(aid,x.approved)
 except ValueError as e:raise HTTPException(404,str(e))
@app.get('/api/render/services')
def services(req:Request):owner(req);return render_services()

PAGE='''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Jarvis 3 Operator</title><style>*{box-sizing:border-box}body{font-family:Inter,system-ui,sans-serif;background:#070b10;color:#e8edf3;margin:0}main{max-width:1250px;margin:35px auto;padding:22px}.top{display:flex;justify-content:space-between;align-items:center}.brand{font-size:30px;font-weight:800;letter-spacing:2px}.tag{color:#7dd3fc}.card{background:#0f1720;border:1px solid #253142;border-radius:16px;padding:20px;margin:14px 0}.grid{display:grid;grid-template-columns:repeat(5,1fr);gap:10px}.stat{background:#0a1119;border:1px solid #202d3c;border-radius:12px;padding:14px}.num{font-size:26px;font-weight:800}textarea,input,button{font:inherit;border-radius:10px;border:1px solid #334155;padding:12px;background:#09111a;color:white}textarea{width:100%;min-height:105px;resize:vertical}button{cursor:pointer;font-weight:700}.primary{background:#0ea5e9;border-color:#0ea5e9;color:#00131d}.danger{background:#7f1d1d}.ok{background:#14532d}.muted{color:#94a3b8}.row{display:flex;gap:10px;align-items:center}.obj{padding:13px 0;border-bottom:1px solid #202b37}.pill{display:inline-block;padding:4px 8px;border-radius:99px;background:#1e293b;font-size:12px;text-transform:uppercase}.blocked{color:#fca5a5}.completed{color:#86efac}#app{display:none}@media(max-width:800px){.grid{grid-template-columns:1fr 1fr}.top{align-items:flex-start;gap:10px;flex-direction:column}}</style></head><body><main><div class="top"><div><div class="brand">JARVIS <span class="tag">3</span></div><div class="muted">Business Operations Command Center</div></div><button id="logout" style="display:none" onclick="doLogout()">Logout</button></div><section id="login" class="card"><h2>Owner Login</h2><div class="row"><input id="pw" type="password" placeholder="Password"><button class="primary" onclick="doLogin()">Sign in</button></div><p id="err" class="muted"></p></section><section id="app"><div id="approval"></div><div class="card"><h2>Give Jarvis an Objective</h2><p class="muted">Describe the business outcome. Jarvis will work it, use connected systems, verify actions, and stop only when completed or genuinely blocked.</p><textarea id="objective" placeholder="Example: Get Panther Peptides operationally ready to take its first order. Inspect what is connected, create and execute the work you can, and tell me only what you truly need from me."></textarea><div class="row"><button class="primary" onclick="submitObjective()">Start Objective</button><span id="submitStatus" class="muted"></span></div></div><div id="stats" class="grid"></div><div class="card"><h2>Objectives</h2><div id="objectives"></div></div><div class="card"><h2>Persistent Business Tasks</h2><div id="tasks"></div></div></section></main><script>const $=id=>document.getElementById(id);const esc=s=>String(s??'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));async function api(url,opt){let r=await fetch(url,opt);if(r.status===401){$('login').style.display='block';$('app').style.display='none';throw Error('Not signed in')}let d=await r.json();if(!r.ok)throw Error(d.detail||'Request failed');return d}async function doLogin(){try{await api('/api/login',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({password:$('pw').value})});$('login').style.display='none';$('app').style.display='block';$('logout').style.display='block';$('err').textContent='';refresh()}catch(e){$('err').textContent=e.message}}async function doLogout(){await fetch('/api/logout',{method:'POST'});location.reload()}async function submitObjective(){let v=$('objective').value.trim();if(!v)return;$('submitStatus').textContent='Starting...';try{let d=await api('/api/objectives',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({objective:v,priority:50})});$('objective').value='';$('submitStatus').textContent='Objective #'+d.objective_id+' started';refresh()}catch(e){$('submitStatus').textContent=e.message}}async function decide(id,approved){await api('/api/approvals/'+id,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({approved})});refresh()}function stat(name,n){return '<div class="stat"><div class="muted">'+name+'</div><div class="num">'+n+'</div></div>'}async function refresh(){try{let d=await api('/api/dashboard');let s=d.operator;$('stats').innerHTML=stat('Queued',s.queued)+stat('Running',s.running)+stat('Approval',s.awaiting_approval)+stat('Blocked',s.blocked)+stat('Completed',s.completed);$('objectives').innerHTML=d.objectives.length?d.objectives.map(o=>'<div class="obj"><b>#'+o.id+' '+esc(o.title)+'</b> <span class="pill '+o.state+'">'+esc(o.state)+'</span><div class="muted">Step '+o.step+(o.result?' · '+esc(o.result):'')+(o.blocked_reason?' · <span class="blocked">'+esc(o.blocked_reason)+'</span>':'')+'</div></div>').join(''):'<div class="muted">No objectives yet.</div>';$('tasks').innerHTML=d.tasks.length?d.tasks.map(t=>'<div class="obj"><b>'+esc(t.title)+'</b> <span class="pill">'+esc(t.status)+'</span><div class="muted">'+esc(t.notes||'')+'</div></div>').join(''):'<div class="muted">No business tasks yet.</div>';let a=d.approval;$('approval').innerHTML=a?'<div class="card"><h2>Owner Approval Required</h2><b>'+esc(a.objective_title)+'</b><p>'+esc(a.question)+'</p><div class="row"><button class="ok" onclick="decide('+a.id+',true)">Approve</button><button class="danger" onclick="decide('+a.id+',false)">Deny</button></div></div>':''}catch(e){}}setInterval(()=>{if($('app').style.display==='block')refresh()},3000);</script></body></html>'''
@app.get('/',response_class=HTMLResponse)
def home():return PAGE
