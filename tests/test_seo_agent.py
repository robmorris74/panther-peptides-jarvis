import json
import tempfile
from pathlib import Path
from unittest.mock import patch
import pytest
from app223 import db, seo

HTML='''<html><head><title>Panther research materials</title><meta name="description" content="Materials for qualified laboratories"><link rel="canonical" href="https://panther-peptides.rob-morris-1523.chatgpt.site/"></head><body><h1>Research catalog</h1><img src="vial.png"><a href="/admin">Private</a><a href="/products/sample">Sample</a><a href="https://evil.example">External</a></body></html>'''
@pytest.fixture
def store(monkeypatch,tmp_path):
    monkeypatch.setattr(db,'DB_PATH',tmp_path/'test.db')

def fetch(url, root):
    if url.endswith('/robots.txt'): return 200,'User-agent: *\nDisallow: /admin',{},url
    if url.endswith('/sitemap.xml'): return 200,'<urlset></urlset>',{},url
    return 200,HTML,{'Content-Type':'text/html'},url

def test_audit_persists_findings_and_excludes_private_pages(store):
    with patch.object(seo,'_fetch',side_effect=fetch) as call:
        out=seo.run_audit(max_pages=2)
    assert out['ok'] and out['report']['state']=='completed'
    assert len(out['report']['pages'])==2
    assert {f['code'] for f in out['report']['findings']} >= {'missing_image_alt','duplicate_title'}
    assert not any('/admin' in c.args[0] or 'evil.example' in c.args[0] for c in call.call_args_list)
    assert seo.latest_report()['report_id']==out['report_id']
    assert out['report']['external_side_effects'] is False

def test_crawl_failure_never_claims_clean_audit(store):
    with patch.object(seo,'_fetch',side_effect=RuntimeError('connection failed')):
        out=seo.run_audit()
    assert out['ok'] is False and out['report']['state']=='blocked'
    assert out['report']['errors'] and not out['report']['pages']

def test_robots_disallow_is_honored(store):
    def blocked(url,root):
        if url.endswith('robots.txt'): return 200,'User-agent: *\nDisallow: /',{},url
        return fetch(url,root)
    with patch.object(seo,'_fetch',side_effect=blocked) as call: out=seo.run_audit()
    assert len(call.call_args_list)==2
    assert out['report']['findings'][0]['code']=='robots_disallowed'
    assert not out['ok']

def test_unknown_site_limits_and_redirect_targets_are_rejected(store):
    for site in ['http://localhost','evil','https://169.254.169.254']:
        with pytest.raises(ValueError): seo.run_audit(site)
    for n in [0,9,100]:
        with pytest.raises(ValueError): seo.run_audit(max_pages=n)
    for url in ['http://localhost/','https://evil.example/','https://01n99q-ac.myshopify.com/','https://panther-peptides.rob-morris-1523.chatgpt.site/admin','https://panther-peptides.rob-morris-1523.chatgpt.site/?secret=1']:
        with pytest.raises(ValueError): seo._safe_url(url,seo.SITES['panther'])

def test_missing_metadata_and_noindex_are_reported(store):
    def empty(url,root):
        if url.endswith(('robots.txt','sitemap.xml')): return fetch(url,root)
        return 200,'<meta name="robots" content="noindex"><h1>A</h1><h1>B</h1>',{'Content-Type':'text/html'},url
    with patch.object(seo,'_fetch',side_effect=empty): out=seo.run_audit()
    assert {f['code'] for f in out['report']['findings']} >= {'missing_title','missing_description','missing_canonical','heading_structure','page_noindex'}

def test_seo_tools_are_available_and_report_verifies_saved_work(store):
    from app223 import tools,agent
    names={t['function']['name'] for t in tools.tool_specs()}
    assert {'seo_audit','seo_report'} <= names
    assert 'seo_audit' in agent.MUTATING_TOOLS and 'seo_report' in agent.READ_ONLY_TOOLS
    with patch.object(seo,'_fetch',side_effect=fetch): result=tools.run_tool('seo_audit',{'max_pages':1})
    assert tools.run_tool('seo_report',{})['report_id']==result['report_id']

def test_owner_auth_required_for_seo_endpoints(store):
    from fastapi.testclient import TestClient
    from app223.main import app
    client=TestClient(app)
    assert client.get('/seo/report').status_code==401
    assert client.post('/seo/audit',json={}).status_code==401
