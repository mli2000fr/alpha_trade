from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text

from service.eodhd.consensus_qualification import qualify, schema_summary
from service.forward_pit import public_macro as macro


def bls_payload(series='LNS14000000', value='4.1'):
    return {'status': 'REQUEST_SUCCEEDED', 'Results': {'series': [
        {'seriesID': series, 'data': [{'year': '2026', 'period': 'M09', 'value': value,
                                     'footnotes': [{'text': 'Preliminary'}]},
                                    {'year': '2026', 'period': 'M13', 'value': '4.0'}]}]}}


def h15_body():
    header = '<thead><tr><th id="col1">2026<br>Oct<br>8</th></tr></thead>'
    rows = ['<tr><th id="cmt">Treasury constant maturities</th></tr>',
            '<tr><th id="nominal">Nominal <a>9</a></th></tr>']
    for index, name in enumerate(macro.H15_SERIES):
        rows.append(f'<tr><th headers="cmt nominal">{name}</th>'
                    f'<td headers="col1">{index+3}.50</td></tr>')
    rows.extend(['<tr><th id="tips">Inflation indexed</th></tr>',
                 '<tr><th headers="cmt tips">10-year</th><td headers="col1">99.0</td></tr>',
                 '<tr><th>Federal funds (effective) <a>1</a></th><td headers="col1">n.a.</td></tr>',
                 '<tr><th>3-month</th><td headers="col1">999.0</td></tr>'])
    return '<table id="h15table">'+header+'<tbody>'+''.join(rows)+'</tbody></table>'


def test_bls_native_units_months_no_invented_release():
    rows = macro.parse_bls(bls_payload(), ['LNS14000000'])
    assert len(rows) == 1
    assert rows[0]['period_start'] == date(2026, 9, 1)
    assert rows[0]['period_end'] == date(2026, 9, 30)
    assert rows[0]['unit'] == 'percent'
    assert 'Preliminary' in rows[0]['metadata_json']
    observed = datetime(2026, 10, 10, 20)
    params = macro.version_parameters(rows[0], observed, 'run', macro.BLS_URL)
    assert params['available_at'] == observed
    assert params['available_at_basis'] == 'FIRST_OBSERVED'
    assert 'release_at' not in params


@pytest.mark.parametrize('payload', [
    {'status': 'REQUEST_FAILED'},
    {'status': 'REQUEST_SUCCEEDED', 'Results': {'series': []}},
])
def test_bls_semantic_failure_is_not_success(payload):
    with pytest.raises(ValueError):
        macro.parse_bls(payload, ['LNS14000000'])


def test_bls_duplicate_identity_rejected():
    payload = bls_payload()
    payload['Results']['series'][0]['data'].append(payload['Results']['series'][0]['data'][0])
    with pytest.raises(ValueError, match='Duplicate'):
        macro.parse_bls(payload, ['LNS14000000'])


def test_h15_uses_nominal_ancestors_and_header_dates_not_row_order():
    rows = macro.parse_h15(h15_body())
    assert len(rows) == 5
    assert {r['period_start'] for r in rows} == {date(2026, 10, 8)}
    assert max(r['value_num'] for r in rows if r['value_num'] is not None) < 10
    assert next(r for r in rows if r['metric_key'] == 'FED_FUNDS_EFFECTIVE_DAILY')['value_num'] is None


def test_h15_missing_coverage_fails_closed():
    with pytest.raises(ValueError):
        macro.parse_h15(h15_body().replace('10-year', 'unknown'))


@pytest.mark.parametrize('header', ['2026<br>Oct<br>12*', '2026 Oct 12 <sup>*</sup>'])
def test_h15_holiday_date_annotation_preserved_without_inventing_values(header):
    body = h15_body().replace('2026<br>Oct<br>8', header)
    rows = macro.parse_h15(body)
    assert {row['period_start'] for row in rows} == {date(2026, 10, 12)}
    assert all('"date_header_annotated":true' in row['metadata_json'] for row in rows)
    assert all('*' in row['metadata_json'] for row in rows)
    assert next(row for row in rows if row['metric_key']=='FED_FUNDS_EFFECTIVE_DAILY')['value_num'] is None


@pytest.mark.parametrize('header', ['2026 Oct 12garbage', '2026 Oct 12**', '2026 Oct 32*'])
def test_h15_unknown_or_invalid_date_stays_rejected(header):
    with pytest.raises(ValueError):
        macro.parse_h15(h15_body().replace('2026<br>Oct<br>8', header))


def test_h15_duplicate_dates_rejected():
    body=h15_body().replace('</thead>', '<tr><th id="col2">2026 Oct 8*</th></tr></thead>')
    with pytest.raises(ValueError,match='Duplicate'):
        macro.parse_h15(body)


@pytest.mark.parametrize('value', ['nan', 'inf', 'abc', '4.1*'])
def test_numbers_fail_closed(value):
    with pytest.raises(ValueError):
        macro.number(value)


