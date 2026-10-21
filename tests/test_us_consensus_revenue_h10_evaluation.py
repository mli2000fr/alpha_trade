"""All paths/prices below are synthetic; no provider, database or real outcome."""
from pathlib import Path

import pandas as pd
import pytest

from scripts.research import us_consensus_revenue_h10_evaluation as s


def bars(entry='2024-03-01', **changes):
    dates = pd.to_datetime(s.calendar_window(entry)['dates'])
    frame = pd.DataFrame(dict(symbol='TEST', date=dates, open=100., high=101., low=99., close=100.,
        volume=10000., is_filled=0, instrument_id=7, data_source='SYNTHETIC', data_adjustment='split'))
    for key, value in changes.items():
        frame[key] = value
    return frame


def qualification(entry='2024-03-01'):
    return dict(symbol='TEST', entry_date=entry, last_session=s.calendar_window(entry)['dates'][-1],
        status='QUALIFIED', currency='USD', instrument_id=7, data_source='SYNTHETIC',
        data_adjustment='split', corporate_actions_status='CLEAR_VERIFIED', final_sessions_verified=True,
        evidence_paths=['artifacts/research/evidence.json'])


@pytest.mark.parametrize('entry,last,maturity', [
    ('2026-10-19', '2026-10-30', '2026-10-30T20:00Z'),
    ('2024-11-22', '2024-12-06', '2024-12-06T21:00Z'),
])
def test_ten_real_sessions_include_entry_and_skip_holidays(entry, last, maturity):
    result = s.calendar_window(entry)
    assert len(result['dates']) == 10 and result['dates'][0] == entry
    assert result['dates'][-1] == last and result['maturity'] == pd.Timestamp(maturity)


@pytest.mark.parametrize('date', ['2026-10-18', '2024-12-25', '2026-10-19T12:00Z'])
def test_no_weekend_holiday_or_timestamp_entry(date):
    with pytest.raises(ValueError):
        s.calendar_window(date)


@pytest.mark.parametrize('side,high,low,expected,price', [
    ('LONG', 110., 99., 'TP_FIRST', 110.),
    ('LONG', 109., 95., 'SL_FIRST', 95.),
    ('SHORT', 101., 90., 'TP_FIRST', 90.),
    ('SHORT', 105., 91., 'SL_FIRST', 105.),
    ('LONG', 110., 95., 'SL_FIRST', 95.),
    ('SHORT', 105., 90., 'SL_FIRST', 105.),
])
def test_barriers_both_directions_and_inclusive_touch(side, high, low, expected, price):
    result = s.barrier_path(bars(high=high, low=low), side)
    assert result['barrier_outcome'] == expected and result['exit_price'] == pytest.approx(price)
    assert result['exit_session'] == 1
    assert result['ambiguous_same_day'] == (high >= 110 and low <= 95 if side == 'LONG' else high >= 105 and low <= 90)


@pytest.mark.parametrize('side,opening,low,high,expected,fill', [
    ('LONG', 80., 79., 85., 'SL_FIRST', 80.),
    ('SHORT', 120., 119., 125., 'SL_FIRST', 120.),
    ('LONG', 120., 119., 125., 'TP_FIRST', 110.),
    ('SHORT', 80., 79., 85., 'TP_FIRST', 90.),
])
def test_open_gaps_stop_not_capped_and_target_conservative(side, opening, low, high, expected, fill):
    f = bars()
    f.loc[1, ['open', 'low', 'high', 'close']] = [opening, low, high, opening]
    result = s.barrier_path(f, side)
    assert result['barrier_outcome'] == expected and result['exit_price'] == pytest.approx(fill)
    assert result['exit_session'] == 2


def test_open_target_before_later_same_day_stop_not_ambiguous():
    f = bars(); f.loc[1, ['open', 'low', 'high', 'close']] = [115., 90., 116., 100.]
    result = s.barrier_path(f, 'LONG')
    assert result['barrier_outcome'] == 'TP_FIRST' and result['ambiguous_same_day'] is False


