import os, json, urllib.request, urllib.error

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
def test_connections():
    gh=os.getenv('GITHUB_TOKEN','').strip(); owner,repo=_repo_parts(); rs=os.getenv('RENDER_API_KEY','').strip(); sid=os.getenv('RENDER_SERVICE_ID','').strip()
    gs,gd=(0,'not configured') if not gh else _request(f'https://api.github.com/repos/{owner}/{repo}',headers={'Authorization':f'Bearer {gh}','Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'Jarvis-v223'},timeout=12)
    rs_status,rd=(0,'not configured') if not rs else _request('https://api.render.com/v1/services'+(f'/{sid}' if sid else ''),headers={'Authorization':f'Bearer {rs}','Accept':'application/json'},timeout=12)
    return {'github':{'configured':bool(gh),'connected':gs==200,'status':gs,'repo':f'{owner}/{repo}','write_capable':gs==200,'detail':gd[:350]},'render':{'configured':bool(rs),'connected':rs_status==200,'status':rs_status,'service_id':sid,'detail':rd[:350]}}
def github_file(path):
    token=os.getenv('GITHUB_TOKEN','').strip(); owner,repo=_repo_parts(); branch=os.getenv('GITHUB_BRANCH','main').strip() or 'main'; url=f'https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={branch}'
    st,body=_request(url,headers={'Authorization':f'Bearer {token}','Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'Jarvis-v223'})
    try:d=json.loads(body)
    except:d={'raw':body[:2000]}
    return st,d
def github_put_file(path,content,message):
    import base64
    token=os.getenv('GITHUB_TOKEN','').strip(); owner,repo=_repo_parts(); branch=os.getenv('GITHUB_BRANCH','main').strip() or 'main'; st,existing=github_file(path); sha=existing.get('sha') if isinstance(existing,dict) and st==200 else None
    payload={'message':message,'content':base64.b64encode(content.encode()).decode(),'branch':branch}
    if sha:payload['sha']=sha
    st,body=_request(f'https://api.github.com/repos/{owner}/{repo}/contents/{path}','PUT',{'Authorization':f'Bearer {token}','Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','Content-Type':'application/json','User-Agent':'Jarvis-v223'},json.dumps(payload).encode(),30)
    try:d=json.loads(body)
    except:d={'raw':body[:2000]}
    return {'status':st,'ok':st in (200,201),'response':d}
def render_deploy(clear_cache=False):
    key=os.getenv('RENDER_API_KEY','').strip(); sid=os.getenv('RENDER_SERVICE_ID','').strip()
    if not key or not sid:return {'ok':False,'status':0,'error':'Render credentials not configured'}
    payload={'clearCache':'clear'} if clear_cache else {}; st,body=_request(f'https://api.render.com/v1/services/{sid}/deploys','POST',{'Authorization':f'Bearer {key}','Accept':'application/json','Content-Type':'application/json'},json.dumps(payload).encode(),30)
    try:d=json.loads(body)
    except:d={'raw':body[:2000]}
    return {'ok':st in (200,201,202),'status':st,'response':d}
