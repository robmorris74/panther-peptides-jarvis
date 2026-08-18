import importlib, os, sqlite3
from pathlib import Path
import pytest

@pytest.fixture
def fresh(tmp_path, monkeypatch):
    db=tmp_path/'operator.db'; monkeypatch.setenv('DATABASE_PATH',str(db)); monkeypatch.setenv('JARVIS_CONFIG_PATH',str(tmp_path/'jarvis.env'))
    import app.db as dbm; importlib.reload(dbm); dbm.init_db(); dbm.init_jarvis_schema()
    import app.backups as b; importlib.reload(b); b.DB_PATH=dbm.DB_PATH; b.BACKUP_DIR=Path(dbm.DB_PATH).resolve().parent/'backups'; b.BACKUP_DIR.mkdir(parents=True,exist_ok=True); b.connect=dbm.connect
    import app.system_health as h; importlib.reload(h); h.DB_PATH=dbm.DB_PATH; h.connect=dbm.connect; h.list_backups=b.list_backups
    import app.connection_tests as c; importlib.reload(c)
    yield dbm,b,h,c,tmp_path

def test_v11_schema_version(fresh):
    dbm,*_=fresh; con=dbm.connect(); v=con.execute("SELECT value FROM company_settings WHERE key='jarvis_version'").fetchone()['value']; con.close(); assert v=='30.0.0'

def test_backups_follow_database_volume(fresh):
    dbm,b,h,c,tmp=fresh; result=b.create_backup('test'); assert Path(result['path']).parent==tmp/'backups'; assert Path(result['path']).exists()

def test_system_health_checks_db_and_storage(fresh):
    dbm,b,h,c,tmp=fresh; b.create_backup('test'); status=h.system_health(); assert status['version']=='30.0.0'; assert status['database']['ok'] is True; assert status['persistent_storage_writable'] is True; assert status['backup_count']>=1

def test_shipping_connection_check_does_not_buy(fresh, monkeypatch):
    dbm,b,h,c,tmp=fresh; monkeypatch.setenv('EASYPOST_API_KEY','EZAK_test'); monkeypatch.setenv('SHIP_FROM_ADDRESS1','1 Test St'); monkeypatch.setenv('SHIP_FROM_CITY','Test'); monkeypatch.setenv('SHIP_FROM_REGION','KS'); monkeypatch.setenv('SHIP_FROM_POSTAL','66000')
    r=c.test_easypost(); assert r['configured'] is True and r['ok'] is True; assert 'first live rate request' in r['detail']
