import os
from pathlib import Path
os.environ['DATABASE_PATH']='./data/test_jarvis_v5.db'
from app.db import init_db,init_jarvis_schema,connect
from app.seed_panther import seed
from app.autonomy import set_rule,propose_action,get_rules
from app.memory import remember,list_memory,forget
from app.jarvis_dashboard import JARVIS_HTML


def reset():
    p=Path(os.environ['DATABASE_PATH'])
    try:p.unlink()
    except FileNotFoundError:pass
    init_db();init_jarvis_schema();seed()


def test_high_risk_actions_cannot_be_auto():
    reset()
    try:
        set_rule('publish_product','auto')
        assert False, 'should have refused auto mode'
    except ValueError:
        pass
    r=set_rule('publish_product','approval')
    assert r['mode']=='approval'


def test_action_proposal_uses_approval_for_high_risk():
    reset()
    x=propose_action('place_purchase_order','Reorder research SKU',{'total':200},'high')
    assert x['mode']=='approval' and x['approval_id']
    con=connect(); a=con.execute('SELECT status FROM approvals WHERE id=?',(x['approval_id'],)).fetchone(); con.close()
    assert a['status']=='pending'


def test_low_risk_action_can_be_draft():
    reset(); set_rule('draft_storefront_copy','draft')
    x=propose_action('draft_storefront_copy','Draft research page',{'sku':'TEST'},'low')
    assert x['mode']=='draft' and x['status']=='drafted' and x['approval_id'] is None


def test_owner_memory_persists_and_can_be_removed():
    reset(); remember('pricing_style','Protect gross margin before discounting','finance')
    m={x['key']:x for x in list_memory()}
    assert m['pricing_style']['value']=='Protect gross margin before discounting'
    assert forget('pricing_style')==1


def test_owner_console_has_permissions_and_memory():
    assert 'Permissions' in JARVIS_HTML
    assert 'Jarvis permission ladder' in JARVIS_HTML
    assert 'durable memory' in JARVIS_HTML

def test_shopify_hmac_verification():
    import base64,hashlib,hmac
    from app.shopify_webhooks import verify_shopify_hmac
    body=b'{"id":123}' ; secret='test-secret'
    sig=base64.b64encode(hmac.new(secret.encode(),body,hashlib.sha256).digest()).decode()
    assert verify_shopify_hmac(body,sig,secret)
    assert not verify_shopify_hmac(body,'wrong',secret)

def test_shopify_adapter_uses_setup_domain_name(monkeypatch):
    monkeypatch.setenv('SHOPIFY_STORE_DOMAIN','example.myshopify.com')
    import importlib,app.integrations as i
    i=importlib.reload(i)
    assert i.SHOPIFY_SHOP_DOMAIN=='example.myshopify.com'
