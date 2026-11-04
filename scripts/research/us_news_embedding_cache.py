"""Persistent research-only embedding cache and durable, fail-closed USD budget.

SQLite is local to research artifacts. No production SQL, automatic API retries,
Web search, chat completion, or broker capability is exposed by this module.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
import gzip
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import uuid

import numpy as np

MODEL = 'text-embedding-3-large'
DIMENSIONS = 256
RATE = Decimal('0.13') / Decimal(1_000_000)
CAP = Decimal('3')


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def identity(text):
    return sha(dict(model=MODEL, dimensions=DIMENSIONS, text=text,
                    protocol='frozen-news-headline-summary-excerpt-v1'))


@contextmanager
def exclusive(path):
    """OS lock, released on exit/crash; never guess another process is dead."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as stream:
        stream.seek(0, 2)
        if stream.tell() == 0:
            stream.write(b'0'); stream.flush()
        stream.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


class EmbeddingCache:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=30)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS embedding (
            cache_key TEXT PRIMARY KEY, text_sha256 TEXT NOT NULL,
            model TEXT NOT NULL, dimensions INTEGER NOT NULL, tokens INTEGER NOT NULL,
            vector BLOB NOT NULL, vector_sha256 TEXT NOT NULL, call_id TEXT NOT NULL,
            created_at TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS paid_call (
            call_id TEXT PRIMARY KEY, campaign TEXT NOT NULL, request_sha256 TEXT NOT NULL,
            status TEXT NOT NULL, reserved_usd TEXT NOT NULL, charged_usd TEXT NOT NULL,
            created_at TEXT NOT NULL, usage_tokens INTEGER, response_sha256 TEXT);
          CREATE TABLE IF NOT EXISTS campaign (
            campaign TEXT PRIMARY KEY, protocol_sha256 TEXT NOT NULL, cap_usd TEXT NOT NULL);
        ''')
        self.db.commit()

    def close(self):
        self.db.close()

    def register(self, campaign, protocol_sha):
        row = self.db.execute('SELECT protocol_sha256,cap_usd FROM campaign WHERE campaign=?',
                              (campaign,)).fetchone()
        if row and row != (protocol_sha, str(CAP)):
            raise ValueError('Campaign protocol/cap changed; refusal to reset budget')
        self.db.execute('INSERT OR IGNORE INTO campaign VALUES(?,?,?)',
                        (campaign, protocol_sha, str(CAP)))
        self.db.commit()

    def get(self, key):
        row = self.db.execute('SELECT vector,vector_sha256,dimensions,model FROM embedding WHERE cache_key=?',
                              (key,)).fetchone()
        if row is None:
            return None
        blob, checksum, dims, model = row
        if hashlib.sha256(blob).hexdigest() != checksum or dims != DIMENSIONS or model != MODEL:
            raise ValueError('Corrupt or incompatible embedding cache')
        vector = np.frombuffer(blob, dtype='<f4').copy()
        if vector.shape != (DIMENSIONS,) or not np.isfinite(vector).all() or np.linalg.norm(vector) == 0:
            raise ValueError('Invalid cached vector')
        return vector

    def summary(self, campaign):
        rows = self.db.execute('SELECT status,charged_usd,usage_tokens FROM paid_call WHERE campaign=?',
                               (campaign,)).fetchall()
        return dict(api_calls=len(rows), completed_calls=sum(r[0] == 'COMPLETE' for r in rows),
            unresolved_calls=sum(r[0] != 'COMPLETE' for r in rows),
            committed_usd=str(sum((Decimal(r[1]) for r in rows), Decimal(0))),
            usage_tokens=sum(r[2] or 0 for r in rows), max_budget_usd=str(CAP))

    def reserve(self, campaign, request, tokens):
        # Exact tokenizer count plus 25% and 32 tokens/input reserved before POST.
        upper_tokens = (tokens * 125 + 99)//100 + 32*len(request['input'])
        reserve = Decimal(upper_tokens) * RATE
        request_sha = sha(request)
        self.db.execute('BEGIN IMMEDIATE')
        try:
            if self.db.execute('SELECT 1 FROM campaign WHERE campaign=?', (campaign,)).fetchone() is None:
                raise ValueError('Unregistered campaign')
            rows = self.db.execute('SELECT request_sha256,status,charged_usd FROM paid_call WHERE campaign=?',
                                   (campaign,)).fetchall()
            if any(r[1] != 'COMPLETE' for r in rows):
                raise ValueError('Unresolved paid request: no automatic retry')
            if any(r[0] == request_sha for r in rows):
                raise ValueError('Request already paid; recover cache instead of paying again')
            total = sum((Decimal(r[2]) for r in rows), Decimal(0))
            if total + reserve > CAP:
                raise ValueError('USD 3 ceiling reached BEFORE request')
            call = uuid.uuid4().hex
            self.db.execute('INSERT INTO paid_call VALUES(?,?,?,?,?,?,?,?,?)',
                (call, campaign, request_sha, 'RESERVED', str(reserve), str(reserve), utc(), None, None))
            self.db.commit()
            return call, reserve
        except BaseException:
            self.db.rollback()
            raise

    def complete(self, call, articles, response, expected_tokens):
        tokens = response.get('usage', {}).get('total_tokens')
        data = response.get('data')
        if (type(tokens) is not int or tokens < 1 or response.get('model') != MODEL
                or not isinstance(data, list) or len(data) != len(articles)):
            raise ValueError('Invalid paid response/model/usage')
        if sorted(item.get('index') for item in data) != list(range(len(articles))):
            raise ValueError('Duplicate/missing response indexes')
        row = self.db.execute('SELECT reserved_usd,status FROM paid_call WHERE call_id=?', (call,)).fetchone()
        cost = Decimal(tokens)*RATE
        if row is None or row[1] != 'RESERVED' or cost > Decimal(row[0]):
            raise ValueError('Unexpected paid usage/reservation; stop')
        blobs = []
        for item in sorted(data, key=lambda a: a['index']):
            v = np.asarray(item['embedding'], dtype='<f4')
            if v.shape != (DIMENSIONS,) or not np.isfinite(v).all() or np.linalg.norm(v) == 0:
                raise ValueError('Invalid returned embedding')
            blobs.append(v.tobytes())
        if tokens != expected_tokens:
            raise ValueError('Tokenizer/provider token mismatch; stop before further calls')
        # Raw response is recoverable even if the subsequent SQLite commit fails.
        raw = self.path.parent/'responses'
        raw.mkdir(exist_ok=True)
        with gzip.open(raw/f'{call}.json.gz', 'xt', encoding='utf-8') as stream:
            json.dump(response, stream, separators=(',', ':'), allow_nan=False)
        with self.db:
            for article, blob in zip(articles, blobs):
                self.db.execute('INSERT INTO embedding VALUES(?,?,?,?,?,?,?,?,?)',
                    (article['key'], hashlib.sha256(article['text'].encode()).hexdigest(), MODEL,
                     DIMENSIONS, article['tokens'], blob, hashlib.sha256(blob).hexdigest(), call, utc()))
            self.db.execute('UPDATE paid_call SET status=?,charged_usd=?,usage_tokens=?,response_sha256=? WHERE call_id=?',
                            ('COMPLETE', str(cost), tokens, sha(response), call))
