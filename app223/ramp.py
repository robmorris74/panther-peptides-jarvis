import os,json,urllib.request,urllib.error

PROD='https://api.ramp.com'
DEMO='https://demo-api.ramp.com'

def _base():
    return DEMO if os.getenv('RAMP_ENV','production').strip().lower() in ('demo','sandbox') else PROD

def configured():
    return bool(os.getenv('RAMP_API_TOKEN','').strip())

def purchase_enabled():
    # Real purchases remain fail-closed until a trusted Ramp agent/payment gateway is configured.
    return bool(os.getenv('RAMP_PURCHASE_ENDPOINT','').strip() and os.getenv('RAMP_PURCHASE_TOKEN','').strip())

def _get(path):
    token=os.getenv('RAMP_API_TOKEN','').strip()
    if not token:raise RuntimeError('RAMP_API_TOKEN is not configured')
    req=urllib.request.Request(_base()+path,headers={'Authorization':f'Bearer {token}','Accept':'application/json','User-Agent':'Panther-Jarvis-v228'})
    with urllib.request.urlopen(req,timeout=20) as r:
        return json.loads(r.read().decode('utf-8','replace') or '{}')

def status(probe=False):
    out={
      'provider':'Ramp',
      'environment':'sandbox' if _base()==DEMO else 'production',
      'credentials_configured':configured(),
      'purchase_gateway_configured':purchase_enabled(),
      'max_transaction_usd':300.0,
      'owner_approval_required':True,
      'pan_cvv_stored_by_jarvis':False,
      'account_setup_required':not configured(),
      'setup_steps':[
        'Create or finish the Panther Peptides Ramp business account in Ramp.',
        'In Ramp, open Settings/Company > Developer and create a Developer API app.',
        'Use only the minimum scopes required for cards, transactions and the approved purchasing workflow.',
        'Store the resulting Ramp API credential in Render as RAMP_API_TOKEN; never enter card PAN or CVV into Jarvis.',
        'Test the connection here before enabling real purchasing.'
      ]
    }
    if probe and configured():
        try:
            cards=_get('/developer/v1/cards/virtual?page_size=2')
            out['connected']=True;out['probe']='virtual_cards_read';out['card_count_sample']=len(cards.get('data') or [])
        except urllib.error.HTTPError as e:
            body=e.read().decode('utf-8','replace')[:1200];out['connected']=False;out['error']=f'Ramp HTTP {e.code}: {body}'
        except Exception as e:
            out['connected']=False;out['error']=str(e)[:1200]
    else:
        out['connected']=None if not configured() else True
    return out

def list_virtual_cards():
    data=_get('/developer/v1/cards/virtual?page_size=100')
    safe=[]
    for c in data.get('data') or []:
        # Never return PAN/CVV even if a future Ramp response includes them.
        safe.append({k:v for k,v in c.items() if k.lower() not in ('pan','cvv','number','card_number','security_code')})
    return {'ok':True,'cards':safe,'page':data.get('page')}
