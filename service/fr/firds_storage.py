"""FIRDS logical paths backed by SQL, including standalone historical CLIs.

Only the canonical FIRDS subtree is routed automatically. Offline fixtures and
other research folders remain files. An absent SQL resource never falls back
to a local copy. No archive is downloaded by a read operation.
"""
from functools import lru_cache
import fnmatch
import io
import json
from pathlib import Path

from sqlalchemy import text

from service.fr import collection_storage as storage

ROOT = storage.ROOT / 'esma_firds'


@lru_cache(maxsize=1)
def default_repository():
    from service.fr.batch_research_store import engine_fr
    engine = engine_fr()
    if engine.url.database != 'alpha_trade_fr':
        raise ValueError('Archives FIRDS : base alpha_trade_fr requise')
    return storage.Repository(engine)


def repository(path):
    path = Path(path).resolve()
    current = storage.active()
    if current is not None and path.is_relative_to(current.root):
        return current
    if path.is_relative_to(ROOT.resolve()):
        return default_repository()
    return None


def read_bytes(path):
    repo = repository(path)
    return repo.get(path) if repo is not None else Path(path).read_bytes()


def read_text(path, encoding='utf-8'):
    return read_bytes(path).decode(encoding)


def is_file(path):
    repo = repository(path)
    if repo is None:
        return Path(path).is_file()
    batch, rel, key = repo.identity(path)
    with repo.engine.connect() as connection:
        row = connection.execute(text('SELECT resource_key FROM fr_collection_heads '
            'WHERE batch_name=:batch AND resource_sha256=:key'), dict(batch=batch, key=key)).scalar_one_or_none()
    if row is not None and row != rel:
        raise ValueError('Collision de cle de ressource SQL')
    return row is not None


def paths(folder, pattern='*.json', *, recursive=False):
    repo = repository(folder)
    if repo is None:
        return sorted(Path(folder).rglob(pattern) if recursive else Path(folder).glob(pattern))
    batch, rel, _ = repo.identity(folder)
    with repo.engine.connect() as connection:
        keys = connection.execute(text('SELECT resource_key FROM fr_collection_heads '
            'WHERE batch_name=:batch'), dict(batch=batch)).scalars().all()
    prefix = rel + '/'
    return sorted(repo.root / key for key in keys if key.startswith(prefix)
        and (recursive or '/' not in key[len(prefix):])
        and fnmatch.fnmatch(key.rsplit('/', 1)[-1], pattern))


def zip_source(path):
    return io.BytesIO(read_bytes(path)) if repository(path) is not None else path


def open_binary(path):
    return io.BytesIO(read_bytes(path)) if repository(path) is not None else Path(path).open('rb')


def write_json(path, payload):
    repo = repository(path)
    if repo is not None:
        # Keep the historical JSON representation and raw hashes reproducible.
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode('utf-8')
        return repo.put(path, raw, is_json=True)
    from service.fr.eodhd_backfill import _atomic_json
    return _atomic_json(Path(path), payload)


def download(item, root, context):
    repo = repository(Path(root) / item['date'][:4] / item['file'])
    if repo is None:
        raise ValueError('SQL download requires a SQL resource path')
    with storage.use(repo):
        return storage.esma_download(item, root, context)
