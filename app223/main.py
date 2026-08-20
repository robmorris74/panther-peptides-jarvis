import os,json,re,urllib.request,urllib.error
from pathlib import Path
from fastapi import FastAPI,Request,HTTPException,UploadFile,File,Form
from fastapi.responses import HTMLResponse,JSONResponse,Response,FileResponse
from pydantic import BaseModel,Field
from .db import init_db,execute,one
from .security import verify_password,make_session,require_owner,COOKIE,valid_session,SESSION_TTL,password_source
from .agent import start,status,create_objective,wake,model_status,_model_call,pending_approval,decide_approval
from .integrations import test_connections
from .business import ensure_business_schema,inventory_rows,dashboard_summary,import_legacy,save_document,review_document,release_inventory,set_inventory_status,events
from .knowledge import ensure_knowledge_schema,save as save_knowledge,list_items as knowledge_items,context as knowledge_context,stats as knowledge_stats,delete_item as delete_knowledge
from .ui import HTML
from .business_ui import BUSINESS_HTML
VER='227.0.0';DATA=Path(os.getenv('JARVIS_DATA_DIR','/var/data'));app=FastAPI(title='Jarvis',version=VER)
class Login(BaseModel):password:str
class Cmd(BaseModel):text:str;request_id:str|None=None
class ChatTurn(BaseModel):role:str;content:str
class ChatReq(BaseModel):message:str;history:list[ChatTurn]=Field(default_factory=list)
class TTSReq(BaseModel):text:str
class ReviewReq(BaseModel):approved:bool
class StatusReq(BaseModel):status:str
class ApprovalReq(BaseModel):approved:bool
@app.on_event('startup')
def boot():init_db();ensure_business_schema();ensure_knowledge_schema();start()
@app.middleware('http')
async def headers(req,call_next):
    try:r=await call_next(req)
    except Exception as e:r=JSONResponse({'ok':False,'error':'internal_error','detail':str(e)[:1000],'version':VER},status_code=500)
    r.headers['X-Jarvis-Version']=VER;r.headers['Cache-Control']='no-store';return r
@app.get('/health')
def health():return {'ok':True,'version':VER}
@app.get('/health/ready')
def ready():
    s=status();persistent=DATA.exists() and os.access(DATA,os.W_OK);ok=s['database_ok'] and persistent and s['worker_alive'] and s['watchdog_alive'];return JSONResponse({'ok':ok,'version':VER,'persistent':persistent,**s},status_code=200 if ok else 503)
@app.get('/',response_class=HTMLResponse)
def home():return BUSINESS_HTML
@app.get('/dashboard',response_class=HTMLResponse)
def dashboard_page():return BUSINESS_HTML
@app.get('/jarvis',response_class=HTMLResponse)
def jarvis_page():return HTML
@app.get('/client/bootstrap')
def bootstrap(req:Request):return {'ok':True,'version':VER,'authenticated':valid_session(req.cookies.get(COOKIE,'')),'runtime':status(),'owner_auth_source':password_source(),'wake_word':'jarvis','voice':'British male','dashboard':'/','jarvis':'/jarvis','knowledge':knowledge_stats() if valid_session(req.cookies.get(COOKIE,'')) else None}
@app.post('/auth/login')
def login(v:Login):
    if not verify_password(v.password):raise HTTPException(401,'Invalid owner password')
    r=JSONResponse({'ok':True,'version':VER});r.set_cookie(COOKIE,make_session(),httponly=True,secure=os.getenv('JARVIS_COOKIE_SECURE','1')!='0',samesite='lax',max_age=SESSION_TTL,path='/');return r
@app.get('/agent/status')
def agent_status(req:Request):require_owner(req);return {**status(),'version':VER,'persistent':DATA.exists() and os.access(DATA,os.W_OK)}
@app.post('/agent/wake')
def agent_wake(req:Request):require_owner(req);return wake()
@app.get('/agent/objectives')
def objectives(req:Request):require_owner(req);return execute('SELECT * FROM objectives ORDER BY id DESC LIMIT 50',fetch=True)
@app.get('/agent/activity')
def activity(req:Request):require_owner(req);return execute('SELECT * FROM activity ORDER BY id DESC LIMIT 120',fetch=True)
@app.get('/agent/approval')
def approval(req:Request):require_owner(req);return {'ok':True,'approval':pending_approval()}
@app.post('/agent/approval/{approval_id}')
def approval_decision(approval_id:int,v:ApprovalReq,req:Request):
    require_owner(req)
    try:return decide_approval(approval_id,v.approved)
    except ValueError as e:raise HTTPException(404,str(e))