@pytest.mark.parametrize('side,expected', [('LONG', .02), ('SHORT', -.02)])
def test_expiry_is_not_counted_as_tp_and_not_a_net_return(side, expected):
    f = bars(); f.loc[9, ['high', 'close']] = [103., 102.]
    result = s.barrier_path(f, side)
    assert result['barrier_outcome'] == 'EXPIRED' and result['exit_session'] == 10
    assert result['exit_date'] == s.calendar_window('2024-03-01')['dates'][-1]
    assert result['gross_return'] == pytest.approx(expected) and result['net_return'] is None


@pytest.mark.parametrize('column,value,reason', [
    ('volume', 0, 'INVALID_VOLUME'), ('open', float('nan'), 'INVALID_OPEN'),
    ('is_filled', 1, 'FILLED_OR_UNKNOWN_BAR'), ('high', 98, 'INVALID_OHLC_GEOMETRY'),
    ('instrument_id', 8, 'UNKNOWN_OR_CHANGED_INSTRUMENT_ID'),
    ('data_source', 'IEX', 'UNKNOWN_OR_CHANGED_DATA_SOURCE'),
    ('data_adjustment', 'UNKNOWN', 'UNKNOWN_OR_CHANGED_DATA_ADJUSTMENT'),
])
def test_bad_whole_window_bar_blocks_even_after_early_tp(column, value, reason):
    f = bars(high=111.); f.loc[9, column] = value
    assert reason in s.quality_window(f, s.calendar_window('2024-03-01')['dates'], qualification())


def test_missing_duplicate_and_unqualified_corporate_actions_do_not_disappear():
    f = bars(); dates = s.calendar_window('2024-03-01')['dates']
    assert 'INCOMPLETE_OR_EXTRANEOUS_WINDOW' in s.quality_window(f.iloc[:-1], dates, qualification())
    assert 'DUPLICATE_SESSION' in s.quality_window(pd.concat([f, f.iloc[:1]]), dates, qualification())
    q = dict(qualification(), corporate_actions_status='UNKNOWN')
    assert 'IDENTITY_CURRENCY_BASIS_OR_ACTIONS_UNQUALIFIED' in s.quality_window(f, dates, q)
    assert s.quality_window(f, dates, qualification()) == []


def test_provisional_session_and_explicit_iex_are_not_qualified_by_a_matching_manifest():
    f = bars(); dates = s.calendar_window('2024-03-01')['dates']
    q = dict(qualification(), final_sessions_verified=False)
    assert 'IDENTITY_CURRENCY_BASIS_OR_ACTIONS_UNQUALIFIED' in s.quality_window(f, dates, q)
    f['data_source'] = 'ALPACA_IEX'
    q = dict(qualification(), data_source='ALPACA_IEX')
    assert 'IEX_NOT_QUALIFIED_FOR_THIS_EXPERIMENT' in s.quality_window(f, dates, q)


def test_kernel_will_not_treat_nine_bars_as_expired_h10():
    with pytest.raises(ValueError):
        s.barrier_path(bars().iloc[:-1], 'LONG')


