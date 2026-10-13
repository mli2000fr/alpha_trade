import numpy as np
import pandas as pd
import pytest

from scripts.research.us_oracle_tp20_sl10_campaign import annual_metrics, model_contract, MODEL
from scripts.research.us_oracle_tp20_sl10_models import unit_path, split_fit_validation, state_values, input_matrix


def test_unit_path_collision_is_stop_first():
    opens=np.full(21,100.);high=opens+1;low=opens-1
    high[2]=125.;low[2]=85.
    assert unit_path(opens,high,low,100.)==(2,90.,'stop')


def test_unit_path_gap_stop_is_not_capped():
    opens=np.full(21,100.);high=opens+1;low=opens-1
    opens[3]=80.;low[3]=79.;high[3]=81.
    assert unit_path(opens,high,low,100.)==(3,80.,'stop_gap')


def test_unit_path_tp_gap_is_conservative_limit():
    opens=np.full(21,100.);high=opens+1;low=opens-1
    opens[3]=140.;high[3]=141.;low[3]=139.
    assert unit_path(opens,high,low,100.)==(3,120.,'tp_gap')


def test_unit_expiry_only_uses_twenty_first_open():
    opens=np.full(21,100.);high=opens+1;low=opens-1
    opens[-1]=105.;high[-1]=200.;low[-1]=1.
    assert unit_path(opens,high,low,100.)==(20,105.,'expiry')


@pytest.mark.parametrize('bad',[np.nan,0.,-1.])
def test_unknown_path_is_not_a_losing_label(bad):
    opens=np.full(21,100.);high=opens+1;low=opens-1;opens[2]=bad
    assert unit_path(opens,high,low,100.) is None


def test_fit_purges_label_availability_not_just_date():
    fit=pd.DataFrame(dict(date=pd.to_datetime(['2021-01-01']*1100),
        label_available=pd.to_datetime(['2021-02-01']*1100)))
    late=fit.iloc[:1].copy();late['label_available']=pd.Timestamp('2022-01-02')
    val=pd.DataFrame(dict(date=pd.to_datetime(['2022-01-03']*600),
        label_available=pd.to_datetime(['2022-02-01']*600)))
    leak=val.iloc[:1].copy();leak['label_available']=pd.Timestamp('2023-01-03')
    external=val.iloc[:1].copy();external['date']=pd.Timestamp('2024-01-01')
    a,b=split_fit_validation(pd.concat([fit,late,val,leak,external]))
    assert len(a)==1100 and len(b)==600


def test_future_targets_never_in_input_matrix():
    frame=pd.DataFrame(dict(momentum_20=[.1],label_win=[1],future_return=[9]))
    assert list(input_matrix(frame,['momentum_20']))==['momentum_20']


def test_annual_pnl_groups_partial_legs_before_winrate():
    trades=pd.DataFrame(dict(symbol=['A','A','B'],entry_date=['2025-01-02']*3,pnl=[10.,-20.,30.]))
    daily=pd.DataFrame(dict(date=pd.to_datetime(['2025-12-31','2026-01-15']),equity=[4010.,4020.]))
    result=dict(return_pct=.005,max_drawdown=-.02,margin_interest=0.,cash_reconciliation_error=0.)
    m=annual_metrics(result,trades,daily,2025)
    assert m['winning_pct']==50 and m['closed_positions']==2
    assert m['winning_amount_usd']==30 and m['losing_amount_usd']==-10
    assert m['calendar_mark_to_market_capital']==4010.


def test_annual_pnl_groups_qualified_ticker_change():
    trades=pd.DataFrame(dict(symbol=['OLD','NEW','B'],entry_symbol=[None,'OLD',None],
        entry_date=['2026-01-02']*3,pnl=[10.,-20.,30.]))
    daily=pd.DataFrame(dict(date=pd.to_datetime(['2026-09-03']),equity=[4020.]))
    result=dict(return_pct=.005,max_drawdown=-.02,margin_interest=0.,cash_reconciliation_error=0.)
    metrics=annual_metrics(result,trades,daily,2026)
    assert metrics['closed_positions']==2 and metrics['winning_pct']==50.


