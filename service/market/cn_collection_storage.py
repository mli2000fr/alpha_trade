"""CN collection resources in alpha_trade_cn, with immutable byte receipts.

Paths under CN data roots are logical SQL keys, never a disk fallback. Models,
source code, configuration and database dumps keep their native storage.
Outside those roots DataPath behaves as pathlib.Path (offline test fixtures).
"""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, UTC
import fnmatch
import hashlib
import io
import json
from pathlib import Path as NativePath, PurePosixPath
from types import SimpleNamespace

import pandas as pd
from sqlalchemy import (MetaData, Table, Column, String, Text as SQLText, LargeBinary,
                        BigInteger, Integer, Float, DateTime, Boolean, select, text)
from sqlalchemy.dialects.mysql import MEDIUMBLOB, LONGTEXT

Text=SQLText().with_variant(LONGTEXT(),'mysql')

ROOT=NativePath(__file__).resolve().parents[2]
_REPOSITORY=ContextVar('cn_collection_repository',default=None)
metadata=MetaData()
objects=Table('cn_collection_objects',metadata,
    Column('content_sha256',String(64),primary_key=True),Column('byte_length',BigInteger,nullable=False),
    Column('stored_at',DateTime,nullable=False))
parts=Table('cn_collection_object_parts',metadata,
    Column('content_sha256',String(64),primary_key=True),Column('part_no',Integer,primary_key=True),
    Column('body',LargeBinary().with_variant(MEDIUMBLOB(),'mysql'),nullable=False))
heads=Table('cn_collection_resources',metadata,
    Column('resource_sha256',String(64),primary_key=True),Column('resource_key',Text,nullable=False),
    Column('content_sha256',String(64),nullable=False),Column('kind',String(16),nullable=False),
    Column('updated_at',DateTime,nullable=False))
versions=Table('cn_collection_versions',metadata,
    Column('version_id',String(64),primary_key=True),Column('resource_key',Text,nullable=False),
    Column('content_sha256',String(64),nullable=False),Column('stored_at',DateTime,nullable=False))
snapshots=Table('cn_dragon_tiger_snapshots',metadata,
    Column('content_sha256',String(64),primary_key=True),Column('trade_date',String(10),nullable=False),
    Column('observed_at_utc',DateTime,nullable=False),Column('phase',String(32)),
    Column('event_count',Integer,nullable=False),Column('retrospective',Boolean),
    Column('historical_pit_qualified',Boolean,nullable=False))
events=Table('cn_dragon_tiger_events',metadata,
    Column('content_sha256',String(64),primary_key=True),Column('row_no',Integer,primary_key=True),
    Column('trade_date',String(10)),Column('exchange',String(16)),Column('code',String(16)),
    Column('reason',Text),Column('first_seen_at_utc',DateTime),Column('payload_sha256',String(64)),
    Column('row_json',Text,nullable=False))
candidates=Table('cn_oracle_prospective_candidates',metadata,
    Column('content_sha256',String(64),primary_key=True),Column('row_no',Integer,primary_key=True),
    Column('decision_date',String(10)),Column('exchange',String(16)),Column('code',String(16)),
    Column('oracle_score',Float(precision=53)),Column('score_available_at_utc',DateTime),Column('row_json',Text,nullable=False))
matches=Table('cn_dragon_tiger_matches',metadata,
    Column('content_sha256',String(64),primary_key=True),Column('row_no',Integer,primary_key=True),
    Column('decision_date',String(10)),Column('exposed_code',String(16)),Column('control_code',String(16)),
    Column('row_json',Text,nullable=False))
runs=Table('cn_collection_reports',metadata,
    Column('version_id',String(64),primary_key=True),Column('resource_key',Text,nullable=False),
    Column('content_sha256',String(64),nullable=False),Column('batch_name',String(128)),
    Column('status',String(96)),Column('report_json',Text,nullable=False),Column('stored_at',DateTime,nullable=False))
migrations=Table('cn_collection_file_migrations',metadata,
    Column('version_id',String(64),primary_key=True),Column('resource_key',Text,nullable=False),
    Column('content_sha256',String(64),nullable=False),Column('byte_length',BigInteger,nullable=False),
    Column('source_mtime_ns',BigInteger,nullable=False),Column('verified_at',DateTime,nullable=False),
    Column('deleted_at',DateTime))


