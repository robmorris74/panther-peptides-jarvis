import os,secrets,hmac,hashlib,time
from pathlib import Path
from fastapi import FastAPI,Request,HTTPException,UploadFile,File,Form
from fastapi.responses import HTMLResponse,JSONResponse,FileResponse
from pydantic import BaseModel
from . import operator,store,attachments
from .ops import list_tasks,render_services
from .ui import PAGE
VERSION='3.3.0-business-os.243';RELEASE='BUSINESS-OS-243';DATA=Path(os.getenv('JARVIS3_DATA_DIR','/app/data'));DATA.mkdir(parents=True,exist_ok=True);SECRET_FILE=DATA/'jarvis3_session_secret'
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
class InventoryItem(BaseModel):product:str;lot:str='';quantity:float=0;status:str='available';coa_status:str='unknown';unit_cost:float=0;unit_price:float=0;notes:str=''
class Note(BaseModel):title:str;note:str;category:str='general'
class Answer(BaseModel):answer:str
class Order(BaseModel):order_number:str='';order_date:str='';customer_name:str='';channel:str='manual';status:str='paid';subtotal:float=0;shipping:float=0;tax:float=0;total:float=0;cogs:float=0;notes:str=''
class CashTxn(BaseModel):txn_date:str='';type:str='expense';category:str='general';description:str='';amount:float=0;account:str='Operating';status:str='posted'
class Purchase(BaseModel):po_number:str='';supplier:str;order_date:str='';expected_date:str='';status:str='open';amount:float=0;paid:float=0;notes:str=''
class Marketing(BaseModel):metric_date:str='';channel:str;spend:float=0;revenue:float=0;leads:int=0;orders:int=0;notes:str=''
class Upgrade(BaseModel):title:str;request:str
@app.on_event('startup')
def startup():operator.start()
@app.get('/health')
def health():return {'ok':True,'service':'jarvis-business-os','version':VERSION,'release':RELEASE,'operator':operator.status()}
@app.get('/version')
def version():return {'version':VERSION,'release':RELEASE,'dashboard':'executive-business','jarvis_led':True,'typing_fix':True,'attachments':True}
@app.get('/ready')
def ready():return {'ok':bool(os.getenv('JARVIS_OWNER_PASSWORD') and os.getenv('OPENAI_API_KEY')),'version':VERSION,'release':RELEASE,'checks':{'owner_password':bool(os.getenv('JARVIS_OWNER_PASSWORD')),'openai':bool(os.getenv('OPENAI_API_KEY')),'render_key':bool(os.getenv('RENDER_API_KEY')),'github_token':bool(os.getenv('GITHUB_TOKEN')),'operator':operator.status()}}
@app.post('/api/login')
def login(x:Login):
 expected=os.getenv('JARVIS_OWNER_PASSWORD','')
 if not expected or not hmac.compare_digest(x.password,expected):raise HTTPException(401,'Invalid password')
 r=JSONResponse({'ok':True});r.set_cookie(COOKIE,session(),httponly=True,secure=os.getenv('JARVIS_COOKIE_SECURE','1')=='1',samesite='lax',max_age=2592000);return r
@app.post('/api/logout')
def logout():r=JSONResponse({'ok':True});r.delete_cookie(COOKIE);return r
@app.get('/api/dashboard')
def dashboard(req:Request):
 owner(req);return {'ok':True,'version':VERSION,'release':RELEASE,'executive':store.executive_summary(),'questions':store.questions(),'operator':operator.status(),'objectives':operator.list_objectives(),'activity':operator.list_activity(60),'approval':operator.pending_approval(),'tasks':list_tasks().get('tasks',[]),'inventory':store.inventory(),'orders':store.orders(),'cash':store.cash_transactions(),'purchases':store.purchase_orders(),'marketing':store.marketing(),'knowledge':store.knowledge(),'attachments':attachments.list_all(),'notes':store.notes(),'integrations':store.integrations(),'upgrades':store.dashboard_upgrades()}
