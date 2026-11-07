"""Bounded SEO specialist used by Jarvis. Audits and drafts only; no publishing."""
import json
import threading
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser
import requests
from .db import execute, one

SITES = {
    'panther': 'https://panther-peptides.rob-morris-1523.chatgpt.site',
    'shopify': 'https://01n99q-ac.myshopify.com',
}
USER_AGENT = 'PantherJarvisSEO/1.0'
MAX_BYTES = 1_000_000
_LOCK = threading.Lock()
SOURCES = [
 'https://developers.google.com/search/docs/essentials',
 'https://developers.google.com/search/docs/appearance/title-link',
 'https://developers.google.com/search/docs/specialty/ecommerce/designing-a-url-structure-for-ecommerce-sites',
]

class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ''; self.in_title = False; self.h1 = 0
        self.description = ''; self.canonical = ''; self.noindex = False
        self.links = []; self.missing_alt = 0; self.structured_data = False
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'title': self.in_title = True
        if tag == 'h1': self.h1 += 1
        if tag == 'meta':
            name = attrs.get('name', '').lower()
            if name == 'description': self.description = attrs.get('content', '')
            if name in ('robots', 'googlebot'):
                tokens = attrs.get('content', '').lower().replace(',', ' ').split()
                self.noindex |= 'noindex' in tokens or 'none' in tokens
        if tag == 'link' and 'canonical' in attrs.get('rel', '').lower().split(): self.canonical = attrs.get('href', '')
        if tag == 'a' and attrs.get('href'): self.links.append(attrs['href'])
        if tag == 'img' and 'alt' not in attrs: self.missing_alt += 1
        if tag == 'script' and attrs.get('type', '').lower() == 'application/ld+json': self.structured_data = True
    def handle_endtag(self, tag):
        if tag == 'title': self.in_title = False
    def handle_data(self, data):
        if self.in_title: self.title += data

def _safe_url(url, root):
    p, origin = urlsplit(url), urlsplit(root)
    if p.scheme != 'https' or p.netloc != origin.netloc or p.username or p.password:
        raise ValueError('SEO fetch must stay on the selected Panther storefront')
    if p.query or any(part in {'admin', 'api', 'cart', 'checkout', 'account', 'signin-with-chatgpt', 'signout-with-chatgpt', 'callback'} for part in p.path.split('/')):
        raise ValueError('Private, checkout and parameterized URLs are excluded')
    return urlunsplit((p.scheme, p.netloc, p.path or '/', '', ''))

def _fetch(url, root):
    """Validate each redirect and cap response bytes, duration and redirect count."""
    for _ in range(4):
        url = _safe_url(url, root)
        with requests.get(url, headers={'User-Agent': USER_AGENT}, timeout=(4, 6), allow_redirects=False, stream=True) as response:
            if response.status_code in (301, 302, 303, 307, 308):
                url = urljoin(url, response.headers.get('Location', ''))
                continue
            data = bytearray()
            for chunk in response.iter_content(16384):
                data.extend(chunk)
                if len(data) > MAX_BYTES: raise ValueError('SEO response exceeds size limit')
            return response.status_code, bytes(data).decode('utf-8', 'replace'), dict(response.headers), url
    raise ValueError('Too many SEO redirects')

def _ensure_schema():
    execute('''CREATE TABLE IF NOT EXISTS seo_reports(
      id INTEGER PRIMARY KEY AUTOINCREMENT, site TEXT NOT NULL,
      created_at TEXT NOT NULL, report_json TEXT NOT NULL)''')

def latest_report(site='panther'):
    if site not in SITES: raise ValueError('Unknown storefront')
    _ensure_schema()
    row = one('SELECT * FROM seo_reports WHERE site=? ORDER BY id DESC LIMIT 1', (site,))
    return {'ok': True, 'report': json.loads(row['report_json']) if row else None, 'report_id': row['id'] if row else None}

def run_audit(site='panther', max_pages=5):
    if site not in SITES: raise ValueError('Unknown storefront')
    if not isinstance(max_pages, int) or not 1 <= max_pages <= 8: raise ValueError('Audit limit must be 1–8 pages')
    if not _LOCK.acquire(blocking=False): raise ValueError('An SEO audit is already running')
    try: return _audit(site, max_pages)
    finally: _LOCK.release()

