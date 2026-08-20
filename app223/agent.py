import os,json,threading,time,urllib.request,urllib.error
from .db import execute,one
from .tools import tool_specs,run_tool
_stop=threading.Event();_wake=threading.Event();_thread=None;_watchdog=None;_heartbeat=0.0;_last_loop_error='';_last_model_error='';_active_model=''
def _beat():
 global _heartbeat;_heartbeat=time.time()
def log(oid,event,detail='',level='info'):
 try:execute('INSERT INTO activity(objective_id,level,event,detail) VALUES(?,?,?,?)',(oid,level,event,str(detail)[:8000]))
 except Exception:pass
def create_objective(text,priority=50):
 title=text.strip().split('\n')[0][:120];oid=execute('INSERT INTO objectives(title,detail,state,priority,max_steps) VALUES(?,?,?,?,?)',(title,text,'queued',priority,int(os.getenv('JARVIS_MAX_STEPS','30'))));log(oid,'objective_created',text);_wake.set();return oid
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
 key=os.getenv('OPENAI_API_KEY','').strip();req=urllib.request.Request('https://api.openai.com/v1/chat/completions',data=json.dumps(payload).encode(),headers={'Authorization':f'Bearer {key}','Content-Type':'application/json','User-Agent':'Jarvis-v227'})
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
 rows=execute("SELECT action,payload,status FROM approvals WHERE objective_id=? AND status IN ('approved','denied') ORDER BY id ASC",(oid,),True)
 if not rows:return ''
 return '\nOWNER DECISIONS ALREADY MADE FOR THIS OBJECTIVE:\n'+json.dumps(rows)[:12000]
def _queue_approval(oid,args):
 pending=one("SELECT * FROM approvals WHERE objective_id=? AND status='pending' ORDER BY id ASC LIMIT 1",(oid,))
 if pending:return pending['id']
 payload={'question':str(args.get('question') or 'Approve this action?')[:1000],'rationale':str(args.get('rationale') or '')[:3000],'estimated_cost':args.get('estimated_cost')}
 aid=execute('INSERT INTO approvals(objective_id,action,payload,status) VALUES(?,?,?,?)',(oid,str(args.get('action') or 'owner_decision')[:500],json.dumps(payload),'pending'))
 execute("UPDATE objectives SET state='awaiting_approval',blocked_reason='owner_approval',updated_at=CURRENT_TIMESTAMP WHERE id=?",(oid,));log(oid,'approval_requested',json.dumps({'approval_id':aid,**payload}));return aid
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
 oid=oj['id'];_beat();system='''You are Jarvis v227, the persistent chief operating and strategy agent for Panther Peptides. Your job is to turn owner objectives into executable business strategy and then carry out every safe action available through your tools. Work autonomously: diagnose, research available knowledge, plan, prioritize, act, observe, verify, adapt, and continue until the objective is genuinely complete. Do not repeatedly ask the owner for information you can discover, infer safely, or postpone. Keep knowledge separate from authority. Never claim success without verification. When an owner decision is genuinely required, call request_owner_approval with exactly ONE concise yes/no question, the proposed action, rationale, and estimated cost when relevant. Stop immediately after creating that approval. Never bundle multiple questions into one approval. On resume, honor the recorded approval or denial and continue the strategy. External commitments, credential/security changes, irreversible/high-impact actions and spending require explicit approval unless a future authority policy explicitly authorizes them. Do not evade laws, platform controls, payment restrictions, or research-use-only requirements.'''
 messages=[{'role':'system','content':system+_approval_context(oid)},{'role':'user','content':oj['detail']}];execute("UPDATE objectives SET state='running',last_error=NULL,blocked_reason=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=?",(oid,))
 for step in range(1,int(oj.get('max_steps') or 30)+1):
  _beat();execute('UPDATE objectives SET step=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',(step,oid));log(oid,'cycle_started',f'cycle {step}')
  try:out=_model_call(messages,tool_specs())
  except Exception as e:
   msg=str(e);reason=msg.split(':',1)[0] if ':' in msg else 'model_error';log(oid,reason,msg,'error');execute("UPDATE objectives SET state='blocked',last_error=?,blocked_reason=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(msg[:4000],reason[:120],oid));return
  if out['tool_calls']:
   messages.append({'role':'assistant','content':out['content'],'tool_calls':out['tool_calls']})
   for tc in out['tool_calls']:
    try:args=json.loads(tc['function'].get('arguments') or '{}')
    except Exception:args={}
    name=tc['function']['name']
    if name=='request_owner_approval':
     aid=_queue_approval(oid,args);messages.append({'role':'tool','tool_call_id':tc['id'],'content':json.dumps({'approval_id':aid,'status':'pending'})});return
    try:result=run_tool(name,args);log(oid,'tool_result',json.dumps(result)[:6000])
    except Exception as e:result={'error':str(e)};log(oid,'tool_error',str(e),'error')
    messages.append({'role':'tool','tool_call_id':tc['id'],'content':json.dumps(result)})
   continue
  text=(out['content'] or '').strip() or 'Objective completed.';log(oid,'agent_result',text);execute("UPDATE objectives SET state='completed',completed_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE id=?",(oid,));return
 execute("UPDATE objectives SET state='blocked',blocked_reason='max_steps_exhausted',updated_at=CURRENT_TIMESTAMP WHERE id=?",(oid,))
def _loop():
 global _last_loop_error;_beat()
 while not _stop.is_set():
  _beat()
  try:
   oj=_claim()
   if oj:_run(oj)
   else:_wake.wait(3);_wake.clear()
  except Exception as e:_last_loop_error=str(e)[:1000];time.sleep(1.5)
def start():
 global _thread,_watchdog
 try:execute("UPDATE objectives SET state='queued',updated_at=CURRENT_TIMESTAMP WHERE state IN ('planning','running')")
 except Exception:pass
 _stop.clear();_beat()
 if not _thread or not _thread.is_alive():_thread=threading.Thread(target=_loop,name='jarvis227-supervisor',daemon=True);_thread.start()
 if not _watchdog or not _watchdog.is_alive():
  def wd():
   global _thread
   while not _stop.wait(5):
    if not _thread or not _thread.is_alive():_thread=threading.Thread(target=_loop,name='jarvis227-supervisor',daemon=True);_thread.start()
  _watchdog=threading.Thread(target=wd,name='jarvis227-watchdog',daemon=True);_watchdog.start()
def wake():_wake.set();return status()
def status():
 try:q=one("SELECT COUNT(*) n FROM objectives WHERE state='queued'")['n'];r=one("SELECT COUNT(*) n FROM objectives WHERE state IN ('planning','running')")['n'];b=one("SELECT COUNT(*) n FROM objectives WHERE state='blocked'")['n'];a=one("SELECT COUNT(*) n FROM objectives WHERE state='awaiting_approval'")['n'];c=one("SELECT COUNT(*) n FROM objectives WHERE state='completed'")['n'];db_ok=True
 except Exception:q=r=b=a=c=0;db_ok=False
 return {'worker_alive':bool(_thread and _thread.is_alive()),'watchdog_alive':bool(_watchdog and _watchdog.is_alive()),'heartbeat_age_seconds':round(max(0,time.time()-_heartbeat),1) if _heartbeat else None,'queued':q,'running':r,'blocked':b,'awaiting_approval':a,'completed':c,'database_ok':db_ok,'last_loop_error':_last_loop_error,'model':model_status(False)}
