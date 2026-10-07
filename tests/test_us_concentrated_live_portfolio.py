from dataclasses import replace

import pandas as pd
import pytest

from scripts.research.us_concentrated_live_portfolio import ArchivedMacro, run_portfolio
from service.market import parse_market_regimes


def fixture_data():
    days = pd.bdate_range('2024-01-01', '2025-02-05')
    close = pd.DataFrame({'FIXTURE': 100., 'SPY': 100.}, index=days)
    frames = dict(opens=close.copy(), close=close, high=close+1, low=close-1, volume=close*10000)
    trading = days[days >= '2025-01-01']
    scores = pd.DataFrame([dict(date=trading[0], symbol='FIXTURE', proba_extreme=.9, ORACLE_TOP10=True)])
    macro = ArchivedMacro(pd.DataFrame({'trade_date': trading, 'sentiment_score': 0.}))
    return frames, scores, macro, trading


@pytest.mark.parametrize('variant,offset', [('CURRENT_NO_EXPIRY', -1),
    ('REFERENCE_20_AFTER_ENTRY', 21), ('NO_TP_FIXED_SL_20_AFTER_ENTRY', 21),
    ('NO_TP_TRAILING_20_AFTER_ENTRY', 21)])
def test_chronological_orchestrator_expiry_is_twenty_sessions_after_entry(tmp_path, variant, offset):
    frames, scores, macro, trading = fixture_data()
    result = run_portfolio(frames=frames, scores=scores, sectors={'FIXTURE': 'Technology'},
        macro=macro, market_config=parse_market_regimes({'enabled': False}),
        policy='ORACLE_TOP10', variant=variant, output=tmp_path)
    trades = pd.read_parquet(tmp_path/'trades.parquet')
    assert len(trades) == 1
    assert trades.entry_date.iloc[0] == trading[1]
    assert trades.exit_date.iloc[0] == trading[offset]
    assert result['cash_reconciliation_error'] == pytest.approx(0., abs=1e-8)
    assert result['return_pct'] < 0 # both legs' costs, even with flat prices


def test_archived_macro_never_reads_future_or_duplicate_rows():
    frame = pd.DataFrame({'trade_date': ['2025-01-02', '2025-01-03'], 'vix': [20., 99.], 'ten_y': [4., 8.]})
    macro = ArchivedMacro(frame)
    assert macro.get_vix_close(pd.Timestamp('2025-01-01').date()) is None
    assert macro.get_vix_close(pd.Timestamp('2025-01-02').date()) == 20.
    assert macro.get_us10y_history(pd.Timestamp('2025-01-02').date(), 10) == [4.]
    with pytest.raises(ValueError, match='Duplicate'):
        ArchivedMacro(pd.concat([frame, frame.iloc[:1]]))


@pytest.mark.parametrize('variant', ['CURRENT_NO_EXPIRY', 'REFERENCE_20_AFTER_ENTRY',
    'NO_TP_FIXED_SL_20_AFTER_ENTRY', 'NO_TP_TRAILING_20_AFTER_ENTRY'])
def test_explicit_window_liquidates_before_twenty_sessions(tmp_path, variant):
    frames, scores, macro, trading = fixture_data()
    result = run_portfolio(frames=frames, scores=scores, sectors={'FIXTURE': 'Technology'},
        macro=macro, market_config=parse_market_regimes({'enabled': False}),
        policy='ORACLE_TOP10', variant=variant, output=tmp_path,
        start_date=trading[0], end_date=trading[5], initial_stop_pct=.07)
    trades = pd.read_parquet(tmp_path/'trades.parquet')
    daily = pd.read_parquet(tmp_path/'daily.parquet')
    assert result['sessions'] == 6
    assert result['terminal_session'] == str(trading[5].date())
    assert trades.exit_date.eq(trading[5]).all()
    assert daily.date.max() == trading[5]
    assert result['cash_reconciliation_error'] == pytest.approx(0., abs=1e-8)


def test_reversed_date_range_rejected_before_replay(tmp_path):
    frames, scores, macro, _ = fixture_data()
    with pytest.raises(ValueError, match='Invalid replay date range'):
        run_portfolio(frames=frames, scores=scores, sectors={}, macro=macro,
            market_config=parse_market_regimes({'enabled': False}), policy='ORACLE_TOP10',
            variant='CURRENT_NO_EXPIRY', output=tmp_path,
            start_date='2026-01-01', end_date='2025-01-01')


@pytest.mark.parametrize('fraction', [.5, 1.])
def test_early_weakness_j5_executes_next_open_once(tmp_path, fraction):
    frames, scores, macro, trading = fixture_data()
    # Entry at trading[1], fifth close trading[5], sale trading[6].
    frames['close'].loc[trading[5], 'FIXTURE'] = 97.
    frames['low'].loc[trading[5], 'FIXTURE'] = 96.
    frames['opens'].loc[trading[6], 'FIXTURE'] = 96.
    frames['low'].loc[trading[6], 'FIXTURE'] = 95.
    result = run_portfolio(frames=frames,scores=scores,sectors={'FIXTURE':'Technology'},
        macro=macro,market_config=parse_market_regimes({'enabled':False}),
        policy='ORACLE_TOP10',variant='NO_TP_FIXED_SL_20_AFTER_ENTRY',output=tmp_path,
        initial_stop_pct=.07,early_weakness_fraction=fraction)
    trades = pd.read_parquet(tmp_path/'trades.parquet')
    early = trades.loc[trades.exit_reason.eq('early_weakness_j5')]
    assert len(early) == 1
    assert early.exit_date.iloc[0] == trading[6]
    assert early.quantity.iloc[0]/trades.quantity.sum() == pytest.approx(fraction)
    assert len(trades) == (2 if fraction == .5 else 1)
    assert result['early_weakness_executions'] == 1
    assert result['cash_reconciliation_error'] == pytest.approx(0.,abs=1e-8)


def test_early_weakness_does_not_exit_positive_position(tmp_path):
    frames,scores,macro,_ = fixture_data()
    result = run_portfolio(frames=frames,scores=scores,sectors={'FIXTURE':'Technology'},
        macro=macro,market_config=parse_market_regimes({'enabled':False}),
        policy='ORACLE_TOP10',variant='NO_TP_FIXED_SL_20_AFTER_ENTRY',output=tmp_path,
        initial_stop_pct=.07,early_weakness_fraction=1.)
    assert result['early_weakness_executions'] == 0


@pytest.mark.parametrize('seed', range(10))
def test_precomputed_correlation_keeps_legacy_greedy_decisions(seed):
    import numpy as np
    from types import SimpleNamespace
    from risk_management.correlation_filter import filter_correlated_signed
    rng = np.random.default_rng(seed)
    matrix = pd.DataFrame(rng.normal(size=(70, 20)), columns=[f'S{i}' for i in range(20)])
    matrix['S1'] = matrix.S0*.9 + matrix.S1*.1
    matrix['S2'] = -matrix.S0
    matrix = matrix.mask(rng.random(matrix.shape) < .1)
    matrix['S3'] = 0.
    candidates = [SimpleNamespace(symbol=s, side='buy' if i%2 else 'sell')
        for i, s in enumerate(matrix.columns)]
    legacy, legacy_rejections = filter_correlated_signed(candidates, matrix, .8, 30)
    fast, fast_rejections = filter_correlated_signed(candidates, matrix, .8, 30, precompute=True)
    assert [c.symbol for c in fast] == [c.symbol for c in legacy]
    assert fast_rejections == legacy_rejections