def synthetic_root(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = tmp_path / 'experiment'; root.mkdir()
    window = s.calendar_window('2024-03-01'); rows = []
    for symbol, rank, signal, group in [('A', 1, 'LONG', 'ORIGINAL_SUPPORT'),
        ('B', 11, 'SHORT', 'LATER_PUBLIC_CONTEXT_EXPLORATORY'),
        ('C', 12, 'ABSTAIN', 'NOT_CONTEXT_QUALIFIED')]:
        rows.append(dict(symbol=symbol, entry_date='2024-03-01', oracle_rank=rank, signal=signal,
            support_group=group, stratum='TOP10' if rank <= 10 else 'RANK11_TO_TOP20_PERCENT',
            entry_open_utc=window['entry_open'], maturity_utc=window['maturity'],
            last_session=window['dates'][-1], live_admission=False))
    pd.DataFrame(rows).to_parquet(root / 'evaluation-cohort.parquet', index=False)
    monkeypatch.setattr(s, 'prepare', lambda root: {'config': {}})
    return root, window


def price_input(tmp_path, window):
    evidence = Path('artifacts/research/evidence.json'); evidence.parent.mkdir(parents=True)
    s.atomic_json(evidence, dict(kind='SYNTHETIC_TEST_ONLY_NOT_REAL_EVIDENCE'))
    price = tmp_path / 'synthetic.parquet'
    pd.concat([bars(symbol=symbol, high=111.) for symbol in ('A', 'B', 'C')], ignore_index=True).to_parquet(price, index=False)
    manifest = tmp_path / 'manifest.json'
    qs = [dict(qualification(), symbol=symbol) for symbol in ('A', 'B', 'C')]
    s.atomic_json(manifest, dict(schema='us_consensus_h10_prices_v1', status='QUALIFIED_RESEARCH_INPUT',
        retrieved_at_utc=window['maturity'], prices_sha256=s.digest(price),
        evidence_files={str(evidence).replace('\\', '/'): s.digest(evidence)}, windows=qs))
    return price, manifest


def test_before_maturity_never_opens_supplied_outcome_files(tmp_path, monkeypatch):
    root, w = synthetic_root(tmp_path, monkeypatch)
    price = tmp_path / 'DO_NOT_OPEN.parquet'; manifest = tmp_path / 'DO_NOT_OPEN.json'
    report, attempt = s.evaluate(root, price, manifest, now=w['maturity'] - pd.Timedelta(seconds=1))
    assert report['status'] == 'WAITING_H10_MATURITY' and report['prices_read'] is False
    assert not (attempt / 'outcomes.parquet').exists()


def test_future_cutoff_rejected_without_price_access(tmp_path, monkeypatch):
    root, w = synthetic_root(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match='Future'):
        s.evaluate(root, as_of=w['maturity'], now=w['maturity'] - pd.Timedelta(days=1))


def test_exact_close_gate_then_missing_snapshot_blocks(tmp_path, monkeypatch):
    root, w = synthetic_root(tmp_path, monkeypatch)
    report, _ = s.evaluate(root, now=w['maturity'])
    assert report['status'] == 'BLOCKED_MISSING_QUALIFIED_PRICE_SNAPSHOT' and not report['prices_read']


def test_synthetic_end_to_end_separates_original_later_and_controls(tmp_path, monkeypatch):
    root, w = synthetic_root(tmp_path, monkeypatch); price, manifest = price_input(tmp_path, w)
    report, attempt = s.evaluate(root, price, manifest, now=w['maturity'])
    assert report['status'] == 'COMPLETE_EXPLORATORY_BARRIER_DIAGNOSTIC'
    assert report['evaluated_side_paths'] == 6
    arms = s.READ(attempt / 'arms.json')
    combined = [a for a in arms if a['stratum'].startswith('ALL_TOP20') and a['support_group'].startswith('COMBINED')]
    assert {a['arm']: a['tp_first_pct'] for a in combined} == {
        'CONSENSUS_DIRECTION': 50., 'ALWAYS_LONG_MATCHED': 100., 'ALWAYS_SHORT_MATCHED': 0.}
    assert all(a['expected'] == 2 and a['entry_sessions'] == 1 and not a['robustness_established'] for a in combined)
    # Repeat evaluation writes a new attempt; it does not overwrite the previous result.
    _, second = s.evaluate(root, price, manifest, now=w['maturity'])
    assert second != attempt and (attempt / 'report.json').exists()


def test_partial_quality_keeps_denominator_and_suppresses_aggregate_rates(tmp_path, monkeypatch):
    root, w = synthetic_root(tmp_path, monkeypatch); price, manifest = price_input(tmp_path, w)
    f = pd.read_parquet(price); f.loc[f.symbol.eq('B') & f.date.eq(f.date.max()), 'volume'] = 0
    f.to_parquet(price, index=False)
    m = s.READ(manifest); m['prices_sha256'] = s.digest(price); s.atomic_json(manifest, m)
    report, attempt = s.evaluate(root, price, manifest, now=w['maturity'])
    assert report['status'] == 'INCOMPLETE_PRICE_QUALITY'
    arms = s.READ(attempt / 'arms.json')
    a = next(a for a in arms if a['stratum'].startswith('ALL_TOP20') and a['support_group'].startswith('COMBINED') and a['arm'] == 'CONSENSUS_DIRECTION')
    assert a['expected'] == 2 and a['evaluated'] == 1 and a['missing'] == 1
    assert a['tp_first_pct'] is None and a['mean_gross_return'] is None


@pytest.mark.parametrize('mutation,match', [('hash', 'checksum'), ('template', 'template'),
    ('future_receipt', 'cutoff'), ('duplicate_window', 'Duplicate'), ('unbound_evidence', 'missing'),
    ('premature_snapshot', 'before the complete')])
def test_manifest_guards(tmp_path, monkeypatch, mutation, match):
    _, w = synthetic_root(tmp_path, monkeypatch); price, manifest = price_input(tmp_path, w)
    m = s.READ(manifest)
    if mutation == 'hash': m['prices_sha256'] = '0' * 64
    elif mutation == 'template': m['status'] = 'REQUIREMENTS_ONLY_NOT_A_QUALIFIED_MANIFEST'
    elif mutation == 'future_receipt': m['retrieved_at_utc'] = w['maturity'] + pd.Timedelta(seconds=1)
    elif mutation == 'duplicate_window': m['windows'].append(m['windows'][0])
    elif mutation == 'premature_snapshot': m['retrieved_at_utc'] = w['maturity'] - pd.Timedelta(days=1)
    else: m['windows'][0]['evidence_paths'] = ['artifacts/research/missing.json']
    with pytest.raises(ValueError, match=match):
        s.manifest_windows(m, price, w['maturity'])


@pytest.mark.parametrize('key,value', [('take_profit_pct', .20), ('stop_loss_pct', .07), ('sessions', 20), ('ambiguous_day', 'TARGET_FIRST')])
def test_frozen_rules_cannot_be_silently_optimized(key, value):
    cfg = s.READ(s.DEFAULT_CONFIG); cfg[key] = value
    with pytest.raises(ValueError, match='protocol'):
        s.validate_config(cfg)


def test_membership_and_support_are_rechecked_without_prices():
    # Real immutable FEATURE artifacts only, never price data or outcomes.
    cfg = s.READ(s.DEFAULT_CONFIG)
    parent = Path(cfg['cohort_root']); context = Path(cfg['context_root'])
    if not (parent / 'qualified-cohort.parquet').exists() or not (context / 'consensus-context-review.parquet').exists():
        pytest.skip('Local sealed research feature snapshots are not distributed with the tests')
    cohort = pd.read_parquet(parent / 'qualified-cohort.parquet')
    contexts = pd.read_parquet(context / 'consensus-context-review.parquet')
    result = s.supported_cohort(cohort, contexts, cfg)
    assert len(result) == 349 and set(result.loc[result.signal.ne('ABSTAIN'), 'symbol']) == {'DOCN', 'FUN', 'TWLO', 'FIVN', 'ENTG', 'AKAM'}
    assert len(result[result.signal.ne('ABSTAIN') & result.stratum.eq('TOP10')]) == 2
    assert not result.qualification_known_before_entry.any() and not result.live_admission.any()
    with pytest.raises(ValueError, match='membership'):
        s.supported_cohort(cohort.iloc[:-1], contexts, cfg)
    broken = cohort.copy(); broken.loc[broken.symbol.eq('DOCN'), 'new_available'] = pd.Timestamp('2026-10-19T14:00Z')
    with pytest.raises(ValueError, match='unavailable'):
        s.supported_cohort(broken, contexts, cfg)