def test_name_change_requires_exact_identity_and_complete_page():
    from scripts.research.us_oracle_tp20_sl10_lifecycle import qualify_name_change
    event=dict(id='fixture',old_symbol='TOELY',new_symbol='TELWY',process_date='2026-09-17',
        old_cusip='889110102',new_cusip='889110201')
    payload=dict(corporate_actions={'name_changes':[event]},next_page_token=None)
    assert qualify_name_change(payload)['ratio']=='1'
    with pytest.raises(ValueError,match='Incomplete'):
        qualify_name_change(dict(payload,next_page_token='next'))
    with pytest.raises(ValueError,match='identity'):
        qualify_name_change(dict(corporate_actions={'name_changes':[dict(event,new_cusip='wrong')]}))
    with pytest.raises(ValueError,match='ambiguous'):
        qualify_name_change(dict(corporate_actions={'name_changes':[event,event]}))


def test_successor_split_normalization_does_not_adjust_volume_twice():
    from scripts.research.us_oracle_tp20_sl10_lifecycle import normalize_successor
    raw=[dict(date='2026-10-06',open=190.,high=200.,low=185.,close=195.,volume=1000.),
         dict(date='2026-10-07',open=38.,high=40.,low=37.,close=39.,volume=1000.)]
    frame=normalize_successor(raw,[{'date':'2026-10-07','split':'5.000000/1.000000'}])
    assert frame.open.tolist()==[38.,38.] and frame.volume.tolist()==[1000.,1000.]


def test_name_change_grid_preserves_tp20_sl10_and_expiry(tmp_path):
    from functools import partial
    from tests.test_us_oracle_merger_ledger import converted_fixture
    from scripts.research.us_oracle_barrier_exit_grid import GridLedger
    from scripts.research.us_concentrated_live_portfolio import run_portfolio
    from service.market import parse_market_regimes
    frames,scores,macro,days,event=converted_fixture()
    for frame in frames.values():frame['NEW']=frame.FIXTURE
    event=dict(event,ratio='1',event_type='NAME_CHANGE')
    result=run_portfolio(frames=frames,scores=scores,sectors={'FIXTURE':'Technology','NEW':'Technology'},
        macro=macro,market_config=parse_market_regimes({'enabled':False}),policy='ORACLE_TOP10',
        variant='CURRENT_NO_EXPIRY',output=tmp_path,expiry_open_sessions=20,decision_end_date=days[0],
        ledger_factory=partial(GridLedger,tp_pct=.2,sl_pct=.1,events=(event,),cash_policy='STRICT'),
        protection_options=dict(take_profit_enabled=True,trailing_enabled=False))
    trade=pd.read_parquet(tmp_path/'trades.parquet').iloc[0]
    assert trade.entry_symbol=='FIXTURE' and trade.symbol=='NEW'
    assert trade.replay_initial_stop_price==90. and trade.replay_take_profit_price==120.
    assert trade.exit_date==days[21]
    assert abs(result['cash_reconciliation_error'])<1e-8


def test_final_audit_refuses_partial_baseline(tmp_path):
    from scripts.research.us_baseline_campaign_result_audit import audit
    from scripts.research.us_concentrated_historical_tapes import atomic_json
    atomic_json(tmp_path/'progress.json',dict(status='RUNNING',phase='baseline'))
    with pytest.raises(ValueError,match='not complete'):
        audit(tmp_path,tmp_path)


def test_hard_stop_distance_in_daily_state():
    state=state_values(4,100,95,110,91,0.)
    assert state['distance_stop']==pytest.approx(5/95)
    assert state['pnl']==pytest.approx(-.05)


def test_learned_exit_next_open_cannot_cancel_open_gap_stop(tmp_path):
    from tests.test_us_concentrated_live_portfolio import fixture_data
    from scripts.research.us_concentrated_live_portfolio import run_portfolio
    from service.market import parse_market_regimes
    frames,scores,macro,days=fixture_data()
    frames['opens'].loc[days[2],'FIXTURE']=80.
    frames['high'].loc[days[2],'FIXTURE']=81.
    frames['low'].loc[days[2],'FIXTURE']=79.
    frames['close'].loc[days[2],'FIXTURE']=80.
    seen=[]
    def policy(day,ledger,observed):
        assert all(frame.index.max()<=day for frame in observed.values())
        seen.append(day)
        return [dict(symbol=s,entry_date=p.entry_date,decision_date=day)
                for s,p in ledger.state.positions.items()]
    run_portfolio(frames=frames,scores=scores,sectors={'FIXTURE':'Technology'},macro=macro,
        market_config=parse_market_regimes({'enabled':False}),policy='ORACLE_TOP10',
        variant='NO_TP_FIXED_SL_20_AFTER_ENTRY',output=tmp_path,
        initial_stop_pct=.1,daily_exit_policy=policy)
    trades=pd.read_parquet(tmp_path/'trades.parquet')
    assert len(trades)==1 and trades.exit_price.iloc[0]<90
    assert 'gap' in trades.exit_reason.iloc[0]
    assert seen


