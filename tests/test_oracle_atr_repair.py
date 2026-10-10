from datetime import date
import pandas as pd

from service.market.oracle_atr_repair import (calendar_changes, qualify_static_extension,
                                             rebuild_dates, fetch_price_evidence)


def group(**overrides):
    return {'prediction_date': date(2026, 9, 3), 'exit_min': date(2026, 10, 2),
            'exit_max': date(2026, 10, 2), 'available_min': None,
            'available_max': None, 'missing_available': 1749, **overrides}


CALENDAR = {date(2026, 9, 3): (date(2026, 10, 2), date(2026, 10, 5))}


def test_rebuild_stale_invalid_labels_is_explicit_and_date_scoped():
    invalid = pd.DataFrame({'prediction_date': ['2026-04-02', '2026-04-01', '2026-04-02'],
                            'symbol': ['A', 'B', 'C']})
    assert rebuild_dates([], [], invalid) == []
    assert rebuild_dates(['2026-04-03'], [date(2026, 4, 1)], invalid,
                         include_invalid=True) == ['2026-04-01', '2026-04-02', '2026-04-03']


def test_both_provider_reads_keep_the_verified_session(monkeypatch):
    from unittest.mock import Mock
    import service.eodhd.clientEodhd as provider
    session = object()
    prices, splits = Mock(return_value=[{'date': '2026-04-01'}]), Mock(return_value=[])
    monkeypatch.setattr(provider, 'fetch_eod', prices)
    monkeypatch.setattr(provider, 'fetch_splits', splits)
    assert fetch_price_evidence('ABC', '2026-04-01', '2026-05-01', session=session) == {
        'bars': [{'date': '2026-04-01'}], 'splits': []}
    assert prices.call_args.kwargs['session'] is session
    assert splits.call_args.kwargs['session'] is session
    assert prices.call_args.kwargs['end'] == '2026-05-01'


def test_missing_report_does_not_replace_top_candidates_with_known_winners():
    from service.market.oracle_atr_missing_report import explain_day
    scores = pd.DataFrame({'symbol': ['A', 'B', 'C', 'D', 'E'],
                           'proba_extreme': [.1, .2, .3, .4, .5]})
    labels = pd.DataFrame({'symbol': ['A', 'B', 'C', 'D', 'E'],
                          'target_quality_valid': [1, 1, 1, 1, 0],
                          'target_quality_reason': [None, None, None, None, 'missing_exit_bar'],
                          'future_return': [.5, .4, .3, .2, None],
                          'oracle_decile': [10, 9, 8, 7, None],
                          'oracle_available_date': ['2026-05-01'] * 5})
    out = explain_day(scores, dict(A=1, B=2, C=3, D=4, E=5), labels,
                      as_of=date(2026, 10, 10), available_date=date(2026, 5, 1))
    assert out['evaluated_count'] == 1
    assert out['predicted_selection_missing'] == ['E']
    assert out['atr_selection_missing'] == ['E']
    assert out['real_benchmark_missing'] == [{'symbol': 'E', 'reason': 'missing_exit_bar'}]


def test_missing_report_distinguishes_future_h20_from_data_holes():
    from service.market.oracle_atr_missing_report import explain_day
    scores = pd.DataFrame({'symbol': ['A'], 'proba_extreme': [.9]})
    labels = pd.DataFrame(columns=['symbol', 'target_quality_valid', 'target_quality_reason',
                                   'future_return', 'oracle_decile', 'oracle_available_date'])
    out = explain_day(scores, {'A': 1}, labels, as_of=date(2026, 10, 10),
                      available_date=date(2026, 10, 12))
    assert out['reason'] == 'H20_NOT_YET_AVAILABLE'
    assert len(out['null_fields']) == 5


def test_missing_availability_can_be_repaired_without_touching_returns():
    updates, rebuild = calendar_changes(pd.DataFrame([group()]), CALENDAR)
    assert updates == [{'day': date(2026, 9, 3), 'available': date(2026, 10, 5)}]
    assert not rebuild


def test_wrong_exit_requires_full_day_rebuild_not_availability_patch():
    updates, rebuild = calendar_changes(pd.DataFrame([group(exit_max=date(2026, 10, 5))]), CALENDAR)
    assert not updates
    assert rebuild == ['2026-09-03']


def test_repeated_calendar_repair_is_idempotent():
    updates, rebuild = calendar_changes(pd.DataFrame([group(missing_available=0,
        available_min=date(2026, 10, 5), available_max=date(2026, 10, 5))]), CALENDAR)
    assert not updates and not rebuild


def test_static_extension_requires_original_reference_membership(tmp_path, monkeypatch):
    import json
    import service.market.oracle_atr_repair as repair
    from contextlib import contextmanager
    monkeypatch.chdir(tmp_path)
    profile = tmp_path / 'artifacts/models/batch/oracle/feature_profile.json'
    profile.parent.mkdir(parents=True)
    profile.write_text(json.dumps({'oracle_universe_mode': 'static_bars'}))

    class Conn:
        def execute(self, query, params):
            return self
        def scalars(self):
            return self
        def all(self):
            return ['ORIGINAL', 'DELISTED']

    class Engine:
        @contextmanager
        def connect(self):
            yield Conn()

    original = {('2026-09-03', 'ORIGINAL')}
    monkeypatch.setattr(repair, 'load_stored_membership', lambda *args: original)
    monkeypatch.setattr(repair, 'load_universe_from_bars', lambda *args, **kwargs: original)
    seed, reason = qualify_static_extension(Engine(), 'batch', 20, '2026-09-03')
    assert seed == ['DELISTED', 'ORIGINAL']
    assert reason.startswith('STATIC_BARS_SEED')
    monkeypatch.setattr(repair, 'load_universe_from_bars', lambda *args, **kwargs: original | {('2026-09-03', 'EXTRA')})
    assert qualify_static_extension(Engine(), 'batch', 20, '2026-09-03')[0] == []
    profile.write_text(json.dumps({'oracle_universe_mode': 'pit_dynamic_bars'}))
    assert qualify_static_extension(Engine(), 'batch', 20, '2026-09-03')[0] == []