def sha(raw):return hashlib.sha256(raw).hexdigest()
def now():return datetime.now(UTC).replace(tzinfo=None)
def encode(obj):return json.dumps(obj,ensure_ascii=False,default=str,allow_nan=False)


def timestamp(value):
    if value is None:return None
    stamp=pd.Timestamp(value)
    if pd.isna(stamp):return None
    if stamp.tzinfo is None:
        raise ValueError('CN source observation must have an explicit timezone')
    return stamp.tz_convert('UTC').to_pydatetime().replace(tzinfo=None)


def resource_key(path):
    p=NativePath(path).absolute()
    if '..' in p.parts:raise ValueError('CN resource traversal refused')
    if not p.is_relative_to(ROOT):raise ValueError('CN SQL resource outside workspace')
    return p.relative_to(ROOT).as_posix()


def managed(path):
    p=NativePath(path).absolute()
    if not p.is_relative_to(ROOT):return False
    key=p.relative_to(ROOT).as_posix()
    if key.startswith('artifacts/research/cn_provider_smoke/python'):return False
    if p.suffix.lower() in ('.cbm','.pkl','.joblib','.pt','.pth'):return False
    if p.name.lower() in ('model.txt','lightgbm.txt','catboost.cbm'):return False
    if p.name=='report.json' and ((p.parent/'model.txt').is_file() or any(p.parent.glob('*.cbm'))):
        return False  # Model receipt belongs to the retained model package.
    return (key=='artifacts/cn' or key.startswith('artifacts/cn/') or
            key.startswith('artifacts/research/cn_'))


def assert_cn(engine):
    if engine.dialect.name=='sqlite':return
    with engine.connect() as c:
        if c.execute(text('SELECT DATABASE()')).scalar()!='alpha_trade_cn':
            raise ValueError('CN collection writes refused outside alpha_trade_cn')


def create_schema(engine):
    assert_cn(engine)
    metadata.create_all(engine)


