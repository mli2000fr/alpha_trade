from functools import partial

import pandas as pd
import pytest

from scripts.research.us_concentrated_live_portfolio import run_portfolio
from scripts.research.us_oracle_barrier_exit_grid import GridLedger
from scripts.research.us_oracle_barrier_trailing_grid import (
    TrailingGridLedger, activation_price, planned_cases, validate_trailing_contract, require_long_trades,
)
from service.market import parse_market_regimes
from tests.test_us_concentrated_live_portfolio import fixture_data


def simulate(tmp_path, frames, scores, macro, days, *, trail=.10, tp=.20, sl=.07):
    result=run_portfolio(frames=frames,scores=scores,sectors={'FIXTURE':'Technology'},
        macro=macro,market_config=parse_market_regimes({'enabled':False}),policy='ORACLE_TOP10',
        variant='CURRENT_NO_EXPIRY',output=tmp_path,decision_end_date=days[0],expiry_open_sessions=20,
        ledger_factory=partial(TrailingGridLedger,tp_pct=tp,sl_pct=sl,trailing_pct=trail,events=()),
        protection_options=dict(take_profit_enabled=True,trailing_enabled=trail is not None))
    trades=pd.read_parquet(tmp_path/'trades.parquet')
    return result,trades


@pytest.mark.parametrize('trail,sl,gain',[(.05,.07,0),(.10,.07,.93/.90-1),(.15,.05,.95/.85-1)])
def test_activation_can_never_loosen_initial_stop(trail,sl,gain):
    trigger=activation_price(100,100*(1-sl),trail)
    assert trigger==pytest.approx(100*(1+gain))
    assert trigger*(1-trail)>=100*(1-sl)-1e-10


@pytest.mark.parametrize('trail',[True,0,-.1,1,float('nan'),float('inf')])
def test_invalid_trailing_rejected(trail):
    with pytest.raises(ValueError,match='Invalid trailing'):
        TrailingGridLedger(trailing_pct=trail,tp_pct=.20,sl_pct=.07)


def test_grid_is_frozen_and_bounded():
    cases=planned_cases()
    assert len(cases)==len(set(cases))==36
    assert sum(c[-1]==.10 for c in cases)==12
    assert all(c[3:6]==('TP20_SL10', .20, .10) for c in cases)
    assert len(planned_cases(True))==4


@pytest.mark.parametrize('column',['side','direction'])
def test_native_trade_side_is_checked(column):
    require_long_trades(pd.DataFrame({column:['buy','long']}))
    with pytest.raises(ValueError,match='SHORT'):
        require_long_trades(pd.DataFrame({column:['buy','sell']}))
    with pytest.raises(ValueError,match='Missing side'):
        require_long_trades(pd.DataFrame({'symbol':['A']}))


def test_off_exactly_reproduces_native_baseline(tmp_path):
    frames,scores,macro,days=fixture_data()
    result,trades=simulate(tmp_path/'off',frames,scores,macro,days,trail=None)
    baseline=run_portfolio(frames=frames,scores=scores,sectors={'FIXTURE':'Technology'},macro=macro,
        market_config=parse_market_regimes({'enabled':False}),policy='ORACLE_TOP10',variant='CURRENT_NO_EXPIRY',
        output=tmp_path/'baseline',decision_end_date=days[0],expiry_open_sessions=20,
        ledger_factory=partial(GridLedger,tp_pct=.20,sl_pct=.07,events=()),
        protection_options=dict(take_profit_enabled=True,trailing_enabled=False))
    assert result['return_pct']==baseline['return_pct']
    pd.testing.assert_frame_equal(trades,pd.read_parquet(tmp_path/'baseline'/'trades.parquet'))
    pd.testing.assert_frame_equal(pd.read_parquet(tmp_path/'off'/'daily.parquet'),
                                  pd.read_parquet(tmp_path/'baseline'/'daily.parquet'))


def test_current_high_does_not_raise_current_stop(tmp_path):
    frames,scores,macro,days=fixture_data()
    # Entry day reaches 115 but low 99 stays above original 93. Native daily
    # trailing would be 103.5 only tomorrow, never retrospectively today.
    frames['high'].loc[days[1],'FIXTURE']=115
    frames['opens'].loc[days[2],'FIXTURE']=102
    result,trades=simulate(tmp_path,frames,scores,macro,days)
    trade=trades.iloc[0]
    assert trade.entry_date==days[1]
    assert trade.exit_date==days[2]
    assert trade.exit_reason=='trailing_stop_gap_open'
    assert trade.exit_price==102
    assert abs(result['cash_reconciliation_error'])<1e-8
    validate_trailing_contract(trades,.20,.07,.10,frames['close'].index)


def test_low_before_safe_activation_keeps_original_sl(tmp_path):
    frames,scores,macro,days=fixture_data()
    # With trail 15%, flat 101 highs have not reached safe activation 109.41.
    frames['low'].loc[days[3],'FIXTURE']=92
    _,trades=simulate(tmp_path,frames,scores,macro,days,trail=.15)
    trade=trades.iloc[0]
    assert trade.exit_reason=='initial_stop'
    assert trade.exit_price==93


def test_intraday_trailing_uses_previous_peak_and_conservative_collision(tmp_path):
    frames,scores,macro,days=fixture_data()
    frames['high'].loc[days[1],'FIXTURE']=115
    for key,price in [('opens',110),('close',110),('high',125),('low',100)]:
        frames[key].loc[days[2],'FIXTURE']=price
    _,trades=simulate(tmp_path,frames,scores,macro,days)
    trade=trades.iloc[0]
    assert trade.exit_date==days[2]
    assert trade.exit_reason=='trailing_stop'  # TP120 also hit: stop-first.
    assert trade.exit_price==pytest.approx(103.5)  # Not 125*.90.


def test_tp_and_expiry_are_retained(tmp_path):
    frames,scores,macro,days=fixture_data()
    _,trades=simulate(tmp_path/'flat',frames,scores,macro,days)
    assert trades.iloc[0].exit_date==days[21]
    assert trades.iloc[0].exit_reason=='expiry_open'
    frames['opens'].loc[days[2],'FIXTURE']=125
    _,trades=simulate(tmp_path/'tp',frames,scores,macro,days)
    assert trades.iloc[0].exit_reason=='take_profit_gap_limit'
    assert trades.iloc[0].exit_price==120


def test_adverse_gap_is_not_capped_at_stop(tmp_path):
    frames,scores,macro,days=fixture_data()
    frames['high'].loc[days[1],'FIXTURE']=115
    for key,price in [('opens',80),('close',80),('high',81),('low',79)]:
        frames[key].loc[days[2],'FIXTURE']=price
    _,trades=simulate(tmp_path,frames,scores,macro,days)
    assert trades.iloc[0].exit_price==80
    validate_trailing_contract(trades,.20,.07,.10,frames['close'].index)
