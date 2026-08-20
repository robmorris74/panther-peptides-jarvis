import os,re,hashlib,json
from pathlib import Path
from .db import execute,connect
DATA=Path(os.getenv('JARVIS_DATA_DIR','/var/data'));ROOT=DATA/'knowledge';ROOT.mkdir(parents=True,exist_ok=True)
TEXT_EXT={'.txt','.md','.csv','.json','.py','.js','.ts','.tsx','.jsx','.html','.css','.yaml','.yml','.xml','.log','.sql'}
def ensure_knowledge_schema():
    with connect() as con:
        cols=[r[1] for r in con.execute('PRAGMA table_info(knowledge)').fetchall()]
        if 'category' not in cols:con.execute('ALTER TABLE knowledge ADD COLUMN category TEXT')
        if 'tags' not in cols:con.execute('ALTER TABLE knowledge ADD COLUMN tags TEXT')
        if 'summary' not in cols:con.execute('ALTER TABLE knowledge ADD COLUMN summary TEXT')
        if 'source' not in cols:con.execute('ALTER TABLE knowledge ADD COLUMN source TEXT')
        if 'updated_at' not in cols:con.execute('ALTER TABLE knowledge ADD COLUMN updated_at TEXT')
        con.execute('CREATE INDEX IF NOT EXISTS idx_knowledge_name ON knowledge(name)')
        con.execute('CREATE INDEX IF NOT EXISTS idx_knowledge_category ON knowledge(category)')
def _extract(filename,content,mime):
    ext=Path(filename).suffix.lower()
    if ext=='.pdf' or mime=='application/pdf':
        try:
            from pypdf import PdfReader
            import io
            return '\n'.join((p.extract_text() or '') for p in PdfReader(io.BytesIO(content)))[:1500000]
        except Exception as e:return f'[PDF text extraction failed: {e}]'
    if ext in TEXT_EXT or (mime or '').startswith('text/'):
        return content.decode('utf-8','replace')[:1500000]
    try:return content.decode('utf-8','replace')[:250000]
    except:return ''
def save(filename,content,mime='application/octet-stream',category='general',tags='',source='owner_upload'):
    ensure_knowledge_schema()
    if not content:raise ValueError('Empty file')
    if len(content)>25*1024*1024:raise ValueError('File exceeds 25 MB limit')
    digest=hashlib.sha256(content).hexdigest();safe=re.sub(r'[^A-Za-z0-9._-]+','_',filename or 'knowledge')[:180];path=ROOT/f'{digest[:12]}_{safe}';path.write_bytes(content);text=_extract(filename,content,mime)
    existing=execute('SELECT id FROM knowledge WHERE sha256=?',(digest,),True)
    if existing:return {'ok':True,'id':existing[0]['id'],'duplicate':True}
    kid=execute('INSERT INTO knowledge(name,path,sha256,mime_type,text_content,size_bytes,category,tags,source,updated_at) VALUES(?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)',(filename,str(path),digest,mime,len(content),category or 'general',tags or '',source or 'owner_upload'))
    return {'ok':True,'id':kid,'duplicate':False,'characters_indexed':len(text)}
def list_items(limit=200):
    ensure_knowledge_schema();return execute("SELECT id,name,mime_type,size_bytes,category,tags,source,created_at,updated_at,length(COALESCE(text_content,'')) characters FROM knowledge ORDER BY id DESC LIMIT ?",(limit,),True)
def search(query,limit=12):
    ensure_knowledge_schema();q=(query or '').strip()
    if not q:return []
    words=[w.lower() for w in re.findall(r'[A-Za-z0-9_-]{3,}',q)][:8]
    if not words:words=[q.lower()]
    clauses=[];params=[]
    for w in words:
        like=f'%{w}%';clauses.append('(lower(name) LIKE ? OR lower(COALESCE(tags,\'\')) LIKE ? OR lower(COALESCE(category,\'\')) LIKE ? OR lower(COALESCE(text_content,\'\')) LIKE ?)');params += [like,like,like,like]
    sql="SELECT id,name,category,tags,source,created_at,substr(COALESCE(text_content,''),1,8000) text FROM knowledge WHERE "+' OR '.join(clauses)+' ORDER BY id DESC LIMIT ?';params.append(limit)
    return execute(sql,tuple(params),True)
def context(query,max_chars=18000):
    rows=search(query,8);parts=[];used=0
    for r in rows:
        block=f"SOURCE: {r['name']} | category={r.get('category') or 'general'} | tags={r.get('tags') or ''}\n{r.get('text') or ''}\n"
        if used+len(block)>max_chars:block=block[:max(0,max_chars-used)]
        if block:parts.append(block);used+=len(block)
        if used>=max_chars:break
    return '\n---\n'.join(parts)
def stats():
    ensure_knowledge_schema();r=execute("SELECT COUNT(*) files,COALESCE(SUM(size_bytes),0) bytes,COALESCE(SUM(length(COALESCE(text_content,''))),0) characters FROM knowledge",fetch=True)[0];cats=execute("SELECT COALESCE(category,'general') category,COUNT(*) n FROM knowledge GROUP BY COALESCE(category,'general') ORDER BY n DESC",fetch=True);return {**r,'categories':cats}
def delete_item(kid):
    rows=execute('SELECT path FROM knowledge WHERE id=?',(kid,),True)
    if not rows:raise ValueError('Knowledge item not found')
    try:Path(rows[0]['path']).unlink(missing_ok=True)
    except:pass
    execute('DELETE FROM knowledge WHERE id=?',(kid,));return {'ok':True}
