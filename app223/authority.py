import os,json,urllib.request
from .db import execute,one

MAX_SPEND=float(os.getenv('JARVIS_MAX_APPROVED_SPEND','300') or 300)

def ensure_authority_schema():
    execute('''CREATE TABLE IF NOT EXISTS authority_policies(
      key TEXT PRIMARY KEY,
      value TEXT NOT NULL,
      updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    execute('''CREATE TABLE IF NOT EXISTS spend_ledger(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      objective_id INTEGER,
      approval_id INTEGER,
      vendor TEXT,
      purpose TEXT NOT NULL,
      amount REAL NOT NULL,
      currency TEXT NOT NULL DEFAULT 'USD',
      status TEXT NOT NULL DEFAULT 'authorized',
      external_reference TEXT,
      detail TEXT,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    defaults={
      'knowledge_is_not_authority':'true',
      'spend_requires_owner_approval':'true',
      'max_spend_per_transaction':str(MAX_SPEND),
      'allow_split_to_bypass_cap':'false',
      'external_commitments_require_approval':'true',
      'credential_changes_require_approval':'true',
      'irreversible_actions_require_approval':'true'
    }
    for k,v in defaults.items():
        execute('INSERT OR IGNORE INTO authority_policies(key,value) VALUES(?,?)',(k,v))

def policies():
    ensure_authority_schema();rows=execute('SELECT key,value,updated_at FROM authority_policies ORDER BY key',fetch=True)
    return {r['key']:r['value'] for r in rows}

def status():
    ensure_authority_schema();p=policies();spent=one("SELECT COALESCE(SUM(amount),0) total FROM spend_ledger WHERE status='executed'")['total']
    return {'max_spend_per_transaction':MAX_SPEND,'spend_requires_owner_approval':True,'payment_connector_configured':bool(os.getenv('JARVIS_PURCHASE_ENDPOINT','').strip() and os.getenv('JARVIS_PURCHASE_TOKEN','').strip()),'lifetime_executed_spend':round(float(spent or 0),2),'policies':p}

def _approved_spend(objective_id,amount):
    rows=execute("SELECT * FROM approvals WHERE objective_id=? AND status='approved' ORDER BY id DESC",(objective_id,),True)
    for r in rows:
        try:p=json.loads(r.get('payload') or '{}')
        except:p={}
        cost=p.get('estimated_cost')
        if cost is not None and abs(float(cost)-float(amount))<0.01:
            return r
    return None

def execute_authorized_spend(objective_id,vendor,purpose,amount,currency='USD'):
    ensure_authority_schema();amount=float(amount)
    if amount<=0:raise ValueError('Spend amount must be greater than zero')
    if amount>MAX_SPEND:raise ValueError(f'Spend exceeds Jarvis authority cap of ${MAX_SPEND:.2f}')
    approval=_approved_spend(objective_id,amount)
    if not approval:raise ValueError('No matching owner-approved spend decision exists for this objective')
    existing=one("SELECT * FROM spend_ledger WHERE approval_id=? AND status='executed'",(approval['id'],))
    if existing:return {'ok':True,'already_executed':True,'ledger_id':existing['id'],'external_reference':existing.get('external_reference')}
    endpoint=os.getenv('JARVIS_PURCHASE_ENDPOINT','').strip();token=os.getenv('JARVIS_PURCHASE_TOKEN','').strip()
    if not endpoint or not token:
        lid=execute('INSERT INTO spend_ledger(objective_id,approval_id,vendor,purpose,amount,currency,status,detail) VALUES(?,?,?,?,?,?,?,?)',(objective_id,approval['id'],vendor,purpose,amount,currency,'authorized','Owner approved, but no trusted purchase connector is configured.'))
        return {'ok':False,'status':'authorized_not_executed','ledger_id':lid,'reason':'payment_connector_not_configured','amount':amount,'currency':currency}
    payload={'vendor':vendor,'purpose':purpose,'amount':amount,'currency':currency,'objective_id':objective_id,'approval_id':approval['id']}
    req=urllib.request.Request(endpoint,data=json.dumps(payload).encode(),headers={'Authorization':f'Bearer {token}','Content-Type':'application/json','User-Agent':'Jarvis-v228'})
    with urllib.request.urlopen(req,timeout=45) as r:
        body=r.read().decode('utf-8','replace')[:5000]
    try:resp=json.loads(body)
    except:resp={'raw':body}
    ref=str(resp.get('id') or resp.get('reference') or resp.get('transaction_id') or '')[:300]
    lid=execute('INSERT INTO spend_ledger(objective_id,approval_id,vendor,purpose,amount,currency,status,external_reference,detail) VALUES(?,?,?,?,?,?,?,?,?)',(objective_id,approval['id'],vendor,purpose,amount,currency,'executed',ref,json.dumps(resp)[:5000]))
    return {'ok':True,'status':'executed','ledger_id':lid,'external_reference':ref,'amount':amount,'currency':currency}
