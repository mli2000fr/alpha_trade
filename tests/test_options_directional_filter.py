"""Offline prospective options gate: no broker, provider, SQL writes or fitting."""
from dataclasses import replace
from datetime import date, datetime, timezone
import json
from types import SimpleNamespace

import pandas as pd
import pytest

from service.options_directional.config import OptionsFilterConfig, load_options_filter_config
from service.options_directional.features import build_features, select_top
from service.options_directional import store

DAY = date(2026, 10, 16)
NOW = datetime(2026, 10, 16, 23, tzinfo=timezone.utc)
RUN = 'opt-' + 'a'*32


def oracle(n=6):
    return [dict(symbol=chr(65+i), proba_extreme=1-i*.01) for i in range(n)]


def feature(x):
    return dict(volume_feature=float(x), oi_feature=float(x), available_at=NOW.isoformat())


def test_top_is_fixed_before_missing_data_and_rank_is_preserved():
    rows = select_top(oracle(), {s: feature(i) for i, s in enumerate('ABCDZ')},
                      OptionsFilterConfig(oracle_top_n=5))
    assert [r['symbol'] for r in rows] == list('ABCDE')
    assert [r['symbol'] for r in rows if r['selected']] == ['C', 'D']
    assert rows[-1]['reason'] == 'MISSING_OR_STALE_OPTIONS'
    assert all(r['combined_score'] <= 1 for r in rows if 'combined_score' in r)


def test_constant_scores_and_small_cohort_abstain():
    for features in ({s: feature(1) for s in 'ABCD'}, {s: feature(i) for i, s in enumerate('ABC')}):
        assert not any(r['selected'] for r in select_top(oracle(), features, OptionsFilterConfig()))


@pytest.mark.parametrize('bad', [float('nan'), float('inf'), -1, 2])
def test_bad_oracle_scores_rejected(bad):
    with pytest.raises(ValueError):
        select_top([dict(symbol='A', proba_extreme=bad)], {}, OptionsFilterConfig())


def source_rows():
    rows = []
    for side, oi, volume in [('CALL', 100, 40), ('PUT', 20, 10)]:
        rows.append(dict(symbol='A', contract_symbol='A261106'+side[0]+'00100000',
            expiration_date='2026-11-06', strike=100., option_type=side,
            observed_at='2026-10-16T21:00:00Z', available_at='2026-10-16T21:01:00Z',
            bar_timestamp='2026-10-16T19:30:00Z', open_interest=oi, volume=volume, payload_hash=side))
    return rows


def test_features_and_no_future_or_missing_receipt():
    frame = pd.DataFrame(source_rows())
    features = build_features(frame, frame, {'A': 100.}, DAY, pd.Timestamp(NOW))
    import math
    assert features['A']['volume_feature'] == pytest.approx(math.log1p(40)-math.log1p(10))
    assert features['A']['oi_feature'] == pytest.approx(math.log1p(100)-math.log1p(20))
    for value in [None, '2026-10-17T01:00:00Z']:
        bad = frame.copy()
        bad.loc[0, 'observed_at'] = value
        assert not build_features(bad, frame, {'A': 100.}, DAY, pd.Timestamp(NOW))
    bad = frame.copy()
    bad.loc[0, 'contract_symbol'] = 'OTHER261106C00100000'
    assert not build_features(bad, frame, {'A': 100.}, DAY, pd.Timestamp(NOW))


def test_conflicting_latest_receipt_is_not_an_arbitrary_oi():
    frame = pd.DataFrame(source_rows())
    conflict = frame.iloc[[0]].copy()
    conflict['open_interest'] = 999
    assert not build_features(pd.concat([frame, conflict]), frame, {'A': 100.}, DAY, pd.Timestamp(NOW))


def report():
    return dict(run_id=RUN, status='COMPLETED', trade_date=str(DAY), account_id='default',
        batch_id='model-test', symbol_source='universe-file:test.txt', capital_preset_key='capital_2001_5000',
        cutoff_utc=NOW.isoformat(), config=OptionsFilterConfig().snapshot(),
        rows=[dict(symbol='A', selected=True)], selected=['A'])