@app.post('/api/objectives')
def create_objective(x:Objective,req:Request):owner(req);return {'ok':True,'objective_id':operator.create_objective(x.objective,max(1,min(100,x.priority)))}
@app.get('/api/objectives/{oid}')
def objective(oid:int,req:Request):owner(req);return operator.get_objective(oid)
@app.post('/api/approvals/{aid}')
def approval(aid:int,x:Decision,req:Request):owner(req);return operator.decide_approval(aid,x.approved)
@app.post('/api/questions/{qid}/answer')
def answer(qid:int,x:Answer,req:Request):owner(req);return {'ok':True,'question':store.answer_question(qid,x.answer)}
@app.post('/api/inventory')
def inv_add(x:InventoryItem,req:Request):owner(req);return {'ok':True,'item':store.inventory_upsert(x.product,x.lot,x.quantity,x.status,x.coa_status,x.notes,x.unit_cost,x.unit_price)}
@app.delete('/api/inventory/{iid}')
def inv_delete(iid:int,req:Request):owner(req);return store.inventory_delete(iid)
@app.post('/api/orders')
def order_add(x:Order,req:Request):owner(req);return {'ok':True,'order':store.add_order(x.model_dump())}
@app.post('/api/cash')
def cash_add(x:CashTxn,req:Request):owner(req);return {'ok':True,'transaction':store.add_cash(x.model_dump())}
@app.post('/api/purchases')
def po_add(x:Purchase,req:Request):owner(req);return {'ok':True,'purchase':store.add_purchase_order(x.model_dump())}
@app.post('/api/marketing')
def marketing_add(x:Marketing,req:Request):owner(req);return {'ok':True,'marketing':store.add_marketing(x.model_dump())}
@app.post('/api/knowledge')
async def knowledge_add(req:Request,file:UploadFile=File(...),category:str=Form('general'),tags:str=Form('')):
 owner(req);data=await file.read()
 if len(data)>25*1024*1024:raise HTTPException(413,'File too large')
 return {'ok':True,'file':store.save_knowledge(file.filename or 'upload',data,category,tags)}
@app.post('/api/attachments')
async def attachment_add(req:Request,files:list[UploadFile]=File(...),context_type:str=Form('general'),context_id:str=Form(''),caption:str=Form('')):
 owner(req);saved=[]
 for f in files:
  data=await f.read()
  if len(data)>50*1024*1024:raise HTTPException(413,f'{f.filename}: file exceeds 50 MB')
  saved.append(attachments.save(f.filename or 'upload',data,f.content_type or '',context_type,context_id,caption))
 return {'ok':True,'attachments':saved}
@app.get('/api/attachments/{aid}/content')
def attachment_content(aid:int,req:Request):
 owner(req);a=attachments.get(aid)
 if not a or not Path(a['path']).exists():raise HTTPException(404,'Attachment not found')
 return FileResponse(a['path'],media_type=a['mime_type'],filename=a['original_name'],content_disposition_type='inline' if attachments.is_image(a) else 'attachment')
@app.delete('/api/attachments/{aid}')
def attachment_delete(aid:int,req:Request):owner(req);return {'ok':attachments.delete(aid)}
@app.post('/api/notes')
def note_add(x:Note,req:Request):owner(req);return {'ok':True,'note':store.add_note(x.title,x.note,x.category)}
@app.post('/api/dashboard-upgrades')
def upgrade_add(x:Upgrade,req:Request):
 owner(req);u=store.request_dashboard_upgrade(x.title,x.request);operator.create_objective('Dashboard upgrade request: '+x.title+'\n'+x.request+'\nAssess the request, create implementation tasks, and if GitHub self-engineering is not connected, block with the exact connection needed.',70);return {'ok':True,'upgrade':u}
