import os,json
from pathlib import Path
from fastapi import FastAPI,Request,HTTPException
from fastapi.responses import HTMLResponse,JSONResponse
from pydantic import BaseModel
from .db import init_db,execute,one,DB_PATH
from .security import verify_password,make_session,require_owner,COOKIE,valid_session,SESSION_TTL,password_source
from .agent import start,status,create_objective,wake,model_status
from .integrations import test_connections
from .ui import HTML
VER='223.0.0'
DATA=Path(os.getenv('JARVIS_DATA_DIR','/var/data'))
app=FastAPI(title='Jarvis',version=VER)
class Login(BaseModel): password:str
class Cmd(BaseModel): text:str; request_id:str|None=None
@app.on_event('startup')
def boot(): init_db(); start()
@app.middleware('http')
async def headers(req,call_next):
    try: r=await call_next(req)
    except Exception as e: r=JSONResponse({'ok':False,'error':'internal_error','detail':str(e)[:1000],'version':VER},status_code=500)
    r.headers['X-Jarvis-Version']=VER; r.headers['Cache-Control']='no-store'; return r
@app.get('/health')
def health(): return {'ok':True,'version':VER}
@app.get('/health/ready')
def ready():
    s=status(); persistent=DATA.exists() and os.access(DATA,os.W_OK); ok=s['database_ok'] and persistent and s['worker_alive'] and s['watchdog_alive']
    return JSONResponse({'ok':ok,'version':VER,'persistent':persistent,**s},status_code=200 if ok else 503)
@app.get('/',response_class=HTMLResponse)
def home(): return HTML
@app.get('/client/bootstrap')
def bootstrap(req:Request): return {'ok':True,'version':VER,'authenticated':valid_session(req.cookies.get(COOKIE,'')),'runtime':status(),'owner_auth_source':password_source()}
@app.post('/auth/login')
def login(v:Login):
    if not verify_password(v.password): raise HTTPException(401,'Invalid owner password')
    r=JSONResponse({'ok':True,'version':VER}); r.set_cookie(COOKIE,make_session(),httponly=True,secure=os.getenv('JARVIS_COOKIE_SECURE','1')!='0',samesite='lax',max_age=SESSION_TTL,path='/'); return r
@app.get('/agent/status')
def agent_status(req:Request): require_owner(req); return {**status(),'version':VER,'persistent':DATA.exists() and os.access(DATA,os.W_OK)}
@app.post('/agent/wake')
def agent_wake(req:Request): require_owner(req); return wake()
@app.get('/agent/objectives')
def objectives(req:Request): require_owner(req); return execute('SELECT * FROM objectives ORDER BY id DESC LIMIT 50',fetch=True)
@app.get('/agent/activity')
def activity(req:Request): require_owner(req); return execute('SELECT * FROM activity ORDER BY id DESC LIMIT 120',fetch=True)
@app.post('/agent/v223/command')
def command(v:Cmd,req:Request):
    require_owner(req); text=v.text.strip()
    if not text: raise HTTPException(400,'Empty command')
    if v.request_id:
        old=one('SELECT response_json FROM command_receipts WHERE request_id=?',(v.request_id,))
        if old:return json.loads(old['response_json'])
    oid=create_objective(text); result={'ok':True,'objective_id':oid,'message':f'Objective #{oid} queued. Jarvis will continue autonomously.'}
    if v.request_id: execute('INSERT OR REPLACE INTO command_receipts(request_id,response_json) VALUES(?,?)',(v.request_id,json.dumps(result)))
    return result
@app.post('/connections/test')
def connections(req:Request): require_owner(req); return test_connections()
@app.post('/model/test')
def model_test(req:Request): require_owner(req); return model_status(True)
@app.get('/launch/readiness')
def readiness(req:Request):
    require_owner(req); s=status(); c=test_connections(); checks={'worker':s['worker_alive'],'watchdog':s['watchdog_alive'],'database':s['database_ok'],'persistent':DATA.exists() and os.access(DATA,os.W_OK),'github':c['github']['connected'],'render':c['render']['connected'],'openai':model_status(False)['configured']}; return {'ok':all(checks.values()),'version':VER,'checks':checks,'connections':c,'status':s}
