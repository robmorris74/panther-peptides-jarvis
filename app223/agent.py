import os,json,threading,time,urllib.request,urllib.error
from .db import execute,one
from .tools import tool_specs,run_tool

_stop=threading.Event();_wake=threading.Event();_thread=None;_watchdog=None
_heartbeat=0.0;_last_loop_error='';_last_model_error='';_active_model='';_current_objective=None
READ_ONLY_TOOLS={'test_connections','knowledge_search','knowledge_stats','authority_status','inventory_list','inventory_summary','business_events','engineering_read_file','engineering_diff','engineering_status','engineering_verify_staging','engineering_verify_production','engineering_list_releases'}
MUTATING_TOOLS={'inventory_set_status','execute_approved_spend','engineering_start_release','engineering_write_file','engineering_write_protected_file','engineering_run_ci','engineering_deploy_staging','engineering_promote'}

def _beat():
 global _heartbeat;_heartbeat=time.time()
def log(oid,event,detail='',level='info'):
 try:execute('INSERT INTO activity(objective_id,level,event,detail) VALUES(?,?,?,?)',(oid,level,event,str(detail)[:8000]))
 except Exception:pass
def _ensure_agent_schema():
 execute('''CREATE TABLE IF NOT EXISTS objective_steps(id INTEGER PRIMARY KEY AUTOINCREMENT,objective_id INTEGER NOT NULL,cycle INTEGER NOT NULL,kind TEXT NOT NULL,tool_name TEXT,status TEXT NOT NULL,detail TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP)''');execute('CREATE INDEX IF NOT EXISTS idx_objective_steps_objective ON objective_steps(objective_id,id DESC)')
def _step(oid,cycle,kind,status,detail='',tool_name=None):
 try:execute('INSERT INTO objective_steps(objective_id,cycle,kind,tool_name,status,detail) VALUES(?,?,?,?,?,?)',(oid,cycle,kind,tool_name,status,str(detail)[:12000]))
 except Exception:pass
def create_objective(text,priority=50):
 _ensure_agent_schema();title=text.strip().split('\n')[0][:120];oid=execute('INSERT INTO objectives(title,detail,state,priority,max_steps) VALUES(?,?,?,?,?)',(title,text,'queued',priority,int(os.getenv('JARVIS_MAX_STEPS','60'))));log(oid,'objective_created',text);_step(oid,0,'objective','queued',text);_wake.set();return oid
def _models():
 raw=[os.getenv('JARVIS_MODEL','').strip(),os.getenv('JARVIS_MODEL_FALLBACK','gpt-5-mini').strip(),'gpt-5-mini'];out=[]
 for m in raw:
  if m and m not in out:out.append(m)
 return out
def _classify_http(code,body):
 low=(body or '').lower()
 if code in (401,403):return 'model_auth_error'
 if code==429:return 'model_rate_limit'
 if code==404 or ('model' in low and ('not found' in low or 'does not exist' in low or 'access' in low)):return 'model_unavailable'
 if code==400:return 'model_request_error'
 if code>=500:return 'model_provider_error'
 return 'model_error'
def _chat_request(model,messages,tools=None,timeout=120):
 payload={'model':model,'messages':messages}
 if tools:payload['tools']=tools;payload['tool_choice']='auto'
 key=os.getenv('OPENAI_API_KEY','').strip();req=urllib.request.Request('https://api.openai.com/v1/chat/completions',data=json.dumps(payload).encode(),headers={'Authorization':f'Bearer {key}','Content-Type':'application/json','User-Agent':'Jarvis-v230'})
 with urllib.request.urlopen(req,timeout=timeout) as r:
  data=json.loads(r.read());m=data['choices'][0]['message'];return {'content':m.get('content') or '','tool_calls':m.get('tool_calls') or [],'model':data.get('model') or model}
