import os,json,re,time,urllib.parse
from .db import execute,one
from .integrations import github_api,github_file_at,github_put_file_at,github_create_branch,github_compare,github_workflow_runs,render_deploy_commit,public_health

PROTECTED_PREFIXES=("data/",".git/",".env","secrets/","credentials/")
PROTECTED_FILES={"render.yaml","Dockerfile.render.agent","app223/security.py","app223/authority.py","app223/self_engineering.py",".github/workflows/jarvis-release.yml"}

def ensure_schema():
    execute('''CREATE TABLE IF NOT EXISTS engineering_releases(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      objective_id INTEGER,
      branch TEXT NOT NULL UNIQUE,
      base_sha TEXT NOT NULL,
      head_sha TEXT NOT NULL,
      state TEXT NOT NULL DEFAULT 'draft',
      summary TEXT,
      ci_state TEXT,
      staging_state TEXT,
      production_state TEXT,
      staging_deploy_id TEXT,
      production_deploy_id TEXT,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
      promoted_at TEXT
    )''')
    execute('''CREATE TABLE IF NOT EXISTS engineering_events(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      release_id INTEGER,
      event TEXT NOT NULL,
      detail TEXT,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')

def _event(rid,event,detail=''):
    execute('INSERT INTO engineering_events(release_id,event,detail) VALUES(?,?,?)',(rid,event,str(detail)[:12000]))

def _safe_path(path):
    p=(path or '').strip().lstrip('/')
    if not p or '..' in p.split('/') or p.startswith(PROTECTED_PREFIXES):
        raise ValueError('Path is not eligible for autonomous self-engineering')
    return p

def _protected(path):
    return _safe_path(path) in PROTECTED_FILES

def _slug(text):
    return re.sub(r'[^a-z0-9]+','-',(text or '').lower()).strip('-')[:42] or 'upgrade'

def start_release(summary,objective_id=None):
    ensure_schema();st,repo=github_api('GET','')
    if st!=200:raise RuntimeError('GitHub repository connection failed')
    default=(repo.get('default_branch') or 'main') if isinstance(repo,dict) else 'main'
    st,ref=github_api('GET',f'git/ref/heads/{urllib.parse.quote(default,safe="")}')
    if st!=200:raise RuntimeError('Unable to resolve production branch')
    sha=ref['object']['sha'];branch=f'jarvis/self-{int(time.time())}-{_slug(summary)}';created=github_create_branch(branch,sha)
    if not created.get('ok'):raise RuntimeError('Unable to create engineering branch: '+json.dumps(created)[:1500])
    rid=execute('INSERT INTO engineering_releases(objective_id,branch,base_sha,head_sha,state,summary) VALUES(?,?,?,?,?,?)',(objective_id,branch,sha,sha,'draft',summary[:2000]))
    _event(rid,'release_started',json.dumps({'branch':branch,'base_sha':sha,'summary':summary}));return {'ok':True,'release_id':rid,'branch':branch,'base_sha':sha,'state':'draft'}

def release(rid):
    ensure_schema();r=one('SELECT * FROM engineering_releases WHERE id=?',(rid,))
    if not r:raise ValueError('Engineering release not found')
    return r

def read_file(rid,path):
    r=release(rid);p=_safe_path(path);st,d=github_file_at(p,r['branch']);return {'ok':st==200,'status':st,'path':p,'branch':r['branch'],'data':d}

def write_file(rid,path,content,message,allow_protected=False):
    r=release(rid)
    if r['state'] not in ('draft','changes_requested','ci_failed'):raise ValueError('Release is not open for edits')
    p=_safe_path(path)
    if _protected(p) and not allow_protected:raise PermissionError('Protected engineering file requires explicit owner approval')
    out=github_put_file_at(p,content,message,r['branch'])
    if not out.get('ok'):return out
    sha=((out.get('response') or {}).get('commit') or {}).get('sha')
    if sha:execute("UPDATE engineering_releases SET head_sha=?,state='draft',ci_state=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=?",(sha,rid))
    _event(rid,'file_written',json.dumps({'path':p,'commit':sha,'message':message,'protected':_protected(p)}));return {'ok':True,'release_id':rid,'path':p,'branch':r['branch'],'commit_sha':sha,'protected':_protected(p)}

def write_protected_file(rid,path,content,message):
    p=_safe_path(path)
    if not _protected(p):return write_file(rid,p,content,message,False)
    action=f'edit_protected_release:{rid}:{p}'
    approved=one("SELECT id FROM approvals WHERE action=? AND status='approved' ORDER BY id DESC LIMIT 1",(action,))
    if not approved:raise PermissionError('Owner approval required with action '+action)
    return write_file(rid,p,content,message,True)

def diff(rid):
    r=release(rid);out=github_compare(r['base_sha'],r['branch'])
    if out.get('ok'):
        files=out.get('files') or [];out['risk']={'protected_files':[f.get('filename') for f in files if f.get('filename') in PROTECTED_FILES],'file_count':len(files)}
    return out

def run_ci(rid):
    r=release(rid);st,d=github_api('POST','actions/workflows/jarvis-release.yml/dispatches',{'ref':r['branch'],'inputs':{'release_id':str(rid)}});ok=st in (200,201,204)
    execute("UPDATE engineering_releases SET state=?,ci_state=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",('ci_running' if ok else 'ci_failed','queued' if ok else 'dispatch_failed',rid));_event(rid,'ci_dispatched',json.dumps({'status':st,'response':d})[:8000]);return {'ok':ok,'status':st,'release_id':rid,'branch':r['branch'],'response':d}

def status(rid):
    r=release(rid);runs=github_workflow_runs(r['branch'],'Jarvis Release Gate');latest=(runs.get('workflow_runs') or [None])[0];ci='not_run'
    if latest:
        ci='running' if latest.get('status')!='completed' else (latest.get('conclusion') or 'unknown');db_ci='passed' if ci=='success' else ('failed' if latest.get('status')=='completed' else 'running')
        execute('UPDATE engineering_releases SET ci_state=?,state=CASE WHEN ?="passed" THEN "ci_passed" WHEN ?="failed" THEN "ci_failed" ELSE state END,updated_at=CURRENT_TIMESTAMP WHERE id=?',(db_ci,db_ci,db_ci,rid));r=release(rid)
    return {'ok':True,'release':r,'ci':ci,'workflow':latest,'diff':diff(rid)}

def deploy_staging(rid):
    s=status(rid);r=s['release']
    if r.get('ci_state')!='passed':raise ValueError('CI must pass before staging deployment')
    sid=os.getenv('RENDER_STAGING_SERVICE_ID','').strip()
    if not sid:return {'ok':False,'error':'RENDER_STAGING_SERVICE_ID is not configured'}
    out=render_deploy_commit(sid,r['head_sha'],False);did=str(((out.get('response') or {}).get('id') or ''));execute("UPDATE engineering_releases SET state=?,staging_state=?,staging_deploy_id=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",('staging','deploying',did,rid));_event(rid,'staging_deploy',json.dumps(out)[:8000]);return {'release_id':rid,**out}

def verify_staging(rid):
    r=release(rid);url=os.getenv('JARVIS_STAGING_URL','').strip().rstrip('/')
    if not url:return {'ok':False,'error':'JARVIS_STAGING_URL is not configured'}
    health=public_health(url);ok=bool(health.get('ok'));execute("UPDATE engineering_releases SET staging_state=?,state=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",('passed' if ok else 'failed','staging_verified' if ok else 'staging_failed',rid));_event(rid,'staging_verified',json.dumps(health)[:8000]);return {'ok':ok,'release_id':rid,'health':health}

def promote(rid):
    r=release(rid)
    if r['staging_state']!='passed':raise ValueError('Staging verification must pass before production promotion')
    if not one("SELECT id FROM approvals WHERE action=? AND status='approved' ORDER BY id DESC LIMIT 1",(f'promote_engineering_release:{rid}',)):raise PermissionError(f'Owner approval required with action promote_engineering_release:{rid}')
    d=diff(rid);protected=((d.get('risk') or {}).get('protected_files') or [])
    if protected and not one("SELECT id FROM approvals WHERE action=? AND status='approved' ORDER BY id DESC LIMIT 1",(f'promote_protected_release:{rid}',)):raise PermissionError(f'Owner approval required with action promote_protected_release:{rid}')
    st,merged=github_api('POST','merges',{'base':os.getenv('GITHUB_BRANCH','main'),'head':r['branch'],'commit_message':f'Promote Jarvis engineering release #{rid}'})
    if st not in (200,201,204):return {'ok':False,'status':st,'error':'GitHub merge failed','response':merged}
    sha=(merged.get('sha') if isinstance(merged,dict) else None) or r['head_sha'];sid=os.getenv('RENDER_SERVICE_ID','').strip()
    if not sid:return {'ok':False,'error':'RENDER_SERVICE_ID is not configured','merged_sha':sha}
    dep=render_deploy_commit(sid,sha,False);did=str(((dep.get('response') or {}).get('id') or ''));execute("UPDATE engineering_releases SET head_sha=?,state='production_deploying',production_state='deploying',production_deploy_id=?,promoted_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE id=?",(sha,did,rid));_event(rid,'production_promoted',json.dumps({'merge':merged,'deploy':dep})[:10000]);return {'ok':bool(dep.get('ok')),'release_id':rid,'merged_sha':sha,'deploy':dep}

def verify_production(rid):
    url=os.getenv('JARVIS_PUBLIC_URL','').strip().rstrip('/')
    if not url:return {'ok':False,'error':'JARVIS_PUBLIC_URL is not configured'}
    health=public_health(url);ok=bool(health.get('ok'));execute("UPDATE engineering_releases SET production_state=?,state=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",('passed' if ok else 'failed','completed' if ok else 'production_failed',rid));_event(rid,'production_verified',json.dumps(health)[:8000]);return {'ok':ok,'release_id':rid,'health':health}

def list_releases(limit=20):
    ensure_schema();return execute('SELECT * FROM engineering_releases ORDER BY id DESC LIMIT ?',(int(limit),),True)
