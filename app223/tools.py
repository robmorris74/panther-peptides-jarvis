import os,urllib.request
from .integrations import test_connections
from .business import inventory_rows,dashboard_summary,set_inventory_status,events
from .knowledge import search as knowledge_search,stats as knowledge_stats
from .authority import status as authority_status,execute_authorized_spend
from .self_engineering import start_release,read_file as engineering_read,write_file as engineering_write,write_protected_file as engineering_write_protected,diff as engineering_diff,run_ci as engineering_run_ci,status as engineering_status,deploy_staging,verify_staging,promote,verify_production,list_releases

def tool_specs():
 return [
 {'type':'function','function':{'name':'test_connections','description':'Test live GitHub and Render credentials.','parameters':{'type':'object','properties':{}}}},
 {'type':'function','function':{'name':'engineering_start_release','description':'Create an isolated Jarvis self-engineering candidate branch from current production. Use before any self-code change.','parameters':{'type':'object','properties':{'summary':{'type':'string'}},'required':['summary']}}},
 {'type':'function','function':{'name':'engineering_read_file','description':'Read a source/config file from an isolated engineering release.','parameters':{'type':'object','properties':{'release_id':{'type':'integer'},'path':{'type':'string'}},'required':['release_id','path']}}},
 {'type':'function','function':{'name':'engineering_write_file','description':'Write a non-protected file only to an isolated engineering branch. Never writes directly to production/main.','parameters':{'type':'object','properties':{'release_id':{'type':'integer'},'path':{'type':'string'},'content':{'type':'string'},'message':{'type':'string'}},'required':['release_id','path','content','message']}}},
 {'type':'function','function':{'name':'engineering_write_protected_file','description':'Write a protected engineering file only after owner approval for action edit_protected_release:<release_id>:<path>. Still writes only to the isolated release branch.','parameters':{'type':'object','properties':{'release_id':{'type':'integer'},'path':{'type':'string'},'content':{'type':'string'},'message':{'type':'string'}},'required':['release_id','path','content','message']}}},
 {'type':'function','function':{'name':'engineering_diff','description':'Inspect all changes and protected-file risk for a release.','parameters':{'type':'object','properties':{'release_id':{'type':'integer'}},'required':['release_id']}}},
 {'type':'function','function':{'name':'engineering_run_ci','description':'Run compile/import/tests/deployment-contract release gate.','parameters':{'type':'object','properties':{'release_id':{'type':'integer'}},'required':['release_id']}}},
 {'type':'function','function':{'name':'engineering_status','description':'Read release, CI and diff status. Use after CI and engineering mutations.','parameters':{'type':'object','properties':{'release_id':{'type':'integer'}},'required':['release_id']}}},
 {'type':'function','function':{'name':'engineering_deploy_staging','description':'Deploy a CI-passed candidate commit to the separately configured Render staging service.','parameters':{'type':'object','properties':{'release_id':{'type':'integer'}},'required':['release_id']}}},
 {'type':'function','function':{'name':'engineering_verify_staging','description':'Verify staging health/readiness after candidate deployment.','parameters':{'type':'object','properties':{'release_id':{'type':'integer'}},'required':['release_id']}}},
 {'type':'function','function':{'name':'engineering_promote','description':'Promote a staging-verified release to main and production. Requires explicit owner approval; protected releases require an additional approval.','parameters':{'type':'object','properties':{'release_id':{'type':'integer'}},'required':['release_id']}}},
 {'type':'function','function':{'name':'engineering_verify_production','description':'Verify public production health/readiness after promotion.','parameters':{'type':'object','properties':{'release_id':{'type':'integer'}},'required':['release_id']}}},
 {'type':'function','function':{'name':'engineering_list_releases','description':'List recent Jarvis self-engineering releases.','parameters':{'type':'object','properties':{}}}},
 {'type':'function','function':{'name':'knowledge_search','description':'Search persistent Panther knowledge.','parameters':{'type':'object','properties':{'query':{'type':'string'}},'required':['query']}}},
 {'type':'function','function':{'name':'knowledge_stats','description':'Report persistent knowledge statistics.','parameters':{'type':'object','properties':{}}}},
 {'type':'function','function':{'name':'authority_status','description':'Read Jarvis authority and spending limits.','parameters':{'type':'object','properties':{}}}},
 {'type':'function','function':{'name':'inventory_list','description':'Read current inventory.','parameters':{'type':'object','properties':{}}}},
 {'type':'function','function':{'name':'inventory_summary','description':'Read inventory summary.','parameters':{'type':'object','properties':{}}}},
 {'type':'function','function':{'name':'inventory_set_status','description':'Change an inventory lot status when explicitly instructed.','parameters':{'type':'object','properties':{'inventory_id':{'type':'integer'},'status':{'type':'string','enum':['available','hold','quarantine']}},'required':['inventory_id','status']}}},
 {'type':'function','function':{'name':'business_events','description':'Read recent business activity.','parameters':{'type':'object','properties':{}}}},
 {'type':'function','function':{'name':'request_owner_approval','description':'Ask exactly one blocking yes/no question. For engineering use exact actions edit_protected_release:<release_id>:<path>, promote_engineering_release:<release_id>, or promote_protected_release:<release_id>. Every spend also requires approval.','parameters':{'type':'object','properties':{'question':{'type':'string'},'action':{'type':'string'},'rationale':{'type':'string'},'estimated_cost':{'type':'number','maximum':300}},'required':['question','action','rationale']}}},
 {'type':'function','function':{'name':'execute_approved_spend','description':'Execute a previously owner-approved purchase up to $300.','parameters':{'type':'object','properties':{'objective_id':{'type':'integer'},'vendor':{'type':'string'},'purpose':{'type':'string'},'amount':{'type':'number','exclusiveMinimum':0,'maximum':300},'currency':{'type':'string'}},'required':['objective_id','vendor','purpose','amount']}}}
 ]
