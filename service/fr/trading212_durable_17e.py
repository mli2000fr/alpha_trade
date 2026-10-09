"""Durable synthetic journal; file-only, no SQL, broker API or credentials."""
from __future__ import annotations

import hashlib
import json
import os
from decimal import Decimal
from threading import RLock

from service.fr.broker_contract_17a import FrenchTestIntent
from service.fr.prediction_contract_16a import ROOT, scoped_path
from service.fr.trading212_reconciliation_17d import SyntheticOrderJournal


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


class JournalBlocked(RuntimeError):
    pass


class FakeTransport:
    """Only accepted transport, returns canned synthetic evidence without I/O."""
    def __init__(self, outcome='accepted'):
        if outcome not in {'accepted', 'timeout', 'crash'}:
            raise ValueError('Unknown fake outcome')
        self.outcome = outcome
        self.calls = 0

    def submit(self, intent_id):
        self.calls += 1
        if self.outcome == 'crash':
            raise SystemExit('Synthetic process interruption')
        if self.outcome == 'timeout':
            raise TimeoutError('Synthetic timeout')
        return {'broker_id': 'fake-' + intent_id, 'status': 'NEW',
                'filled': '0', 'sequence': 0}


class DurableSyntheticJournal:
    simulated = True
    orders_allowed = False

    def __init__(self, *, directory, max_intent_notional_eur, root=ROOT):
        self.path = scoped_path(directory, root)
        self.path.mkdir(parents=True, exist_ok=True)
        self._lockfile = (self.path / 'writer.lock').open('a+b')
        self._closed = False
        self._poisoned = False
        self._records = []
        self._mutex = RLock()
        self._limit = max_intent_notional_eur
        self._state = SyntheticOrderJournal(self._limit)
        try:
            self._acquire()
            path = self.path / 'events.jsonl'
            if path.exists():
                if path.stat().st_size > 32 * 1024 * 1024:
                    raise JournalBlocked('Oversized journal')
                raw = path.read_bytes()
                if not raw or not raw.endswith(b'\n'):
                    raise JournalBlocked('Incomplete or oversized journal: manual review required')
                previous = '0' * 64
                for index, line in enumerate(raw.splitlines()):
                    record = json.loads(line)
                    digest = record.pop('sha256')
                    if (record['sequence'] != index or record['previous'] != previous
                            or hashlib.sha256(canonical(record)).hexdigest() != digest):
                        raise JournalBlocked('Journal integrity mismatch')
                    if index == 0:
                        if record['event'] != self._config():
                            raise JournalBlocked('Journal context/limit mismatch')
                    else:
                        self._apply(self._state, record['event'])
                    record['sha256'] = digest
                    self._records.append(record)
                    previous = digest
            if not self._records:
                self._append(self._config())
            # A persisted attempt without acknowledgement must NEVER be sent again.
            for key, order in list(self._state._orders.items()):
                if order.status == 'SUBMISSION_PENDING_SYNTHETIC':
                    self._change({'op': 'submission_timeout', 'intent_id': key})
        except BaseException:
            self.close()
            raise

    def _config(self):
        return {'op': 'config', 'schema_version': 1, 'market_code': 'FR_EQ',
                'account': 'fr_simulated', 'orders_allowed': False,
                'max_intent_notional_eur': str(self._limit)}

    def _acquire(self):
        # OS advisory lock is released even after process death; do not delete lock files.
        self._lockfile.seek(0, 2)
        if self._lockfile.tell() == 0:
            self._lockfile.write(b'0')
            self._lockfile.flush()
        self._lockfile.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self._lockfile.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._lockfile.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise JournalBlocked('Another journal writer is active') from None

    def _ensure(self):
        if self._closed or self._poisoned:
            raise JournalBlocked('Journal closed or persistence uncertain')

    @staticmethod
    def _apply(state, event):
        op = event['op']
        args = {k: v for k, v in event.items() if k not in {'op', 'expected_rejection'}}
        if op == 'register':
            args['reference_price_eur'] = Decimal(args['reference_price_eur'])
            action = lambda: state.register(FrenchTestIntent(**args))
        elif op == 'observe':
            args['filled'] = Decimal(args['filled'])
            action = lambda: state.observe(**args)
        elif op in {'begin_dispatch', 'submission_timeout', 'request_cancel', 'kill'}:
            action = lambda: getattr(state, op)(**args)
        else:
            raise JournalBlocked('Unknown durable event')
        try:
            result = action()
        except ValueError:
            if event.get('expected_rejection') is not True:
                raise
            return None
        if event.get('expected_rejection'):
            raise JournalBlocked('Rejection replay mismatch')
        return result

    def _append(self, event):
        record = {'sequence': len(self._records), 'previous': self._records[-1]['sha256']
                  if self._records else '0' * 64, 'event': event}
        record['sha256'] = hashlib.sha256(canonical(record)).hexdigest()
        try:
            with (self.path / 'events.jsonl').open('ab') as stream:
                line = canonical(record) + b'\n'
                if stream.write(line) != len(line):
                    raise OSError('Incomplete write')
                stream.flush()
                os.fsync(stream.fileno())
        except OSError:
            self._poisoned = True
            raise JournalBlocked('Journal persistence failed; dispatch prohibited') from None
        self._records.append(record)

    def _change(self, event):
        with self._mutex:
            return self._change_locked(event)

    def _change_locked(self, event):
        self._ensure()
        # Validate on a reconstructed candidate; append/fsync BEFORE exposing new state.
        candidate = SyntheticOrderJournal(self._limit)
        for record in self._records[1:]:
            self._apply(candidate, record['event'])
        rejection = None
        try:
            result = self._apply(candidate, event)
        except ValueError as exc:
            event = {**event, 'expected_rejection': True}
            rejection = exc
            result = None
        self._append(event)
        self._state = candidate
        if rejection is not None:
            raise rejection
        return result

    def register(self, intent):
        from dataclasses import asdict
        args = asdict(intent)
        args['reference_price_eur'] = str(args['reference_price_eur'])
        return self._change({'op': 'register', **args})

    def submit_fake(self, intent_id, transport):
        with self._mutex:
            return self._submit_fake_locked(intent_id, transport)

    def _submit_fake_locked(self, intent_id, transport):
        if type(transport) is not FakeTransport:
            raise JournalBlocked('Only exact offline FakeTransport permitted')
        self._change({'op': 'begin_dispatch', 'intent_id': intent_id})
        try:
            response = transport.submit(intent_id)
        except TimeoutError:
            return self._change({'op': 'submission_timeout', 'intent_id': intent_id})
        return self.observe(intent_id, **response)

    def observe(self, intent_id, *, broker_id, status, filled, sequence):
        return self._change({'op': 'observe', 'intent_id': intent_id,
                             'broker_id': broker_id, 'status': status,
                             'filled': str(filled), 'sequence': sequence})

    def request_cancel(self, intent_id):
        return self._change({'op': 'request_cancel', 'intent_id': intent_id})

    def kill(self):
        return self._change({'op': 'kill'})

    def snapshot(self, intent_id):
        with self._mutex:
            self._ensure()
            return self._state.snapshot(intent_id)

    def close(self):
        with self._mutex:
            if not self._closed:
                self._closed = True
                self._lockfile.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
