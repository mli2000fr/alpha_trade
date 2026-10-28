"""Primary SQL repository for FR collectors.

Logical resource keys retain old names to reuse existing SQL history. They are
not filesystem paths in SQL mode. Missing SQL data never falls back to disk.
The file adapter is for historical/offline tools outside an operational session.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
import fnmatch
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[2]/'artifacts/fr'
_SESSION = ContextVar('fr_primary_sql', default=None)
TABLES = ('fr_collection_objects','fr_collection_object_parts','fr_collection_versions',
          'fr_collection_heads','fr_collection_runs')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def clock():
    return datetime.now(UTC).replace(tzinfo=None)


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, allow_nan=False)


def active():
    return _SESSION.get()


@contextmanager
def use(repository):
    token = _SESSION.set(repository)
    try:
        yield repository
    finally:
        _SESSION.reset(token)


class Repository:
    def __init__(self, engine, *, root=ROOT):
        self.engine, self.root = engine, Path(root).resolve()

    def check_schema(self):
        from service.fr import batch_research_store as typed
        typed.check_schema(self.engine)
        with self.engine.connect() as c:
            for table in TABLES:
                c.execute(text(f'SELECT * FROM {table} LIMIT 0'))

    def identity(self, path):
        from service.fr.batch_research_store import FOLDERS
        path = Path(path).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError('Ressource SQL hors périmètre FR')
        rel = path.relative_to(self.root).as_posix()
        bits = rel.split('/')
        if len(bits)>=2 and bits[0]=='operations':
            batch = bits[2] if bits[1]=='runs' and len(bits)>2 else {v:k for k,v in FOLDERS.items()}.get(bits[1])
            if bits[1]=='staging_runs':
                batch='fr_daily_bars_sync'
            if batch is None:
                raise ValueError('Famille SQL FR inconnue : '+bits[1])
        else:
            batch = 'fr_reference_inputs'
        return batch, rel, sha(rel.encode())

    def _legacy(self, c, batch, rel):
        # Read former file archives from SQL, never re-open the old file.
        if not rel.startswith('operations/'):
            return None
        key = rel[len('operations/'):]
        row = c.execute(text('SELECT d.document_json,d.content_sha256 FROM fr_batch_research_file_versions f '
            'JOIN fr_batch_research_documents d USING(document_id) WHERE f.batch_name=:batch '
            'AND f.relative_path=:key ORDER BY f.file_modified_at DESC,f.imported_at DESC LIMIT 1'),
            dict(batch=batch,key=key)).first()
        if row:
            raw = row[0].encode('utf-8')
            if sha(raw)!=row[1]:
                raise ValueError('Ancien document SQL corrompu')
            return raw
        if batch=='fr_options_open_interest_sync' and '/raw/' in rel:
            raw = c.execute(text('SELECT body FROM fr_option_oi_public_responses WHERE body_sha256=:hash LIMIT 1'),
                            dict(hash=rel.rsplit('/',1)[-1])).scalar_one_or_none()
            if raw is not None and sha(raw)!=rel.rsplit('/',1)[-1]:
                raise ValueError('Réponse OI SQL corrompue')
            return raw
        return None

    def get(self, path):
        batch,rel,key = self.identity(path)
        with self.engine.connect() as c:
            h = c.execute(text('SELECT content_sha256,resource_key FROM fr_collection_heads '
                'WHERE batch_name=:batch AND resource_sha256=:key'),dict(batch=batch,key=key)).first()
            if h is None:
                raw = self._legacy(c,batch,rel)
                if raw is None:
                    raise FileNotFoundError('Ressource absente de SQL : '+rel)
                return raw
            if h[1]!=rel:
                raise ValueError('Collision de clé de ressource SQL')
            size = c.execute(text('SELECT byte_length FROM fr_collection_objects WHERE content_sha256=:hash'),
                             dict(hash=h[0])).scalar_one()
            parts = c.execute(text('SELECT part_no,body FROM fr_collection_object_parts '
                'WHERE content_sha256=:hash ORDER BY part_no'),dict(hash=h[0])).all()
        if [r[0] for r in parts]!=list(range(len(parts))):
            raise ValueError('Objet SQL incomplet')
        raw = b''.join(r[1] for r in parts)
        if len(raw)!=size or sha(raw)!=h[0]:
            raise ValueError('Objet SQL corrompu')
        return raw

    def exists(self,path):
        try:
            self.get(path)
            return True
        except FileNotFoundError:
            return False

    def paths(self, folder, pattern='*.json'):
        batch,rel,_ = self.identity(folder)
        with self.engine.connect() as c:
            keys = set(c.execute(text('SELECT resource_key FROM fr_collection_heads WHERE batch_name=:batch'),
                                 dict(batch=batch)).scalars())
            old = c.execute(text('SELECT DISTINCT relative_path FROM fr_batch_research_file_versions '
                                 'WHERE batch_name=:batch'),dict(batch=batch)).scalars()
            keys.update('operations/'+p for p in old)
        prefix = rel+'/'
        return [self.root/key for key in sorted(keys) if key.startswith(prefix)
                and '/' not in key[len(prefix):] and fnmatch.fnmatch(key[len(prefix):],pattern)]

    def put(self,path,raw,*,is_json=False):
        from service.fr import batch_research_store as typed
        batch,rel,key = self.identity(path)
        content, now = sha(raw), clock()
        # A successful provider body survives any subsequent parsing failure.
        with self.engine.begin() as c:
            if not c.execute(text('SELECT 1 FROM fr_collection_objects WHERE content_sha256=:hash'),dict(hash=content)).scalar():
                prefix = 'INSERT IGNORE' if self.engine.dialect.name=='mysql' else 'INSERT OR IGNORE'
                c.execute(text(prefix+' INTO fr_collection_objects VALUES (:hash,:size,:now)'),
                          dict(hash=content,size=len(raw),now=now))
                parts = [raw[i:i+1_000_000] for i in range(0,len(raw),1_000_000)] or [b'']
                c.execute(text(prefix+' INTO fr_collection_object_parts VALUES (:hash,:part,:body)'),
                          [dict(hash=content,part=i,body=b) for i,b in enumerate(parts)])
            prefix = 'INSERT IGNORE' if self.engine.dialect.name=='mysql' else 'INSERT OR IGNORE'
            c.execute(text(prefix+' INTO fr_collection_versions '
                '(batch_name,resource_sha256,content_sha256,resource_key,stored_at,available_at) '
                'VALUES (:batch,:key,:hash,:rel,:now,NULL)'),dict(batch=batch,key=key,hash=content,rel=rel,now=now))
        data = json.loads(raw) if is_json else None
        if is_json and batch in typed.PROVIDERS:
            identities=self.identities() if batch in ('fr_security_master_sync','fr_amf_short_sync','fr_dila_disclosures_sync') else {}
            table,rows = typed.normalized(batch,rel.removeprefix('operations/'),data,identities)
        else:
            table,rows = None,[]
        with self.engine.begin() as c:
            if is_json and batch in typed.PROVIDERS:
                document_id = typed.document_key(batch,content)
                if not c.execute(text('SELECT 1 FROM fr_batch_research_documents WHERE document_id=:id'),dict(id=document_id)).scalar():
                    observed = typed.clock(data.get('observed_at') or data.get('last_observed_at')) if isinstance(data,dict) else None
                    available = typed.clock(data.get('available_at') or data.get('last_observed_at')) if isinstance(data,dict) else None
                    if observed and available and available<observed:
                        raise ValueError('Disponibilité source SQL contradictoire')
                    typed.insert(c,typed.DOCUMENTS,[dict(document_id=document_id,batch_name=batch,market_code='FR_EQ',
                        provider=typed.PROVIDERS[batch],parser_version=typed.PARSER,content_sha256=content,
                        source_observed_at=observed,source_available_at=available,sql_available_at=clock(),
                        document_json=raw.decode('utf-8'),record_count=len(rows),ml_eligible=False,canonical=False,
                        historical_pit_qualified=False)])
                    if table:
                        typed.insert(c,table,[dict(document_id=document_id,**r) for r in rows])
                if isinstance(data,dict) and data.get('raw_sha256'):
                    observed,available=typed.clock(data.get('observed_at')),typed.clock(data.get('available_at'))
                    if observed and available and available>=observed:
                        c.execute(text('UPDATE fr_batch_research_documents SET source_observed_at=:observed,'
                            'source_available_at=:available WHERE batch_name=:batch AND content_sha256=:raw '
                            'AND (source_available_at IS NULL OR source_available_at>:available)'),
                            dict(batch=batch,raw=data['raw_sha256'],observed=observed,available=available))
            values = dict(batch=batch,key=key,hash=content,rel=rel,now=clock())
            c.execute(text('UPDATE fr_collection_versions SET available_at=COALESCE(available_at,:now) '
                'WHERE batch_name=:batch AND resource_sha256=:key AND content_sha256=:hash'),values)
            current = c.execute(text('SELECT resource_key FROM fr_collection_heads WHERE batch_name=:batch '
                                     'AND resource_sha256=:key'),values).scalar_one_or_none()
            if current is not None and current!=rel:
                raise ValueError('Collision de clé de ressource SQL')
            if current is None:
                c.execute(text('INSERT INTO fr_collection_heads VALUES (:batch,:key,:hash,:rel,:now)'),values)
            else:
                c.execute(text('UPDATE fr_collection_heads SET content_sha256=:hash,updated_at=:now '
                    'WHERE batch_name=:batch AND resource_sha256=:key'),values)
        if getattr(self,'current_result',None):
            run,result=self.current_result
            self.save_run(run,{**result,'sql_writes':True})
        return content

    def identities(self):
        path=self.root/'sprint6c_reference/identities.jsonl.gz'
        rows=[json.loads(line) for line in gzip.decompress(self.get(path)).decode('utf-8').splitlines() if line.strip()]
        return {r['isin']:r.get('provider_symbol') for r in rows if r.get('identity_state')=='VERIFIED_RESEARCH'}

    @contextmanager
    def lock(self,name):
        with self.lock_many([name]):
            yield

    @contextmanager
    def lock_many(self,names):
        if self.engine.dialect.name!='mysql':
            yield
            return
        with self.engine.connect() as c:
            acquired=[]
            try:
                for name in names:
                    key='FRPrimary:'+sha(name.encode())[:40]
                    if c.execute(text('SELECT GET_LOCK(:key,0)'),dict(key=key)).scalar()!=1:
                        raise RuntimeError('Collecte SQL FR déjà en cours : '+name)
                    acquired.append(key)
                yield
            finally:
                for key in reversed(acquired):
                    c.execute(text('SELECT RELEASE_LOCK(:key)'),dict(key=key))

    def save_run(self,run_id,result):
        started=datetime.fromisoformat(result['started_at']).astimezone(UTC).replace(tzinfo=None)
        finished=result.get('finished_at')
        finished=datetime.fromisoformat(finished).astimezone(UTC).replace(tzinfo=None) if finished else None
        with self.engine.begin() as c:
            params=dict(run=run_id,batch=result['batch'],status=result['status'],started=started,
                        finished=finished,summary=encode(result))
            if c.execute(text('SELECT 1 FROM fr_collection_runs WHERE operational_run_id=:run'),params).scalar():
                c.execute(text('UPDATE fr_collection_runs SET status=:status,finished_at=:finished,summary_json=:summary '
                               'WHERE operational_run_id=:run'),params)
            else:
                c.execute(text('INSERT INTO fr_collection_runs VALUES (:run,:batch,:status,:started,:finished,:summary)'),params)


def read_bytes(path):
    return active().get(path) if active() else Path(path).read_bytes()


def read_text(path,encoding='utf-8'):
    return read_bytes(path).decode(encoding)


def exists(path):
    return active().exists(path) if active() else Path(path).exists()


def paths(folder,pattern='*.json'):
    return active().paths(folder,pattern) if active() else list(Path(folder).glob(pattern))


def write_bytes(path,raw):
    if active():
        return active().put(path,raw)
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    Path(path).write_bytes(raw)


def write_json(path,payload):
    if active():
        return active().put(path,encode(payload).encode(),is_json=True)
    from service.inpi.files import atomic
    return atomic(Path(path),payload)


def identity_rows(path):
    return [json.loads(line) for line in gzip.decompress(read_bytes(path)).decode('utf-8').splitlines() if line.strip()]


def take_lock(path):
    if active():
        return None  # Operational runner holds a MySQL named lock throughout.
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    try:
        fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError:
        raise RuntimeError('Collecte FR déjà verrouillée ; vérifier le processus') from None
    with os.fdopen(fd,'w') as stream:
        stream.write(str(os.getpid()))
    return path


def release_lock(path):
    if path is not None:
        Path(path).unlink(missing_ok=True)


def zip_source(path):
    return io.BytesIO(read_bytes(path)) if active() else path


def esma_download(item,root,context):
    from service.fr.esma_firds_download import _download,_check
    if not active():
        return _download(item,root,context)
    target=Path(root)/item['date'][:4]/item['file']
    with tempfile.TemporaryDirectory(prefix='fr-esma-work-') as work:
        local=Path(work)/item['date'][:4]/item['file']
        if exists(target):
            local.parent.mkdir(parents=True,exist_ok=True)
            local.write_bytes(read_bytes(target))
        proof=_download(item,Path(work),context)
        proof.update(_check(local,item['md5']))
        write_bytes(target,local.read_bytes())
        return proof