def test_repeat_dedup_preserves_first_observation_and_reversions():
    engine = create_engine('sqlite://')
    row = macro.parse_bls(bls_payload(), ['LNS14000000'])[0]
    params = macro.version_parameters(row, datetime(2026, 10, 10), 'a', macro.BLS_URL)
    with engine.begin() as conn:
        columns = ['id INTEGER PRIMARY KEY'] + [f'{name} '+('TIMESTAMP' if name.endswith('_at')
                                                        else 'TEXT') for name in params]
        conn.execute(text(f"CREATE TABLE {macro.TABLE} ({','.join(columns)})"))
        # SQLite DBAPI returns TEXT for untyped text selects; adapter below restores datetime.
        original = macro.persist_versions
        class Connection:
            def execute(self, statement, parameters):
                result = conn.execute(statement, parameters)
                if str(statement).lstrip().startswith('SELECT'):
                    previous = result.mappings().first()
                    if previous:
                        previous = dict(previous)
                        previous['observed_at'] = datetime.fromisoformat(previous['observed_at'])
                    return SimpleNamespace(mappings=lambda: SimpleNamespace(first=lambda: previous))
                return result
        adapter = Connection()
        stamp = params['observed_at']
        assert original(adapter, [row], stamp, 'a', macro.BLS_URL) == 1
        assert original(adapter, [row], stamp+timedelta(hours=1), 'b', macro.BLS_URL) == 0
        revised = macro.parse_bls(bls_payload(value='4.2'), ['LNS14000000'])[0]
        assert original(adapter, [revised], stamp+timedelta(hours=2), 'c', macro.BLS_URL) == 1
        assert original(adapter, [row], stamp+timedelta(hours=3), 'd', macro.BLS_URL) == 1
        versions = conn.execute(text(f'SELECT available_at,value_num FROM {macro.TABLE} ORDER BY id')).all()
        assert len(versions) == 3
        assert versions[0][0] == stamp.isoformat(sep=' ')
        assert [float(v[1]) for v in versions] == [4.1, 4.2, 4.1]
        with pytest.raises(ValueError, match='out-of-order'):
            original(adapter, [revised], stamp+timedelta(hours=1), 'e', macro.BLS_URL)


class Response:
    def __init__(self, status, payload):
        self.status_code = status
        self.payload = payload
    def json(self):
        return self.payload


class Client:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return next(self.responses)


def test_eodhd_403_no_subscription_or_personal_data_dump():
    client = Client([Response(200, {'name': 'PRIVATE', 'email': 'PRIVATE', 'subscriptionType': 'monthly'}),
                     Response(403, {'error': 'PRIVATE'})])
    report = qualify(session=client, token='SECRET')
    assert report['status'] == 'ACCESS_DENIED'
    assert report['purchase_made'] is False
    assert 'PRIVATE' not in str(report) and 'SECRET' not in str(report)
    assert len(client.calls) == 2
    assert all(kwargs['allow_redirects'] is False for _, kwargs in client.calls)


def test_eodhd_access_not_rights_or_pit_qualification():
    client = Client([Response(200, {}), Response(200, {'trends': [[{'date': '2026-12-31',
                                                               'epsEstimateAvg': 'SECRET'}]]})])
    report = qualify(session=client, token='TOKEN')
    assert report['status'] == 'ACCESS_CONFIRMED'
    assert report['rights_status'] == 'PENDING_WRITTEN_CONFIRMATION'
    assert not report['checks']['consensus']['historical_pit_confirmed']
    assert not report['consensus_payload_archived']
    assert 'SECRET' not in str(report)


def test_eodhd_unknown_or_empty_schema_not_false_go():
    assert schema_summary({'trends': [[]]})['status'] == 'EMPTY_COVERAGE'
    assert schema_summary({'error': 'Access error'})['status'] == 'UNEXPECTED_SCHEMA'


def test_partial_provider_failure_keeps_counts(monkeypatch):
    from service.forward_pit.batch import BatchRunError
    row = macro.parse_bls(bls_payload(), ['LNS14000000'])[0]
    def fetch(provider, cfg, session):
        if provider == 'federal_reserve_board':
            raise ValueError('Missing official H15 headers')
        return macro.BLS_URL, bls_payload(), [row], datetime(2026, 10, 10)
    monkeypatch.setattr(macro, 'fetch', fetch)
    with pytest.raises(BatchRunError) as failure:
        macro.collect(None, {}, 'run', True, session=Client([]))
    outcome = failure.value.outcome
    assert (outcome.requested, outcome.received, outcome.persisted, outcome.failed) == (2, 1, 0, 1)
    assert outcome.details['providers']['bls']['status'] == 'OK'
    assert outcome.details['providers']['federal_reserve_board']['status'] == 'FAILED'


def test_cross_market_guard_before_network():
    with pytest.raises(ValueError, match='alpha_trade'):
        macro.collect(SimpleNamespace(url=SimpleNamespace(database='alpha_trade_fr')), {}, 'run', False)
