from dataclasses import asdict
from functools import partial

import numpy as np
import pandas as pd
import pytest

from modelFactory.oracle.build_labels import nyse_sessions
from scripts.research.us_concentrated_live_portfolio import ArchivedMacro, run_portfolio
from scripts.research.us_oracle_barrier_exit_grid import GridLedger
from scripts.research.us_oracle_barrier_grid_summary import verify_trade_contract
from scripts.research.us_oracle_path_economic_replay import (cohort_metrics, cohort_window, covered_windows,
    freeze_top, qualify_entries)
from service.market import parse_market_regimes


def scores():
    return pd.DataFrame(dict(date=['2025-01-02']*4, symbol=['D', 'C', 'B', 'A'],
        score_lightgbm=[.1, .8, .9, .9], future_return=[10., 0., -99., 99.]))


def test_rank_ties_and_percentiles_precede_top_and_ignore_future_labels():
    a = freeze_top(scores(), 2)
    assert a.symbol.tolist() == ['A', 'B']
    assert a.oracle_rank.tolist() == [1, 2]
    assert a.proba_extreme.tolist() == [.875, .875]
    assert 'future_return' not in a
    b = scores()
    b['future_return'] *= -100
    pd.testing.assert_frame_equal(a, freeze_top(b, 2))


@pytest.mark.parametrize('kind', ['duplicate', 'nan', 'inf', 'out_of_range'])
def test_invalid_scores_rejected(kind):
    frame = scores()
    if kind == 'duplicate':
        frame = pd.concat([frame, frame.iloc[:1]])
    else:
        frame.loc[0, 'score_lightgbm'] = {'nan': np.nan, 'inf': np.inf, 'out_of_range': 1.1}[kind]
    with pytest.raises(ValueError):
        freeze_top(frame, 10)


def test_windows_have_entry_plus_twenty_session_tail():
    calendar = nyse_sessions(pd.Timestamp('2023-01-01').date(), pd.Timestamp('2026-10-09').date())
    for year in (2024, 2025, 2026):
        decision, terminal = cohort_window(year, calendar)
        assert calendar.get_loc(terminal)-calendar.get_loc(decision) == 21
        assert terminal.year == (year+1 if year < 2026 else 2026)
    assert cohort_window(2026, calendar) == (pd.Timestamp('2026-09-10'), pd.Timestamp('2026-10-09'))
    with pytest.raises(ValueError, match='tail'):
        cohort_window(2026, calendar[calendar < '2026-10-09'])


def test_macro_truncation_is_global_not_outcome_dependent():
    calendar = nyse_sessions(pd.Timestamp('2023-01-01').date(), pd.Timestamp('2026-10-09').date())
    windows = covered_windows(calendar, calendar[calendar <= '2026-10-02'])
    assert windows['2026']['decision_end'] == '2026-09-02'
    assert windows['2026']['terminal_date'] == '2026-10-02'
    assert windows['2025']['decision_end'] == '2025-12-31'
    with pytest.raises(ValueError, match='continuous macro'):
        covered_windows(calendar, calendar[calendar != '2025-01-15'])


def test_quality_is_past_only_and_does_not_replace_rejected_top():
    days = pd.bdate_range('2024-11-01', '2025-01-10')
    prices = pd.DataFrame([dict(date=d, symbol=s, open=100., high=101., low=99., close=100.,
        volume=10000., is_filled=0, instrument_id=s) for d in days for s in ['A', 'B', 'C', 'D']])
    candidates = freeze_top(scores(), 2)
    prices.loc[prices.symbol.eq('A') & prices.date.eq('2025-01-02'), 'volume'] = 0
    qualified = qualify_entries(candidates, prices, days)
    assert qualified.symbol.tolist() == ['A', 'B']
    assert qualified.selected.tolist() == [False, True]
    # A later missing/contradictory bar must not retroactively exclude B.
    future = prices.date.gt('2025-01-02')
    prices.loc[future, ['open', 'high', 'low', 'close', 'volume']] = np.nan
    prices.loc[future, 'instrument_id'] = 'changed'
    pd.testing.assert_frame_equal(qualified, qualify_entries(candidates, prices, days))


def test_identity_or_filled_history_prevents_entry():
    days = pd.bdate_range('2024-11-01', '2025-01-10')
    prices = pd.DataFrame([dict(date=d, symbol=s, open=100., high=101., low=99., close=100.,
        volume=10000., is_filled=0, instrument_id=s) for d in days for s in ['A', 'B']])
    prices.loc[prices.symbol.eq('A') & prices.date.eq('2024-12-30'), 'is_filled'] = 1
    prices.loc[prices.symbol.eq('B') & prices.date.eq('2024-12-30'), 'instrument_id'] = 'old'
    assert not qualify_entries(freeze_top(scores(), 2), prices, days).selected.any()


@pytest.mark.parametrize('contact,reason', [('none', 'expiry_open'), ('tp', 'take_profit'), ('sl_gap', 'initial_stop_gap_open')])
def test_actual_shared_ledger_tp20_sl10_and_expiry(tmp_path, contact, reason):
    days = nyse_sessions(pd.Timestamp('2024-01-01').date(), pd.Timestamp('2025-02-10').date())
    close = pd.DataFrame({'FIXTURE': 100., 'SPY': 100.}, index=days)
    frames = dict(opens=close.copy(), close=close, high=close+1, low=close-1, volume=close*10000)
    trading = days[days >= '2025-01-01']
    selected = pd.DataFrame([dict(date=trading[0], symbol='FIXTURE', proba_extreme=.9, selected=True)])
    if contact == 'tp':
        frames['high'].loc[trading[2], 'FIXTURE'] = 125.
    if contact == 'sl_gap':
        for key in ('opens', 'close', 'high', 'low'):
            frames[key].loc[trading[2], 'FIXTURE'] = 85.
    market = parse_market_regimes({'enabled': False})
    result = run_portfolio(frames=frames, scores=selected, sectors={'FIXTURE': 'Technology'},
        macro=ArchivedMacro(pd.DataFrame({'trade_date': trading, 'sentiment_score': 0.})),
        market_config=parse_market_regimes(asdict(market)), policy='selected', variant='CURRENT_NO_EXPIRY',
        output=tmp_path, start_date=trading[0], end_date=trading[21], decision_end_date=trading[0],
        ledger_factory=partial(GridLedger, tp_pct=.2, sl_pct=.1, events=(), cash_policy='STRICT'),
        expiry_open_sessions=20, protection_options=dict(take_profit_enabled=True, trailing_enabled=False))
    trades = pd.read_parquet(tmp_path/'trades.parquet')
    assert len(trades) == 1
    assert trades.exit_reason.iloc[0] == reason
    audit = verify_trade_contract(trades, .2, .1, days)
    assert audit['exceeding_stop_on_gap'] == int(contact == 'sl_gap')
    assert result['cash_reconciliation_error'] == pytest.approx(0., abs=1e-8)
    metrics = cohort_metrics(result, trades, pd.read_parquet(tmp_path/'daily.parquet'), 2025, trading[0])
    assert metrics['winning_positions'] == int(contact == 'tp')
    assert metrics['losing_positions'] == int(contact != 'tp')
    assert metrics['calendar_mark_to_market_capital'] != metrics['final_capital_usd']
