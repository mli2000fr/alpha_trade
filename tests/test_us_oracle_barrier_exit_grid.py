from functools import partial

import pandas as pd
import pytest

from scripts.research.us_concentrated_live_portfolio import run_portfolio
from scripts.research.us_oracle_barrier_exit_grid import GridLedger, PROFILES
from scripts.research.us_oracle_barrier_grid_prepare import replace_avb_features
from service.market import parse_market_regimes
from tests.test_us_concentrated_live_portfolio import fixture_data


@pytest.mark.parametrize('name,tp,sl',PROFILES)
def test_all_profiles_anchor_tp_and_sl_to_actual_fill(tmp_path,name,tp,sl):
    frames,scores,macro,days = fixture_data()
    result=run_portfolio(frames=frames,scores=scores,sectors={'FIXTURE':'Technology'},
        macro=macro,market_config=parse_market_regimes({'enabled':False}),policy='ORACLE_TOP10',
        variant='CURRENT_NO_EXPIRY',output=tmp_path,decision_end_date=days[0],expiry_open_sessions=20,
        ledger_factory=partial(GridLedger,tp_pct=tp,sl_pct=sl,events=()),
        protection_options=dict(take_profit_enabled=True,trailing_enabled=False))
    trade=pd.read_parquet(tmp_path/'trades.parquet').iloc[0]
    assert trade.replay_take_profit_price == pytest.approx(100*(1+tp))
    assert trade.replay_initial_stop_price == pytest.approx(100*(1-sl))
    assert trade.exit_date == days[21]
    assert abs(result['cash_reconciliation_error']) < 1e-8


@pytest.mark.parametrize('tp,sl',[(True,.07),(.20,0),(-.1,.1),(.2,float('nan'))])
def test_invalid_profile_is_rejected_before_ledger_initialisation(tp,sl):
    with pytest.raises(ValueError,match='Invalid TP/SL'):
        GridLedger(tp_pct=tp,sl_pct=sl)


def test_feature_repair_preserves_other_symbols_and_membership():
    data=pd.DataFrame(dict(date=pd.to_datetime(['2026-07-13','2026-07-13']),
                          symbol=['AVB','OTHER'],daily_return=[-.64,.02],selector_short_score=[1.,2.]))
    fixed=data.loc[data.symbol.eq('AVB')].assign(daily_return=.014)
    result=replace_avb_features(data,fixed)
    assert result.loc[result.symbol.eq('AVB'),'daily_return'].iloc[0] == .014
    pd.testing.assert_frame_equal(result.loc[result.symbol.eq('OTHER')].reset_index(drop=True),
                                  data.loc[data.symbol.eq('OTHER')].reset_index(drop=True))
    assert len(result)==len(data)
    assert set(result.symbol)==set(data.symbol)


def test_feature_repair_rejects_missing_rebuilt_dates():
    data=pd.DataFrame(dict(date=pd.to_datetime(['2026-07-13']),symbol=['AVB'],daily_return=[-.64]))
    with pytest.raises(ValueError,match='feature keys changed'):
        replace_avb_features(data,data.iloc[:0])


@pytest.mark.parametrize('name,tp,sl',PROFILES)
def test_adverse_stop_gap_keeps_actual_open_fill(tmp_path,name,tp,sl):
    frames,scores,macro,days=fixture_data()
    for key,price in [('opens',85.),('close',85.),('high',86.),('low',84.)]:
        frames[key].loc[days[3],'FIXTURE']=price
    run_portfolio(frames=frames,scores=scores,sectors={'FIXTURE':'Technology'},macro=macro,
        market_config=parse_market_regimes({'enabled':False}),policy='ORACLE_TOP10',
        variant='CURRENT_NO_EXPIRY',output=tmp_path,decision_end_date=days[0],expiry_open_sessions=20,
        ledger_factory=partial(GridLedger,tp_pct=tp,sl_pct=sl,events=()),
        protection_options=dict(take_profit_enabled=True,trailing_enabled=False))
    trade=pd.read_parquet(tmp_path/'trades.parquet').iloc[0]
    assert trade.exit_date==days[3]
    assert trade.exit_price==85.


@pytest.mark.parametrize('tp,expected_day',[(.10,2),(.20,21),(.25,21)])
def test_changed_tp_changes_exit_not_ranking(tmp_path,tp,expected_day):
    frames,scores,macro,days=fixture_data()
    frames['high'].loc[days[2],'FIXTURE']=115.
    run_portfolio(frames=frames,scores=scores,sectors={'FIXTURE':'Technology'},macro=macro,
        market_config=parse_market_regimes({'enabled':False}),policy='ORACLE_TOP10',
        variant='CURRENT_NO_EXPIRY',output=tmp_path,decision_end_date=days[0],expiry_open_sessions=20,
        ledger_factory=partial(GridLedger,tp_pct=tp,sl_pct=.07,events=()),
        protection_options=dict(take_profit_enabled=True,trailing_enabled=False))
    trade=pd.read_parquet(tmp_path/'trades.parquet').iloc[0]
    assert trade.exit_date==days[expected_day]
    assert trade.exit_price==pytest.approx(110. if tp==.10 else 100.)
