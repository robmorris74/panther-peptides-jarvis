import os,urllib.request
from .integrations import test_connections,github_file,github_put_file,render_deploy
from .business import inventory_rows,dashboard_summary,set_inventory_status,events
from .knowledge import search as knowledge_search,stats as knowledge_stats

def tool_specs():
 return [
 {'type':'function','function':{'name':'test_connections','description':'Test live GitHub and Render credentials.','parameters':{'type':'object','properties':{}}}},
 {'type':'function','function':{'name':'github_read_file','description':'Read a file from configured GitHub repository.','parameters':{'type':'object','properties':{'path':{'type':'string'}},'required':['path']}}},
 {'type':'function','function':{'name':'github_write_file','description':'Write/update an explicitly authorized code/config file in GitHub.','parameters':{'type':'object','properties':{'path':{'type':'string'},'content':{'type':'string'},'message':{'type':'string'}},'required':['path','content','message']}}},
 {'type':'function','function':{'name':'render_deploy','description':'Trigger Render deployment after an authorized repository change.','parameters':{'type':'object','properties':{'clear_cache':{'type':'boolean'}}}}},
 {'type':'function','function':{'name':'run_health_check','description':'Check local health and readiness endpoints.','parameters':{'type':'object','properties':{}}}},
 {'type':'function','function':{'name':'knowledge_search','description':'Search the full persistent Jarvis knowledge library.','parameters':{'type':'object','properties':{'query':{'type':'string'}},'required':['query']}}},
 {'type':'function','function':{'name':'knowledge_stats','description':'Report size and categories of the persistent Jarvis knowledge library.','parameters':{'type':'object','properties':{}}}},
 {'type':'function','function':{'name':'inventory_list','description':'Read current Panther Peptides inventory including availability, quarantine/hold status and documents.','parameters':{'type':'object','properties':{}}}},
 {'type':'function','function':{'name':'inventory_summary','description':'Read current Panther Peptides inventory summary.','parameters':{'type':'object','properties':{}}}},
 {'type':'function','function':{'name':'inventory_set_status','description':'Change an inventory lot between available, hold, and quarantine when explicitly instructed by the owner.','parameters':{'type':'object','properties':{'inventory_id':{'type':'integer'},'status':{'type':'string','enum':['available','hold','quarantine']}},'required':['inventory_id','status']}}},
 {'type':'function','function':{'name':'business_events','description':'Read recent Panther Peptides business activity.','parameters':{'type':'object','properties':{}}}},
 {'type':'function','function':{'name':'request_owner_approval','description':'Ask the owner exactly one blocking yes/no question when a decision, irreversible action, external commitment, credential change, or spend requires approval. Ask only one question at a time.','parameters':{'type':'object','properties':{'question':{'type':'string'},'action':{'type':'string'},'rationale':{'type':'string'},'estimated_cost':{'type':'number'}},'required':['question','action','rationale']}}}
 ]
def run_tool(name,args):
 if name=='test_connections':return test_connections()
 if name=='github_read_file':
  st,d=github_file(args['path']);return {'status':st,'data':d}
 if name=='github_write_file':return github_put_file(args['path'],args['content'],args['message'])
 if name=='render_deploy':return render_deploy(bool(args.get('clear_cache',False)))
 if name=='run_health_check':
  out={};port=os.getenv('PORT','8000')
  for path in ('health','health/ready'):
   try:
    with urllib.request.urlopen(f'http://127.0.0.1:{port}/{path}',timeout=4) as r:out[path]={'status':r.status,'body':r.read().decode()[:1200]}
   except Exception as e:out[path]={'status':0,'error':str(e)}
  return out
 if name=='knowledge_search':return {'query':args.get('query',''),'results':knowledge_search(args.get('query',''),12)}
 if name=='knowledge_stats':return knowledge_stats()
 if name=='inventory_list':return {'items':inventory_rows()}
 if name=='inventory_summary':return dashboard_summary()
 if name=='inventory_set_status':return set_inventory_status(int(args['inventory_id']),args['status'])
 if name=='business_events':return {'events':events()}
 if name=='request_owner_approval':raise RuntimeError('request_owner_approval must be handled by the agent runtime')
 raise ValueError('unknown tool')