@app.post('/agent/v223/command')
def command(v:Cmd,req:Request):
    require_owner(req);text=v.text.strip()
    if not text:raise HTTPException(400,'Empty command')
    if v.request_id:
        old=one('SELECT response_json FROM command_receipts WHERE request_id=?',(v.request_id,))
        if old:return json.loads(old['response_json'])
    oid=create_objective(text);result={'ok':True,'objective_id':oid,'message':f'Objective #{oid} queued. Jarvis will plan, execute, verify and ask one approval question at a time only when required.'}
    if v.request_id:execute('INSERT OR REPLACE INTO command_receipts(request_id,response_json) VALUES(?,?)',(v.request_id,json.dumps(result)))
    return result
@app.post('/assistant/message')
def assistant_message(v:ChatReq,req:Request):
    require_owner(req);text=v.message.strip()
    if not text:raise HTTPException(400,'Empty message')
    history=[{'role':t.role,'content':t.content[:4000]} for t in v.history[-12:] if t.role in ('user','assistant') and t.content.strip()];inv=dashboard_summary();kctx=knowledge_context(text);recent=events()[:8]
    system=('You are Jarvis, the owner-facing AI chief operating agent for Panther Peptides. Think across operations, inventory, documents, software, deployment, purchasing, fulfillment, marketing planning and business administration. Communicate naturally and concisely. Never falsely claim an action was performed. The dashboard is the primary frontend. Quarantined and held inventory are excluded from the default sellable view. Panther Peptides products are FOR RESEARCH USE ONLY, NOT FOR HUMAN OR VETERINARY USE. For actual multi-step execution, recommend or create an autonomous objective rather than pretending conversational text performed the action. Current inventory summary: '+json.dumps(inv)+'\nRecent business events: '+json.dumps(recent)[:6000]+'\nRETRIEVED KNOWLEDGE:\n'+(kctx or '[none retrieved]'))
    out=_model_call([{'role':'system','content':system},*history,{'role':'user','content':text}]);return {'ok':True,'reply':(out.get('content') or '').strip(),'model':out.get('model'),'knowledge_used':bool(kctx)}
def _spoken_version(text):
    clean=re.sub(r'```.*?```','',text,flags=re.S);clean=re.sub(r'[`*_#>|]','',clean);clean=re.sub(r'\s+',' ',clean).strip()
    if not clean:return 'Done.'
    try:
        out=_model_call([{'role':'system','content':'You write concise spoken dialogue for a British male AI assistant named Jarvis.'},{'role':'user','content':'Give the key conclusion in one or two natural British-English sentences, maximum 45 words. Do not read this verbatim:\n'+clean[:6000]}]);spoken=(out.get('content') or '').strip()
        if spoken:return spoken[:700]
    except Exception:pass
    return re.split(r'(?<=[.!?])\s+',clean)[0][:300]
@app.post('/voice/tts')
def tts(v:TTSReq,req:Request):
    require_owner(req);spoken=_spoken_version(v.text.strip());key=os.getenv('OPENAI_API_KEY','').strip()
    if not key:raise HTTPException(503,'OPENAI_API_KEY is not configured')
    payload={'model':os.getenv('JARVIS_TTS_MODEL','gpt-4o-mini-tts'),'voice':os.getenv('JARVIS_TTS_VOICE','onyx'),'input':spoken,'response_format':'mp3','instructions':os.getenv('JARVIS_TTS_INSTRUCTIONS','Adult British male voice. Polished modern received-pronunciation English accent, lower male register, calm and assured, warm but restrained, articulate and intelligent. Never feminine, high-pitched, robotic, announcer-like, or American.')}
    try:q=urllib.request.Request('https://api.openai.com/v1/audio/speech',data=json.dumps(payload).encode(),headers={'Authorization':f'Bearer {key}','Content-Type':'application/json','User-Agent':'Jarvis-v227'});audio=urllib.request.urlopen(q,timeout=90).read();return Response(content=audio,media_type='audio/mpeg')
    except urllib.error.HTTPError as e:raise HTTPException(e.code if e.code<500 else 502,'TTS provider error: '+e.read().decode('utf-8','replace')[:1600])
    except Exception as e:raise HTTPException(502,'TTS transport error: '+str(e)[:800])
