import os, json, urllib.request, urllib.error, urllib.parse

def _request(url,method='GET',headers=None,data=None,timeout=20):
    req=urllib.request.Request(url,data=data,headers=headers or {},method=method)
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r:return r.status,r.read().decode('utf-8','replace')
    except urllib.error.HTTPError as e:return e.code,e.read().decode('utf-8','replace')
    except Exception as e:return 0,str(e)
def _repo_parts():
    owner=os.getenv('GITHUB_REPO_OWNER','robmorris74').strip(); repo=os.getenv('GITHUB_REPO','panther-peptides-jarvis').strip()
    if '/' in repo: owner,repo=repo.split('/',1)
    return owner.strip(),repo.strip()
def _gh_headers():
    return {'Authorization':f"Bearer {os.getenv('GITHUB_TOKEN','').strip()}",'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','Content-Type':'application/json','User-Agent':'Jarvis-v230'}
def github_api(method,path,payload=None,timeout=30):
    owner,repo=_repo_parts();url=f'https://api.github.com/repos/{owner}/{repo}'+(('/'+path.lstrip('/')) if path else '')
    st,body=_request(url,method,_gh_headers(),None if payload is None else json.dumps(payload).encode(),timeout)
    if not body:return st,{}
    try:return st,json.loads(body)
    except:return st,{'raw':body[:4000]}
def test_connections():
    gh=os.getenv('GITHUB_TOKEN','').strip(); owner,repo=_repo_parts(); rs=os.getenv('RENDER_API_KEY','').strip(); sid=os.getenv('RENDER_SERVICE_ID','').strip();ssid=os.getenv('RENDER_STAGING_SERVICE_ID','').strip()
    gs,gd=(0,'not configured') if not gh else _request(f'https://api.github.com/repos/{owner}/{repo}',headers=_gh_headers(),timeout=12)
    rs_status,rd=(0,'not configured') if not rs else _request('https://api.render.com/v1/services'+(f'/{sid}' if sid else ''),headers={'Authorization':f'Bearer {rs}','Accept':'application/json'},timeout=12)
    return {'github':{'configured':bool(gh),'connected':gs==200,'status':gs,'repo':f'{owner}/{repo}','write_capable':gs==200,'detail':gd[:350]},'render':{'configured':bool(rs),'connected':rs_status==200,'status':rs_status,'service_id':sid,'staging_service_id':ssid,'staging_configured':bool(ssid),'detail':rd[:350]}}
def github_file_at(path,branch):
    st,d=github_api('GET',f'contents/{urllib.parse.quote(path,safe="/")}?ref={urllib.parse.quote(branch,safe="")}')
    return st,d
def github_file(path):
    return github_file_at(path,os.getenv('GITHUB_BRANCH','main').strip() or 'main')
def github_put_file_at(path,content,message,branch):
    import base64
    st,existing=github_file_at(path,branch);sha=existing.get('sha') if isinstance(existing,dict) and st==200 else None
    payload={'message':message,'content':base64.b64encode(content.encode()).decode(),'branch':branch}
    if sha:payload['sha']=sha
    st,d=github_api('PUT',f'contents/{urllib.parse.quote(path,safe="/")}',payload)
    return {'status':st,'ok':st in (200,201),'response':d}
def github_put_file(path,content,message):
    return github_put_file_at(path,content,message,os.getenv('GITHUB_BRANCH','main').strip() or 'main')
def github_create_branch(branch,sha):
    st,d=github_api('POST','git/refs',{'ref':f'refs/heads/{branch}','sha':sha});return {'ok':st in (200,201),'status':st,'response':d}
def github_compare(base,head):
    st,d=github_api('GET',f'compare/{urllib.parse.quote(base,safe="")}...{urllib.parse.quote(head,safe="/")}')
    if st!=200:return {'ok':False,'status':st,'response':d}
    return {'ok':True,'status':st,'ahead_by':d.get('ahead_by'),'behind_by':d.get('behind_by'),'status_text':d.get('status'),'files':d.get('files') or [],'commits':d.get('commits') or []}
def github_workflow_runs(branch,workflow_name=None):
    q=urllib.parse.urlencode({'branch':branch,'per_page':10});st,d=github_api('GET','actions/runs?'+q)
    runs=(d.get('workflow_runs') or []) if isinstance(d,dict) else []
    if workflow_name:runs=[r for r in runs if r.get('name')==workflow_name]
    return {'ok':st==200,'status':st,'workflow_runs':runs}
def _render_headers():return {'Authorization':f"Bearer {os.getenv('RENDER_API_KEY','').strip()}",'Accept':'application/json','Content-Type':'application/json'}
def render_service(service_id):
    if not service_id:return {'ok':False,'error':'service id not configured'}
    st,b=_request(f'https://api.render.com/v1/services/{service_id}',headers=_render_headers(),timeout=20)
    try:d=json.loads(b)
    except:d={'raw':b[:3000]}
    return {'ok':st==200,'status':st,'response':d}
def render_deploy_commit(service_id,commit_id,clear_cache=False):
    if not os.getenv('RENDER_API_KEY','').strip() or not service_id:return {'ok':False,'status':0,'error':'Render credentials/service not configured'}
    payload={'clearCache':'clear' if clear_cache else 'do_not_clear','commitId':commit_id};st,b=_request(f'https://api.render.com/v1/services/{service_id}/deploys','POST',_render_headers(),json.dumps(payload).encode(),30)
    try:d=json.loads(b)
    except:d={'raw':b[:3000]}
    return {'ok':st in (200,201,202),'status':st,'response':d}
def render_deploy(clear_cache=False):
    return render_deploy_commit(os.getenv('RENDER_SERVICE_ID','').strip(),None,clear_cache) if False else _legacy_render_deploy(clear_cache)
def _legacy_render_deploy(clear_cache=False):
    key=os.getenv('RENDER_API_KEY','').strip();sid=os.getenv('RENDER_SERVICE_ID','').strip()
    if not key or not sid:return {'ok':False,'status':0,'error':'Render credentials not configured'}
    payload={'clearCache':'clear'} if clear_cache else {};st,b=_request(f'https://api.render.com/v1/services/{sid}/deploys','POST',_render_headers(),json.dumps(payload).encode(),30)
    try:d=json.loads(b)
    except:d={'raw':b[:2000]}
    return {'ok':st in (200,201,202),'status':st,'response':d}
def public_health(base_url):
    out={};ok=True
    for path in ('health','health/ready'):
        try:
            with urllib.request.urlopen(base_url.rstrip('/')+'/'+path,timeout=15) as r:
                body=r.read().decode('utf-8','replace');out[path]={'status':r.status,'body':body[:3000]};ok=ok and r.status==200
        except Exception as e:out[path]={'status':0,'error':str(e)};ok=False
    return {'ok':ok,'url':base_url,'checks':out}