class Repository:
    def __init__(self,engine):
        assert_cn(engine)
        self.engine=engine

    @contextmanager
    def lock(self,name):
        if self.engine.dialect.name=='sqlite':
            yield
            return
        key='CNCollection:'+sha(str(name).encode())[:40]
        with self.engine.connect() as c:
            if c.execute(text('SELECT GET_LOCK(:k,0)'),dict(k=key)).scalar()!=1:
                raise RuntimeError('CN SQL collection already running: '+str(name))
            try:yield
            finally:c.execute(text('SELECT RELEASE_LOCK(:k)'),dict(k=key))

    def _read(self,c,digest):
        size=c.execute(select(objects.c.byte_length).where(objects.c.content_sha256==digest)).scalar_one()
        rows=c.execute(select(parts.c.part_no,parts.c.body).where(parts.c.content_sha256==digest).order_by(parts.c.part_no)).all()
        if [r[0] for r in rows]!=list(range(len(rows))):raise ValueError('CN SQL object missing part')
        raw=b''.join(r[1] for r in rows)
        if len(raw)!=size or sha(raw)!=digest:raise ValueError('CN SQL object integrity mismatch')
        return raw

    def get(self,path):
        key=resource_key(path)
        with self.engine.connect() as c:
            row=c.execute(select(heads).where(heads.c.resource_sha256==sha(key.encode()))).mappings().first()
            if row is None or row['kind']!='file':raise FileNotFoundError('CN SQL resource absent: '+key)
            if row['resource_key']!=key:raise ValueError('CN resource hash collision')
            return self._read(c,row['content_sha256'])

    def keys(self):
        with self.engine.connect() as c:return c.execute(select(heads.c.resource_key,heads.c.kind)).all()

    def exists(self,path,kind=None):
        key=resource_key(path)
        with self.engine.connect() as c:
            row=c.execute(select(heads.c.resource_key,heads.c.kind).where(heads.c.resource_sha256==sha(key.encode()))).first()
            if row and row[0]!=key:raise ValueError('CN resource hash collision')
            if row and (kind is None or row[1]==kind):return True
            if kind=='file':return False
            return any(k.startswith(key+'/') for k,_ in self.keys())

    def _project(self,c,key,digest,raw):
        # Parse only known business contracts. All other source bytes are preserved intact.
        version=sha((key+'\0'+digest).encode())
        if key.endswith('.json'):
            try:data=json.loads(raw)
            except (ValueError,UnicodeDecodeError):return
            if isinstance(data,dict) and data.get('schema')=='cn_dragon_tiger_observation_v1':
                rows=data.get('events')
                if not isinstance(rows,list) or len(rows)!=int(data['counts']['events']):
                    raise ValueError('CN snapshot event count mismatch')
                if c.execute(select(snapshots.c.content_sha256).where(snapshots.c.content_sha256==digest)).first() is None:
                    c.execute(snapshots.insert(),dict(content_sha256=digest,trade_date=data['trade_date'],
                        observed_at_utc=timestamp(data['observed_at_utc']),phase=(data.get('collection_context') or {}).get('phase'),
                        event_count=len(rows),retrospective=data.get('retrospective'),historical_pit_qualified=False))
                    if rows:c.execute(events.insert(),[dict(content_sha256=digest,row_no=i,trade_date=r.get('date'),
                        exchange=r.get('exchange'),code=r.get('code'),reason=r.get('reason'),
                        first_seen_at_utc=timestamp(r.get('first_seen_at_utc')),payload_sha256=r.get('payload_sha256'),
                        row_json=encode(r)) for i,r in enumerate(rows)])
            if isinstance(data,dict) and ('status' in data or 'batch' in data):
                if not c.execute(select(runs.c.version_id).where(runs.c.version_id==version)).first():
                    c.execute(runs.insert(),dict(version_id=version,resource_key=key,content_sha256=digest,
                        batch_name=data.get('batch'),status=str(data.get('status','UNKNOWN'))[:96],report_json=raw.decode('utf-8'),stored_at=now()))
        table=candidates if key.endswith('/oracle_top20.parquet') else matches if key.endswith('/outcome_blind_matches.parquet') else None
        if table is not None and not c.execute(select(table.c.content_sha256).where(table.c.content_sha256==digest).limit(1)).first():
            frame=pd.read_parquet(io.BytesIO(raw))
            rows=[]
            for i,r in enumerate(frame.astype(object).where(pd.notna(frame),None).to_dict('records')):
                common=dict(content_sha256=digest,row_no=i,decision_date=r.get('decision_date'),row_json=encode(r))
                if table is candidates:
                    common.update(exchange=r.get('exchange'),code=r.get('code'),oracle_score=r.get('oracle_score'),
                        score_available_at_utc=timestamp(r.get('score_available_at_utc')))
                else:common.update(exposed_code=r.get('exposed_code'),control_code=r.get('control_code'))
                rows.append(common)
            if rows:c.execute(table.insert(),rows)

    def put(self,path,raw,*,exclusive=False,kind='file'):
        key=resource_key(path);digest=sha(raw);keyhash=sha(key.encode());clock=now()
        with self.lock(key),self.engine.begin() as c:
            old=c.execute(select(heads).where(heads.c.resource_sha256==keyhash)).mappings().first()
            if old and old['resource_key']!=key:raise ValueError('CN SQL resource collision')
            if old and exclusive:raise FileExistsError(key)
            if not c.execute(select(objects.c.content_sha256).where(objects.c.content_sha256==digest)).first():
                # INSERT IGNORE makes cross-resource content deduplication concurrency-safe.
                statement=objects.insert()
                if self.engine.dialect.name=='mysql':statement=statement.prefix_with('IGNORE')
                c.execute(statement,dict(content_sha256=digest,byte_length=len(raw),stored_at=clock))
                statement=parts.insert()
                if self.engine.dialect.name=='mysql':statement=statement.prefix_with('IGNORE')
                for i in range(0,max(1,len(raw)),1000000):
                    c.execute(statement,dict(content_sha256=digest,part_no=i//1000000,body=raw[i:i+1000000]))
            version=sha((key+'\0'+digest).encode())
            if not c.execute(select(versions.c.version_id).where(versions.c.version_id==version)).first():
                c.execute(versions.insert(),dict(version_id=version,resource_key=key,content_sha256=digest,stored_at=clock))
            if kind=='file':self._project(c,key,digest,raw)
            values=dict(resource_sha256=keyhash,resource_key=key,content_sha256=digest,kind=kind,updated_at=clock)
            if old:c.execute(heads.update().where(heads.c.resource_sha256==keyhash).values(**values))
            else:c.execute(heads.insert(),values)
        return digest

    def remove(self,path,missing_ok=False):
        key=resource_key(path)
        with self.engine.begin() as c:
            n=c.execute(heads.delete().where(heads.c.resource_sha256==sha(key.encode()))).rowcount
            if not n and not missing_ok:raise FileNotFoundError(key)

    def move(self,source,target):
        first,last=resource_key(source),resource_key(target)
        if first==last:return
        with self.lock(first),self.lock(last),self.engine.begin() as c:
            all_rows=list(c.execute(select(heads)).mappings())
            rows=[r for r in all_rows if r['resource_key']==first or r['resource_key'].startswith(first+'/')]
            if not rows:raise FileNotFoundError(first)
            directory=any(r['kind']=='directory' for r in rows) or len(rows)>1
            if directory and any(r['resource_key']==last or r['resource_key'].startswith(last+'/') for r in all_rows):
                raise FileExistsError('CN publication already exists: '+last)
            # Renaming publication folders is atomic; readers see either complete version.
            for r in rows:
                key=last+r['resource_key'][len(first):];kh=sha(key.encode())
                c.execute(heads.delete().where(heads.c.resource_sha256==kh))
                if r['kind']=='file':self._project(c,key,r['content_sha256'],self._read(c,r['content_sha256']))
                c.execute(heads.insert(),dict(resource_sha256=kh,resource_key=key,content_sha256=r['content_sha256'],kind=r['kind'],updated_at=now()))
            for r in rows:c.execute(heads.delete().where(heads.c.resource_sha256==r['resource_sha256']))


def repository():
    repo=_REPOSITORY.get()
    if repo is None:
        from database.router import get_market_engine
        repo=Repository(get_market_engine('CN_A',database_alias='cn_primary'))
        _REPOSITORY.set(repo)
    return repo


@contextmanager
def use(repo):
    token=_REPOSITORY.set(repo)
    try:yield repo
    finally:_REPOSITORY.reset(token)


class _Buffer(io.BytesIO):
    def __init__(self,path,mode,raw=b''):
        super().__init__(raw);self.path=path;self.mode_string=mode
        if 'a' in mode:self.seek(0,2)
    def close(self):
        if not self.closed and any(k in self.mode_string for k in ('w','x','a','+')):
            repository().put(self.path,self.getvalue(),exclusive='x' in self.mode_string)
        super().close()


class DataPath(type(NativePath())):
    def read_bytes(self):return repository().get(self) if managed(self) else super().read_bytes()
    def read_text(self,encoding=None,errors=None,newline=None):
        if not managed(self):return super().read_text(encoding=encoding,errors=errors,newline=newline)
        return self.read_bytes().decode(encoding or 'utf-8',errors or 'strict')
    def write_bytes(self,data):
        if not managed(self):return super().write_bytes(data)
        repository().put(self,bytes(data));return len(data)
    def write_text(self,data,encoding=None,errors=None,newline=None):
        if not managed(self):return super().write_text(data,encoding=encoding,errors=errors,newline=newline)
        self.write_bytes(data.encode(encoding or 'utf-8',errors or 'strict'));return len(data)
    def open(self,mode='r',buffering=-1,encoding=None,errors=None,newline=None):
        if not managed(self):return super().open(mode,buffering,encoding,errors,newline)
        exists=self.is_file()
        if 'x' in mode and exists:raise FileExistsError(str(self))
        if 'r' in mode and not exists:raise FileNotFoundError(str(self))
        raw=self.read_bytes() if exists and ('r' in mode or 'a' in mode) else b''
        stream=_Buffer(self,mode,raw)
        return stream if 'b' in mode else io.TextIOWrapper(stream,encoding=encoding or 'utf-8',errors=errors,newline=newline)
    def exists(self,*,follow_symlinks=True):return repository().exists(self) if managed(self) else super().exists(follow_symlinks=follow_symlinks)
    def is_file(self,*,follow_symlinks=True):return repository().exists(self,'file') if managed(self) else super().is_file(follow_symlinks=follow_symlinks)
    def is_dir(self,*,follow_symlinks=True):return repository().exists(self,'directory') if managed(self) else super().is_dir(follow_symlinks=follow_symlinks)
    def mkdir(self,mode=0o777,parents=False,exist_ok=False):
        if not managed(self):return super().mkdir(mode=mode,parents=parents,exist_ok=exist_ok)
        if self.exists():
            if exist_ok and self.is_dir():return
            raise FileExistsError(str(self))
        repository().put(self,b'',kind='directory')
    def glob(self,pattern,**kwargs):
        if not managed(self):yield from super().glob(pattern,**kwargs);return
        base=resource_key(self)+'/'
        seen=set()
        for key,_ in repository().keys():
            if key.startswith(base) and PurePosixPath(key[len(base):]).full_match(pattern):
                seen.add(key);yield DataPath(ROOT/key)
        # Retained model packages remain discoverable, never a data fallback.
        for path in NativePath(self).glob(pattern,**kwargs):
            if path.is_file() and not managed(path) and resource_key(path) not in seen:yield DataPath(path)
    def rglob(self,pattern,**kwargs):
        if not managed(self):yield from super().rglob(pattern,**kwargs);return
        base=resource_key(self)+'/'
        seen=set()
        for key,_ in repository().keys():
            if key.startswith(base) and (fnmatch.fnmatch(key[len(base):],pattern) or NativePath(key[len(base):]).match(pattern)):
                seen.add(key);yield DataPath(ROOT/key)
        for path in NativePath(self).rglob(pattern,**kwargs):
            if path.is_file() and not managed(path) and resource_key(path) not in seen:yield DataPath(path)
    def iterdir(self):
        if not managed(self):yield from super().iterdir();return
        base=resource_key(self)+'/'
        names={key[len(base):].split('/')[0] for key,_ in repository().keys() if key.startswith(base)}
        yield from (self/name for name in sorted(names))
    def unlink(self,missing_ok=False):
        if not managed(self):return super().unlink(missing_ok=missing_ok)
        repository().remove(self,missing_ok)
    def replace(self,target):
        dest=DataPath(target)
        if managed(self)!=managed(dest):raise ValueError('CN SQL/disk move refused')
        if not managed(self):return DataPath(super().replace(dest))
        repository().move(self,dest);return dest
    rename=replace
    def stat(self,*,follow_symlinks=True):
        if not managed(self):return super().stat(follow_symlinks=follow_symlinks)
        raw=self.read_bytes();return SimpleNamespace(st_size=len(raw),st_mtime=0)


def frame_input(path):
    return io.BytesIO(DataPath(path).read_bytes()) if isinstance(path,(str,NativePath)) and managed(path) else path


def read_parquet(path,*args,**kwargs):return pd.read_parquet(frame_input(path),*args,**kwargs)
def read_csv(path,*args,**kwargs):return pd.read_csv(frame_input(path),*args,**kwargs)


@contextmanager
def gzip_open(path,mode='rb',encoding=None,**kwargs):
    import gzip
    if not managed(path):
        with gzip.open(path,mode,encoding=encoding,**kwargs) as stream:yield stream
        return
    path=DataPath(path)
    writing=any(k in mode for k in ('w','x','a'))
    if writing and 'a' in mode:raise ValueError('CN compressed SQL append is unsupported')
    if writing:
        raw=io.BytesIO()
        with gzip.GzipFile(fileobj=raw,mode='wb',mtime=0) as compressed:
            if 't' in mode:
                with io.TextIOWrapper(compressed,encoding=encoding or 'utf-8') as stream:yield stream
            else:yield compressed
        repository().put(path,raw.getvalue(),exclusive='x' in mode)
    else:
        raw=gzip.decompress(path.read_bytes())
        with (io.StringIO(raw.decode(encoding or 'utf-8'),newline=None) if 't' in mode else io.BytesIO(raw)) as stream:yield stream


def write_parquet(frame,path,*args,**kwargs):
    if isinstance(path,(str,NativePath)) and managed(path):
        stream=io.BytesIO();frame.to_parquet(stream,*args,**kwargs);DataPath(path).write_bytes(stream.getvalue())
    else:frame.to_parquet(path,*args,**kwargs)


def model_file(path):
    """Only native model packages need a physical directory for their library."""
    path=NativePath(path)
    if managed(path):raise ValueError('CN model output is not an allowed model filename')
    path.parent.mkdir(parents=True,exist_ok=True)
    return path


@contextmanager
def campaign_lock(path):
    if managed(path):
        with repository().lock(str(path)):yield
    else:
        import msvcrt
        with NativePath(path).open('a+b') as stream:
            stream.seek(0,2)
            if stream.tell()==0:stream.write(b'0');stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
            try:yield
            finally:stream.seek(0);msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
