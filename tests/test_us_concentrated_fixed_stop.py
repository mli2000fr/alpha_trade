from types import SimpleNamespace

import pandas as pd
import pytest

from scripts.research.us_concentrated_fixed_stop import fixed_stop_protections
from scripts.research.us_concentrated_live_portfolio import run_portfolio
from service.market import parse_market_regimes
from tests.test_us_concentrated_live_portfolio import fixture_data


def test_fixed_stop_updates_every_protection_without_changing_tp_or_trailing():
    from backtesting.execution_lifecycle_replay import ProtectionReplayResult
    signals = pd.DataFrame([dict(symbol='X', fill_price=110., replay_initial_stop_price=80.,
        replay_take_profit_price=117., replay_trailing_stop_pct=.15)])
    orders = pd.DataFrame([dict(symbol='X', intent_role='initial_stop', stop_price=80.),
        dict(symbol='X', intent_role='trailing_stop', stop_price=None)])
    original = ProtectionReplayResult(signals, signals.copy(), {}, orders)
    updated = fixed_stop_protections(original, .07)
    assert updated.signals_df.replay_initial_stop_price.iloc[0] == pytest.approx(102.3)
    assert updated.protection_frame.replay_initial_stop_price.iloc[0] == pytest.approx(102.3)
    assert updated.order_lifecycle_frame.stop_price.iloc[0] == pytest.approx(102.3)
    assert updated.signals_df.replay_take_profit_price.iloc[0] == 117.
    assert updated.signals_df.replay_trailing_stop_pct.iloc[0] == .15
    assert original.signals_df.replay_initial_stop_price.iloc[0] == 80.


@pytest.mark.parametrize('value', [0., 1., -.07, float('nan'), float('inf')])
def test_invalid_fixed_stop_rejected(value):
    with pytest.raises(ValueError):
        fixed_stop_protections(SimpleNamespace(), value)


@pytest.mark.parametrize('gap', [False, True])
def test_fixed_stop_native_execution_and_gap_can_exceed_seven_percent(tmp_path, gap):
    frames, scores, macro, trading = fixture_data()
    # Actual entry 101 differs from signal close 100. Fixed stop must be 93.93.
    frames['opens'].loc[trading[1], 'FIXTURE'] = 101.
    frames['high'].loc[trading[1], 'FIXTURE'] = 102.
    frames['low'].loc[trading[2], 'FIXTURE'] = 92.
    if gap:
        frames['opens'].loc[trading[2], 'FIXTURE'] = 90.
        frames['low'].loc[trading[2], 'FIXTURE'] = 89.
    result = run_portfolio(frames=frames, scores=scores, sectors={'FIXTURE': 'Technology'},
        macro=macro, market_config=parse_market_regimes({'enabled': False}),
        policy='ORACLE_TOP10', variant='NO_TP_FIXED_SL_20_AFTER_ENTRY',
        output=tmp_path, initial_stop_pct=.07)
    trades = pd.read_parquet(tmp_path/'trades.parquet')
    assert len(trades) == 1
    assert trades.entry_price.iloc[0] == pytest.approx(101.)
    assert trades.replay_initial_stop_price.iloc[0] == pytest.approx(93.93)
    assert trades.exit_date.iloc[0] == trading[2]
    assert trades.exit_price.iloc[0] == pytest.approx(90. if gap else 93.93)
    assert result['cash_reconciliation_error'] == pytest.approx(0., abs=1e-8)
    assert result['research_initial_stop_pct'] == .07
