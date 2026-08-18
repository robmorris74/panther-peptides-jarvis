from pathlib import Path
import tempfile
import app.db as db
import app.security as sec
import app.backups as backups


def reset(tmp_path):
    db.DB_PATH=Path(tmp_path)/'operator.db'
    backups.DB_PATH=db.DB_PATH
    backups.BACKUP_DIR=Path(tmp_path)/'backups'
    backups.BACKUP_DIR.mkdir(parents=True,exist_ok=True)
    db.init_db(); db.init_jarvis_schema()


def test_owner_password_hash_and_verify(tmp_path):
    reset(tmp_path)
    assert not sec.password_configured()
    sec.set_owner_password('correct-horse-battery')
    assert sec.password_configured()
    assert sec.authenticate_owner('correct-horse-battery')
    assert not sec.authenticate_owner('wrong-password')
    con=db.connect(); value=con.execute("SELECT value FROM company_settings WHERE key='owner_password_hash'").fetchone()['value']; con.close()
    assert 'correct-horse-battery' not in value
    assert value.startswith('pbkdf2_sha256$')


def test_signed_session_rejects_tampering(tmp_path,monkeypatch):
    reset(tmp_path)
    monkeypatch.setenv('JARVIS_SESSION_SECRET','test-secret-that-is-long-enough')
    token=sec.create_session()
    assert sec.verify_session(token)
    bad=token[:-2]+('aa' if token[-2:]!='aa' else 'bb')
    assert not sec.verify_session(bad)


def test_backup_is_valid_sqlite_copy(tmp_path):
    reset(tmp_path)
    con=db.connect(); con.execute("INSERT INTO jarvis_tasks(title) VALUES ('preserve me')"); con.commit(); con.close()
    result=backups.create_backup('test')
    path=Path(result['path'])
    assert path.exists() and path.stat().st_size>0
    import sqlite3
    con=sqlite3.connect(path); n=con.execute("SELECT COUNT(*) FROM jarvis_tasks WHERE title='preserve me'").fetchone()[0]; con.close()
    assert n==1
