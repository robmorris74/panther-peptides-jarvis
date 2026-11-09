"""Persistent daily public-site audits. Never publishes or touches traffic/quotes."""
import logging
import os
import threading
from datetime import datetime, timezone
from . import seo

REVISION = 'seo-daily-1'
INTERVAL_SECONDS = 24 * 60 * 60
_thread = None
_stop = threading.Event()
_last_error = ''

def enabled():
    # Enabled for the production service; local tests/development opt in explicitly.
    default = '1' if os.getenv('JARVIS_ENV') == 'production' else '0'
    return os.getenv('JARVIS_SEO_ENABLED', default).lower() in ('1', 'true', 'yes')

def run_if_due(now=None):
    now = now or datetime.now(timezone.utc)
    saved = seo.latest_report('panther')['report']
    if saved:
        last = datetime.fromisoformat(saved['created_at'])
        if (now - last).total_seconds() < INTERVAL_SECONDS:
            return {'ran': False, 'reason': 'daily audit already recorded'}
    return {'ran': True, **seo.run_audit('panther', max_pages=8)}

def _loop():
    global _last_error
    while not _stop.is_set():
        try:
            run_if_due()
            _last_error = ''
        except Exception:
            # Do not leak transport errors, URLs or credentials through public health.
            _last_error = 'scheduled_audit_failed'
            logging.getLogger(__name__).exception('Scheduled SEO audit failed')
        _stop.wait(60)

def start():
    global _thread
    if enabled() and not (_thread and _thread.is_alive()):
        _stop.clear()
        _thread = threading.Thread(target=_loop, name='panther-seo-daily', daemon=True)
        _thread.start()

def health():
    return {'revision': REVISION, 'enabled': enabled(),
            'worker_alive': bool(_thread and _thread.is_alive())}

def status():
    return {**health(), 'interval_seconds': INTERVAL_SECONDS,
            'last_error': _last_error, 'latest': seo.latest_report('panther')}
