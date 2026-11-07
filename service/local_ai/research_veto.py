"""Research-only news veto. No trading imports, network, SQL server or orders."""
import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import jsonschema


SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'required': ['symbol', 'assessment', 'evidence_quality', 'reason', 'facts', 'counterarguments'],
    'properties': {
        'symbol': {'type': 'string'},
        'assessment': {'enum': ['FAVORABLE', 'UNFAVORABLE', 'INDETERMINABLE']},
        'evidence_quality': {'enum': ['SUFFICIENT', 'INSUFFICIENT']},
        'reason': {'type': 'string', 'minLength': 1, 'maxLength': 2500},
        'counterarguments': {'type': 'array', 'maxItems': 8,
                             'items': {'type': 'string', 'maxLength': 1500}},
        'facts': {'type': 'array', 'maxItems': 8, 'items': {
            'type': 'object', 'additionalProperties': False,
            'required': ['source_id', 'quote', 'impact', 'issuer_is_subject'],
            'properties': {'source_id': {'type': 'string'},
                           'quote': {'type': 'string', 'minLength': 12, 'maxLength': 280},
                           'impact': {'enum': ['BULLISH', 'BEARISH', 'MIXED']},
                           'issuer_is_subject': {'type': 'boolean'}}}},
    },
}


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False,
                      separators=(',', ':'), default=str)


def key_for(request, revision):
    return hashlib.sha256(encoded({'version': 1, 'request': request,
                                  'declared_model_revision': revision}).encode()).hexdigest()


def validate_response(response, packet):
    """Validate syntax, exact citations and mechanical veto; no semantic truth claim."""
    if response.get('finish_reason') != 'stop':
        raise ValueError('Réponse incomplète ou tronquée')
    if response.get('model') != packet['model']:
        raise ValueError('Modèle de réponse différent du modèle figé')
    def unique(pairs):
        result = {}
        for k, v in pairs:
            if k in result:
                raise ValueError('Clé JSON dupliquée')
            result[k] = v
        return result
    value = json.loads(response['content'], object_pairs_hook=unique,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nombre non fini')))
    jsonschema.validate(value, SCHEMA)
    if value['symbol'] != packet['context']['symbol']:
        raise ValueError('Symbole de réponse différent du dossier')
    sources = {s['source_id']: s for s in packet['context']['news']}
    bearish = False
    whitespace_normalized = 0
    for fact in value['facts']:
        source = sources.get(fact['source_id'])
        if source is None:
            raise ValueError('Citation absente du texte fourni')
        if fact['quote'] not in source['text']:
            # Paragraph breaks vs spaces are typography, not missing words.
            # Punctuation, order and every non-whitespace character stay exact.
            normalize = lambda s: re.sub(r'\s+', ' ', s).strip()
            if normalize(fact['quote']) not in normalize(source['text']):
                raise ValueError('Citation absente du texte fourni')
            whitespace_normalized += 1
        bearish |= (fact['impact'] == 'BEARISH' and fact['issuer_is_subject']
                    and source['primary_ticker_association'])
    veto = value['assessment'] == 'UNFAVORABLE' and value['evidence_quality'] == 'SUFFICIENT' and bearish
    return dict(valid=True, veto=bool(veto), analysis=value,
                citation_whitespace_normalized=whitespace_normalized,
                attribution='MODEL_ASSERTED_NOT_INDEPENDENTLY_VERIFIED',
                reason='BEARISH_ISSUER_NEWS_VETO' if veto else 'KEEP_BASELINE')


class Cache:
    """Append-only SQLite attempts plus exact-request success reuse; scoped to research."""
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.execute('''CREATE TABLE IF NOT EXISTS attempts (
            id INTEGER PRIMARY KEY, request_key TEXT NOT NULL, created_at TEXT NOT NULL,
            request_json TEXT NOT NULL, response_json TEXT, validation_json TEXT NOT NULL)''')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_attempts_key ON attempts(request_key,id)')
        self.conn.commit()

    def latest(self, key):
        row = self.conn.execute('SELECT request_json,response_json,validation_json FROM attempts '
                                'WHERE request_key=? ORDER BY id DESC LIMIT 1', (key,)).fetchone()
        if row is None:
            return None
        return dict(request=json.loads(row[0]), response=json.loads(row[1]) if row[1] else None,
                    validation=json.loads(row[2]))

    def put(self, key, request, response, validation):
        self.conn.execute('INSERT INTO attempts(request_key,created_at,request_json,response_json,validation_json) '
                          'VALUES(?,?,?,?,?)', (key, datetime.now(timezone.utc).isoformat(), encoded(request),
                                              encoded(response) if response else None, encoded(validation)))
        self.conn.commit()

    def close(self):
        self.conn.close()