def run_tool(name,args):
 if name=='test_connections':return test_connections()
 if name=='engineering_start_release':return start_release(args['summary'],args.get('objective_id'))
 if name=='engineering_read_file':return engineering_read(int(args['release_id']),args['path'])
 if name=='engineering_write_file':return engineering_write(int(args['release_id']),args['path'],args['content'],args['message'])
 if name=='engineering_write_protected_file':return engineering_write_protected(int(args['release_id']),args['path'],args['content'],args['message'])
 if name=='engineering_diff':return engineering_diff(int(args['release_id']))
 if name=='engineering_run_ci':return engineering_run_ci(int(args['release_id']))
 if name=='engineering_status':return engineering_status(int(args['release_id']))
 if name=='engineering_deploy_staging':return deploy_staging(int(args['release_id']))
 if name=='engineering_verify_staging':return verify_staging(int(args['release_id']))
 if name=='engineering_promote':return promote(int(args['release_id']))
 if name=='engineering_verify_production':return verify_production(int(args['release_id']))
 if name=='engineering_list_releases':return {'ok':True,'releases':list_releases()}
 if name=='knowledge_search':return {'query':args.get('query',''),'results':knowledge_search(args.get('query',''),20)}
 if name=='knowledge_stats':return knowledge_stats()
 if name=='authority_status':return authority_status()
 if name=='inventory_list':return {'items':inventory_rows()}
 if name=='inventory_summary':return dashboard_summary()
 if name=='inventory_set_status':return set_inventory_status(int(args['inventory_id']),args['status'])
 if name=='business_events':return {'events':events()}
 if name=='execute_approved_spend':return execute_authorized_spend(int(args['objective_id']),str(args['vendor']),str(args['purpose']),float(args['amount']),str(args.get('currency') or 'USD'))
 if name=='request_owner_approval':raise RuntimeError('request_owner_approval must be handled by the agent runtime')
 raise ValueError('unknown tool')