def test_new_model_matches_expected_training_barriers():
    protocol,profile,fold=model_contract(MODEL)
    assert protocol['barriers']['stop_loss_pct']==.1
    assert fold.name<'2024-01-01'
    assert len(profile['feature_columns'])>100


def test_local_feature_repair_preserves_pre_event_bits_and_dtype():
    from scripts.research.us_oracle_tp20_sl10_remediation import replace_base_features
    frame=pd.DataFrame(dict(date=pd.to_datetime(['2026-01-02','2026-07-13','2026-07-13']),
        symbol=['A','A','B'],momentum_20=np.array([.1234567,.2,.3],dtype=np.float32)))
    replacement=frame.loc[frame.symbol.eq('A')].copy()
    replacement['momentum_20']=[.1234567001,.6]
    result=replace_base_features(frame,replacement,['momentum_20'],effective_date='2026-07-13')
    assert result.loc[0,'momentum_20']==frame.loc[0,'momentum_20']
    assert result.loc[2,'momentum_20']==frame.loc[2,'momentum_20']
    assert result.loc[1,'momentum_20']==np.float32(.6)
    assert result.momentum_20.dtype==frame.momentum_20.dtype
    assert result[['date','symbol']].equals(frame[['date','symbol']])


def test_local_repair_rejects_partial_membership():
    from scripts.research.us_oracle_tp20_sl10_remediation import replace_base_features
    frame=pd.DataFrame(dict(date=pd.to_datetime(['2026-01-02','2026-07-13']),
        symbol=['A','A'],momentum_20=[.1,.2]))
    with pytest.raises(ValueError,match='eligibility'):
        replace_base_features(frame,frame.iloc[:1],['momentum_20'])


@pytest.mark.parametrize('tp,sl',[(.1,.07),(.2,.1),(.25,.1)])
def test_personalized_profile_and_sizing_preserve_accounting(tmp_path,tp,sl):
    from functools import partial
    from tests.test_us_concentrated_live_portfolio import fixture_data
    from scripts.research.us_concentrated_live_portfolio import run_portfolio
    from scripts.research.us_oracle_tp20_sl10_models import SizedSession,PersonalizedLedger
    from service.market import parse_market_regimes
    frames,scores,macro,days=fixture_data()
    profiles={(day,'FIXTURE'):(tp,sl) for day in days}
    result=run_portfolio(frames=frames,scores=scores,sectors={'FIXTURE':'Technology'},macro=macro,
        market_config=parse_market_regimes({'enabled':False}),policy='ORACLE_TOP10',
        variant='CURRENT_NO_EXPIRY',output=tmp_path,decision_end_date=days[0],expiry_open_sessions=20,
        session_factory=partial(SizedSession,profiles=profiles),
        ledger_factory=partial(PersonalizedLedger,profiles=profiles,events=(),cash_policy='STRICT'),
        protection_options=dict(take_profit_enabled=True,trailing_enabled=False))
    trade=pd.read_parquet(tmp_path/'trades.parquet').iloc[0]
    assert trade.replay_initial_stop_price==pytest.approx(100*(1-sl))
    assert trade.replay_take_profit_price==pytest.approx(100*(1+tp))
    assert trade.exit_date==days[21]
    assert result['personalized_protection_audit']['verified']
    assert result['cash_reconciliation_error']==pytest.approx(0.,abs=1e-7)
    from scripts.research.us_concentrated_contract_audit import frozen_backtest_config
    risk=frozen_backtest_config(days[0],days[-1]).risk_config
    assert trade.quantity*100*sl<=4000*risk.risk_per_trade_pct