def _model_call(messages,tools=None):
 global _last_model_error,_active_model
 if not os.getenv('OPENAI_API_KEY','').strip():_last_model_error='OPENAI_API_KEY is not configured';raise RuntimeError('model_auth_error: OPENAI_API_KEY is not configured')
 errors=[]
 for model in _models():
  for attempt in range(3):
   try:out=_chat_request(model,messages,tools);_active_model=out.get('model') or model;_last_model_error='';return out
   except urllib.error.HTTPError as e:
    body=e.read().decode('utf-8','replace')[:3000];kind=_classify_http(e.code,body);msg=f'{kind}: OpenAI HTTP {e.code} using {model}: {body}';errors.append(msg);_last_model_error=msg
    if e.code in (429,500,502,503,504) and attempt<2:time.sleep(min(8,2**attempt));continue
    if kind=='model_auth_error':raise RuntimeError(msg)
    break
   except Exception as e:
    msg=f'model_transport_error using {model}: {e}';errors.append(msg);_last_model_error=msg
    if attempt<2:time.sleep(min(8,2**attempt));continue
    break
 raise RuntimeError(errors[-1] if errors else 'model request failed')
def model_status(probe=False):
 base={'configured':bool(os.getenv('OPENAI_API_KEY','').strip()),'models':_models(),'active_model':_active_model or None,'last_error':_last_model_error or None}
 if not probe or not base['configured']:return base
 try:out=_model_call([{'role':'user','content':'Reply with exactly: JARVIS_MODEL_OK'}]);base.update({'ok':True,'active_model':out.get('model'),'probe_text':out.get('content','')[:120]})
 except Exception as e:base.update({'ok':False,'last_error':str(e)[:3000]})
 return base
def _claim():
 row=one("SELECT * FROM objectives WHERE state='queued' ORDER BY priority DESC,id ASC LIMIT 1")
 if not row:return None
 execute("UPDATE objectives SET state='planning',updated_at=CURRENT_TIMESTAMP WHERE id=? AND state='queued'",(row['id'],));return one('SELECT * FROM objectives WHERE id=?',(row['id'],))
def _approval_context(oid):
 rows=execute("SELECT id,action,payload,status FROM approvals WHERE objective_id=? AND status IN ('approved','denied') ORDER BY id ASC",(oid,),True);return '' if not rows else '\nOWNER DECISIONS ALREADY MADE FOR THIS OBJECTIVE:\n'+json.dumps(rows)[:16000]
def _queue_approval(oid,args):
 pending=one("SELECT * FROM approvals WHERE objective_id=? AND status='pending' ORDER BY id ASC LIMIT 1",(oid,))
 if pending:return pending['id']
 cost=args.get('estimated_cost')
 if cost is not None and float(cost)>300:raise ValueError('Jarvis cannot request or execute a transaction above $300')
 payload={'question':str(args.get('question') or 'Approve this action?')[:1000],'rationale':str(args.get('rationale') or '')[:3000],'estimated_cost':cost};aid=execute('INSERT INTO approvals(objective_id,action,payload,status) VALUES(?,?,?,?)',(oid,str(args.get('action') or 'owner_decision')[:500],json.dumps(payload),'pending'));execute("UPDATE objectives SET state='awaiting_approval',blocked_reason='owner_approval',updated_at=CURRENT_TIMESTAMP WHERE id=?",(oid,));log(oid,'approval_requested',json.dumps({'approval_id':aid,**payload}));return aid
def decide_approval(aid,approved):
 row=one("SELECT * FROM approvals WHERE id=? AND status='pending'",(aid,))
 if not row:raise ValueError('Pending approval not found')
 state='approved' if approved else 'denied';execute("UPDATE approvals SET status=?,decided_at=CURRENT_TIMESTAMP WHERE id=?",(state,aid));execute("UPDATE objectives SET state='queued',blocked_reason=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=?",(row['objective_id'],));log(row['objective_id'],'approval_decided',json.dumps({'approval_id':aid,'decision':state,'action':row['action']}));_wake.set();return {'ok':True,'approval_id':aid,'decision':state,'objective_id':row['objective_id']}
def pending_approval():
 row=one("SELECT a.*,o.title objective_title FROM approvals a LEFT JOIN objectives o ON o.id=a.objective_id WHERE a.status='pending' ORDER BY a.id ASC LIMIT 1")
 if not row:return None
 try:row['payload']=json.loads(row.get('payload') or '{}')
 except:row['payload']={'question':row.get('payload') or 'Approve this action?'}
 return row
