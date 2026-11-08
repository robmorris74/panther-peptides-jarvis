from unittest.mock import patch
import requests
import pytest
from fastapi.testclient import TestClient
from app223 import db, seo
HTML='''<html><head><title>Panther research materials</title><meta name="description" content="Materials for qualified laboratories"><link rel="canonical" href="https://panther-peptides.rob-morris-1523.chatgpt.site/"></head><body><h1>Research catalog</h1><img src="vial.png"><a href="/admin">Private</a><a href="/products/sample">Sample</a><a href="https://evil.example">External</a></body></html>'''
def fetch(url, root):
    if url.endswith('/robots.txt'): return 200,'User-agent: *\nDisallow: /admin',{},url
    if url.endswith('/sitemap.xml'): return 200,'<urlset></urlset>',{},url
    return 200,HTML,{'Content-Type':'text/html'},url

ROOT = seo.SITES['panther']

@pytest.fixture(autouse=True)
def store(monkeypatch, tmp_path):
    monkeypatch.setattr(db, 'DB_PATH', tmp_path / 'audit.db')

class Response:
    def __init__(self, status=200, body='ok', headers=None):
        self.status_code=status; self.body=body; self.headers=headers or {}
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def iter_content(self, size): yield self.body.encode()


def test_transient_timeout_retries_with_bounded_evidence():
    context={'deadline':seo.time.monotonic()+60,'requests':[],'policy':None}
    token=seo._CONTEXT.set(context)
    try:
        with patch.object(seo.requests,'get',side_effect=[requests.ReadTimeout(),Response()]) as get:
            assert seo._fetch(ROOT+'/',ROOT)[0]==200
        assert get.call_count==2
        assert context['requests'][0]['error_kind']=='timeout'
        assert context['requests'][1]['status']==200
        assert all('elapsed_ms' in r for r in context['requests'])
    finally: seo._CONTEXT.reset(token)


def test_redirect_to_other_host_never_fetched():
    with patch.object(seo.requests,'get',return_value=Response(302,headers={'Location':'https://evil.example/'})) as get:
        with pytest.raises(seo.CrawlError,match='stay on'):seo._fetch(ROOT+'/',ROOT)
        assert get.call_count==1


def test_redirect_to_robots_excluded_target_never_fetched():
    token=seo._CONTEXT.set({'deadline':seo.time.monotonic()+60,'requests':[],'policy':seo.RobotsPolicy('User-agent: *\nDisallow: /restricted')})
    try:
        with patch.object(seo.requests,'get',return_value=Response(302,headers={'Location':'/restricted'})) as get:
            with pytest.raises(seo.CrawlError) as e:seo._fetch(ROOT+'/',ROOT)
            assert e.value.code=='robots_disallowed' and get.call_count==1
    finally:seo._CONTEXT.reset(token)

@pytest.mark.parametrize('path',['/%61dmin','/ADMIN','/%2561dmin','/x/../admin','/accounts','/orders','/checkouts','/api%2Fquotes'])
def test_encoded_and_private_routes_excluded(path):
    with pytest.raises(ValueError):seo._safe_url(ROOT+path,ROOT)


def test_response_size_and_retry_after_are_respected(monkeypatch):
    monkeypatch.setattr(seo,'MAX_BYTES',3)
    with patch.object(seo.requests,'get',return_value=Response(body='oversize')):
        with pytest.raises(seo.CrawlError) as e:seo._fetch(ROOT+'/',ROOT)
    assert e.value.code=='response_too_large'
    with patch.object(seo.requests,'get',return_value=Response(429,body='',headers={'Retry-After':'60'})) as get:
        assert seo._fetch(ROOT+'/',ROOT)[0]==429
        assert get.call_count==1


def test_rep_specific_groups_wildcards_and_allow_precedence():
    policy=seo.RobotsPolicy('User-agent: *\nDisallow: /\nUser-agent: PantherJarvisSEO\nDisallow: /restricted*\nAllow: /restricted/public\nDisallow: /exact$')
    assert policy.can_fetch(ROOT+'/')
    assert not policy.can_fetch(ROOT+'/restricted/thing')
    assert policy.can_fetch(ROOT+'/restricted/public')
    assert not policy.can_fetch(ROOT+'/exact')
    assert policy.can_fetch(ROOT+'/exact/more')
    policy=seo.RobotsPolicy('User-agent: *\nDisallow: /same\nAllow: /same')
    assert policy.can_fetch(ROOT+'/same')


def test_html_robots_is_blocked_and_timeout_is_not_missing_sitemap():
    def response(url, root):
        if url.endswith('robots.txt'):return 200,'<!doctype html><html>Password</html>',{},url
        raise seo.CrawlError('timeout','Request timed out')
    with patch.object(seo,'_fetch',side_effect=response):out=seo.run_audit()
    assert out['report']['state']=='blocked'
    assert not out['complete']
    assert 'sitemap_missing' not in {f['code'] for f in out['report']['findings']}
    assert {e['code'] for e in out['report']['errors']}=={'timeout','invalid_robots'}