def test_immutable_archive_hash_date_account_age_and_exact_context(tmp_path, monkeypatch):
    monkeypatch.setattr(store, 'validate_window', lambda *a: None)
    store.seal(RUN, report(), {'raw': [1, 2]}, root=tmp_path)
    assert store.qualified(RUN, trade_date=DAY, now=NOW, root=tmp_path)['selected'] == ['A']
    for kwargs in [dict(batch_id='wrong'), dict(account_id='test1'), dict(symbol_source='wrong'),
                   dict(capital_preset_key='wrong')]:
        with pytest.raises(ValueError):
            store.qualified(RUN, trade_date=DAY, now=NOW, root=tmp_path, **kwargs)
    with pytest.raises(ValueError):
        store.qualified(RUN, trade_date=DAY, now=NOW.replace(day=22), root=tmp_path)
    with pytest.raises(FileExistsError):
        store.seal(RUN, report(), {}, root=tmp_path)
    folder = store.directory(RUN, tmp_path)
    (folder/'inputs.json').write_text('{}', encoding='utf-8')
    with pytest.raises(ValueError, match='altérée'):
        store.qualified(RUN, trade_date=DAY, now=NOW, root=tmp_path)


@pytest.mark.parametrize('run', ['../other', 'auto', 'opt-x', 'llm-'+'a'*32])
def test_no_unsafe_or_implicit_id(run):
    with pytest.raises(ValueError):
        store.directory(run)


def test_window_before_close_after_open_and_weekend():
    close = NOW.replace(hour=20)
    opened = NOW.replace(day=19, hour=13, minute=30)
    calendar = SimpleNamespace(session_dates=lambda a, b: [DAY], next_session=lambda a: date(2026,10,19),
        session_bounds=lambda d: (NOW.replace(hour=13), close) if d==DAY else (opened, opened.replace(hour=20)))
    store.validate_window(DAY, NOW, calendar)
    for now in (close.replace(hour=19), opened):
        with pytest.raises(ValueError):
            store.validate_window(DAY, now, calendar)


def test_risk_gate_long_only_keeps_original_score_and_only_removes():
    from risk_management.selection_contract import MLRankedCandidate
    from service.options_directional.risk_adapter import filter_candidates
    candidates = [MLRankedCandidate(symbol=s, trade_date=DAY, side=side, p_long=.8, p_short=0,
        p_flat=.2, p_side=.8, side_rank=i+1, model_run_id='model', universe_run_id='universe',
        account='default', lineage={}) for i,(s,side) in enumerate([('A','long'),('B','short'),('C','long')])]
    kept = filter_candidates(candidates, dict(selected=['A','B'],run_id=RUN))
    assert [c.symbol for c in kept] == ['A']
    assert kept[0].p_side == .8 and kept[0].side_rank == 1
    assert kept[0].lineage['options_filter_run_id'] == RUN


def test_enabled_deployment_is_separate_from_disabled_gpt():
    from service.llm_directional.config import load_filter_config
    assert load_options_filter_config().enabled
    assert OptionsFilterConfig().oracle_top_n == 20  # deployment override remains user-configurable
    assert not load_filter_config().enabled


def test_oracle_lineage_is_causal_and_tied_to_model_and_feature_hashes():
    from service.options_directional.runner import validate_oracle_lineage
    row = dict(fold_start='2026-01-08',lineage_fold_start='2026-01-08',
        target_name='oracle_path_extreme20',target_horizon=20,model_available_date='2026-01-07',
        feature_profile_sha256='profile',model_sha256='weights')
    folds = {'2026-01-08':dict(model_sha256='weights',metrics=dict(
        train_available_max='2025-07-09',val_available_max='2026-01-07'))}
    validate_oracle_lineage([row],DAY,'profile',folds)
    for change in [dict(model_sha256='wrong'),dict(feature_profile_sha256='wrong'),
                   dict(model_available_date='2026-01-06'),dict(target_horizon=10),
                   dict(lineage_fold_start=None)]:
        with pytest.raises(ValueError):
            validate_oracle_lineage([{**row,**change}],DAY,'profile',folds)
    with pytest.raises(ValueError):
        validate_oracle_lineage([row],date(2026,1,7),'profile',folds)
