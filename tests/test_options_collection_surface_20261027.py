"""Offline regressions for the directional OI collector surface."""
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import pandas as pd
import pytest

from service.forward_pit import batch
from service.options_directional.features import _rows, build_features


DAY = date(2026, 10, 26)


def contract(side, strike=100, *, days=25, root='AAA'):
    return f'{root}{DAY + timedelta(days=days):%y%m%d}{side}{round(strike * 1000):08d}'


def choose(names, metadata=None, **kwargs):
    if metadata is None:
        metadata = {name: {'open_interest': 100} for name in names}
    return batch._select_directional_oi_pair(names, metadata, symbol='AAA', spot=100,
                                            as_of=DAY, min_open_interest=10, **kwargs)


def test_window_includes_directional_upper_bound_even_with_legacy_tolerance():
    assert batch._option_expiration_window(DAY, (5, 10, 20), 4)[1] == date(2026, 11, 20)
    assert batch._option_expiration_window(DAY, (5, 10, 20), 4,
                                          ensure_directional_pair=False)[1] == date(2026, 11, 19)
    assert batch._option_expiration_window(DAY, (5, 10, 20), 5)[1] == date(2026, 11, 20)


@pytest.mark.parametrize('value', [None, True, False, 'NaN', 'Infinity', -1, '10.5', {}])
def test_invalid_oi_is_never_fabricated(value):
    names = [contract('C'), contract('P')]
    metadata = {name: {'open_interest': value} for name in names}
    assert batch._option_open_interest({'open_interest': value}) is None
    assert choose(names, metadata) == set()


@pytest.mark.parametrize('value', [10, '10', '10.0'])
def test_integer_oi_is_accepted(value):
    assert batch._option_open_interest({'open_interest': value}) == 10


def test_joint_pair_same_strike_same_expiry_and_deterministic_tenor():
    # Separate closest strikes do not form a pair; an adjacent pair does.
    names = [contract('C', 100), contract('P', 100.25),
             contract('C', 100.5), contract('P', 100.5)]
    assert choose(names) == {contract('C', 100.5), contract('P', 100.5)}
    names += [contract('C', 101, days=20), contract('P', 101, days=20)]
    assert choose(list(reversed(names))) == {contract('C', 101, days=20), contract('P', 101, days=20)}


@pytest.mark.parametrize('kwargs', [{'days': 14}, {'days': 26}, {'root': 'AAA1'},
                                  {'root': 'BBB'}, {'strike': 106}])
def test_pair_cannot_bypass_surface_contract(kwargs):
    assert choose([contract('C', **kwargs), contract('P', **kwargs)]) == set()


def test_pair_requires_both_eligible_sides_and_known_minimum_oi():
    call, put = contract('C'), contract('P')
    assert choose([call]) == set()
    assert choose([call, put], {call: {'open_interest': 100}, put: {'open_interest': 9}}) == set()
    assert choose([call, put], {call: {'open_interest': 100}}) == set()
    assert choose([call, contract('P', days=20)]) == set()


@pytest.mark.parametrize('days,expected', [(14, 0), (15, 1), (25, 1), (26, 0)])
def test_filter_accepts_same_calendar_bounds_as_collector(days, expected):
    frame = pd.DataFrame([dict(symbol='AAA', contract_symbol=contract('C', days=days),
        expiration_date=DAY + timedelta(days=days), option_type='CALL', payload_hash='sealed',
        observed_at='2026-10-26T20:20:00Z', available_at='2026-10-26T20:20:00Z')])
    assert len(_rows(frame, DAY, pd.Timestamp('2026-10-26T22:00:00Z'))) == expected


@pytest.mark.parametrize('ensure,oi,expected_pair', [(True, 100, True), (False, 100, False),
                                                  (True, 9, False), (True, None, False)])
