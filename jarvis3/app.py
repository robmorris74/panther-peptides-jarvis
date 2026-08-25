import os,secrets,hmac,hashlib,time
from pathlib import Path
from fastapi import FastAPI,Request,HTTPException,UploadFile,File,Form
from fastapi.responses import HTMLResponse,JSONResponse
from pydantic import BaseModel
from . import operator,store
from .ops import list_tasks,render_services
from .ui import PAGE
VERSION='3.1.0-use-now.240';RELEASE='USE-NOW-240';DATA=Path(os.getenv('JARVIS3_DATA_DIR','/app/data'));DATA.mkdir(parents=True,exist_ok=True);SECRET_FILE=DATA/'jarvis3_session_secret'
if SECRET_FILE.exists():SECRET=SECRET_FILE.read_text().strip().encode()
else:SECRET=secrets.token_hex(48).encode();SECRET_FILE.write_text(SECRET.decode())
COOKIE='jarvis3_owner';app=FastAPI(title='Panther Peptides - Jarvis Business OS',version=VERSION)
def sign(b):return hmac.new(SECRET,b.encode(),hashlib.sha256).hexdigest()
def session():b=f'owner:{int(time.time())}';return b+'.'+sign(b)
def valid(t):
 try:b,s=t.rsplit('.',1);role,ts=b.split(':',1);return role=='owner' and hmac.compare_digest(s,sign(b)) and 0<=int(time.time())-int(ts)<2592000
 except:return False
def owner(r):
 if not valid(r.cookies.get(COOKIE,'')):raise HTTPException(401,'Owner authentication required')
class Login(BaseModel):password:str
class Objective(BaseModel):objective:str;priority:int=50
class Decision(BaseModel):approved:bool
class InventoryItem(BaseModel):product:str;lot:str='';quantity:float=0;status:str='available';coa_status:str='unknown';notes:str=''
class Note(BaseModel):title:str;note:str;category:str='general'
@app.on_event('startup')
def startup():operator.start();store.init()
@app.get('/health')
def health():return {'ok':True,'service':'jarvis-business-os','version':VERSION,'release':RELEASE,'operator':operator.status()}
@app.get('/ready')
def ready():return {'ok':bool(os.getenv('JARVIS_OWNER_PASSWORD') and os.getenv('OPENAI_API_KEY')),'version':VERSION,'release':RELEASE,'checks':{'owner_password':bool(os.getenv('JARVIS_OWNER_PASSWORD')),'openai':bool(os.getenv('OPENAI_API_KEY')),'render_key':bool(os.getenv('RENDER_API_KEY')),'operator':operator.status()}}
@app.get('/version')
def version():return {'version':VERSION,'release':RELEASE,'built_for':'Panther Peptides','ui':'business-operating-dashboard'}
@app.post('/api/login')
def login(x:Login):
 expected=os.getenv('JARVIS_OWNER_PASSWORD','')
 if not expected or not hmac.compare_digest(x.password,expected):raise HTTPException(401,'Invalid password')
 r=JSONResponse({'ok':True,'version':VERSION,'release':RELEASE});r.set_cookie(COOKIE,session(),httponly=True,secure=os.getenv('JARVIS_COOKIE_SECURE','1')=='1',samesite='lax',max_age=2592000);return r
@app.post('/api/logout')
def logout():r=JSONResponse({'ok':True});r.delete_cookie(COOKIE);return r
@app.get('/api/dashboard')
def dashboard(req:Request):
 owner(req);return {'ok':True,'version':VERSION,'release':RELEASE,'operator':operator.status(),'objectives':operator.list_objectives(),'activity':operator.list_activity(60),'approval':operator.pending_approval(),'tasks':list_tasks().get('tasks',[]),'inventory':store.inventory(),'inventory_summary':store.inventory_summary(),'knowledge':store.knowledge(),'notes':store.notes(),'integrations':store.integrations()}
@app.post('/api/objectives')
def create_objective(x:Objective,req:Request):owner(req);return {'ok':True,'objective_id':operator.create_objective(x.objective,max(1,min(100,x.priority)))}
@app.get('/api/objectives/{oid}')
def objective(oid:int,req:Request):owner(req);return operator.get_objective(oid)
@app.post('/api/approvals/{aid}')
def approval(aid:int,x:Decision,req:Request):owner(req);return operator.decide_approval(aid,x.approved)
@app.get('/api/render/services')
def services(req:Request):owner(req);return render_services()
@app.post('/api/inventory')
def save_inventory(x:InventoryItem,req:Request):
 owner(req)
 if not x.product.strip():raise HTTPException(400,'Product is required')
 return {'ok':True,'item':store.inventory_upsert(x.product.strip(),x.lot.strip(),x.quantity,x.status,x.coa_status,x.notes)}
@app.delete('/api/inventory/{iid}')
def delete_inventory(iid:int,req:Request):owner(req);return store.inventory_delete(iid)
@app.post('/api/knowledge')
async def knowledge_upload(req:Request,file:UploadFile=File(...),category:str=Form('general'),tags:str=Form('')):
 owner(req);data=await file.read()
 if len(data)>25*1024*1024:raise HTTPException(413,'File exceeds 25 MB')
 return {'ok':True,'file':store.save_knowledge(file.filename or 'file',data,category,tags)}
@app.post('/api/notes')
def note(x:Note,req:Request):
 owner(req)
 if not x.title.strip() or not x.note.strip():raise HTTPException(400,'Title and note are required')
 return {'ok':True,'note':store.add_note(x.title.strip(),x.note.strip(),x.category.strip() or 'general')}
@app.get('/',response_class=HTMLResponse)
def home():return PAGE
