"""Three explicit schemas only. Credentials are stdin/env, never argv/logs."""
from dataclasses import dataclass,field
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import pymysql
import yaml
from .tracking import emit

DATABASES=('alpha_trade','alpha_trade_fr','alpha_trade_cn')


def identifier(value):
    return '`'+value.replace('`','``')+'`'


@dataclass
class Connection:
    host:str='localhost'
    port:int=3306
    user:str=''
    password:str=field(default='',repr=False)
    ssl_ca:str|None=None


class MySQL:
    def __init__(self,connections,*,mysqldump=None,mysql=None):
        if set(connections)!=set(DATABASES):raise ValueError('Les trois routes MySQL explicites sont requises')
        self.connections=connections
        self.dump_tool=self.tool(mysqldump,'mysqldump')
        self.mysql_tool=self.tool(mysql,'mysql')
    @staticmethod
    def tool(path,name):
        if path and Path(path).is_file():return str(Path(path).resolve())
        detected=shutil.which(name)
        if detected:return detected
        if path:
            sibling=Path(path).with_name(name+'.exe')
            if sibling.is_file():return str(sibling)
        raise ValueError(f'Client MySQL {name} introuvable : renseigner son chemin')
    @classmethod
    def source(cls,root,**kwargs):
        root=Path(root);doc=yaml.safe_load((root/'config/databases.yaml').read_text(encoding='utf-8'))
        connections={}
        for alias in ('us_primary','fr_primary','cn_primary'):
            route=doc['databases'][alias];db=route['database']
            if db not in DATABASES:raise ValueError('Route MySQL hors périmètre')
            override=os.getenv(route.get('database_env',''))
            if override and override!=db:raise ValueError('Nom de base environnement différent du contrat des trois bases')
            def env(name,fallback=None,default=''):
                return os.getenv(route.get(name,'')) or os.getenv(route.get(fallback,'')) if fallback else os.getenv(route.get(name,'')) or default
            user=env('user_env','fallback_user_env');password=env('password_env','fallback_password_env')
            if not user or not password:raise ValueError(f'Identifiants de la route {alias} absents')
            connections[db]=Connection(env('host_env',default=route.get('host','localhost')),
                int(route.get('port',3306)),user,password,os.getenv('DB_SSL_CA_PATH'))
        return cls(connections,**kwargs)
    def connect(self,db):
        c=self.connections[db]
        return pymysql.connect(host=c.host,port=c.port,user=c.user,password=c.password,
            charset='utf8mb4',autocommit=True,cursorclass=pymysql.cursors.DictCursor,
            ssl={'ca':c.ssl_ca} if c.ssl_ca else None,connect_timeout=20,read_timeout=None)
    def inspect(self,db,*,allow_missing=False,count_rows=True):
        if db not in DATABASES:raise ValueError('Base hors périmètre')
        with self.connect(db) as conn,conn.cursor() as cur:
            cur.execute('SELECT VERSION() version');version=cur.fetchone()['version']
            cur.execute('SELECT @@server_uuid server_uuid');server_uuid=cur.fetchone()['server_uuid']
            cur.execute('SELECT DEFAULT_CHARACTER_SET_NAME charset,DEFAULT_COLLATION_NAME collation_name '
                'FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s',(db,));schema=cur.fetchone()
            if schema is None:
                if allow_missing:return None
                raise ValueError(f'Base {db} absente')
            cur.execute('SELECT TABLE_NAME name,TABLE_TYPE kind,ENGINE engine FROM information_schema.TABLES '
                'WHERE TABLE_SCHEMA=%s ORDER BY TABLE_NAME',(db,));tables=cur.fetchall()
            for index,table in enumerate(tables):
                emit(getattr(self,'on_progress',None),database=db,item=table['name'],files_done=index,files_total=len(tables),unit='tables')
                if table['kind']=='BASE TABLE' and table['engine']!='InnoDB':
                    raise ValueError(f'Table non transactionnelle : {db}.{table["name"]}')
                if count_rows and table['kind']=='BASE TABLE':
                    cur.execute(f'SELECT COUNT(*) n FROM {identifier(db)}.{identifier(table["name"])}')
                    table['rows']=int(cur.fetchone()['n'])
                emit(getattr(self,'on_progress',None),files_done=index+1)
            objects={}
            for key,query in {
                'columns':'SELECT TABLE_NAME,COLUMN_NAME,ORDINAL_POSITION,COLUMN_TYPE,IS_NULLABLE,COLUMN_DEFAULT,EXTRA,GENERATION_EXPRESSION FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=%s ORDER BY TABLE_NAME,ORDINAL_POSITION',
                'indexes':'SELECT TABLE_NAME,INDEX_NAME,NON_UNIQUE,SEQ_IN_INDEX,COLUMN_NAME,SUB_PART FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=%s ORDER BY TABLE_NAME,INDEX_NAME,SEQ_IN_INDEX',
                'triggers':'SELECT TRIGGER_NAME,EVENT_MANIPULATION,EVENT_OBJECT_TABLE,ACTION_STATEMENT,ACTION_TIMING,DEFINER FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=%s ORDER BY TRIGGER_NAME',
                'routines':'SELECT ROUTINE_NAME,ROUTINE_TYPE,ROUTINE_DEFINITION,SECURITY_TYPE,DEFINER FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA=%s ORDER BY ROUTINE_NAME',
            }.items():
                cur.execute(query,(db,));rows=cur.fetchall()
                objects[key]=dict(count=len(rows),sha256=hashlib.sha256(json.dumps(rows,sort_keys=True,default=str).encode()).hexdigest())
            cur.execute('SELECT EVENT_NAME,STATUS,DEFINER FROM information_schema.EVENTS WHERE EVENT_SCHEMA=%s ORDER BY EVENT_NAME',(db,))
            events=cur.fetchall();event_defs=[]
            for event in events:
                cur.execute(f'SHOW CREATE EVENT {identifier(db)}.{identifier(event["EVENT_NAME"])}')
                event_defs.append(dict(name=event['EVENT_NAME'],status=event['STATUS'],sql=cur.fetchone()['Create Event']))
            cur.execute('SELECT DEFINER FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=%s '
                'UNION SELECT DEFINER FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA=%s '
                'UNION SELECT DEFINER FROM information_schema.EVENTS WHERE EVENT_SCHEMA=%s',(db,db,db))
            definers=sorted({r['DEFINER'] for r in cur.fetchall()})
        return dict(database=db,version=version,server_uuid=server_uuid,**schema,tables=tables,objects=objects,definers=definers,event_definitions=event_defs)
    def public_metadata(self,metadata):
        return {k:v for k,v in metadata.items() if k!='event_definitions'}
    def check_destination(self,source,*,allow_same_server=False):
        for db,meta in source.items():
            c=self.connections[db]
            if c.host not in ('localhost','127.0.0.1','::1'):raise ValueError('La restauration destructive est limitée au serveur local')
            with self.connect(db) as conn,conn.cursor() as cur:
                cur.execute('SELECT VERSION() v');version=cur.fetchone()['v']
                cur.execute('SELECT @@server_uuid server_uuid');server_uuid=cur.fetchone()['server_uuid']
                if not allow_same_server and meta.get('server_uuid')==server_uuid:
                    raise ValueError('Le serveur cible est le serveur source : restauration refusée pour préserver le PC source')
                if '.'.join(version.split('.')[:2])!='.'.join(meta['version'].split('.')[:2]):
                    raise ValueError('Installer la même famille/version MySQL majeure.mineure que la source')
                if meta.get('definers'):
                    cur.execute("SELECT CONCAT(User,'@',Host) definer FROM mysql.user")
                    actual={r['definer'] for r in cur.fetchall()}
                    if set(meta['definers'])-actual:raise ValueError('Comptes DEFINER MySQL manquants sur la destination')
    def args(self,db,tool):
        c=self.connections[db]
        args=[tool,'--host',c.host,'--port',str(c.port),'--user',c.user,'--default-character-set=utf8mb4']
        if c.ssl_ca:args+=['--ssl-ca',c.ssl_ca]
        env=dict(os.environ,MYSQL_PWD=c.password)
        return args,env
    def dump(self,db,output,check=lambda:None):
        args,env=self.args(db,self.dump_tool)
        args+=['--single-transaction','--skip-lock-tables','--routines','--triggers','--skip-events',
            '--hex-blob','--set-gtid-purged=OFF','--no-tablespaces',db]
        with tempfile.TemporaryFile() as errors:
            proc=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=errors,env=env)
            try:
                with gzip.GzipFile(fileobj=output,mode='wb',mtime=0) as packed:
                    while block:=proc.stdout.read(1024*1024):check();packed.write(block)
                if proc.wait()!=0:raise RuntimeError(f'Export MySQL {db} échoué (code {proc.returncode})')
            except BaseException:
                proc.kill();proc.wait();raise
            finally:proc.stdout.close()
    def recreate(self,db,meta):
        if db not in DATABASES:raise ValueError('Base hors périmètre')
        for name in ('charset','collation_name'):
            if not re.fullmatch('[a-zA-Z0-9_]+',meta[name]):raise ValueError('Encodage SQL invalide')
        with self.connect(db) as conn,conn.cursor() as cur:
            cur.execute(f'DROP DATABASE IF EXISTS {identifier(db)}')
            cur.execute(f'CREATE DATABASE {identifier(db)} CHARACTER SET {meta["charset"]} COLLATE {meta["collation_name"]}')
    def drop(self,db):
        if db not in DATABASES:raise ValueError('Base hors périmètre')
        with self.connect(db) as conn,conn.cursor() as cur:cur.execute(f'DROP DATABASE IF EXISTS {identifier(db)}')
    def load(self,db,source,check=lambda:None):
        args,env=self.args(db,self.mysql_tool)
        with tempfile.TemporaryFile() as errors:
            proc=subprocess.Popen(args+[db],stdin=subprocess.PIPE,stdout=errors,stderr=errors,env=env)
            try:
                with gzip.GzipFile(fileobj=source,mode='rb') as raw:
                    transferred=0
                    while block:=raw.read(1024*1024):
                        check();proc.stdin.write(block);transferred+=len(block)
                        emit(getattr(self,'on_progress',None),processed_bytes=transferred,unit='octets SQL')
                proc.stdin.close()
                if proc.wait()!=0:raise RuntimeError(f'Import MySQL {db} échoué (code {proc.returncode})')
            except BaseException:
                proc.kill();proc.wait();raise
    def load_events_disabled(self,db,definitions):
        with self.connect(db) as conn,conn.cursor() as cur:
            cur.execute('USE '+identifier(db))
            for event in definitions:
                sql,n=re.subn(r'\b(?:ENABLE|DISABLE(?: ON SLAVE)?)\s+DO\b','DISABLE DO',event['sql'],count=1,flags=re.I)
                if n!=1:raise ValueError('Définition événement MySQL non normalisable')
                cur.execute(sql)
    def validate(self,db,expected):
        current=self.inspect(db)
        actual=current['tables']
        if not any('rows' in t for t in expected['tables']):actual=[{k:v for k,v in t.items() if k!='rows'} for t in actual]
        if (actual!=expected['tables'] or current['objects']!=expected['objects']):
            raise ValueError(f'Comptages ou schéma incompatibles après import : {db}')
        if [(e['name']) for e in current['event_definitions']] != [(e['name']) for e in expected.get('event_definitions',[])]:
            raise ValueError('Événements MySQL incomplets')
        if any(e['status']!='DISABLED' for e in current['event_definitions']):raise ValueError('Événement SQL actif après restauration')
    def reset_runtime_locks(self):
        with self.connect('alpha_trade') as conn,conn.cursor() as cur:
            cur.execute("SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA='alpha_trade' AND TABLE_NAME='execution_locks'")
            if cur.fetchone():cur.execute('DELETE FROM alpha_trade.execution_locks')
