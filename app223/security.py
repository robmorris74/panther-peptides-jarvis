import os,hmac,hashlib,secrets,time,base64,sqlite3
from pathlib import Path
from fastapi import Request,HTTPException
DATA=Path(os.getenv('JARVIS_DATA_DIR','/app/data')); DATA.mkdir(parents=True,exist_ok=True); DB_PATH=Path(os.getenv('DATABASE_PATH',str(DATA/'operator.db'))); SECRET_FILE=Path(os.getenv('JARVIS_SESSION_SECRET_FILE',str(DATA/'jarvis_session_secret')))
if SECRET_FILE.exists() and SECRET_FILE.read_text().strip(): SECRET=SECRET_FILE.read_text().strip().encode()
else:
    SECRET=secrets.token_hex(48).encode(); SECRET_FILE.write_text(SECRET.decode())
    try: os.chmod(SECRET_FILE,0o600)
    except Exception: pass
COOKIE='jarvis_owner'; SESSION_TTL=int(os.getenv('JARVIS_SESSION_TTL_SECONDS',str(30*86400)))
def _sign(v): return hmac.new(SECRET,v.encode(),hashlib.sha256).hexdigest()
def make_session():
    body=f'owner:{int(time.time())}'; return body+'.'+_sign(body)
def valid_session(token):
    try:
        body,sig=token.rsplit('.',1)
        if not hmac.compare_digest(sig,_sign(body)):return False
        role,ts=body.split(':',1); age=int(time.time())-int(ts); return role=='owner' and 0<=age<SESSION_TTL
    except Exception:return False
def require_owner(req:Request):
    if not valid_session(req.cookies.get(COOKIE,'')):raise HTTPException(401,'Owner authentication required')
    return True
def _verify_legacy_hash(password,encoded):
    try:
        algo,iters,salt_b64,hash_b64=encoded.split('$',3)
        if algo!='pbkdf2_sha256':return False
        salt=base64.urlsafe_b64decode(salt_b64.encode()); expected=base64.urlsafe_b64decode(hash_b64.encode()); actual=hashlib.pbkdf2_hmac('sha256',password.encode(),salt,int(iters)); return hmac.compare_digest(actual,expected)
    except Exception:return False
def _legacy_owner_hash():
    if not DB_PATH.exists():return ''
    try:
        con=sqlite3.connect(DB_PATH,timeout=5); con.row_factory=sqlite3.Row; row=con.execute("SELECT value FROM company_settings WHERE key='owner_password_hash'").fetchone(); con.close(); return row['value'] if row and row['value'] else ''
    except (sqlite3.Error,OSError,KeyError):return ''
def password_source():
    if _legacy_owner_hash():return 'persistent_legacy_hash'
    if os.getenv('JARVIS_OWNER_PASSWORD'):return 'JARVIS_OWNER_PASSWORD'
    if os.getenv('JARVIS_CLAIM_CODE'):return 'JARVIS_CLAIM_CODE'
    if os.getenv('JARVIS_ENV','development').lower()!='production':return 'development_default'
    return 'unconfigured'
def verify_password(pw):
    legacy=_legacy_owner_hash()
    if legacy:return _verify_legacy_hash(pw,legacy)
    expected=os.getenv('JARVIS_OWNER_PASSWORD') or os.getenv('JARVIS_CLAIM_CODE')
    if expected:return hmac.compare_digest(pw,expected)
    if os.getenv('JARVIS_ENV','development').lower()!='production':return hmac.compare_digest(pw,'jarvis')
    return False