def test_collector_persists_joint_pair_only_after_quote_and_oi_guards(monkeypatch, ensure, oi, expected_pair):
    class FixedClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 26, 20, 20, tzinfo=UTC).astimezone(tz)

    names = [contract('C', 100), contract('P', 100.25),
             contract('C', 100.5), contract('P', 100.5)]
    snapshots = {name: {'latestQuote': {'bp': 1, 'ap': 1.1, 't': '2026-10-26T20:19:00Z'}}
                 for name in names}
    snapshots[names[0]]['latestQuote']['bp'] = 0  # Must remain excluded.
    metadata = [{'symbol': name, 'open_interest': oi if name == names[3] else 100} for name in names]
    requests_seen, persisted, receipts = [], [], []

    def pages(session, url, *, params, **kwargs):
        requests_seen.append((url, params))
        return [({'option_contracts': metadata} if url.endswith('/contracts') else
                 {'snapshots': snapshots}, 200)]

    class Engine:
        @contextmanager
        def begin(self):
            yield self

        def execute(self, sql, params):
            assert 'INSERT IGNORE INTO stock_option_snapshots' in str(sql)
            persisted.append(params)
            return SimpleNamespace(rowcount=1)

    monkeypatch.setattr(batch, 'datetime', FixedClock)
    monkeypatch.setattr(batch, '_utcnow', lambda: datetime(2026, 10, 26, 20, 20))
    monkeypatch.setattr(batch, '_collection_symbols', lambda cfg: ['AAA'])
    monkeypatch.setattr(batch, 'get_alpaca_credentials', lambda: ('test', 'test'))
    monkeypatch.setattr(batch, '_configure_alpaca_session', lambda *a, **k: None)
    monkeypatch.setattr(batch, 'historical_sip_snapshots',
                        lambda *a: ({'AAA': {'dailyBar': {'c': 100}}}, 200))
    monkeypatch.setattr(batch, '_paginated_json', pages)
    monkeypatch.setattr(batch, '_raw', lambda *a: receipts.append(a))
    outcome = batch.options_snapshot(Engine(), {
        'request_interval_seconds': 0, 'moneyness_targets': '1.00',
        'ensure_directional_oi_pair': ensure, 'dte_tolerance_days': 5,
    }, 'offline-test', False)

    assert len(requests_seen) == 2  # No extra provider request to add the pair.
    assert all(p['expiration_date_lte'] == '2026-11-20' for _, p in requests_seen)
    assert len(receipts) == 3  # Underlying, chain and metadata receipts preserved.
    expected = {names[1], names[2], names[3]} if expected_pair else {names[1]}
    assert {row['contract'] for row in persisted} == expected
    assert outcome.received == outcome.persisted == len(expected)
    assert outcome.details['symbols_with_directional_oi_pair'] == int(expected_pair)
    assert outcome.details['directional_pair_contracts_added'] == (2 if expected_pair else 0)
    assert outcome.details['symbols_without_directional_oi_pair'] == int(ensure and not expected_pair)
    assert outcome.details['contracts_rejected_liquidity'] == 1
    if expected_pair:
        assert all(row['open_interest'] == 100 for row in persisted)

    # Persisted collector rows must actually yield the production feature,
    # rather than merely increasing the number of rows in the snapshot table.
    oi_frame = pd.DataFrame([dict(symbol=row['underlying'], contract_symbol=row['contract'],
        expiration_date=row['expiry'], strike=row['strike'], option_type=row['otype'],
        open_interest=row['open_interest'], observed_at=row['observed'], available_at=row['observed'],
        provider_timestamp=row['provider_ts'], payload_hash=row['hash']) for row in persisted])
    volume_frame = pd.DataFrame([dict(symbol='AAA', contract_symbol=contract(side, 100.5),
        expiration_date=date(2026, 11, 20), option_type=otype, volume=100,
        bar_timestamp='2026-10-26T19:30:00Z', observed_at='2026-10-26T20:20:00Z',
        available_at='2026-10-26T20:20:00Z', payload_hash=side)
        for side, otype in [('C', 'CALL'), ('P', 'PUT')]])
    features = build_features(oi_frame, volume_frame, {'AAA': 100}, DAY,
                              pd.Timestamp('2026-10-26T22:00:00Z'))
    assert set(features) == ({'AAA'} if expected_pair else set())


def test_pair_config_must_be_boolean(monkeypatch):
    monkeypatch.setattr(batch, '_collection_symbols', lambda cfg: ['AAA'])
    with pytest.raises(ValueError, match='booléen'):
        batch.options_snapshot(None, {'ensure_directional_oi_pair': 'false'}, 'offline-test', True)