def test_password_gate_never_counted_as_catalog_audit():
    def response(url,root):
        if url.endswith(('robots.txt','sitemap.xml')):return fetch(url,root)
        return 200,HTML,{'Content-Type':'text/html'},root+'/password'
    with patch.object(seo,'_fetch',side_effect=response):out=seo.run_audit()
    assert not out['ok'] and out['report']['state']=='blocked'
    assert out['report']['pages']==[]
    assert 'storefront_password_gate' in {f['code'] for f in out['report']['findings']}


def test_custom_sitemap_index_discovers_pages_without_home_links():
    def response(url,root):
        if url.endswith('robots.txt'):return 200,f'User-agent: *\nSitemap: {ROOT}/index.xml',{},url
        if url.endswith('index.xml'):return 200,f'<sitemapindex><sitemap><loc>{ROOT}/pages.xml</loc></sitemap></sitemapindex>',{},url
        if url.endswith('pages.xml'):return 200,f'<urlset><url><loc>{ROOT}/public</loc></url><url><loc>{ROOT}/admin</loc></url></urlset>',{},url
        if url.endswith('sitemap.xml'):return 404,'',{},url
        return 200,HTML.replace('<a href="/products/sample">Sample</a>',''),{'Content-Type':'text/html'},url
    with patch.object(seo,'_fetch',side_effect=response) as get:out=seo.run_audit()
    assert out['report']['state']=='completed'
    assert len(out['report']['pages'])==2
    assert not any(c.args[0].endswith('/admin') for c in get.call_args_list)
    assert not any(f['code']=='sitemap_missing' for f in out['report']['findings'])


def test_page_http_failure_and_page_limit_report_partial():
    def response(url,root):
        if url.endswith('/products/sample'):return 503,'',{},url
        return fetch(url,root)
    with patch.object(seo,'_fetch',side_effect=response):out=seo.run_audit(max_pages=2)
    assert out['report']['state']=='partial' and not out['complete']
    assert out['report']['errors'][0]['code']=='page_http_error'
    with patch.object(seo,'_fetch',side_effect=fetch):out=seo.run_audit(max_pages=1)
    assert out['report']['state']=='partial' and out['report']['stop_reason']=='page_limit'


def test_report_ids_remain_retrievable_after_new_report_and_owner_auth():
    from app223.main import app
    from app223.security import COOKIE, make_session
    with patch.object(seo,'_fetch',side_effect=fetch):old=seo.run_audit(max_pages=2)
    with patch.object(seo,'_fetch',side_effect=RuntimeError('network down')):seo.run_audit()
    client=TestClient(app);client.cookies.set(COOKIE,make_session())
    saved=client.get('/seo/report',params={'report_id':old['report_id']})
    assert saved.status_code==200 and saved.json()['report']==old['report']
    assert client.get('/seo/report').json()['report']['state']=='blocked'
    assert not client.get('/seo/report',params={'report_id':9999}).json()['ok']
    assert client.post('/seo/audit',json={},headers={'Origin':'https://evil.example'}).status_code==403
    assert client.post('/seo/audit',json={'site':'unknown'}).status_code==400
    assert client.post('/seo/audit',json={'max_pages':99}).status_code==422


def test_both_quote_and_seo_tools_remain_registered():
    from app223 import agent,tools
    names={t['function']['name'] for t in tools.tool_specs()}
    assert {'quote_requests','quote_sync_status','seo_audit','seo_report'}<=names
    assert {'quote_requests','quote_sync_status','seo_report'}<=agent.READ_ONLY_TOOLS
    assert 'seo_audit' in agent.MUTATING_TOOLS


def test_concurrent_audit_rejected_and_lock_released_after_failure():
    seo._LOCK.acquire()
    try:
        with pytest.raises(ValueError,match='already running'):seo.run_audit()
    finally:seo._LOCK.release()
    with patch.object(seo,'_audit',side_effect=RuntimeError('bad')):
        with pytest.raises(RuntimeError):seo.run_audit()
    assert seo._LOCK.acquire(blocking=False)
    seo._LOCK.release()


def test_robots_percent_encoded_unreserved_octets_are_equivalent():
    policy=seo.RobotsPolicy('User-agent: *\nDisallow: /restricted')
    assert not policy.can_fetch(ROOT+'/%72estricted')
    policy=seo.RobotsPolicy('User-agent: *\nDisallow: /r%C3%A9sum%C3%A9')
    assert not policy.can_fetch(ROOT+'/résumé')
