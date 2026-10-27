"""SEC identity regression, offline; no provider calls or production SQL writes."""
from copy import deepcopy
from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import OperationalError

from service.forward_pit import batch
from service.forward_pit.outcomes import BatchRunError


ACCESSION = '0001477932-26-006377'
CIK = '0001938338'


class Result:
    def __init__(self, rows=None, first=None, rowcount=0):
        self.rows, self.row, self.rowcount = rows or [], first, rowcount

    def fetchall(self):
        return self.rows

    def mappings(self):
        return self

    def first(self):
        return self.row


class Engine:
    """Simulate the symbol/IID trigger and MySQL's update rowcount=2."""
    def __init__(self, existing=None, symbols=None, rejected=()):
        self.existing, self.symbols = deepcopy(existing or {}), symbols or []
        self.rejected, self.writes, self.statements = set(rejected), [], []

    def connect(self):
        return self

    def begin(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement, params=None):
        sql = str(statement)
        self.statements.append(sql)
        if 'FROM security_master_snapshots' in sql:
            assert 'available_at<=:observed' in sql
            return Result(rows=[SimpleNamespace(cik=c, symbol=s) for c, s in self.symbols])
        if sql.startswith('SELECT id,cik,symbol'):
            return Result(first=self.existing.get(params['a']))
        if sql.startswith('INSERT INTO sec_filing_raw'):
            assert 'symbol=COALESCE(symbol,VALUES(symbol))' in sql
            if params['accession'] in self.rejected:
                raise OperationalError(sql, {}, Exception(1644, 'symbol/instrument identity mismatch'))
            old = self.existing.get(params['accession'])
            # The regression: GLTKD's assigned IID cannot be used with GLTK.
            if old and old.get('instrument_id') and params['symbol'] != old['symbol']:
                raise OperationalError(sql, {}, Exception(1644, 'symbol/instrument identity mismatch'))
            self.writes.append(dict(params))
            self.existing[params['accession']] = dict(id=1, cik=params['cik'], symbol=params['symbol'],
                has_content=bool(params['content']), instrument_id=(old or {}).get('instrument_id'))
            return Result(rowcount=2 if old else 1)
        raise AssertionError('Unexpected SQL: '+sql)


def collect(monkeypatch, engine, lines=None, document_error=False, **options):
    lines = lines or [f'1938338|GlobalTech Corp|10-K/A|2026-10-21|edgar/data/1938338/{ACCESSION}.txt']
    response = SimpleNamespace(status_code=200, text='header\n'+'-'*80+'\n'+'\n'.join(lines),
                               raise_for_status=lambda: None)
    class Session:
        def __enter__(self):
            return self
        def __exit__(self, *_):
            pass
        def get(self, url, **kw):
            assert '/daily-index/' in url
            return response
    monkeypatch.setenv('SEC_EDGAR_USER_AGENT', 'alpha-trade test@example.com')
    monkeypatch.setattr(batch.requests, 'Session', Session)
    monkeypatch.setattr(batch, '_raw', lambda *a, **kw: None)
    monkeypatch.setattr(batch, '_previous_weekdays', lambda *a: [date(2026, 10, 21)])
    def document(*a, **kw):
        if document_error:
            raise RuntimeError('SEC document unavailable')
        return dict(content='Qualified filing content', acceptance=None, primary_document=None,
            content_url=a[1], used_primary_fallback=False, oversized_primary=False)
    monkeypatch.setattr(batch, '_download_sec_document', document)
    monkeypatch.setattr(batch.time, 'sleep', lambda *a: None)
    config = dict(forms='10-K/A,8-K', download_primary_documents=True, download_exhibits=False) | options
    return batch.sec_edgar_incremental(engine, config, 'sec-identity-test', False)


def test_retry_preserves_gltkd_symbol_and_instrument_not_latest_gltk(monkeypatch):
    existing = dict(id=13387, cik=CIK, symbol='GLTKD', instrument_id=67338, has_content=False)
    engine = Engine({ACCESSION: existing}, [(CIK, 'GLTK')])
    result = collect(monkeypatch, engine)
    assert engine.writes[0]['symbol'] == 'GLTKD'
    assert engine.existing[ACCESSION]['instrument_id'] == 67338
    assert result.failed == 0 and result.persisted == 1  # Not SQL update rowcount=2.
    assert result.details['filings_persisted'] == 1
    assert result.details['preserved_symbol_changes'] == [dict(accession=ACCESSION,
        stored_symbol='GLTKD', latest_symbol='GLTK')]