@app.get('/api/render/services')
def services(req:Request):owner(req);return render_services()
@app.get('/',response_class=HTMLResponse)
def home():
 page=PAGE.replace('BUSINESS-OS-241',RELEASE)
 old="setInterval(()=>{if(!$('app').classList.contains('hidden'))load()},5000)"
 new="setInterval(()=>{const a=document.activeElement;const typing=a&&['INPUT','TEXTAREA','SELECT'].includes(a.tagName);if(!typing&&!$('app').classList.contains('hidden'))load()},5000)"
 page=page.replace(old,new)
 oldk='<section id="knowledge" class="card hidden"><h2>Knowledge & Business Memory</h2>'
 uploader='''<section id="files" class="card hidden"><div class="sectionhead"><div><h2>Files & Pictures</h2><p class="muted">Upload business documents, spreadsheets, PDFs, photos, labels, product images, COAs and other files for Jarvis.</p></div></div><form id="attachForm" onsubmit="uploadAttachments(event)"><div class="forms"><input id="af" class="field" type="file" multiple required accept="image/*,.pdf,.doc,.docx,.xls,.xlsx,.csv,.txt,.rtf,.ppt,.pptx,.zip"><select id="actx"><option value="general">General</option><option value="question">Jarvis Question</option><option value="objective">Objective</option><option value="inventory">Inventory / Product</option><option value="supplier">Supplier</option><option value="order">Order</option><option value="marketing">Marketing</option><option value="finance">Finance</option></select><input id="acid" class="field" placeholder="Related ID or name (optional)"><input id="acap" class="field" placeholder="Tell Jarvis what this is"><button class="btn primary">Upload to Jarvis</button></div></form><div id="attachlist"></div></section>'''
 page=page.replace(oldk,uploader+oldk)
 page=page.replace('<button class="btn tab" onclick="tab(\'knowledge\',this)">Knowledge</button>','<button class="btn tab" onclick="tab(\'files\',this)">Files & Pictures</button><button class="btn tab" onclick="tab(\'knowledge\',this)">Knowledge</button>')
 page=page.replace("['executive','sales','finance','inventory','purchasing','marketing','jarvis','knowledge','systems']","['executive','sales','finance','inventory','purchasing','marketing','jarvis','files','knowledge','systems']")
 insert="""async function uploadAttachments(ev){ev.preventDefault();let f=new FormData();for(const x of $('af').files)f.append('files',x);f.append('context_type',$('actx').value);f.append('context_id',$('acid').value);f.append('caption',$('acap').value);note('Uploading files to Jarvis...');await req('/api/attachments',{method:'POST',body:f});ev.target.reset();note('Files saved to Jarvis.');load()}function renderAttachments(){if(!$('attachlist'))return;let aa=D.attachments||[];$('attachlist').innerHTML=aa.length?aa.map(a=>`<div class=\"event\"><div class=\"sectionhead\"><div><b>${esc(a.original_name)}</b><br><span class=\"muted\">${esc(a.context_type)}${a.context_id?' · '+esc(a.context_id):''} · ${(a.size_bytes/1024).toFixed(1)} KB</span><br>${a.caption?esc(a.caption):''}</div><div>${String(a.mime_type).startsWith('image/')?`<a class=\"btn\" target=\"_blank\" href=\"/api/attachments/${a.id}/content\">View Picture</a>`:`<a class=\"btn\" href=\"/api/attachments/${a.id}/content\">Open File</a>`}</div></div>${String(a.mime_type).startsWith('image/')?`<img src=\"/api/attachments/${a.id}/content\" style=\"max-width:220px;max-height:160px;margin-top:10px;border-radius:10px;border:1px solid #315779\">`:''}</div>`).join(''):'<p class=\"muted\">No files or pictures uploaded yet.</p>'}"""
 page=page.replace('async function uploadKnowledge(ev)',insert+'async function uploadKnowledge(ev)')
 page=page.replace("$('integrations').innerHTML=(D.integrations||[])","renderAttachments();$('integrations').innerHTML=(D.integrations||[])")
 return page