@app.post('/connections/test')
def connections(req:Request):require_owner(req);return test_connections()
@app.post('/model/test')
def model_test(req:Request):require_owner(req);return model_status(True)
@app.get('/launch/readiness')
def readiness(req:Request):
    require_owner(req);s=status();c=test_connections();checks={'worker':s['worker_alive'],'watchdog':s['watchdog_alive'],'database':s['database_ok'],'persistent':DATA.exists() and os.access(DATA,os.W_OK),'github':c['github']['connected'],'render':c['render']['connected'],'openai':model_status(False)['configured']};return {'ok':all(checks.values()),'version':VER,'checks':checks,'connections':c,'status':s}
@app.get('/business/dashboard')
def business_dashboard(req:Request):require_owner(req);return {'ok':True,'summary':dashboard_summary(),'inventory':inventory_rows(),'events':events(),'objectives':execute('SELECT * FROM objectives ORDER BY id DESC LIMIT 30',fetch=True),'activity':execute('SELECT * FROM activity ORDER BY id DESC LIMIT 60',fetch=True),'runtime':status(),'knowledge':knowledge_stats(),'approval':pending_approval()}
@app.get('/business/inventory')
def business_inventory(req:Request):require_owner(req);return {'ok':True,'items':inventory_rows(),'summary':dashboard_summary()}
@app.post('/business/inventory/import-legacy')
def business_import(req:Request):require_owner(req);return import_legacy()
@app.post('/business/inventory/{inventory_id}/documents')
async def business_upload(inventory_id:int,req:Request,file:UploadFile=File(...),kind:str=Form('coa')):
    require_owner(req)
    try:return save_document(inventory_id,file.filename or 'document',await file.read(),file.content_type or 'application/octet-stream',kind)
    except ValueError as e:raise HTTPException(400,str(e))
@app.post('/business/documents/{doc_id}/review')
def business_review(doc_id:int,v:ReviewReq,req:Request):
    require_owner(req)
    try:return review_document(doc_id,v.approved)
    except ValueError as e:raise HTTPException(400,str(e))
@app.post('/business/inventory/{inventory_id}/status')
def business_status(inventory_id:int,v:StatusReq,req:Request):
    require_owner(req)
    try:return set_inventory_status(inventory_id,v.status)
    except ValueError as e:raise HTTPException(400,str(e))
@app.post('/business/inventory/{inventory_id}/release')
def business_release(inventory_id:int,req:Request):
    require_owner(req)
    try:return release_inventory(inventory_id)
    except ValueError as e:raise HTTPException(409,str(e))
@app.get('/business/documents/{doc_id}')
def business_document(doc_id:int,req:Request):
    require_owner(req);rows=execute('SELECT * FROM pp_inventory_documents WHERE id=?',(doc_id,),True)
    if not rows:raise HTTPException(404,'Document not found')
    d=rows[0];p=Path(d['stored_path'])
    if not p.exists():raise HTTPException(404,'Stored document missing')
    return FileResponse(str(p),media_type=d.get('mime_type') or 'application/octet-stream',filename=d['original_name'])
@app.get('/knowledge')
def knowledge_list(req:Request):require_owner(req);return {'ok':True,'items':knowledge_items(),'stats':knowledge_stats()}
@app.post('/knowledge/upload')
async def knowledge_upload(req:Request,file:UploadFile=File(...),category:str=Form('general'),tags:str=Form('')):
    require_owner(req)
    try:return save_knowledge(file.filename or 'knowledge',await file.read(),file.content_type or 'application/octet-stream',category,tags)
    except ValueError as e:raise HTTPException(400,str(e))
@app.delete('/knowledge/{kid}')
def knowledge_delete(kid:int,req:Request):
    require_owner(req)
    try:return delete_knowledge(kid)
    except ValueError as e:raise HTTPException(404,str(e))