def test_new_filing_uses_unique_current_symbol(monkeypatch):
    engine = Engine(symbols=[(CIK, 'GLTK'), (CIK, 'GLTK')])
    result = collect(monkeypatch, engine)
    assert engine.writes[0]['symbol'] == 'GLTK' and result.persisted == 1


def test_missing_document_retry_keeps_old_identity_and_records_real_download_failure(monkeypatch):
    existing = dict(id=13387, cik=CIK, symbol='GLTKD', instrument_id=67338, has_content=False)
    engine = Engine({ACCESSION: existing}, [(CIK, 'GLTK')])
    result = collect(monkeypatch, engine, document_error=True)
    assert engine.writes[0]['symbol'] == 'GLTKD' and engine.writes[0]['content'] is None
    assert result.failed == 1 and result.persisted == 1
    assert result.details['persistence_error_count'] == 0
    assert result.details['document_errors'][0]['accession'] == ACCESSION


def test_multi_share_class_cik_does_not_choose_arbitrary_last_symbol(monkeypatch):
    for symbols in [[(CIK, 'GLTK'), (CIK, 'GLTKD')], [(CIK, 'GLTKD'), (CIK, 'GLTK')]]:
        engine = Engine(symbols=symbols)
        result = collect(monkeypatch, engine)
        assert engine.writes[0]['symbol'] is None  # Issuer filing retained, no stock invented.
        assert result.details['ambiguous_cik_count'] == 1
        assert result.details['ambiguous_cik_symbols'][CIK] == ['GLTK', 'GLTKD']


def test_existing_null_symbol_can_be_enriched_with_unique_current_symbol(monkeypatch):
    engine = Engine({ACCESSION: dict(id=1, cik=CIK, symbol=None, instrument_id=None, has_content=False)},
                    [(CIK, 'GLTK')])
    result = collect(monkeypatch, engine)
    assert result.failed == 0 and engine.writes[0]['symbol'] == 'GLTK'


def test_accession_cannot_receive_content_from_a_different_issuer(monkeypatch):
    engine = Engine({ACCESSION: dict(id=1, cik='0000001234', symbol='OTHER', has_content=False)},
                    [(CIK, 'GLTK')])
    with pytest.raises(BatchRunError) as error:
        collect(monkeypatch, engine)
    assert not engine.writes and error.value.outcome.failed == 1
    assert 'SEC_ACCESSION_CIK_MISMATCH' in error.value.outcome.details['persistence_errors'][0]['error']


def test_trigger_error_isolated_other_filings_kept_and_run_stays_failed(monkeypatch):
    other = '0000001234-26-000001'
    engine = Engine(symbols=[(CIK, 'GLTK'), ('0000001234', 'ABC')], rejected=[ACCESSION])
    lines = [f'1938338|GlobalTech Corp|10-K/A|2026-10-21|edgar/data/1938338/{ACCESSION}.txt',
             f'1234|Example Corp|8-K|2026-10-21|edgar/data/1234/{other}.txt']
    with pytest.raises(BatchRunError) as error:
        collect(monkeypatch, engine, lines)
    result = error.value.outcome
    assert [w['accession'] for w in engine.writes] == [other]
    assert result.received == 2 and result.persisted == 1 and result.failed == 1
    assert result.details['persistence_error_count'] == 1
    assert result.details['persistence_errors'][0]['phase'] == 'metadata_write'
    assert result.details['persistence_errors'][0]['accession'] == ACCESSION


def test_cik_normalization_and_duplicate_provider_rows_are_deterministic():
    mapping, ambiguous = batch._sec_cik_symbols([SimpleNamespace(cik='1938338', symbol=' gltk '),
        SimpleNamespace(cik=CIK, symbol='GLTK'), SimpleNamespace(cik='2', symbol=None)])
    assert mapping == {CIK: 'GLTK'} and not ambiguous
