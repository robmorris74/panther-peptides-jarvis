"""Durable quote intake and owner alerts. Customer text never becomes an objective."""
import json
import os
import re
import smtplib
import ssl
import threading
from datetime import datetime, timezone
from email.message import EmailMessage
import requests
from .db import execute, one

SOURCE = 'https://panther-peptides.rob-morris-1523.chatgpt.site'
ENDPOINT = SOURCE + '/api/integrations/jarvis/quotes'
_stop = threading.Event()
_thread = None
_lock = threading.Lock()
_last_error = None
_last_sync = None

def ensure_schema():
    execute('''CREATE TABLE IF NOT EXISTS incoming_quotes (
      id TEXT PRIMARY KEY, payload TEXT NOT NULL, received_at TEXT NOT NULL,
      email_alert_at TEXT, email_attempts INTEGER NOT NULL DEFAULT 0,
      email_error TEXT)''')

def list_quotes(limit=50):
    ensure_schema()
    rows=execute('SELECT * FROM incoming_quotes ORDER BY received_at DESC LIMIT ?', (max(1,min(int(limit),100)),),True)
    return [{**json.loads(r['payload']), 'received_at':r['received_at'], 'email_alert_at':r['email_alert_at'], 'email_error':r['email_error']} for r in rows]

def status():
    ensure_schema()
    count=one('SELECT COUNT(*) n FROM incoming_quotes')['n']
    pending=one('SELECT COUNT(*) n FROM incoming_quotes WHERE email_alert_at IS NULL')['n']
    configured=bool(os.getenv('PANTHER_QUOTES_TOKEN','').strip())
    return {'configured':configured,'worker_alive':bool(_thread and _thread.is_alive()),'received':count,'email_alerts_pending':pending,
       'email_configured':bool(os.getenv('SMTP_HOST') and os.getenv('SMTP_FROM')),
       'last_sync':_last_sync,'last_error':_last_error,'poll_seconds':60}

def _save(quote):
    if not isinstance(quote,dict) or not re.fullmatch(r'[a-f0-9-]{36}',str(quote.get('id',''))): raise ValueError('Invalid quote ID')
    required=('name','email','institution','purpose','destination','items','created_at')
    if not all(isinstance(quote.get(k),str) for k in required): raise ValueError('Invalid quote fields')
    payload=json.dumps({k:quote[k] for k in ('id',)+required})
    if len(payload)>24000: raise ValueError('Quote exceeds size limit')
    # A transaction makes the inbox entry and dashboard alert atomic across retries/restarts.
    from .db import connect, _lock as db_lock
    with db_lock, connect() as con:
        con.execute('BEGIN IMMEDIATE')
        try:
            inserted=con.execute('INSERT OR IGNORE INTO incoming_quotes(id,payload,received_at) VALUES(?,?,?)',
               (quote['id'],payload,datetime.now(timezone.utc).isoformat())).rowcount
            if inserted:
                con.execute('INSERT INTO activity(level,event,detail) VALUES(?,?,?)',
                  ('info','new_quote_request',json.dumps({'reference':'PP-'+quote['id'],'institution':quote['institution'],'review_url':SOURCE+'/admin'})))
            con.execute('COMMIT')
        except Exception:
            con.execute('ROLLBACK'); raise
    return bool(inserted)

def _send_alert(row):
    host=os.getenv('SMTP_HOST','').strip(); sender=os.getenv('SMTP_FROM','').strip()
    if not host or not sender: return False
    quote=json.loads(row['payload'])
    recipient=os.getenv('PANTHER_QUOTES_ALERT_EMAIL') or os.getenv('OWNER_NOTIFICATION_EMAIL') or 'rob.morris@egc-inc.com'
    msg=EmailMessage(); msg['From']=sender; msg['To']=recipient
    msg['Subject']='Jarvis: New Panther quote PP-'+quote['id']
    msg['Message-ID']='<panther-quote-'+quote['id']+'@panther-peptides.local>'
    msg.set_content('A new Panther Peptides quote request is waiting for your review.\n\nReference: PP-'+quote['id']+'\nInstitution: '+quote['institution']+'\n\nOpen your private quote inbox: '+SOURCE+'/admin\n\nJarvis has saved this request. No order or payment has been confirmed.')
    port=int(os.getenv('SMTP_PORT','587')); context=ssl.create_default_context()
    factory=smtplib.SMTP_SSL if port==465 else smtplib.SMTP
    with factory(host,port,timeout=15,**({'context':context} if port==465 else {})) as smtp:
        if port!=465: smtp.ehlo(); smtp.starttls(context=context); smtp.ehlo()
        if os.getenv('SMTP_USER'): smtp.login(os.environ['SMTP_USER'],os.getenv('SMTP_PASSWORD',''))
        smtp.send_message(msg)
    return True

def sync_once():
    global _last_error,_last_sync
    token=os.getenv('PANTHER_QUOTES_TOKEN','').strip()
    if not token: return {'ok':False,'blocker':'PANTHER_QUOTES_TOKEN is not configured'}
    if not _lock.acquire(blocking=False): return {'ok':False,'blocker':'Quote sync already running'}
    try:
        ensure_schema()
        headers={'Authorization':'Bearer '+token,'Accept':'application/json'}
        response=requests.get(ENDPOINT,headers=headers,timeout=(5,20),allow_redirects=False)
        if response.status_code!=200: raise RuntimeError('Quote inbox returned HTTP '+str(response.status_code))
        if len(response.content)>1500000: raise ValueError('Quote inbox response too large')
        quotes=response.json().get('quotes')
        if not isinstance(quotes,list) or len(quotes)>50: raise ValueError('Invalid quote inbox response')
        received=0
        for quote in quotes:
            received+=int(_save(quote))
            ack=requests.post(ENDPOINT,headers=headers,json={'id':quote['id']},timeout=(5,15),allow_redirects=False)
            if ack.status_code!=200: raise RuntimeError('Quote acknowledgement returned HTTP '+str(ack.status_code))
        for row in execute('SELECT * FROM incoming_quotes WHERE email_alert_at IS NULL ORDER BY received_at LIMIT 20',fetch=True):
            try:
                if _send_alert(row):
                    execute('UPDATE incoming_quotes SET email_alert_at=?,email_attempts=email_attempts+1,email_error=NULL WHERE id=?',(datetime.now(timezone.utc).isoformat(),row['id']))
            except Exception:
                execute('UPDATE incoming_quotes SET email_attempts=email_attempts+1,email_error=? WHERE id=?',('Email delivery failed; retry pending',row['id']))
        _last_sync=datetime.now(timezone.utc).isoformat();_last_error=None
        return {'ok':True,'new_quotes':received,'status':status()}
    except Exception as error:
        # Do not copy transport errors into logs: they can contain connection credentials.
        _last_error='Quote sync failed ('+type(error).__name__+'); requests remain queued for retry'
        return {'ok':False,'error':_last_error}
    finally: _lock.release()

def start():
    global _thread
    ensure_schema()
    if _thread and _thread.is_alive(): return
    _stop.clear()
    def loop():
        while not _stop.is_set():
            if os.getenv('PANTHER_QUOTES_TOKEN','').strip(): sync_once()
            _stop.wait(60)
    _thread=threading.Thread(target=loop,name='jarvis-quote-intake',daemon=True);_thread.start()

def stop(): _stop.set()