def _audit(site, max_pages):
    root = SITES[site]; findings = []; pages = []; errors = []
    def issue(url, priority, code, action):
        findings.append({'url': url, 'priority': priority, 'code': code, 'action': action})
    robots = RobotFileParser(); robots.parse([]); robots_known = True
    for path in ('/robots.txt', '/sitemap.xml'):
        url = root + path
        try:
            status, body, _, _ = _fetch(url, root)
            if status != 200:
                issue(url, 'high' if path == '/robots.txt' else 'medium', 'discovery_file_unavailable', 'Review crawl discovery configuration; response status '+str(status))
                if path == '/robots.txt' and status != 404: robots_known = False
            elif path == '/robots.txt': robots.parse(body.splitlines())
            elif '<urlset' not in body and '<sitemapindex' not in body:
                issue(url, 'medium', 'invalid_sitemap', 'Serve a valid XML sitemap of canonical public pages')
        except Exception as error:
            errors.append({'url': url, 'error': str(error)[:300]})
            if path == '/robots.txt': robots_known = False
    queue = [root + '/']; seen = set(); titles = {}
    while queue and len(seen) < max_pages and robots_known:
        url = queue.pop(0)
        if url in seen: continue
        seen.add(url)
        if not robots.can_fetch(USER_AGENT, url):
            issue(url, 'high', 'robots_disallowed', 'Review whether this public page should be crawlable; do not override robots exclusions')
            continue
        try:
            status, body, headers, final_url = _fetch(url, root)
            if status != 200:
                issue(url, 'high', 'page_http_error', 'Review public page response status '+str(status)); continue
            if 'text/html' not in headers.get('Content-Type', headers.get('content-type', '')).lower(): continue
            page = Page(); page.feed(body)
            pages.append({'url': final_url, 'status': status, 'title': page.title.strip(), 'description': page.description, 'h1_count': page.h1, 'canonical': page.canonical})
            if not page.title.strip(): issue(url, 'high', 'missing_title', 'Draft a concise, descriptive research-material title')
            elif page.title.strip() in titles: issue(url, 'medium', 'duplicate_title', 'Draft a unique page title')
            titles[page.title.strip()] = url
            if not page.description.strip(): issue(url, 'medium', 'missing_description', 'Draft a factual description for qualified research buyers')
            if page.h1 != 1: issue(url, 'medium', 'heading_structure', 'Review the main heading and page hierarchy')
            if not page.canonical: issue(url, 'medium', 'missing_canonical', 'Set a consistent canonical URL for this public page')
            if page.noindex or any(v.lower().find('noindex') >= 0 for k,v in headers.items() if k.lower() == 'x-robots-tag'):
                issue(url, 'high', 'page_noindex', 'Review intentional indexing settings before proposing changes')
            if page.missing_alt: issue(url, 'low', 'missing_image_alt', 'Add accurate image descriptions where images convey information')
            if not page.structured_data: issue(url, 'low', 'structured_data_review', 'Assess appropriate factual structured data; do not invent offers, reviews, stock or certifications')
            for href in page.links:
                try: target = _safe_url(urljoin(final_url, href), root)
                except ValueError: continue
                if target not in seen and target not in queue and len(queue) < 32: queue.append(target)
        except Exception as error: errors.append({'url': url, 'error': str(error)[:300]})
    order = {'high': 0, 'medium': 1, 'low': 2}; findings.sort(key=lambda f: order[f['priority']])
    report = {'agent': 'Panther SEO specialist', 'site': site, 'created_at': datetime.now(timezone.utc).isoformat(),
       'state': 'completed' if pages and not errors and robots_known else 'partial' if pages else 'blocked',
       'pages': pages, 'findings': findings, 'errors': errors, 'crawl_limit': max_pages,
       'external_side_effects': False, 'scope': 'Public-page HTML audit and draft recommendations only',
       'limitations': ['No search ranking, keyword volume or Search Console metrics are available from this audit.', 'No JavaScript rendering or Core Web Vitals measurement.', 'No ranking or indexing guarantees.'],
       'draft_brief': 'Prioritize evidence-backed fixes. Maintain laboratory-research-only positioning. Do not add dosing, human-use or medical claims, fabricated testing, certifications or customer reviews. Use Jarvis engineering release workflow for source changes; this agent never publishes.',
       'sources': SOURCES}
    _ensure_schema()
    report_id = execute('INSERT INTO seo_reports(site,created_at,report_json) VALUES(?,?,?)', (site,report['created_at'],json.dumps(report)))
    return {'ok': report['state'] != 'blocked', 'report_id': report_id, 'report': report}