def _run(oj):
 global _current_objective
 oid=oj['id'];_current_objective=oid;_beat();_ensure_agent_schema()
 system='''You are Jarvis v230, Panther Peptides' execution-first autonomous operating and self-engineering agent. An objective is a job to perform, not a question to answer.

For ordinary operations: inspect, act, verify, continue. Prose is not completion.

SELF-ENGINEERING POLICY: Never modify your production/main source directly and never use legacy direct-write/deploy patterns. For any request to repair, upgrade, refactor or improve Jarvis itself: (1) create exactly one engineering release with engineering_start_release, (2) inspect relevant files on that release, (3) make all code changes only on that isolated release, (4) inspect engineering_diff, (5) run engineering_run_ci and poll engineering_status until CI completes, repairing the candidate if CI fails, (6) deploy only a CI-passed candidate to staging, (7) verify staging, (8) request owner approval using action promote_engineering_release:<release_id>; if protected files are in the diff also request promote_protected_release:<release_id>, (9) promote only after approval, and (10) verify production. Do not call production complete before engineering_verify_production succeeds.

PROTECTED ENGINEERING: security, authority, self-engineering controller, release workflow, Render config and production Dockerfile are protected. To change one, first request owner approval using exact action edit_protected_release:<release_id>:<path>. After approval use engineering_write_protected_file. Protected-file edit approval is not production-promotion approval.

If staging is not configured, stop with the exact missing RENDER_STAGING_SERVICE_ID/JARVIS_STAGING_URL dependency; never substitute production for staging. If CI or staging fails, repair the candidate and retry rather than promoting it.

AUTHORITY: external commitments, credentials/security changes, irreversible/high-impact actions and every spend require owner approval. Spending is capped at $300 per transaction and may not be split to evade the cap. Products are FOR RESEARCH USE ONLY, NOT FOR HUMAN OR VETERINARY USE. Never execute evasion, concealment, misrepresentation, human-use positioning, medical claims, regulatory circumvention or platform/payment bypasses.

OWNER EXPERIENCE: continue autonomously until genuinely blocked. Ask one concise blocking approval question only when required. Never claim success without verification.'''
 messages=[{'role':'system','content':system+_approval_context(oid)},{'role':'user','content':oj['detail']}];execute("UPDATE objectives SET state='running',last_error=NULL,blocked_reason=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=?",(oid,));log(oid,'execution_started','Jarvis v230 controlled self-engineering runtime started');_step(oid,0,'runtime','running','v230 controlled self-engineering runtime');mutation_successes=0;verification_after_mutation=False;no_action_turns=0;max_steps=int(oj.get('max_steps') or 60)
 for cycle in range(1,max_steps+1):
  _beat();execute('UPDATE objectives SET step=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',(cycle,oid))
  try:out=_model_call(messages,tool_specs())
  except Exception as e:
   msg=str(e);reason=msg.split(':',1)[0] if ':' in msg else 'model_error';execute("UPDATE objectives SET state='blocked',last_error=?,blocked_reason=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(msg[:4000],reason[:120],oid));log(oid,reason,msg,'error');_current_objective=None;return
  calls=out.get('tool_calls') or []
  if calls:
   no_action_turns=0;messages.append({'role':'assistant','content':out.get('content') or '','tool_calls':calls})
   for tc in calls:
    try:args=json.loads(tc['function'].get('arguments') or '{}')
    except Exception:args={}
    name=tc['function']['name'];_step(oid,cycle,'tool','started',json.dumps(args)[:4000],name)
    if name=='request_owner_approval':
     try:aid=_queue_approval(oid,args);_step(oid,cycle,'approval','pending',json.dumps({'approval_id':aid,**args})[:6000],name)
     except Exception as e:messages.append({'role':'tool','tool_call_id':tc['id'],'content':json.dumps({'error':str(e)})});continue
     messages.append({'role':'tool','tool_call_id':tc['id'],'content':json.dumps({'approval_id':aid,'status':'pending'})});_current_objective=None;return
    try:
     if name=='execute_approved_spend':args['objective_id']=oid
     if name=='engineering_start_release':args['objective_id']=oid
     result=run_tool(name,args);ok=not (isinstance(result,dict) and (result.get('ok') is False or result.get('error')))
     if ok:
      if name in MUTATING_TOOLS:mutation_successes+=1;verification_after_mutation=False
      elif mutation_successes>0 and name in READ_ONLY_TOOLS:verification_after_mutation=True
     _step(oid,cycle,'tool','success' if ok else 'failed',json.dumps(result)[:10000],name);log(oid,'tool_result',json.dumps({'tool':name,'result':result})[:8000],'info' if ok else 'error')
    except Exception as e:result={'error':str(e)};_step(oid,cycle,'tool','error',str(e),name);log(oid,'tool_error',str(e),'error')
    messages.append({'role':'tool','tool_call_id':tc['id'],'content':json.dumps(result)})
   continue
  text=(out.get('content') or '').strip()
  if mutation_successes==0:
   no_action_turns+=1
   if no_action_turns>=3:execute("UPDATE objectives SET state='blocked',last_error=?,blocked_reason='no_executable_action',updated_at=CURRENT_TIMESTAMP WHERE id=?",((text or 'No executable action')[:4000],oid));_current_objective=None;return
   messages.extend([{'role':'assistant','content':text},{'role':'user','content':'Do not finish with prose. Use the available tools to execute the objective or verify the exact missing dependency.'}]);continue
  if not verification_after_mutation:
   messages.extend([{'role':'assistant','content':text},{'role':'user','content':'A mutation succeeded but has not been verified. Use the appropriate status/read/health tool before finishing.'}]);continue
  final=text or 'Objective completed and verified.';log(oid,'agent_result',final);_step(oid,cycle,'objective','completed',final);execute("UPDATE objectives SET state='completed',completed_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE id=?",(oid,));_current_objective=None;return
 execute("UPDATE objectives SET state='blocked',blocked_reason='max_steps_exhausted',updated_at=CURRENT_TIMESTAMP WHERE id=?",(oid,));_current_objective=None
def _loop():
 global _last_loop_error;_beat();_ensure_agent_schema()
 while not _stop.is_set():
  _beat()
  try:
   oj=_claim()
   if oj:_run(oj)
   else:_wake.wait(2);_wake.clear()
  except Exception as e:_last_loop_error=str(e)[:1000];time.sleep(1.5)
def start():
 global _thread,_watchdog
 _ensure_agent_schema()
 try:execute("UPDATE objectives SET state='queued',updated_at=CURRENT_TIMESTAMP WHERE state IN ('planning','running')")
 except Exception:pass
 _stop.clear();_beat()
 if not _thread or not _thread.is_alive():_thread=threading.Thread(target=_loop,name='jarvis230-executor',daemon=True);_thread.start()
 if not _watchdog or not _watchdog.is_alive():
  def wd():
   global _thread
   while not _stop.wait(5):
    if not _thread or not _thread.is_alive():_thread=threading.Thread(target=_loop,name='jarvis230-executor',daemon=True);_thread.start()
  _watchdog=threading.Thread(target=wd,name='jarvis230-watchdog',daemon=True);_watchdog.start()
def wake():_wake.set();return status()
def status():
 try:q=one("SELECT COUNT(*) n FROM objectives WHERE state='queued'")['n'];r=one("SELECT COUNT(*) n FROM objectives WHERE state IN ('planning','running')")['n'];b=one("SELECT COUNT(*) n FROM objectives WHERE state='blocked'")['n'];a=one("SELECT COUNT(*) n FROM objectives WHERE state='awaiting_approval'")['n'];c=one("SELECT COUNT(*) n FROM objectives WHERE state='completed'")['n'];db_ok=True
 except Exception:q=r=b=a=c=0;db_ok=False
 return {'worker_alive':bool(_thread and _thread.is_alive()),'watchdog_alive':bool(_watchdog and _watchdog.is_alive()),'heartbeat_age_seconds':round(max(0,time.time()-_heartbeat),1) if _heartbeat else None,'current_objective':_current_objective,'queued':q,'running':r,'blocked':b,'awaiting_approval':a,'completed':c,'database_ok':db_ok,'last_loop_error':_last_loop_error,'model':model_status(False),'runtime':'controlled_self_engineering_v230'}
