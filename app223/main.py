import os,json,re,urllib.request,urllib.error
from pathlib import Path
from fastapi import FastAPI,Request,HTTPException
from fastapi.responses import HTMLResponse,JSONResponse,Response
from pydantic import BaseModel,Field
from .db import init_db,execute,one
from .security import verify_password,make_session,require_owner,COOKIE,valid_session,SESSION_TTL,password_source
from .agent import start,status,create_objective,wake,model_status,_model_call
from .integrations import test_connections
from .ui import HTML

VER='224.0.0'
DATA=Path(os.getenv('JARVIS_DATA_DIR','/var/data'))
app=FastAPI(title='Jarvis',version=VER)

class Login(BaseModel): password:str
class Cmd(BaseModel): text:str; request_id:str|None=None
class ChatTurn(BaseModel): role:str; content:str
class ChatReq(BaseModel):
    message:str
    history:list[ChatTurn]=Field(default_factory=list)
class TTSReq(BaseModel): text:str

@app.on_event('startup')
def boot(): init_db(); start()

@app.middleware('http')
async def headers(req,call_next):
    try: r=await call_next(req)
    except Exception as e: r=JSONResponse({'ok':False,'error':'internal_error','detail':str(e)[:1000],'version':VER},status_code=500)
    r.headers['X-Jarvis-Version']=VER
    r.headers['Cache-Control']='no-store'
    return r

@app.get('/health')
def health(): return {'ok':True,'version':VER}

@app.get('/health/ready')
def ready():
    s=status(); persistent=DATA.exists() and os.access(DATA,os.W_OK)
    ok=s['database_ok'] and persistent and s['worker_alive'] and s['watchdog_alive']
    return JSONResponse({'ok':ok,'version':VER,'persistent':persistent,**s},status_code=200 if ok else 503)

@app.get('/',response_class=HTMLResponse)
def home(): return HTML

@app.get('/client/bootstrap')
def bootstrap(req:Request):
    return {'ok':True,'version':VER,'authenticated':valid_session(req.cookies.get(COOKIE,'')),'runtime':status(),'owner_auth_source':password_source(),'wake_word':'jarvis','voice':'British male'}

@app.post('/auth/login')
def login(v:Login):
    if not verify_password(v.password): raise HTTPException(401,'Invalid owner password')
    r=JSONResponse({'ok':True,'version':VER})
    r.set_cookie(COOKIE,make_session(),httponly=True,secure=os.getenv('JARVIS_COOKIE_SECURE','1')!='0',samesite='lax',max_age=SESSION_TTL,path='/')
    return r

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
    oid=create_objective(text); result={'ok':True,'objective_id':oid,'message':f'Objective #{oid} queued. I will continue autonomously.'}
    if v.request_id: execute('INSERT OR REPLACE INTO command_receipts(request_id,response_json) VALUES(?,?)',(v.request_id,json.dumps(result)))
    return result

@app.post('/assistant/message')
def assistant_message(v:ChatReq,req:Request):
    require_owner(req)
    text=v.message.strip()
    if not text: raise HTTPException(400,'Empty message')
    history=[]
    for t in v.history[-12:]:
        if t.role in ('user','assistant') and t.content.strip(): history.append({'role':t.role,'content':t.content[:4000]})
    system=(
        'You are Jarvis, the owner-facing AI operating agent for Panther Peptides. '
        'Communicate naturally, calmly, confidently, and concisely, using British English wording where natural. '
        'You are in conversation mode: answer questions and discuss plans. Do not falsely claim an action was performed. '
        'If the owner asks you to carry out autonomous work, tell them you can start it as an objective and briefly restate the objective. '
        'Panther Peptides products are for research use only, not for human or veterinary use.'
    )
    out=_model_call([{'role':'system','content':system},*history,{'role':'user','content':text}])
    return {'ok':True,'reply':(out.get('content') or '').strip(),'model':out.get('model')}

def _spoken_version(text:str)->str:
    clean=re.sub(r'```.*?```','',text,flags=re.S)
    clean=re.sub(r'[`*_#>|]','',clean)
    clean=re.sub(r'\s+',' ',clean).strip()
    if not clean:return 'Done.'
    # Do not simply read the written answer aloud. Create a short, conversational voice response.
    try:
        prompt=(
            'Turn the following written Jarvis response into a distinct short spoken response. '
            'Do NOT read or repeat the written text verbatim. Give the owner the key conclusion naturally in one or two sentences, '
            'maximum 45 words, in polished British English. Do not mention that details are written unless helpful. '
            'Written response:\n'+clean[:6000]
        )
        out=_model_call([{'role':'system','content':'You write concise spoken dialogue for a British male AI assistant named Jarvis.'},{'role':'user','content':prompt}])
        spoken=(out.get('content') or '').strip()
        if spoken:return spoken[:700]
    except Exception:
        pass
    # Low-latency fallback: first useful sentence, never the whole displayed response.
    parts=re.split(r'(?<=[.!?])\s+',clean)
    first=(parts[0] if parts else clean)[:300]
    return first if len(parts)<=1 else first+' I have the rest on screen.'

@app.post('/voice/tts')
def tts(v:TTSReq,req:Request):
    require_owner(req)
    text=v.text.strip()
    if not text: raise HTTPException(400,'Empty speech text')
    spoken=_spoken_version(text)
    key=os.getenv('OPENAI_API_KEY','').strip()
    if not key: raise HTTPException(503,'OPENAI_API_KEY is not configured')
    payload={
        'model':os.getenv('JARVIS_TTS_MODEL','gpt-4o-mini-tts'),
        'voice':os.getenv('JARVIS_TTS_VOICE','onyx'),
        'input':spoken,
        'response_format':'mp3',
        'instructions':os.getenv('JARVIS_TTS_INSTRUCTIONS','Adult British male voice. Polished modern received-pronunciation English accent, lower male register, calm and assured, warm but restrained, articulate, intelligent personal aide. Natural conversational cadence with subtle dry confidence. Never feminine, never high-pitched, never robotic, never announcer-like. Do not sound American.')
    }
    try:
        q=urllib.request.Request('https://api.openai.com/v1/audio/speech',data=json.dumps(payload).encode(),headers={'Authorization':f'Bearer {key}','Content-Type':'application/json','User-Agent':'Jarvis-v224'})
        with urllib.request.urlopen(q,timeout=90) as r: audio=r.read()
        return Response(content=audio,media_type='audio/mpeg',headers={'Cache-Control':'no-store','X-Jarvis-Voice':'British-male-onyx'})
    except urllib.error.HTTPError as e:
        body=e.read().decode('utf-8','replace')[:1600]
        raise HTTPException(e.code if e.code<500 else 502,f'TTS provider error: {body}')
    except Exception as e:
        raise HTTPException(502,f'TTS transport error: {str(e)[:800]}')

@app.post('/connections/test')
def connections(req:Request): require_owner(req); return test_connections()

@app.post('/model/test')
def model_test(req:Request): require_owner(req); return model_status(True)

@app.get('/launch/readiness')
def readiness(req:Request):
    require_owner(req); s=status(); c=test_connections()
    checks={'worker':s['worker_alive'],'watchdog':s['watchdog_alive'],'database':s['database_ok'],'persistent':DATA.exists() and os.access(DATA,os.W_OK),'github':c['github']['connected'],'render':c['render']['connected'],'openai':model_status(False)['configured']}
    return {'ok':all(checks.values()),'version':VER,'checks':checks,'connections':c,'status':s}
